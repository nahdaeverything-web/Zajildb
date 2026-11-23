// tests/clutch.test.js — the clutch (RULED 2026-11-23). Port-only: engine/clutch.js has no vanilla counterpart, and
// engine/validate.js is declared divergent for the one warning asserted here (guards/run.mjs, PORT-COMPLETE.md).
import { test, assertDeepEq } from './harness.js';
import { clutchMates } from '../src/engine/clutch.js';
import { validateBird, classifySave } from '../src/engine/validate.js';

const birds = [
  { id: 'A', sireId: 'P', damId: 'Q', clutchId: 'k1' },
  { id: 'B', sireId: 'P', damId: 'Q', clutchId: 'k1' },
  { id: 'C', sireId: 'P', damId: 'Q' },                    // a chick of the round below, no clutchId
  { id: 'D', sireId: 'P', damId: 'Q' },                    // its mate in the round
  { id: 'E', sireId: null, damId: null, clutchId: 'k2' },  // alone in its group
  { id: 'P', sex: 'cock' }, { id: 'Q', sex: 'hen' }, { id: 'R', sex: 'cock' },
];
const pairs = [{ id: 'pair', sireId: 'P', damId: 'Q', rounds: [{ id: 'r1', eggs: [{ id: 'e1', chickId: 'C' }, { id: 'e2', chickId: 'D' }, { id: 'e3', chickId: null }] }, { id: 'r2', eggs: [{ id: 'e4', chickId: 'A' }] }] }];
const getBird = (id) => birds.find((b) => b.id === id) || null;
const ids = (list) => list.map((b) => b.id).sort();

test('clutchMates: a shared clutchId, the same round of a pair, both, and neither', () => {
  assertDeepEq(ids(clutchMates(getBird('A'), birds, pairs, getBird)), ['B'], 'the group id:');
  assertDeepEq(ids(clutchMates(getBird('C'), birds, pairs, getBird)), ['D'], 'the round, no clutchId on either:');
  assertDeepEq(ids(clutchMates({ ...getBird('C'), clutchId: 'k1' }, birds, pairs, getBird)), ['A', 'B', 'D'], 'both ways at once:');
  assertDeepEq(ids(clutchMates(getBird('E'), birds, pairs, getBird)), [], 'alone in its group:');
  assertDeepEq(ids(clutchMates(getBird('P'), birds, pairs, getBird)), [], 'a parent of the pair is not a chick of its round:');
  assertDeepEq(ids(clutchMates(getBird('A'), birds, undefined, getBird)), ['B'], 'no pairs handed over:');
  assertDeepEq(clutchMates(null, birds, pairs, getBird), [], 'no bird:');
});

test('validateBird: clutch-mates that do not share sire and dam — a warning, never an error', () => {
  const keys = (r) => r.warnings.map((w) => [w.key, w.params.otherId]);
  assertDeepEq(keys(validateBird(getBird('A'), getBird, birds, pairs)), [], 'the same parents:');
  const moved = validateBird({ ...getBird('A'), sireId: 'R' }, getBird, birds, pairs);
  assertDeepEq(keys(moved), [['val.clutchParents', 'B']], 'another father:');
  assertDeepEq(moved.errors, [], 'never an error:');
  assertDeepEq(keys(validateBird({ ...getBird('A'), damId: null }, getBird, birds, pairs)), [['val.clutchParents', 'B']], 'a missing mother is not a shared mother:');
  assertDeepEq(keys(validateBird({ ...getBird('C'), sireId: 'R' }, getBird, birds, pairs)), [['val.clutchParents', 'D']], 'the round:');
  assertDeepEq(keys(validateBird({ ...getBird('C'), sireId: 'R' }, getBird, birds)), [], 'without the pairs the round is not known — the three-argument call of the vanilla engine still works:');
  assertDeepEq(classifySave({ ...getBird('C'), sireId: 'R' }, getBird, birds, { pairs }).ok, false, 'strict by default:');
  assertDeepEq(classifySave({ ...getBird('C'), sireId: 'R' }, getBird, birds, { pairs, allowWarnings: true }).ok, true, 'confirmed:');
});
