#!/usr/bin/env node
// Phase 0.5 guards. Each is a source scan over next/ that fails the build on a
// violation. They exist so the rules the specs impose are enforced by a
// process, not remembered by a person. `npm run build` runs them first
// (prebuild); `node guards/run.mjs --only <name>` runs one.
//
// A guard that has never been seen to fail is not evidence of anything, so
// every guard here was proved to fire by reintroducing its violation — see
// the Phase 0.5 commit.
import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join, relative, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(fileURLToPath(import.meta.url), '..', '..');
const SKIP = new Set(['node_modules', '.next', 'out', '.git']);

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (SKIP.has(name)) continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p); else yield p;
  }
}
const files = (...exts) => [...walk(ROOT)].filter((f) => exts.includes(extname(f)));
const rel = (f) => relative(ROOT, f);
const lines = (f) => readFileSync(f, 'utf8').split('\n');
// A colour NAMED IN A COMMENT is not a colour the app paints — and a guard that cannot
// tell code from prose pushes you to write vaguer comments, which is the opposite of what
// this repo wants: every dropped or substituted spec value is supposed to say so in place.
// Comments are masked with spaces so line and column numbers stay exact.
const maskComments = (src) => src
  .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
  .replace(/(^|[^:])\/\/[^\n]*/g, (m, p1) => p1 + ' '.repeat(m.length - p1.length));
const codeLines = (f) => maskComments(readFileSync(f, 'utf8')).split('\n');

// ─── the sanctioned palette (tokens.css is the source of truth; this list
//     mirrors its comments and must be edited together with it) ───
const CORE = ['#128C6E', '#0E6F57', '#E3F4EE', '#101820', '#4A5560', '#8C97A2',
              '#F5F7F8', '#FFFFFF', '#E4E9ED', '#C9971F', '#FBF3DF', '#C43D2B'];
const EXT  = ['#8A6410', '#7A5A0E', '#F8E6E3', '#2FBF95', '#A83223'];
const DEV  = ['#5CD6A8', '#FF8A78', '#E6B84A', '#D8DEE3'];
const SEX  = ['#E4EDF6', '#0A4D8C', '#F6E4EE', '#8C0A57'];   // ruled in: sex chips
const SANCTIONED = new Set([...CORE, ...EXT, ...DEV, ...SEX].map((h) => h.toUpperCase()));
const expand = (h) => (h.length === 4 ? '#' + [...h.slice(1)].map((c) => c + c).join('') : h).toUpperCase();

