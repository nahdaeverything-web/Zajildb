// next/tests/run.js — the engine-relevant subset of the root suite, run
// against next/src/engine/. Same harness, same test bodies; only the paths
// differ. `node next/tests/run.js`
import './engine.test.js';
import './sample.test.js';
import './example-large.test.js';
import { runAll } from './harness.js';

const { passed, failed, results } = await runAll();
for (const r of results) console.log(`${r.ok ? '✓' : '✗'} ${r.name}${r.ok ? '' : ' — ' + r.error}`);
console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
