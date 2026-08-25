// tests/integrity.test.js — referential integrity as a pure, checkable property.
//
// Deleting a bird used to leave its race results, health events, pairs and egg
// links pointing at a record that no longer exists. checkIntegrity() makes that
// class of defect detectable rather than discovered by a user months later.

import { test, assert, assertEq } from './harness.js';
import { checkIntegrity } from '../js/engine/integrity.js';

const CLEAN = {
  birds: [
    { id: 'S', sireId: null, damId: null },
    { id: 'D', sireId: null, damId: null },
    { id: 'C', sireId: 'S', damId: 'D' },
  ],
  pairs: [{ id: 'P', sireId: 'S', damId: 'D',
    rounds: [{ id: 'R', eggs: [{ id: 'E', chickId: 'C' }] }] }],
  raceResults: [{ id: 'RR', birdId: 'C' }],
  healthEvents: [{ id: 'H', birdId: 'C' }, { id: 'HL', birdId: null, wholeLoft: true }],
};

test('checkIntegrity: a consistent database reports nothing', () => {
  assertEq(checkIntegrity(CLEAN).length, 0, JSON.stringify(checkIntegrity(CLEAN)));
});

test('checkIntegrity: a dangling parent link is reported', () => {
  const r = checkIntegrity({ ...CLEAN, birds: [{ id: 'C', sireId: 'GHOST', damId: null }] });
  assert(r.some((x) => x.key === 'integrity.birdParent' && x.params.missingId === 'GHOST'), JSON.stringify(r));
});

test('checkIntegrity: a dangling pair parent is reported', () => {
  const r = checkIntegrity({ ...CLEAN, pairs: [{ id: 'P', sireId: 'GHOST', damId: 'D', rounds: [] }] });
  assert(r.some((x) => x.key === 'integrity.pairParent' && x.params.missingId === 'GHOST'), JSON.stringify(r));
});

test('checkIntegrity: a dangling egg chick link is reported', () => {
  const r = checkIntegrity({ ...CLEAN,
    pairs: [{ id: 'P', sireId: 'S', damId: 'D', rounds: [{ id: 'R', eggs: [{ id: 'E', chickId: 'GHOST' }] }] }] });
  assert(r.some((x) => x.key === 'integrity.eggChick' && x.params.missingId === 'GHOST'), JSON.stringify(r));
});

test('checkIntegrity: dangling race and health references are reported', () => {
  const r = checkIntegrity({ ...CLEAN,
    raceResults: [{ id: 'RR', birdId: 'GHOST' }],
    healthEvents: [{ id: 'H', birdId: 'GHOST2' }] });
  assert(r.some((x) => x.key === 'integrity.raceBird' && x.params.missingId === 'GHOST'), JSON.stringify(r));
  assert(r.some((x) => x.key === 'integrity.healthBird' && x.params.missingId === 'GHOST2'), JSON.stringify(r));
});

test('checkIntegrity: whole-loft health events have no bird and are not flagged', () => {
  const r = checkIntegrity({ ...CLEAN, healthEvents: [{ id: 'HL', birdId: null, wholeLoft: true }] });
  assertEq(r.length, 0, JSON.stringify(r));
});

test('checkIntegrity: null parents are unknown ancestry, not dangling', () => {
  assertEq(checkIntegrity({ birds: [{ id: 'A', sireId: null, damId: null }],
    pairs: [], raceResults: [], healthEvents: [] }).length, 0);
});

test('checkIntegrity: accepts Maps as well as arrays', () => {
  const asMaps = {
    birds: new Map(CLEAN.birds.map((b) => [b.id, b])),
    pairs: new Map(CLEAN.pairs.map((p) => [p.id, p])),
    raceResults: new Map(CLEAN.raceResults.map((r) => [r.id, r])),
    healthEvents: new Map(CLEAN.healthEvents.map((h) => [h.id, h])),
  };
  assertEq(checkIntegrity(asMaps).length, 0);
});

test('checkIntegrity: returns i18n keys and params, never rendered strings', () => {
  const r = checkIntegrity({ ...CLEAN, raceResults: [{ id: 'RR', birdId: 'GHOST' }] });
  for (const x of r) {
    assert(x.key.startsWith('integrity.'), x.key);
    assert(typeof x.params === 'object' && x.params !== null);
  }
});

test('checkIntegrity: tolerates missing stores', () => {
  assertEq(checkIntegrity({ birds: [{ id: 'A', sireId: null, damId: null }] }).length, 0);
  assertEq(checkIntegrity({}).length, 0);
});
