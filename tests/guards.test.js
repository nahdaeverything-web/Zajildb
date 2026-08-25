// tests/guards.test.js — structural guards.
//
// Phase 1 installed five primitives and routed today's callers through them.
// These tests are what stops a FUTURE view from quietly going around them and
// reintroducing the same class of bug wearing different clothes.
//
// Two kinds of guard:
//   • SOURCE SCANS for patterns that are reliably detectable in text.
//   • A DATA-LEVEL invariant, which is stronger than any scan: build records
//     through the real factory and assert the properties hold.
//
// A scan that cannot be made reliable is not loosened until it passes — it is
// reported instead. See the note on newBird at the bottom.

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import { test, assert, assertEq } from './harness.js';
import { newBird, REFERENCE_STATUS } from '../js/db.js';
import { checkIntegrity } from '../js/engine/integrity.js';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const JS = join(ROOT, 'js');

function sources(dir = JS, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) sources(p, out);
    else if (name.endsWith('.js')) out.push({ path: p, rel: relative(ROOT, p), src: readFileSync(p, 'utf8') });
  }
  return out;
}
const FILES = sources();

/** Report every offending line so a failure names the file and line, not just a count. */
function scan(files, re, { allow = () => false } = {}) {
  const hits = [];
  for (const f of files) {
    if (allow(f)) continue;
    f.src.split('\n').forEach((line, i) => {
      if (re.test(line) && !/^\s*(\/\/|\*)/.test(line)) hits.push(`${f.rel}:${i + 1}  ${line.trim().slice(0, 90)}`);
    });
  }
  return hits;
}

test('guard: no UTC date slicing outside js/dates.js', () => {
  const hits = scan(FILES, /toISOString\(\)\.slice\(\s*0\s*,\s*10\s*\)|nowISO\(\)\.slice\(\s*0\s*,\s*10\s*\)/,
    { allow: (f) => f.rel === 'js/dates.js' });
  assertEq(hits.length, 0,
    `use todayISO() from js/dates.js — a UTC slice names the wrong day east of Greenwich:\n  ${hits.join('\n  ')}`);
});

test('guard: no view writes to IndexedDB directly', () => {
  // reads (idbGet/idbGetAll) are fine; WRITES must go through db.js so the
  // change event fires and the in-memory mirror stays in sync
  const hits = scan(FILES, /\bidbPut\b|\bidbDelete\b|\bidbClear\b/,
    { allow: (f) => f.rel === 'js/db.js' });
  assertEq(hits.length, 0,
    `writes must go through db.js (saveBird/Pairs.save/restoreMedia/…):\n  ${hits.join('\n  ')}`);
});

test('guard: views never call validateBird directly', () => {
  // validation lives at the write boundary; views use db.js checkBird()
  const hits = scan(FILES.filter((f) => f.rel.startsWith('js/views/')), /\bvalidateBird\b/);
  assertEq(hits.length, 0,
    `use checkBird() from db.js — saveBird enforces it anyway:\n  ${hits.join('\n  ')}`);
});

test('guard: the engine stays pure — no DOM, no db, no i18n', () => {
  const engine = FILES.filter((f) => f.rel.startsWith('js/engine/'));
  assert(engine.length >= 7, `expected the engine modules, found ${engine.length}`);
  const hits = scan(engine, /from '\.\.\/db\.js'|from '\.\.\/i18n\.js'|from '\.\.\/ui\.js'|\bdocument\.|\bwindow\.|\bindexedDB\b/);
  assertEq(hits.length, 0, `the engine must stay storage- and UI-agnostic:\n  ${hits.join('\n  ')}`);
});

test('guard: every i18n key has BOTH ar and en', () => {
  const src = FILES.find((f) => f.rel === 'js/i18n.js').src;
  const dict = src.slice(src.indexOf('const dict = {'), src.indexOf('\n};', src.indexOf('const dict = {')));
  const missing = [];
  for (const m of dict.matchAll(/^\s*'([\w.\-+]+)':\s*\{([^\n]*)\}/gm)) {
    const [, key, body] = m;
    if (!/\bar:/.test(body)) missing.push(`${key} (no ar)`);
    if (!/\ben:/.test(body)) missing.push(`${key} (no en)`);
  }
  assertEq(missing.length, 0, `every string needs both languages:\n  ${missing.join('\n  ')}`);
});

test('guard: RTL stays structural — no [dir="rtl"] layout overrides in CSS', () => {
  const css = readFileSync(join(ROOT, 'css', 'app.css'), 'utf8');
  const offenders = [];
  css.split('\n').forEach((line, i) => {
    if (!/\[dir\s*=\s*["']rtl["']\]/.test(line)) return;
    // a direction-flip on a transform is legitimate; box-model overrides are not
    if (/margin-(left|right)|padding-(left|right)|(^|\s)(left|right)\s*:|float\s*:|text-align\s*:\s*(left|right)/.test(line)) {
      offenders.push(`css/app.css:${i + 1}  ${line.trim().slice(0, 80)}`);
    }
  });
  assertEq(offenders.length, 0,
    `use logical properties (inline-start/end) so mirroring is structural:\n  ${offenders.join('\n  ')}`);
});

test('guard: every SHELL precache entry exists on disk', () => {
  const sw = readFileSync(join(ROOT, 'sw.js'), 'utf8');
  const list = sw.slice(sw.indexOf('const SHELL = ['), sw.indexOf('];', sw.indexOf('const SHELL = [')));
  const missing = [];
  for (const m of list.matchAll(/'\.\/([^']*)'/g)) {
    const rel = m[1];
    if (!rel) continue;   // './' is the navigation entry
    try { statSync(join(ROOT, rel)); } catch { missing.push(rel); }
  }
  assertEq(missing.length, 0, `sw.js precaches files that do not exist:\n  ${missing.join('\n  ')}`);
});

test('guard: every app module is precached, or offline will break', () => {
  const sw = readFileSync(join(ROOT, 'sw.js'), 'utf8');
  const notListed = FILES.map((f) => f.rel).filter((rel) => !sw.includes(`'./${rel}'`));
  assertEq(notListed.length, 0,
    `add these to the SHELL list in sw.js:\n  ${notListed.join('\n  ')}`);
});

// ---------------------------------------------------------------- data level

test('invariant: every bird from the factory satisfies ownership <-> status', () => {
  // Stronger than a source scan: object literals that build bird records are
  // not reliably detectable in text, so we assert the PROPERTY instead of
  // trying to police the syntax.
  const built = [
    newBird({}),
    newBird({ external: true }),
    newBird({ external: true, status: 'stock' }),
    newBird({ status: REFERENCE_STATUS }),
    newBird({ status: 'breeder' }),
    newBird({ external: false, status: 'race team' }),
  ];
  for (const b of built) {
    assertEq(b.external, b.status === REFERENCE_STATUS,
      `ownership and status disagree: external=${b.external} status=${b.status}`);
  }
});

test('invariant: the shipped datasets satisfy every structural rule', () => {
  for (const file of ['sample-data.json', 'example-loft-large.json']) {
    const d = JSON.parse(readFileSync(join(ROOT, file), 'utf8'));
    for (const b of d.birds) {
      assertEq(b.external === true, b.status === REFERENCE_STATUS,
        `${file}: ${b.name || b.id} external=${b.external} status=${b.status}`);
    }
    const dangling = checkIntegrity(d);
    assertEq(dangling.length, 0, `${file} has dangling references: ${JSON.stringify(dangling)}`);
  }
});
