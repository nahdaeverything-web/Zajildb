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
//
// v1.9 MOVED THREE ALLOW-LISTS from `js/db.js` to `js/db/` — note: to, not
// also. db.js became a facade over four modules and the write path moved into
// that directory, so the facade itself is no longer exempt. It provably
// contains zero writes (the guard below asserts it is re-exports and comment),
// and privileges should track proof: a stray idbPut in js/db.js now fails
// exactly as it would in a view.
//
// A changed allow-list is a weakened guard unless it is re-proven, so each of
// the three is proven TWICE — once with the violation in a view, once with it
// in the facade. Note the remaining consequence: ANY file added under js/db/
// is exempt from all three. That is deliberate — the directory IS the boundary
// now — and it is why js/db/sync.js arrives with its own dedicated guard
// (`origin: 'sync'` must never reach logOp) rather than relying on these.

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import { test, assert, assertEq } from './harness.js';
import * as db from '../js/db.js';
import { newBird, REFERENCE_STATUS } from '../js/db.js';
import { checkIntegrity } from '../js/engine/integrity.js';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const JS = join(ROOT, 'js');

/**
 * Blank out `export { … } from '…'` statements, preserving line numbering.
 *
 * A re-export NAMES a symbol; it cannot call one. Without this the facade
 * fails the very guards it exists to submit to — `export { idbPut, … } from
 * './db/storage.js'` reads, to a text scan, exactly like a write. Blanking is
 * not a loophole: there is no syntax that both matches this shape and executes
 * anything. Lines are replaced rather than removed so a reported line number
 * still points at the real line.
 */
function withoutReExports(src) {
  const lines = src.split('\n');
  let inBlock = false;
  return lines.map((l) => {
    if (inBlock) { if (/^\}\s*from\s*'[^']+';/.test(l)) inBlock = false; return ''; }
    if (/^export\s*\{[^}]*\}\s*from\s*'[^']+';/.test(l)) return '';   // single line
    if (/^export\s*\{\s*$/.test(l)) { inBlock = true; return ''; }      // block opener
    return l;
  }).join('\n');
}

function sources(dir = JS, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) sources(p, out);
    else if (name.endsWith('.js')) {
      const src = readFileSync(p, 'utf8');
      out.push({ path: p, rel: relative(ROOT, p), src, code: withoutReExports(src) });
    }
  }
  return out;
}
const FILES = sources();

