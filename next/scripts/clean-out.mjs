#!/usr/bin/env node
// `next build` with output:'export' writes INTO out/ and does not empty it
// first (proved: a stray file survived a clean build). A stale route from a
// previous harness build would therefore outlive a normal build and trip the
// postbuild guard — or worse, ship. Every build starts from an empty out/.
import { rmSync } from 'node:fs';
rmSync('out', { recursive: true, force: true });
