#!/usr/bin/env node
// `npm run build:harness` — the ONLY way app/test-harness/ exists. (Not
// __harness: the App Router excludes underscore-prefixed folders from routing.) The route
// source is copied in, the build runs with NEXT_PUBLIC_HARNESS=1, and the
// copy is removed in a finally so an aborted build cannot leave it behind.
import { cpSync, rmSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
const SRC = 'harness', DST = 'app/test-harness';
const GLOBALS = 'src/harness-globals.tsx', GLOBALS_SRC = 'harness/HarnessGlobals.tsx';
const stub = readFileSync(GLOBALS, 'utf8');
if (existsSync(DST)) rmSync(DST, { recursive: true, force: true });
rmSync('out', { recursive: true, force: true });   // same rule as scripts/clean-out.mjs
cpSync(SRC, DST, { recursive: true });
writeFileSync(GLOBALS, readFileSync(GLOBALS_SRC, 'utf8'));   // real globals for this build only
let code = 1;
try {
  // the prebuild guards run from the npm lifecycle only for `npm run build`; a harness build must not skip them
  // (4B: the breeding module's unsanctioned hover reached a green harness build and failed the shipped one)
  code = spawnSync('node', ['guards/run.mjs'], { stdio: 'inherit', env: { ...process.env, NEXT_PUBLIC_HARNESS: '1' } }).status ?? 1;
  if (code === 0) code = spawnSync('npx', ['next', 'build'], { stdio: 'inherit', env: { ...process.env, NEXT_PUBLIC_HARNESS: '1' } }).status ?? 1;
  // The service worker and the postbuild guards run from the npm lifecycle only for
  // `npm run build`; run them here explicitly, in the same order — the worker is generated
  // first so the guards can check it. Its generator excludes the harness route itself, so a
  // harness build gets a worker whose shell is the shipped one.
  if (code === 0) code = spawnSync('node', ['scripts/build-sw.mjs'], { stdio: 'inherit', env: { ...process.env, NEXT_PUBLIC_HARNESS: '1' } }).status ?? 1;
  if (code === 0) code = spawnSync('node', ['guards/postbuild.mjs'], { stdio: 'inherit', env: { ...process.env, NEXT_PUBLIC_HARNESS: '1' } }).status ?? 1;
} finally {
  rmSync(DST, { recursive: true, force: true });
  writeFileSync(GLOBALS, stub);                               // the shipped stub is back
}
process.exit(code);
