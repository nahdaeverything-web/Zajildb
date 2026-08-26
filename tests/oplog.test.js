// tests/oplog.test.js — the pure parts of the op log.
//
// The op log records what THIS DEVICE DID, so a future sync layer can replay
// or reconcile intent rather than guessing from final state. Two pieces are
// pure and therefore testable here; the IndexedDB behaviour (one op per write,
// monotonic seq) is proven in tests/e2e/oplog.py.

import { test, assert, assertEq, assertDeepEq } from './harness.js';
import { diffFields, opRecord } from '../js/db.js';

test('diffFields: a new record reports every field', () => {
  const next = { id: 'A', name: 'x', sex: 'cock' };
  assertDeepEq(diffFields(null, next).sort(), ['id', 'name', 'sex']);
  assertDeepEq(diffFields(undefined, next).sort(), ['id', 'name', 'sex']);
});

test('diffFields: an unchanged record reports nothing', () => {
  const r = { id: 'A', name: 'x', rings: [{ raw: 'JO-1' }] };
  assertDeepEq(diffFields(r, { ...r, rings: [{ raw: 'JO-1' }] }), []);
});

test('diffFields: only the changed top-level fields are reported', () => {
  const prev = { id: 'A', name: 'x', sex: 'cock', status: 'stock' };
  const next = { id: 'A', name: 'y', sex: 'cock', status: 'breeder' };
  assertDeepEq(diffFields(prev, next).sort(), ['name', 'status']);
});

test('diffFields: nested and array changes surface as the top-level field', () => {
  const prev = { id: 'A', rings: [{ raw: 'JO-1' }], notes: [] };
  assertDeepEq(diffFields(prev, { ...prev, rings: [{ raw: 'JO-2' }] }), ['rings']);
  assertDeepEq(diffFields(prev, { ...prev, notes: [{ text: 'hi' }] }), ['notes']);
});

test('diffFields: added and removed fields both count as changed', () => {
  assertDeepEq(diffFields({ id: 'A' }, { id: 'A', colour: 'blue' }), ['colour']);
  assertDeepEq(diffFields({ id: 'A', colour: 'blue' }, { id: 'A' }), ['colour']);
});

test('diffFields: undefined and missing are the same absence', () => {
  assertDeepEq(diffFields({ id: 'A', x: undefined }, { id: 'A' }), []);
});

test('diffFields: field ORDER never counts as a change', () => {
  assertDeepEq(diffFields({ id: 'A', a: 1, b: 2 }, { b: 2, a: 1, id: 'A' }), []);
});

test('opRecord: strips a media blob but keeps the metadata', () => {
  const m = { id: 'm1', birdId: 'b1', kind: 'photo', name: 'x.png', blob: { size: 999 } };
  const stored = opRecord(m);
  assertEq(stored.blob, undefined, 'a blob must never enter the op log');
  assertEq(stored.name, 'x.png');
  assertEq(stored.birdId, 'b1');
  assert(!('blob' in stored), 'the key itself should be gone, not just undefined');
});

test('opRecord: an ordinary record passes through unchanged', () => {
  const b = { id: 'A', name: 'x', rings: [{ raw: 'JO-1' }] };
  assertDeepEq(opRecord(b), b);
});

test('opRecord: null/undefined is tolerated', () => {
  assertEq(opRecord(null), null);
  assertEq(opRecord(undefined), null);
});
