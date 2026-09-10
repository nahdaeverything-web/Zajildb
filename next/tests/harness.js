// tests/harness.js — micro test framework usable from node and the browser.

export const tests = [];

export function test(name, fn) {
  tests.push({ name, fn });
}

export function assert(cond, msg = 'assertion failed') {
  if (!cond) throw new Error(msg);
}

export function assertEq(actual, expected, msg = '') {
  if (actual !== expected) {
    throw new Error(`${msg} expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

export function assertClose(actual, expected, eps = 1e-12, msg = '') {
  if (typeof actual !== 'number' || Math.abs(actual - expected) > eps) {
    throw new Error(`${msg} expected ≈${expected}, got ${actual}`);
  }
}

export function assertDeepEq(actual, expected, msg = '') {
  const a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a !== e) throw new Error(`${msg} expected ${e}, got ${a}`);
}

/** Run all registered tests. Returns { passed, failed, results }. */
export async function runAll() {
  const results = [];
  let passed = 0, failed = 0;
  for (const t of tests) {
    try {
      await t.fn();
      results.push({ name: t.name, ok: true });
      passed++;
    } catch (err) {
      results.push({ name: t.name, ok: false, error: err.message });
      failed++;
    }
  }
  return { passed, failed, results };
}
