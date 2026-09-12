#!/usr/bin/env node
// Generate out/sw.js from sw/sw.template.js and the FINISHED export.
//
// Runs FIRST in `postbuild`, before guards/postbuild.mjs — which is what lets that guard's
// sw-precache-sound check, and its Supabase and harness scans, see out/sw.js at all.
// It never guesses: the precache list is a walk of out/, so every entry provably exists —
// which matters because install is one atomic addAll and a single 404 leaves no cache at
// all (vanilla sw.js:55-57, asserted by tests/e2e/service_worker.py).
//
// Two placeholders are filled:
//   __VERSION__  'zajil-' + the version in package.json. The literal lives in exactly one
//                place, and because this file WRITES it rather than containing it, the
//                no-hardcoded-version guard (which skips out/) and version_display #5
//                (which wants `const VERSION = '…'` inside sw.js) both hold.
//   __SHELL__    the generated list, base-path prefixed.
//
// EXCLUDED from the precache, each for a reason:
//   · sw.js itself — a worker does not precache itself; the browser handles its update.
//   · test-harness* — the harness route exists only in a harness build and must never be
//     part of the shipped shell (it is what the no-harness-output guard is about).
//   · 404.html / _not-found.html — answered by the host, and byte-identical to each other.
//   · *.map — source maps are for a developer with a network.
import { readFileSync, writeFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(fileURLToPath(import.meta.url), '..', '..');
const OUT = join(ROOT, 'out');
const TEMPLATE = join(ROOT, 'sw', 'sw.template.js');

const BASE = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/$/, '');
const SCOPE = BASE + '/';

const EXCLUDE = [
  /^sw\.js$/,
  // Every harness artefact, not just the document: a harness build also emits
  // test-harness.txt and test-harness/** RSC payloads. Excluded from a SHIPPED shell —
  // but a harness build is what every suite serves, and leaving it out meant an offline
  // reload of the harness page fell through to index.html and silently rendered the wrong
  // document. So it is excluded only when this is not a harness build, and
  // sw-precache-sound enforces that either way.
  ...(process.env.NEXT_PUBLIC_HARNESS === '1' ? [] : [/^test-harness(\.|\/|$)/]),
  // the host answers these, and offline the navigation fallback does; excluding the
  // document while precaching its four RSC payloads was four dead entries
  /^404(\.|\/|$)/,
  /^_not-found(\.|\/|$)/,
  /\.map$/,
  // out/fonts/** is the verbatim public/ passthrough and nothing fetches it — next/font
  // reads those files at BUILD time and emits hashed copies under _next/static/media,
  // which are what the CSS and the preload links ask for. Precaching both would ship
  // 105 KB twice.
  /^fonts\//,
];

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

if (!existsSync(OUT)) {
  console.error('  build-sw: no out/ — run a build first');
  process.exit(2);
}
if (!existsSync(join(OUT, 'index.html'))) {
  console.error('  build-sw: out/index.html is missing — the export is not what this expects');
  process.exit(2);
}

const version = 'zajil-v' + JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8')).version;

const files = [...walk(OUT)]
  .map((f) => relative(OUT, f).split(sep).join('/'))
  .filter((r) => !EXCLUDE.some((re) => re.test(r)))
  .sort();

// The navigation entry first, as vanilla lists './' first: a bare visit to the scope root
// must be a cache hit, and on a clean-URL host that request's path IS the scope.
const shell = [SCOPE, ...files.map((r) => SCOPE + r)];

const src = readFileSync(TEMPLATE, 'utf8')
  .replace('__VERSION__', version)
  .replace('__BASE__', SCOPE)
  .replace('__SHELL__', JSON.stringify(shell, null, 2));

if (src.includes('__VERSION__') || src.includes('__SHELL__') || src.includes('__BASE__')) {
  console.error('  build-sw: a placeholder was not filled — the template changed shape');
  process.exit(2);
}

writeFileSync(join(OUT, 'sw.js'), src);

const bytes = files.reduce((n, r) => n + statSync(join(OUT, r)).size, 0);
console.log(`✓ service worker            out/sw.js — ${version}, ${shell.length} precache entries, `
  + `${(bytes / 1024 / 1024).toFixed(2)} MB${BASE ? `, scope ${SCOPE}` : ''}`);
