#!/usr/bin/env node
// Runs after every `next build` (npm postbuild). Without NEXT_PUBLIC_HARNESS=1
// the static export must contain no test-harness route; with it, it must.
import { existsSync } from 'node:fs';
const harness = process.env.NEXT_PUBLIC_HARNESS === '1';
const present = existsSync('out/test-harness.html') || existsSync('out/test-harness');
if (!harness && present) { console.log('✗ no-harness-output  out/test-harness exists in a NORMAL build'); process.exit(1); }
if (harness && !present)  { console.log('✗ harness-output-expected  build:harness produced no out/test-harness.html'); process.exit(1); }
console.log(harness ? '✓ harness-output-expected  out/test-harness.html present (harness build)' : '✓ no-harness-output  (normal build)');
