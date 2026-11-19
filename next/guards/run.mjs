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
// BUILD OUTPUT, never source. `release*` is scripts/stage-release.mjs's verified staging
// copy of out/ — added 2026-09-27, after it tripped no-hardcoded-version on its own sw.js:
// a guard reading generated output reports the generator's work as a source defect.
// `out.lock` is the single-writer lock, not a directory of files.
const SKIP = new Set(['node_modules', '.next', 'out', '.git', 'out.lock']);
const SKIP_PREFIX = ['release'];

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (SKIP.has(name) || SKIP_PREFIX.some((p) => name === p || name.startsWith(p + '-'))) continue;
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
  // The port does not reimplement the data layer, it COPIES it. Every file below is
  // byte-identical to its counterpart in js/, and that is what makes an export from one app
  // importable by the other — the property the whole cutover rests on. Nothing enforced it
  // until now: identity held by care, and care is not a mechanism.
  //
  // DIVERGENT lists the files the port is RULED to own. Each needs a reason in
  // PORT-COMPLETE.md. The list is meant to stay short; a file arriving here silently is the
  // failure this guard exists to prevent.
  // RULED 2026-10-30 (RF-18): the removal's bypass of save-time WARNINGS is bounded to its own two re-saves. The
  // flag already exists in four ruled places (the bird form's save after the fancier confirmed the warnings, the
  // «make it a reference» path, the breeding screen's chick saves, and the layer's own defaults); this guard pins
  // every site and its count, so a save path that gains the flag — a new file, one more use in an old one, or the
  // removal's INTERNAL moved into something shared — fails here. Errors are not affected by the flag at all.
  'allow-warnings-bounded'() {
    const ALLOWED = new Map([
      ['src/example-data.js', 1],        // const INTERNAL = Object.freeze({ allowWarnings: true }) — the removal's reference flips and re-files
      ['app/bird/form.tsx', 2],          // the save after the fancier confirmed the warnings dialog; the sibling-of save
      ['app/bird/view.tsx', 1],          // «اجعله مرجعًا»: a bird in pairs or races raises warnings none of which apply to a reference
      ['app/breeding/shared.tsx', 4],    // chick saves from the breeding screen (ringing, hatch date, parents)
      ['src/db/records.js', 1],          // a doc comment on saveBird ("Pass { allowWarnings: true } once the user has confirmed"), not a use
      ['src/engine/validate.js', 1],     // a doc comment on classifySave, not a use
    ]);
    const bad = [];
    const seen = new Map();
    for (const f of files('.js', '.mjs', '.ts', '.tsx')) {
      if (f.includes('/node_modules/') || f.includes('/out/') || f.includes('/release/') || f.includes('/.next/')) continue;
      const rel_ = relative(ROOT, f);
      if (!/^(src|app)\//.test(rel_)) continue;
      const src = readFileSync(f, 'utf8');
      // any value but `false` counts — `true`, `!0`, a variable: the point is the property being set at all
      const uses = (src.match(/allowWarnings\s*:/g) || []).length - (src.match(/allowWarnings\s*:\s*false\b/g) || []).length;
      seen.set(rel_, uses);
      if (!uses) continue;
      const allowed = ALLOWED.get(rel_);
      if (allowed === undefined) bad.push(`${rel_} sets allowWarnings (${uses}×) — not a ruled site; the removal's bypass must not spread`);
      else if (uses !== allowed) bad.push(`${rel_} sets allowWarnings ${uses}× — ${allowed} ruled`);
    }
    // every ruled site must still be exactly as pinned, including one that has lost its use (a stale list hides a move)
    for (const [rel_, n] of ALLOWED) if ((seen.get(rel_) || 0) !== n) bad.push(`${rel_}: ${seen.get(rel_) || 0} use(s) of allowWarnings, ${n} pinned — re-rule the list`);
    const ex = readFileSync(join(ROOT, 'src/example-data.js'), 'utf8');
    // THE A-SET (RULED, built 2026-11-16): the option is FROZEN, and it has exactly ONE user — resave(), which refuses
    // to alter anything but the reference flag and loftId. Counted over the code, comments masked: the definition and
    // the one use. A third mention is the option travelling (a second save, an export, a spread).
    if (!/const INTERNAL = Object\.freeze\(\{ allowWarnings: true \}\);/.test(ex)) bad.push('src/example-data.js: the removal must set the flag exactly as `const INTERNAL = Object.freeze({ allowWarnings: true });`, for its own re-saves');
    const mentions = (maskComments(ex).match(/\bINTERNAL\b/g) || []).length;
    if (mentions !== 2) bad.push(`src/example-data.js: INTERNAL is mentioned ${mentions}× in code — 2 ruled (its definition, and resave())`);
    if (!/const RESAVE_MAY_ALTER = Object\.freeze\(\['external', 'status', 'loftId'\]\);/.test(ex)) bad.push("src/example-data.js: a removal re-save may alter only the reference flag and loftId — `const RESAVE_MAY_ALTER = Object.freeze(['external', 'status', 'loftId']);`");
    return bad;
  },

  // THE A-SET (RULED, built 2026-11-16): `{ force: true }` makes classifySave skip errors AND warnings. Nothing in the
  // app passes it — importAll and the sync apply write without classifySave at all — and nothing may start to: any
  // `force:` with a value other than `false` under src/ or app/ fails here. Comments are masked, so the two doc
  // comments that describe the option do not count. Blind spots, declared as for allow-warnings-bounded: a shorthand
  // `{ force }`, a computed key, an assignment. The suites set it freely, to build shapes validation would refuse.
  'force-never-passed'() {
    const bad = [];
    for (const f of files('.js', '.mjs', '.ts', '.tsx')) {
      const rel_ = relative(ROOT, f);
      if (!/^(src|app)\//.test(rel_)) continue;
      const src = maskComments(readFileSync(f, 'utf8'));
      const uses = (src.match(/\bforce\s*:/g) || []).length - (src.match(/\bforce\s*:\s*false\b/g) || []).length;
      if (uses) bad.push(`${rel_} passes force (${uses}×) — no save in the app may skip validation`);
    }
    return bad;
  },

  // RF-16 (RULED 2026-11-18): forgetting a deletion is the DATASET LOADERS' act alone. loadExampleDataset() clears the
  // tombstones of the shipped ids in the file it is about to load; importAll must go on honouring every deletion.
  // Pinned: who may clear a tombstone at all, that the example module clears in exactly one place, that importAll's
  // file knows nothing of the example data, and the three call sites of the loader (comments masked).
  'example-loader-only'() {
    const bad = [];
    const CLEARERS = new Set(['src/db/oplog.js', 'src/db/io.js', 'src/db/records.js', 'src/example-data.js']);
    const CALLS = new Map([['src/example-data.js', 1], ['app/birds/view.tsx', 1], ['app/tools/parts.tsx', 1]]);   // the definition; the empty state; الأدوات (both buttons share one load())
    const seen = new Map();
    for (const f of files('.js', '.mjs', '.ts', '.tsx')) {
      const rel_ = relative(ROOT, f);
      if (!/^(src|app)\//.test(rel_)) continue;
      const src = maskComments(readFileSync(f, 'utf8'));
      const clears = (src.match(/\bclearTombstone\s*\(/g) || []).length;
      if (clears && !CLEARERS.has(rel_)) bad.push(`${rel_} clears a tombstone (${clears}×) — only the data layer and the dataset loader may`);
      if (rel_ === 'src/example-data.js' && clears !== 1) bad.push(`src/example-data.js clears a tombstone ${clears}× — 1 ruled, inside loadExampleDataset()`);
      const calls = (src.match(/\bloadExampleDataset\s*\(/g) || []).length;
      if (calls) seen.set(rel_, calls);
      if (calls && !CALLS.has(rel_)) bad.push(`${rel_} calls loadExampleDataset (${calls}×) — the three dataset loaders only; a backup import must honour deletions`);
      if (/^src\/db\//.test(rel_) && /example-data|example-ids|exampleIds|loadExampleDataset/.test(src)) bad.push(`${rel_} mentions the example data — importAll and the data layer must not know it`);
    }
    for (const [rel_, n] of CALLS) if ((seen.get(rel_) || 0) !== n) bad.push(`${rel_}: loadExampleDataset appears ${seen.get(rel_) || 0}× — ${n} pinned`);
    return bad;
  },

  // PHOTO SYNC, STAGE 1 (RULED 2026-11-18): bytes travel AFTER records and never hold them up. One door starts an
  // upload pass — the coordinator, after a record cycle that succeeded, and it does not wait for it. One file speaks
  // to storage. A second caller, an awaited pass, or a second place that knows the storage endpoint fails the build.
  'photo-pass-owner'() {
    const bad = []; let calls = 0;
    for (const f of files('.js', '.mjs', '.ts', '.tsx')) {
      const rel_ = relative(ROOT, f);
      if (!/^(src|app)\//.test(rel_)) continue;
      const src = maskComments(readFileSync(f, 'utf8'));
      const n = (src.match(/\brunPhotoPass\s*\(/g) || []).length;
      if (rel_ === 'src/db/sync.js') {
        calls = n;
        if (/await\s+runPhotoPass\s*\(/.test(src)) bad.push('src/db/sync.js awaits runPhotoPass() — a record cycle must never wait for bytes');
      } else if (rel_ === 'src/db/photos.js') {
        if (n !== 1) bad.push(`src/db/photos.js: runPhotoPass( appears ${n}× — 1 pinned, its definition`);
      } else if (n) bad.push(`${rel_} calls runPhotoPass (${n}×) — only the coordinator starts an upload pass (src/db/sync.js)`);
      if (rel_ !== 'src/db/photos.js' && /storage\/v1\//.test(src)) bad.push(`${rel_} names the storage endpoint — only src/db/photos.js speaks to storage`);
    }
    if (calls !== 1) bad.push(`src/db/sync.js: runPhotoPass( appears ${calls}× — 1 pinned, after a cycle that succeeded`);
    return bad;
  },

  // RULED 2026-11-13 (RF-19): ONE coordinator owns every reason a sync cycle runs. It lives in src/db/sync.js and is
  // started once, by src/components/SyncCoordinator.tsx. The only other doors are the two that ask it for a cycle NOW —
  // the sign-in flow and the «مزامنة الآن» button — and the on/off switch; all three go through its single flight.
  // Anything else calling a cycle, or a leg of one, is a second owner: it fails the build. Pinned by count, so a moved
  // or duplicated call is seen too.
  'sync-single-owner'() {
    const NAMES = ['startSyncLoop', 'runSyncCycle', 'syncNow', 'syncOnce', 'pushAll', 'pullAll', 'pushOnce', 'pullOnce', 'setSyncEnabled'];
    const ALLOWED = new Map([
      ['src/components/SyncCoordinator.tsx', { startSyncLoop: 1 }],
      ['app/sign-in/view.tsx', { syncNow: 1 }],
      ['app/tools/parts.tsx', { syncNow: 1, setSyncEnabled: 1 }],
    ]);
    const bad = []; const seen = new Map();
    for (const f of files('.js', '.mjs', '.ts', '.tsx')) {
      const rel_ = rel(f);
      if (!/^(src|app)\//.test(rel_) || rel_ === 'src/db/sync.js') continue;
      const code = codeLines(f).join('\n');
      for (const name of NAMES) {
        const n = (code.match(new RegExp('\\b' + name + '\\s*\\(', 'g')) || []).length;
        if (!n) continue;
        seen.set(rel_ + ' ' + name, n);
        const allowed = (ALLOWED.get(rel_) || {})[name];
        if (allowed === undefined) bad.push(`${rel_} calls ${name}() — only the coordinator starts a sync cycle (src/db/sync.js, src/components/SyncCoordinator.tsx)`);
        else if (n !== allowed) bad.push(`${rel_} calls ${name}() ${n}× — ${allowed} ruled`);
      }
    }
    for (const [rel_, names] of ALLOWED) for (const [name, n] of Object.entries(names)) {
      if ((seen.get(rel_ + ' ' + name) || 0) !== n) bad.push(`${rel_}: ${seen.get(rel_ + ' ' + name) || 0} call(s) of ${name}(), ${n} pinned — re-rule the list`);
    }
    return bad;
  },

  'data-layer-identity'() {
    const DIVERGENT = new Map([
      ['src/db/io.js',
       'exportAllBlob(): the export is assembled as a Blob instead of one JSON string, because '
       + 'past ~180 photos V8 threw `Invalid string length` and the failure was SILENT. '
       + "Vanilla's copy is a separate decision — main is the live deployment. "
       + 'RF-15 (RULED 2026-11-13): a replace-import, and so a restore, tombstones and logs a deletion for every '
       + 'record it drops (replacePreview() states the counts first), so the replacement travels instead of '
       + 'being undone by the next pull. Port-only; vanilla is not changed. THE PHOTO SET (RULED 2026-11-16): a '
       + 'replace deletes a photo only with its bird, and an import rejects a media row that carries no bytes '
       + '(carriesBytes) instead of fetching its address.'],
      ['src/db.js',
       'the facade must re-export exportAllBlob and replacePreview (because src/db/io.js is divergent), '
       + 'ensureCurrentLoft (RF-14) and the example-data module src/example-data.js '
       + '(RULED 2026-10-14, port-only), and the photo-sync module src/db/photos.js (RULED 2026-11-18, port-only).'],
      ['src/db/storage.js',
       'RF-14 (RULED 2026-10-14): ensureCurrentLoft() — a stored currentLoftId is validated at boot '
       + 'instead of trusted; a dangling one adopts the single remaining loft or gets a fresh pristine '
       + 'loft, so a new bird is never filed under an id no loft has. Vanilla has the same defect and '
       + 'is NOT changed — main is the live deployment. RF-25 (RULED 2026-11-17): setSetting() puts memory back '
       + 'when storage refuses the write, so a refused setting does not stay shown or acted on. Vanilla is NOT changed. '
       + 'RF-26 (RULED 2026-11-18): idbAtomic() — one readwrite transaction over several stores, for the pull apply.'],
      ['src/db/oplog.js',
       'RF-27 (RULED 2026-11-19): buildOp(), tombstoneRecord() and tombstoneKey() — the op and the tombstone as values, '
       + 'so a local delete or undo can write its record change, its operation and its tombstone in ONE transaction '
       + '(records.js). logOp() and the rest are unchanged. Vanilla has the same windows and is NOT changed.'],
      ['src/db/records.js',
       'RF-14 (RULED 2026-10-14): the generic remove() and applySyncDelete() call ensureCurrentLoft() '
       + 'after a loft goes, locally or by a pulled tombstone. Port-only, as storage.js. RF-23 (RULED 2026-11-16): '
       + 'withHeldBytes() — applySyncPut() keeps the bytes a media record already holds instead of replacing the '
       + 'record with the pulled, bytes-less row. Vanilla has the same defect and is NOT changed. RF-26 (RULED 2026-11-18): '
       + 'applySyncPut() and applySyncDelete() compare the row with the record on the device and its unpushed operations, '
       + 'and write, in ONE IndexedDB transaction; remoteWins() moved here from sync.js. Vanilla has the same defect and is NOT changed. '
       + 'RF-27 (RULED 2026-11-19): deleteBird(), restoreBird(), the generic remove() and restore(), deleteMedia() and '
       + 'restoreMedia() each write everything they change in ONE transaction (atomicWrite); the mirror follows the commit.'],
      ['src/db/sync.js',
       'the account collision (RF-13): signIn() compares the incoming user with the owner of '
       + 'the data on the device and stops before storing a session that is not the same '
       + 'account; the owner is recorded in settings (dataOwnerId / dataOwnerHint), failing '
       + 'that named by the session, failing that by the op log (RULED 2026-10-07), and '
       + 'clearLocalData() is the one explicit way to change it. RULED 2026-10-05 as a '
       + 'port-only fix. Vanilla has the same defect and is NOT changed — main is the live '
       + 'deployment. THE RE-ENQUEUE LAW (RULED 2026-11-13, RF-20): the first-login enqueue runs once '
       + '(firstEnqueueSeq) instead of on every cycle until lastSyncAt exists. THE COORDINATOR (RULED '
       + '2026-11-13, RF-19/RF-20): single flight with one follow-up instead of a busy refusal; triggers for a '
       + 'debounced change, the background and pagehide (keepalive push) beside online and foreground; the '
       + 'heartbeat is 60 s while unsent, 1-2-4-8-15 minutes capped while failing, 5 minutes idle, and nothing '
       + 'while hidden or signed out. Vanilla keeps its 2-60 s curve and flat 60 s heartbeat. HONEST STATUS '
       + '(RULED 2026-11-13, RF-19): syncStatus() answers unknown until the op log is counted after a load and '
       + 'never synced inside an error window; pendingSince; unsentChanges() for the destructive questions. '
       + 'PHOTO SYNC, STAGE 1 (RULED 2026-11-18): after a cycle that succeeded the coordinator starts the upload pass of '
       + 'src/db/photos.js (port-only, no vanilla counterpart) and does not wait for it. RF-26 (RULED 2026-11-18): applyPage() hands each row\'s last-write-wins decision to records.js, where it runs in the transaction that writes.'],
    ]);
    const FILES = [
      'src/db.js', 'src/db/storage.js', 'src/db/oplog.js', 'src/db/records.js',
      'src/db/io.js', 'src/db/sync.js', 'src/dates.js', 'src/i18n.js', 'src/sync-config.js',
      ...['coi', 'fci', 'integrity', 'pedigree', 'relationship', 'rings', 'validate', 'velocity']
        .map((n) => `src/engine/${n}.js`),
    ];
    const bad = [];
    for (const rel_ of FILES) {
      const mine = join(ROOT, rel_);
      const theirs = join(ROOT, '..', 'js', rel_.replace(/^src\//, ''));
      if (!existsSync(mine)) { bad.push(`${rel_} is listed here but does not exist`); continue; }
      if (!existsSync(theirs)) { bad.push(`${rel_} has no counterpart under js/ — is the list stale?`); continue; }
      const same = readFileSync(mine).equals(readFileSync(theirs));
      if (DIVERGENT.has(rel_)) {
        if (same) bad.push(`${rel_} is listed as DIVERGENT but is still byte-identical — drop it from the list`);
      } else if (!same) {
        bad.push(`${rel_} has drifted from js/${rel_.replace(/^src\//, '')}. If that is deliberate, add it to DIVERGENT with a reason and record it in PORT-COMPLETE.md.`);
      }
    }
    return bad;
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
