#!/usr/bin/env node
/**
 * Build a release and STAGE IT, then verify the staged bytes — not the build.
 *
 *   NEXT_PUBLIC_BASE_PATH=/zajilv2 node scripts/stage-release.mjs
 *   node scripts/stage-release.mjs --verify-only release        (check an existing staging dir)
 *
 * WHY THE DISTINCTION MATTERS, and it is the whole reason this file exists. On 2026-09-25 a
 * release was built correctly — `✓ base-path-consistent asked "/zajilv2"` — and a root-prefix
 * build reached production anyway, because a gate in another shell rewrote `out/` between the
 * build and the copy. Every postbuild guard had passed, truthfully, about bytes that no longer
 * existed. A check that runs at build time cannot speak for what is shipped; only a check on
 * the shipped bytes can.
 *
 * So this does three things in an order that cannot be reversed:
 *   1. takes an exclusive lock on out/, so nothing else can write it while this runs;
 *   2. builds, then copies out/ into a staging directory the gate never touches;
 *   3. verifies THE STAGING DIRECTORY, and exits non-zero if it is wrong.
 *
 * The staging directory is what gets deployed. `out/` is scratch.
 */
import { execFileSync } from 'node:child_process';
import { cpSync, existsSync, readFileSync, readdirSync, rmSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

import { lockOut } from './_outlock.mjs';

const args = process.argv.slice(2);
const verifyOnly = args.includes('--verify-only');
const STAGE = args.find((a) => !a.startsWith('--')) || 'release';
const WANT = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/$/, '');
const PREFIX = WANT ? `${WANT}/` : '/';

const die = (msg) => { console.error(`✗ stage-release  ${msg}`); process.exit(1); };
const ok = (msg) => console.log(`✓ stage-release  ${msg}`);

// ── verify the STAGED bytes ───────────────────────────────────────────────────
function verify(dir) {
  const problems = [];

  if (!existsSync(join(dir, 'sw.js'))) problems.push('no sw.js — this is not a built export');
  else {
    const sw = readFileSync(join(dir, 'sw.js'), 'utf8');
    const builtFor = (sw.match(/^const BUILT_FOR = '([^']*)'/m) || [])[1];
    if (builtFor === undefined) problems.push('sw.js bakes no BUILT_FOR');
    else if (builtFor !== PREFIX) {
      problems.push(`sw.js was built for "${builtFor}" but this release is for "${PREFIX}" `
        + '— THIS IS THE 2026-09-25 FAILURE: the wrong build reached the staging directory');
    }
  }

  const index = join(dir, 'index.html');
  if (!existsSync(index)) problems.push('no index.html');
  else {
    const html = readFileSync(index, 'utf8');
    // every root-absolute href/src must sit under the prefix. Under a root deployment every
    // one of them trivially does, which is exactly why this is invisible without a prefix.
    const refs = [...html.matchAll(/(?:href|src)="(\/[^"]*)"/g)].map((m) => m[1]);
    const stray = refs.filter((u) => !u.startsWith(PREFIX));
    if (stray.length) {
      problems.push(`index.html has ${stray.length} root-absolute reference(s) outside "${PREFIX}": `
        + stray.slice(0, 4).join(', '));
    }
    if (WANT && !refs.some((u) => u.startsWith(PREFIX))) {
      problems.push(`index.html carries NO reference under "${PREFIX}" — the prefix never reached the export`);
    }
  }

  if (!existsSync(join(dir, '.nojekyll'))) {
    problems.push('no .nojekyll — GitHub Pages drops every /_next/ path without it');
  }

  const maps = [];
  (function walk(d) {
    for (const e of readdirSync(d, { withFileTypes: true })) {
      const p = join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (e.name.endsWith('.map')) maps.push(relative(dir, p));
    }
  })(dir);
  if (maps.length) problems.push(`${maps.length} source map(s) in the release: ${maps.slice(0, 3).join(', ')}`);

  return problems;
}

// ── run ───────────────────────────────────────────────────────────────────────
if (verifyOnly) {
  if (!existsSync(STAGE)) die(`${STAGE}/ does not exist`);
  const problems = verify(STAGE);
  if (problems.length) {
    console.error(`✗ stage-release  ${STAGE}/ is NOT deployable (${problems.length}):`);
    for (const p of problems) console.error(`    ${p}`);
    process.exit(1);
  }
  ok(`${STAGE}/ verified for "${PREFIX}" — safe to deploy`);
  process.exit(0);
}

const release = lockOut('stage-release');
try {
  console.log(`  building for "${PREFIX}" with out/ locked…`);
  execFileSync('npm', ['run', 'build'], { stdio: 'inherit', env: process.env });

  if (existsSync(STAGE)) rmSync(STAGE, { recursive: true, force: true });
  cpSync('out', STAGE, { recursive: true });
  const n = statSync(STAGE).isDirectory() ? readdirSync(STAGE).length : 0;
  console.log(`  staged out/ -> ${STAGE}/ (${n} entries at the root)`);
} finally {
  release();
}

// verify AFTER the lock is released: if anything rewrote out/ in the meantime it no longer
// matters, because the staging copy is what will be deployed and it is what is checked.
const problems = verify(STAGE);
if (problems.length) {
  console.error(`✗ stage-release  REFUSING TO DEPLOY ${STAGE}/ (${problems.length} problem(s)):`);
  for (const p of problems) console.error(`    ${p}`);
  console.error('    Nothing was published. Fix the build and stage again.');
  process.exit(1);
}
ok(`${STAGE}/ built and verified for "${PREFIX}" — deploy THIS directory, not out/`);
