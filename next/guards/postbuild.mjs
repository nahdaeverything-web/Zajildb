#!/usr/bin/env node
// Runs after every `next build` (npm postbuild). Without NEXT_PUBLIC_HARNESS=1
// the static export must contain no test-harness route; with it, it must.
import { existsSync, readdirSync, readFileSync, rmSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

// Shipped = sync-inert, like main. The config arrives at RUNTIME through
// globalThis.ZAJIL_SYNC_CONFIG (the suites' add_init_script; a self-hosted
// deployment's own script) or is filled in at release time — never baked into
// the static export by this branch. So no build, normal or harness, may
// contain a Supabase host or a publishable key. Needles are assembled from
// parts so this file cannot match itself if it is ever scanned.
// Configuration is detected by SHAPE, not by hostname. The literal needles were the whole
// check, and the cutover's own requirements walk straight past them: *.supabase.co must be
// replaced by a custom domain before any Gulf pilot (SPIKE-SUPABASE.md:326-335), and a
// legacy JWT anon key is `eyJ…` rather than `sb_publishable_`. So the constants themselves
// are what gets checked — a build is configured when they are not empty, whatever they hold.
const NEEDLES = [
  ['a Supabase host', /\bhttps?:\/\/[a-z0-9-]+\.supabase\.(co|in|net)\b/],
  // built from parts so this file cannot match itself; a regex literal cannot concatenate
  ['a publishable key', new RegExp('sb_' + 'publishable_[A-Za-z0-9_-]{8,}')],
  ['a JWT anon key', /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/],
  // the bundled constants, filled in: `SUPABASE_URL = "https://…"` survives minification as
  // an assignment or an object property, so the value is what is looked for
  ['a filled-in sync endpoint', /(SUPABASE_URL|publishableKey|SUPABASE_PUBLISHABLE_KEY)\s*[:=]\s*["'`]\s*[^"'`\s][^"'`]*["'`]/],
];
function* walk(d) { for (const n of readdirSync(d)) { const p = join(d, n); if (statSync(p).isDirectory()) yield* walk(p); else yield p; } }
function scanOut() {
  if (!existsSync('out')) return [];
  const bad = [];
  for (const f of walk('out')) {
    if (!/\.(html|js|mjs|css|json|webmanifest|txt|map)$/.test(f)) continue;
    const t = readFileSync(f, 'utf8');
    for (const [what, re] of NEEDLES) if (re.test(t)) bad.push(`${f}  carries ${what}`);
  }
  return bad;
}
const leaks = scanOut();
if (leaks.length) {
  console.log('✗ no-sync-config-in-build  (' + leaks.length + ')');
  for (const l of leaks) console.log('    ' + l);
  // `next build` has already written out/ in full, so failing the command is not enough: a
  // pipeline that uploads regardless of the exit code would publish exactly this. The
  // artefact goes with the failure.
  rmSync('out', { recursive: true, force: true });
  console.log('    out/ was REMOVED — a configured export must not survive a failed guard');
  process.exit(1);
}
console.log('✓ no-sync-config-in-build  out/ carries no endpoint, no key of any kind, and no filled-in constant');
// ── base-path-consistent (RULED at Phase 6 acceptance) ──────────────────────────
// A service worker whose baked prefix does not match the host it is deployed to registers
// happily and caches NOTHING: every one of its ~130 precache URLs 404s, install rejects
// atomically, and ServiceWorker.tsx's .catch swallows it. The app then reports a registered
// worker with no offline mode, which looks exactly like "not activated yet". There is no
// runtime signal and no user-visible error — so it has to be impossible to ship.
//
// basePath is a BUILD-TIME constant, so all three of these must agree:
//   · what was ASKED for      — NEXT_PUBLIC_BASE_PATH
//   · what the EXPORT carries — the asset URLs Next actually wrote into the documents
//   · what the WORKER baked   — BUILT_FOR and the first precache entry
// The third against the first is the easy check and was already here. The second is the one
// that matters: a var set for the postbuild step but not for `next build` gives a
// root-absolute export with a prefixed worker, and nothing downstream would notice.
if (existsSync('out/sw.js') && existsSync('out/index.html')) {
  const want = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/$/, '');
  const sw = readFileSync('out/sw.js', 'utf8');
  const html = readFileSync('out/index.html', 'utf8');
  const bad = [];

  const builtFor = (sw.match(/^const BUILT_FOR = '([^']*)'/m) || [])[1];
  const m = sw.match(/const SHELL = (\[[\s\S]*?\n\]);/);
  const first = m ? JSON.parse(m[1])[0] : undefined;

  if (builtFor === undefined) {
    bad.push('out/sw.js bakes no BUILT_FOR, so nothing can check the prefix it was generated for');
  } else if (builtFor !== want + '/') {
    bad.push(`the worker was generated for "${builtFor}" but this build asked for "${want || '(root)'}"`);
  }
  if (first !== undefined && first !== want + '/') {
    bad.push(`the worker's navigation entry is "${first}", not this build's "${want}/"`);
  }

  // What the EXPORT actually carries. Next writes asset URLs origin-absolute, so under a
  // base path they read /<base>/_next/… and at the root /_next/… — there is no third form.
  const assets = [...html.matchAll(/(?:src|href)="(\/[^"]*_next\/[^"]*)"/g)].map((x) => x[1]);
  if (!assets.length) {
    bad.push('out/index.html references no /_next asset, so the export could not be checked for its prefix');
  } else {
    const prefixed = assets.filter((u) => u.startsWith(want + '/_next/'));
    if (prefixed.length !== assets.length) {
      const stray = assets.find((u) => !u.startsWith(want + '/_next/'));
      bad.push(want
        ? `a base path "${want}" was requested but the export is root-absolute — e.g. ${stray}. `
          + 'NEXT_PUBLIC_BASE_PATH reached this guard and not `next build`; the worker would '
          + 'precache one prefix while the documents ask for another.'
        : `no base path was requested but the export is prefixed — e.g. ${stray}`);
    }
  }
  const manifest = (html.match(/<link[^>]+rel="manifest"[^>]+href="([^"]+)"/) || [])[1];
  if (manifest && !manifest.startsWith(want + '/')) {
    bad.push(`the manifest link "${manifest}" is not under this build's prefix "${want}/"`);
  }

  if (bad.length) { console.log('✗ base-path-consistent  (' + bad.length + ')'); for (const b of bad) console.log('    ' + b); process.exit(1); }
  console.log(`✓ base-path-consistent  asked "${want || '(root)'}" · export, worker and manifest all agree`);
}

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
    // 3. the things the app cannot work offline without
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
    // 4. every DOCUMENT the shell can navigate to, or that route is dead offline
    // 404 and _not-found are not navigable app routes — the worker serves index.html as the
    // navigation fallback — so they are excluded. BOTH SHAPES: `trailingSlash: true` writes
    // them as 404/index.html and _not-found/index.html rather than 404.html, and a pattern
    // that knew only the flat shape reported them as dead offline routes the moment the
    // config was ruled (2026-09-25).
    const docs = [...files].filter((f) => f.endsWith('.html') && !/^(404|_not-found)(\.html|\/index\.html)$/.test(f)
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
