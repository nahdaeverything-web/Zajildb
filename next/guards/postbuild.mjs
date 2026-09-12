#!/usr/bin/env node
// Runs after every `next build` (npm postbuild). Without NEXT_PUBLIC_HARNESS=1
// the static export must contain no test-harness route; with it, it must.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

// Shipped = sync-inert, like main. The config arrives at RUNTIME through
// globalThis.ZAJIL_SYNC_CONFIG (the suites' add_init_script; a self-hosted
// deployment's own script) or is filled in at release time — never baked into
// the static export by this branch. So no build, normal or harness, may
// contain a Supabase host or a publishable key. Needles are assembled from
// parts so this file cannot match itself if it is ever scanned.
const NEEDLES = ['supabase' + '.co', 'sb_' + 'publishable_'];
function* walk(d) { for (const n of readdirSync(d)) { const p = join(d, n); if (statSync(p).isDirectory()) yield* walk(p); else yield p; } }
function scanOut() {
  if (!existsSync('out')) return [];
  const bad = [];
  for (const f of walk('out')) {
    if (!/\.(html|js|css|json|txt|map)$/.test(f)) continue;
    const t = readFileSync(f, 'utf8');
    for (const n of NEEDLES) if (t.includes(n)) bad.push(`${f}  contains "${n}"`);
  }
  return bad;
}
const leaks = scanOut();
if (leaks.length) { console.log('✗ no-sync-config-in-build  (' + leaks.length + ')'); for (const l of leaks) console.log('    ' + l); process.exit(1); }
console.log('✓ no-sync-config-in-build  out/ carries no Supabase host and no publishable key');
// ── the service worker (Phase 5) ────────────────────────────────────────────────
// The precache list is GENERATED from out/, so it cannot drift the way vanilla's
// hand-written SHELL could (tests/guards.test.js:163-180 guards that one). What can
// still go wrong is the generation itself, and silently: an install is one atomic
// addAll, so a single entry that is not on disk leaves NO cache at all and the app has
// no offline mode — which looks exactly like a worker that has not activated yet.
if (existsSync('out/sw.js')) {
  const sw = readFileSync('out/sw.js', 'utf8');
  const bad = [];
  const m = sw.match(/const SHELL = (\[[\s\S]*?\n\]);/);
  const version = (sw.match(/^const VERSION = '([^']+)'/m) || [])[1];
  if (!m) bad.push('out/sw.js has no SHELL array — the generator did not run');
  if (!version) bad.push("out/sw.js has no `const VERSION = '…'` — version_display #5 reads exactly that");
  else if (!version.startsWith('zajil-')) bad.push(`cache name "${version}" does not start with the app's own prefix — activate would spare stale caches and could delete a sibling project's`);
  if (m) {
    const base = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/$/, '');
    const shell = JSON.parse(m[1]);
    const files = new Set([...walk('out')].map((f) => f.split(sep).join('/').replace(/^out\//, '')));
    // 1. every entry exists. The scope root is the navigation entry and has no file.
    for (const u of shell) {
      if (u === base + '/') continue;
      const rel = u.slice((base + '/').length);
      if (!files.has(rel)) bad.push(`precached but not on disk: ${u}`);
    }
    // 2. the harness route belongs in the precache list of a HARNESS build and nowhere
    //    else: without it an offline reload of the harness page falls through to
    //    index.html and silently renders the wrong document; with it in a shipped build
    //    the shell is not the shipped shell.
    const harnessEntries = shell.filter((u) => /test-harness/.test(u));
    if (process.env.NEXT_PUBLIC_HARNESS === '1') {
      if (!harnessEntries.length) bad.push('a harness build precaches no harness route, so an offline reload of it renders the wrong document');
    } else {
      for (const u of harnessEntries) bad.push(`the harness route is in the precache list of a NORMAL build: ${u}`);
    }
    // 3. the prefix the shell was generated with is baked in and agrees with this build
    const builtFor = (sw.match(/^const BUILT_FOR = '([^']*)'/m) || [])[1];
    if (builtFor === undefined) bad.push('out/sw.js does not bake the prefix its shell was generated with, so a deploy under the wrong prefix would 404 every entry in silence');
    else if (builtFor !== base + '/') bad.push(`the baked prefix "${builtFor}" is not this build's "${base}/"`);
    else if (shell[0] !== base + '/') bad.push(`the navigation entry "${shell[0]}" is not this build's prefix "${base}/"`);
    // 4. the things the app cannot work offline without
    const need = [
      [/\/index\.html$/, 'index.html — the navigation fallback'],
      [/\/manifest\.webmanifest$/, 'the manifest'],
      [/\/icons\/icon-192\.png$/, 'the 192px icon'],
      [/\/sample-data\.json$/, 'the small teaching dataset'],
      [/\/example-loft-large\.json$/, 'the large teaching dataset'],
      [/alexandria.*\.woff2$/, 'the Arabic face'],
      [/ibm_plex_mono.*\.woff2$/, 'the mono face'],
      [/_next\/static\/chunks\/.*\.css$/, 'at least one stylesheet'],
      [/_next\/static\/chunks\/.*\.js$/, 'at least one chunk'],
    ];
    for (const [re, what] of need) if (!shell.some((u) => re.test(u))) bad.push(`missing from the precache list: ${what}`);
    // 5. every DOCUMENT the shell can navigate to, or that route is dead offline
    const docs = [...files].filter((f) => f.endsWith('.html') && !/^(404|_not-found)\.html$/.test(f)
      && (process.env.NEXT_PUBLIC_HARNESS === '1' || !/test-harness/.test(f)));
    for (const d of docs) if (!shell.includes(base + '/' + d)) bad.push(`a route that would be dead offline: ${d}`);
  }
  if (bad.length) { console.log('✗ sw-precache-sound  (' + bad.length + ')'); for (const b of bad) console.log('    ' + b); process.exit(1); }
  console.log(`✓ sw-precache-sound  ${JSON.parse(m[1]).length} entries, all on disk, ${version}`);
}

const harness = process.env.NEXT_PUBLIC_HARNESS === '1';
const present = existsSync('out/test-harness.html') || existsSync('out/test-harness');
// harness globals must never ship: in a normal build no chunk may mention __zajilDb
if (!harness && existsSync('out')) {
  const hit = [...walk('out')].filter((f) => /\.js$/.test(f) && readFileSync(f, 'utf8').includes('__zajil' + 'Db'));
  if (hit.length) { console.log('✗ no-harness-globals-in-build  ' + hit.length + ' chunk(s) mention __zajilDb in a NORMAL build'); for (const h of hit) console.log('    ' + h); process.exit(1); }
  console.log('✓ no-harness-globals-in-build  (normal build)');
}
if (!harness && present) { console.log('✗ no-harness-output  out/test-harness exists in a NORMAL build'); process.exit(1); }
if (harness && !present)  { console.log('✗ harness-output-expected  build:harness produced no out/test-harness.html'); process.exit(1); }
console.log(harness ? '✓ harness-output-expected  out/test-harness.html present (harness build)' : '✓ no-harness-output  (normal build)');
