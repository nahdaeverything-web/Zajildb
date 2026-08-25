// tests/run.js — node test runner: `node tests/run.js`
import './dates.test.js';
import './engine.test.js';
import './writeboundary.test.js';
import './sample.test.js';
import './example-large.test.js';
import { runAll } from './harness.js';

const { passed, failed, results } = await runAll();
for (const r of results) {
  console.log(`${r.ok ? '✓' : '✗'} ${r.name}${r.ok ? '' : ' — ' + r.error}`);
}
console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
