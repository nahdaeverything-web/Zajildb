#!/usr/bin/env node
// Runs after every `next build` (npm postbuild). Without NEXT_PUBLIC_HARNESS=1
// the static export must contain no test-harness route; with it, it must.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

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
