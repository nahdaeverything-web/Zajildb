#!/usr/bin/env node
// `npm run build:harness` — the ONLY way app/test-harness/ exists. (Not
// __harness: the App Router excludes underscore-prefixed folders from routing.) The route
// source is copied in, the build runs with NEXT_PUBLIC_HARNESS=1, and the
// copy is removed in a finally so an aborted build cannot leave it behind.
import { cpSync, rmSync, existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
const SRC = 'harness', DST = 'app/test-harness';
if (existsSync(DST)) rmSync(DST, { recursive: true, force: true });
rmSync('out', { recursive: true, force: true });   // same rule as scripts/clean-out.mjs
cpSync(SRC, DST, { recursive: true });
let code = 1;
try {
  code = spawnSync('npx', ['next', 'build'], { stdio: 'inherit', env: { ...process.env, NEXT_PUBLIC_HARNESS: '1' } }).status ?? 1;
  // the postbuild guard runs from the npm lifecycle only for `npm run build`; run it here explicitly
  if (code === 0) code = spawnSync('node', ['guards/postbuild.mjs'], { stdio: 'inherit', env: { ...process.env, NEXT_PUBLIC_HARNESS: '1' } }).status ?? 1;
} finally {
  rmSync(DST, { recursive: true, force: true });
}
process.exit(code);