const guards = {
  // 1. Any hex colour in .css/.ts/.tsx outside the sanctioned set fails.
  //    rgba()/rgb() are allowed (focus rings, hairline insets).
  palette() {
    const bad = [];
    for (const f of files('.css', '.tsx', '.ts')) {
      codeLines(f).forEach((l, i) => {
        for (const m of l.matchAll(/#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b/g)) {
          if (!SANCTIONED.has(expand(m[0]))) bad.push(`${rel(f)}:${i + 1}  ${m[0]}`);
        }
      });
    }
    return bad;
  },
  // 2. next/ never reaches into the root at all: no import/url of ../js, ../css or ../tools.
  'no-root-imports'() {
    const bad = [];
    for (const f of files('.ts', '.tsx', '.js', '.mjs', '.css')) {
      lines(f).forEach((l, i) => {
        if (/['"(](\.\.\/)+(js|css|tools)\//.test(l)) bad.push(`${rel(f)}:${i + 1}  ${l.trim()}`);
      });
    }
    return bad;
  },
  // 3. The document is Arabic and RTL, in source and — when built — in every page.
  'html-rtl'() {
    const bad = [];
    const layout = readFileSync(join(ROOT, 'app', 'layout.tsx'), 'utf8');
    const tag = layout.match(/<html[^>]*>/)?.[0] ?? '';
    if (!/\blang="ar"/.test(tag)) bad.push(`app/layout.tsx  <html> lacks lang="ar": ${tag}`);
    if (!/\bdir="rtl"/.test(tag)) bad.push(`app/layout.tsx  <html> lacks dir="rtl": ${tag}`);
    const out = join(ROOT, 'out');
    if (existsSync(out)) {
      for (const name of readdirSync(out).filter((n) => n.endsWith('.html'))) {
        const h = readFileSync(join(out, name), 'utf8').match(/<html[^>]*>/)?.[0] ?? '';
        if (!/\blang="ar"/.test(h) || !/\bdir="rtl"/.test(h)) bad.push(`out/${name}  ${h.slice(0, 60)}`);
      }
    }
    return bad;
  },
  // 4. No gradients. No blurred box-shadow: a shadow is allowed only if it is
  //    `inset` (hairline) or its blur radius — the third length — is 0
  //    (focus ring `0 0 0 Npx`). Applies to CSS and to inline styles in TSX.
  'no-gradient-no-blur'() {
    const bad = [];
    for (const f of files('.css', '.tsx')) {
      codeLines(f).forEach((l, i) => {
        if (/gradient/i.test(l)) bad.push(`${rel(f)}:${i + 1}  gradient: ${l.trim()}`);
        for (const m of l.matchAll(/box-?[sS]hadow\s*:\s*['"]?([^;'"}]+)/g)) {
          for (const shadow of m[1].split(/,(?![^()]*\))/)) {
            const s = shadow.trim();
            if (!s || s === 'none') continue;
            if (/^inset\b/.test(s)) continue;
            const lens = s.match(/-?\d*\.?\d+(px|em|rem)?/g) ?? [];
            const blur = lens[2] ?? '0';
            if (parseFloat(blur) !== 0) bad.push(`${rel(f)}:${i + 1}  blurred shadow: ${s}`);
          }
        }
      });
    }
    return bad;
  },
  // 6. The test harness route must not exist unless this is a harness build.
  //    app/test-harness/ is created by scripts/build-harness.mjs for one build and
  //    removed after; its presence during a normal build is a defect.
  'no-harness-route'() {
    if (process.env.NEXT_PUBLIC_HARNESS === '1') return [];
    return existsSync(join(ROOT, 'app', 'test-harness')) ? ['app/test-harness/  exists in a NORMAL build'] : [];
  },
  // 7. A secret key never appears under next/ — not in source, tests, docs or
  //    config. The secret key grants everything; the publishable one grants
  //    nothing on its own (js/sync-config.js). Needle assembled from parts so
  //    this file cannot match itself.
  'no-secret-key'() {
    const needle = 'sb_' + 'secret_';
    const bad = [];
    for (const f of files('.js', '.mjs', '.ts', '.tsx', '.css', '.json', '.md', '.py', '.txt', '.env', '.html')) {
      lines(f).forEach((l, i) => { if (l.includes(needle)) bad.push(`${rel(f)}:${i + 1}`); });
    }
    return bad;
  },
  // 5. No dynamic route segments: user data cannot be enumerated at build time,
  //    so [id] cannot be statically exported. Record views use ?id=.
  'no-dynamic-segments'() {
    const bad = [];
    for (const f of walk(join(ROOT, 'app'))) {
      const seg = rel(f).split('/').find((p) => /^\[.*\]$/.test(p));
      if (seg) bad.push(`${rel(f)}  segment ${seg}`);
    }
    return [...new Set(bad.map((b) => b.split('/page')[0].split('/layout')[0]))];
  },
  // 8. (4A) UI code talks to the data layer through its facade and the React
  //    bridge only. A view, component or harness file that imports
  //    src/db/storage|oplog|records|io|sync directly bypasses the write
  //    boundary (records.js saveBird validates; storage.js emits) — the
  //    layer's own rule: "Import from db.js, never from here directly".
  'ui-imports'() {
    const bad = [];
    // Writing to IndexedDB directly skips the op log and the change event, which is what
    // change_events.py#7 is about. Reads are fine — a view fetching a blob calls idbGet.
    const RAW_WRITE = /\bdb\.(idbPut|idbDelete|idbClear)\s*\(/;
    // src/components/settings.ts raises the layer's OWN event after a settings write,
    // because setSetting deliberately emits nothing (db/storage.js:168) and vanilla's
    // views call rerender() instead. That is the one sanctioned caller.
    const EMIT = /\bdb\.emitChange\s*\(/;
    const EMIT_OK = 'src/components/settings.ts';
    for (const dir of ['app', 'components', 'src/components', 'harness']) {
      if (!existsSync(join(ROOT, dir))) continue;
      for (const f of [...walk(join(ROOT, dir))].filter((p) => ['.ts', '.tsx'].includes(extname(p)))) {
        codeLines(f).forEach((l, i) => {
          const m = l.match(/from\s+['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]/);
          const spec = m && (m[1] || m[2]);
          if (spec && /(^|\/)src\/db\/(storage|oplog|records|io|sync)(\.js)?$/.test(spec)) bad.push(`${rel(f)}:${i + 1}  ${l.trim()}`);
          if (RAW_WRITE.test(l)) bad.push(`${rel(f)}:${i + 1}  writes IndexedDB directly, skipping the op log and the change event — ${l.trim()}`);
          if (EMIT.test(l) && rel(f) !== EMIT_OK) bad.push(`${rel(f)}:${i + 1}  raises a change event outside ${EMIT_OK} — ${l.trim()}`);
        });
      }
    }
    return bad;
  },
  // 9. (4A) The string guard — guards/strings.mjs, run as its own process so
  //    it stays a standalone tool (--only, --emit-mock). Every Arabic string a
  //    SHIPPED spec renders must be a key, a template, recorded mock content
  //    or a pending ruling; anything else fails the build. Its report (⚠
  //    pending lines) is passed through so a pending ruling is never silent.
  // 10. (4D) Every custom property a stylesheet READS must be DECLARED somewhere.
  //     Found the hard way: six modules painted `var(--danger-tint)`, the token was
  //     sanctioned in Phase 0.2 but never declared in tokens.css, and every danger
  //     ground rendered transparent. CSS fails silently here — an undeclared property
  //     is not an error, it is an empty value — so only a guard can see it.
  //     A `var(--x, fallback)` is fine: it says what to do when --x is absent.
  //     Properties set from script (el.style.setProperty('--zw', …)) count as declared.
  'no-undefined-token'() {
    const cssFiles = files('.css');
    const decls = (src) => new Set([...src.matchAll(/(--[A-Za-z0-9_-]+)\s*:/g)].map((m) => m[1]));
    // GLOBAL: only the token sheet's :root crosses module boundaries. Custom properties are
    // SCOPED — a `--gap:14px` inside .mini in one module does nothing for another module's
    // .gen, which is exactly the hole the first version of this guard had: it pooled every
    // declaration in the tree and so proved nothing. The pedigree tree read --gap four
    // times, declared it nowhere, and its connector offsets resolved to nothing.
    const global = new Set();
    for (const f of cssFiles) {
      if (!/(^|\/)(styles|app)\/(tokens|globals)\.css$/.test(rel(f))) continue;
      for (const d of decls(readFileSync(f, 'utf8'))) global.add(d);
    }
    // properties set from script, or declared by next/font at runtime
    for (const f of files('.ts', '.tsx')) {
      const src = readFileSync(f, 'utf8');
      for (const m of src.matchAll(/setProperty\(\s*['"`](--[A-Za-z0-9_-]+)['"`]/g)) global.add(m[1]);
      for (const m of src.matchAll(/['"`](--[A-Za-z0-9_-]+)['"`]\s*:/g)) global.add(m[1]);
      for (const m of src.matchAll(/variable\s*:\s*['"`](--[A-Za-z0-9_-]+)['"`]/g)) global.add(m[1]);
    }
    const bad = [];
    for (const f of cssFiles) {
      const own = decls(readFileSync(f, 'utf8'));
      codeLines(f).forEach((l, i) => {
        // only var() with NO fallback: the comma form already says what to do when absent
        for (const m of l.matchAll(/var\(\s*(--[A-Za-z0-9_-]+)\s*\)/g)) {
          if (!global.has(m[1]) && !own.has(m[1])) {
            bad.push(`${rel(f)}:${i + 1}  ${m[1]} is read but declared neither here nor in the token sheet`);
          }
        }
      });
    }
    return [...new Set(bad)];
  },
  // 10. (4D) No source file carries the app version. version_display #8: the
  //     number on the About row is whatever the SERVICE WORKER reports, so a
  //     constant in the source is a second source of truth that goes stale the
  //     first time a build ships without it. The pattern is the one the app's
  //     own cache names use (zajil-vX.Y.Z); assembled from parts so this guard
  //     cannot match itself.
  'no-hardcoded-version'() {
    const re = new RegExp('zajil' + '-v\\d+\\.\\d+\\.\\d+');
    const bad = [];
    for (const f of files('.js', '.mjs', '.ts', '.tsx')) {
      if (/^(guards|tests)\//.test(rel(f))) continue;   // the guard and its proof name the shape on purpose
      codeLines(f).forEach((l, i) => { if (re.test(l)) bad.push(`${rel(f)}:${i + 1}  ${l.trim()}`); });
    }
    return bad;
  },
  // The root tree has had this guard since v1.4 (tests/guards.test.js:87-92) and the port
  // never got it, which is exactly how app/cert/view.tsx came to date a printed pedigree
  // certificate with `new Date().toISOString().slice(0,10)`. That is the UTC date: east of
  // Greenwich, between local midnight and the offset, it names YESTERDAY — so a certificate
  // printed at 01:00 in Amman carried the previous day. src/dates.js exists for this and
  // says so in its header; todayISO() is the local calendar date.
  //
  // The port's version covers the SUITES as well as the source, because the same slice in a
  // python assertion is a test that fails for three hours a night and passes the rest of the
  // time — which is how this was found: screens/health.py, run at 00:29 local.
  'no-utc-date'() {
    const re = /toISOString\(\)\.slice\(\s*0\s*,\s*10\s*\)/;
    const bad = [];
    for (const f of files('.js', '.mjs', '.ts', '.tsx', '.py')) {
      const r = rel(f);
      if (r === 'src/dates.js') continue;        // the module that documents the mistake
      if (r.startsWith('guards/')) continue;     // this guard and its proof name the shape
      const ls = extname(f) === '.py' ? lines(f) : codeLines(f);
      ls.forEach((l, i) => {
        if (!re.test(l)) return;
        if (/^\s*#/.test(l)) return;             // a python comment is prose, like // above
        bad.push(`${r}:${i + 1}  ${l.trim().slice(0, 90)}`);
      });
    }
    return bad.length ? bad.concat(['use todayISO() from src/dates.js — a UTC slice names the wrong day east of Greenwich']) : bad;
  },
  strings() {
    const r = spawnSync(process.execPath, [join(ROOT, 'guards', 'strings.mjs')], { encoding: 'utf8' });
    const out = (r.stdout || '') + (r.stderr || '');
    for (const l of out.split('\n')) if (l.trim()) console.log('    ' + l);
    return r.status === 0 ? [] : ['guards/strings.mjs exited ' + r.status];
  },
};

const only = process.argv.includes('--only') ? process.argv[process.argv.indexOf('--only') + 1] : null;
let failed = 0;
for (const [name, fn] of Object.entries(guards)) {
  if (only && name !== only) continue;
  const bad = fn();
  if (bad.length) {
    failed++;
    console.log(`✗ ${name}  (${bad.length})`);
    for (const b of bad) console.log(`    ${b}`);
  } else {
    console.log(`✓ ${name}`);
  }
}
console.log(failed ? `\n${failed} guard(s) FAILED` : '\nall guards pass');
process.exit(failed ? 1 : 0);