/** Report every offending line so a failure names the file and line, not just a count. */
function scan(files, re, { allow = () => false } = {}) {
  const hits = [];
  for (const f of files) {
    if (allow(f)) continue;
    (f.code ?? f.src).split('\n').forEach((line, i) => {
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
    { allow: (f) => f.rel.startsWith('js/db/') });
  assertEq(hits.length, 0,
    `writes must go through db.js (saveBird/Pairs.save/restoreMedia/…):\n  ${hits.join('\n  ')}`);
});

test('guard: logOp never escapes js/db.js', () => {
  // The op log must be a faithful record of the WRITE PATH. A view writing to
  // it directly would log something that never went through saveBird, so the
  // log would stop matching what actually happened to the data.
  const hits = scan(FILES, /\blogOp\b/, { allow: (f) => f.rel.startsWith('js/db/') });
  assertEq(hits.length, 0,
    `writes go through db.js, which logs them:\n  ${hits.join('\n  ')}`);
});

test('guard: nothing reads oplog or tombstones raw outside js/db.js', () => {
  // idbGetAll returns records in KEY order, and oplog's key is a random uuid,
  // so a raw read is effectively shuffled — any "last N" or slice gets
  // arbitrary ops. Read through listOps()/getOpsSinceSeq() instead. Views have
  // no business reading either store directly in any case.
  const hits = scan(FILES, /idbGetAll\(\s*['"](oplog|tombstones)['"]/,
    { allow: (f) => f.rel.startsWith('js/db/') });
  assertEq(hits.length, 0,
    `use listOps() / getOpsSinceSeq(); the raw store is unordered:\n  ${hits.join('\n  ')}`);
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

// ------------------------------------------------------------------- the facade

// The public API of the db layer, pinned. db.js was split into four modules in
// v1.9; this list is what "no view changed a single import" MEANS. A name may
// be added here deliberately, but one must never go missing by accident — a
// dropped re-export is invisible until a view calls it at runtime.
const FACADE = [
  'AUTH_SETTING_KEYS', 'AuthError', 'Health', 'Lofts', 'OPLOG_KEEP', 'PULL_PAGE',
  'PUSH_BATCH', 'Pairs', 'REFERENCE_STATUS', 'Races', 'SENSITIVE_SETTING_PREFIXES', 'STORES',
  'SYNC_STORES', 'ValidationError', 'addMedia', 'allBirds', 'applySyncDelete', 'applySyncPut',
  'authHeaders', 'authState', 'autoBackup', 'checkBird', 'collapseOps', 'currentLoft',
  'dataURLToBlob', 'deleteBird', 'deleteMedia', 'diffFields', 'emitChange',
  'ensureAccessToken', 'exportAll', 'exportBirdWithAncestry', 'exportableSettings', 'getBird',
  'getOpsSinceSeq', 'getTombstone', 'idbClear', 'idbDelete', 'idbGet', 'idbGetAll', 'idbPut',
  'importAll', 'initDB', 'isSignedIn', 'listBackups', 'listOps', 'listSyncAnomalies',
  'listTombstones', 'loftStatuses', 'makeGeneric', 'mediaForBird', 'newBird', 'nowISO',
  'onChange', 'opRecord', 'opToRow', 'openDB', 'pruneOplog', 'pullAll', 'pullOnce', 'pushAll',
  'pushOnce', 'refreshSession', 'restoreBird', 'restoreMedia', 'saveBird', 'setSetting',
  'signIn', 'signOut', 'state', 'syncConfig', 'syncOnce', 'uuid',
];

test('guard: js/db.js exports exactly the pinned public surface', () => {
  const actual = Object.keys(db).sort();
  const missing = FACADE.filter((n) => !actual.includes(n));
  const extra = actual.filter((n) => !FACADE.includes(n));
  assertEq(missing.length + extra.length, 0,
    `the db facade drifted — missing: [${missing.join(', ')}] unexpected: [${extra.join(', ')}]`);
  assertEq(actual.length, 73, `expected 73 exports, found ${actual.length}`);
});

test('guard: js/db.js stays a facade — re-exports only, no logic', () => {
  const src = FILES.find((f) => f.rel === 'js/db.js').src;
  const code = src.split('\n')
    .map((l, i) => ({ n: i + 1, l }))
    .filter(({ l }) => l.trim() && !/^\s*(\/\/|\*|\/\*)/.test(l));
  // every non-comment line must belong to an `export { ... } from '...'` block
  const offenders = code.filter(({ l }) =>
    !/^export \{$/.test(l.trim()) && !/^\}? ?from '\.\/db\/\w+\.js';$/.test(l.trim()) &&
    !/^[A-Za-z0-9_$]+,$/.test(l.trim()) && !/^export \{.*\} from '\.\/db\/\w+\.js';$/.test(l.trim()));
  assertEq(offenders.length, 0,
    `db.js must only re-export; move logic into js/db/:\n  ${offenders.map((o) => `js/db.js:${o.n}  ${o.l.trim()}`).join('\n  ')}`);
});

test('guard: the db modules form a DAG — storage <- oplog <- records <- io', () => {
  // A cycle here would be a real bug, not a style point: ES modules would hand
  // one of the two files a partly-initialised namespace, and which one depends
  // on import order. The layering is also what keeps `storage` importable by
  // anything without dragging the write path along.
  const RANK = { 'js/db/storage.js': 0, 'js/db/oplog.js': 1, 'js/db/records.js': 2,
                 'js/db/io.js': 3, 'js/db/sync.js': 4 };
  const bad = [];
  for (const f of FILES.filter((x) => RANK[x.rel] !== undefined)) {
    for (const m of f.src.matchAll(/from '\.\/(\w+)\.js'/g)) {
      const target = `js/db/${m[1]}.js`;
      if (RANK[target] === undefined) { bad.push(`${f.rel} imports unknown sibling ${m[1]}.js`); continue; }
      if (RANK[target] >= RANK[f.rel]) bad.push(`${f.rel} imports ${target} — wrong direction`);
    }
    if (/from '\.\.\/db\.js'/.test(f.src)) bad.push(`${f.rel} imports the facade — that is a cycle`);
  }
  assertEq(bad.length, 0, `the db layer must stay acyclic:\n  ${bad.join('\n  ')}`);
});

// ------------------------------------------------------- echo prevention (§8)

test('guard: every logOp call names its origin as a STRING LITERAL', () => {
  // The echo-prevention scan below reads the origin at each call site. A
  // computed origin would be invisible to it, so the scan would silently stop
  // guarding anything. Requiring a literal is what keeps it sound.
  const hits = [];
  for (const f of FILES) {
    for (const m of f.src.matchAll(/(?<!function\s)logOp\(\s*\{[\s\S]*?\}\s*\)/g)) {
      if (!/origin:\s*(['"])[a-z]+\1/.test(m[0])) {
        hits.push(`${f.rel}  ${m[0].replace(/\s+/g, ' ').slice(0, 90)}`);
      }
    }
  }
  assertEq(hits.length, 0,
    `origin must be a literal so the echo-prevention scan can see it:\n  ${hits.join('\n  ')}`);
});

test("guard: origin 'sync' never reaches logOp — echo prevention", () => {
  // THE load-bearing invariant of the pull path, and it is one careless line
  // from being broken: a pulled change that logged an op would be pushed
  // straight back, and two devices would trade the same record forever.
  // Asserted behaviourally too, in tests/e2e/pull.py.
  const hits = [];
  for (const f of FILES) {
    for (const m of f.src.matchAll(/(?<!function\s)logOp\(\s*\{[\s\S]*?\}\s*\)/g)) {
      if (/origin:\s*(['"])sync\1/.test(m[0])) {
        hits.push(`${f.rel}  ${m[0].replace(/\s+/g, ' ').slice(0, 90)}`);
      }
    }
  }
  assertEq(hits.length, 0,
    `a pulled change must log NO op, or the two devices echo forever:\n  ${hits.join('\n  ')}`);
});

test('guard: the sync-apply path neither logs an op nor stamps a record', () => {
  // Stronger than reading origins: the apply functions must not REACH either
  // primitive at all. stamp() would rewrite updatedAt and deviceId onto a
  // record another device authored, corrupting LWW and falsifying the audit
  // trail; logOp would echo.
  const src = FILES.find((f) => f.rel === 'js/db/records.js').src;
  const start = src.indexOf('export async function applySyncPut');
  assert(start > 0, 'applySyncPut not found — has the sync-apply path moved?');
  const region = src.slice(start);
  const offenders = region.split('\n')
    .map((line, i) => ({ line, n: i }))
    .filter(({ line }) => !/^\s*(\/\/|\*)/.test(line))
    .filter(({ line }) => /\blogOp\b/.test(line) || /(?<![A-Za-z_$])stamp\s*\(/.test(line));
  assertEq(offenders.length, 0,
    `a sync apply is not authorship — write the record verbatim:\n  ${offenders.map((o) => o.line.trim()).join('\n  ')}`);
});

test('guard: js/db/sync.js never writes a record itself', () => {
  // The pull loop routes every write through the boundary in records.js so the
  // mirror stays in step and views are told. A raw idbPut here would be a
  // silent write: correct on disk, invisible in the app until a reload.
  const src = FILES.find((f) => f.rel === 'js/db/sync.js').src;
  const offenders = src.split('\n')
    .map((line, n) => ({ line, n: n + 1 }))
    .filter(({ line }) => !/^\s*(\/\/|\*)/.test(line))
    .filter(({ line }) => /\bidbPut\s*\(\s*['"](birds|pairs|raceResults|healthEvents|lofts|media)['"]/.test(line));
  assertEq(offenders.length, 0,
    `route record writes through applySyncPut/applySyncDelete:\n  ${offenders.map((o) => `js/db/sync.js:${o.n}  ${o.line.trim()}`).join('\n  ')}`);
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
