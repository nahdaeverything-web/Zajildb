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

// ───────────────────── tombstone consistency (v1.8) ─────────────────────

test('checkIntegrity: a live record with a matching tombstone is REPORTED', () => {
  // This state means a deletion half-completed, or a resurrection slipped past
  // the import guard. Either way the database is lying about whether the
  // record exists.
  const r = checkIntegrity({
    ...CLEAN,
    tombstones: [{ id: 'birds:C', store: 'birds', recordId: 'C', at: '2026-01-01T00:00:00.000Z' }],
  });
  assert(r.some((x) => x.key === 'integrity.liveWithTombstone'
    && x.params.store === 'birds' && x.params.recordId === 'C'), JSON.stringify(r));
});

test('checkIntegrity: a tombstone for an absent record is CORRECT, not a problem', () => {
  // the normal case: the record is gone and the tombstone records that
  const r = checkIntegrity({
    ...CLEAN,
    tombstones: [{ id: 'birds:GHOST', store: 'birds', recordId: 'GHOST', at: '2026-01-01T00:00:00.000Z' }],
  });
  assert(!r.some((x) => x.key === 'integrity.liveWithTombstone'), JSON.stringify(r));
});

test('checkIntegrity: catches a live/tombstone clash in every store', () => {
  const stores = {
    birds: 'C', pairs: 'P', raceResults: 'RR', healthEvents: 'H',
  };
  for (const [store, recordId] of Object.entries(stores)) {
    const r = checkIntegrity({
      ...CLEAN,
      tombstones: [{ id: `${store}:${recordId}`, store, recordId, at: '2026-01-01T00:00:00.000Z' }],
    });
    assert(r.some((x) => x.key === 'integrity.liveWithTombstone' && x.params.store === store),
      `${store} clash not reported: ${JSON.stringify(r)}`);
  }
});

test('checkIntegrity: the op log is NEVER scanned for dangling references', () => {
  // ops legitimately reference records that no longer exist — that is the
  // entire point of keeping them
  const r = checkIntegrity({
    ...CLEAN,
    oplog: [
      { opId: 'o1', seq: 1, store: 'birds', op: 'delete', recordId: 'LONG-GONE', record: { id: 'LONG-GONE' } },
      { opId: 'o2', seq: 2, store: 'raceResults', op: 'delete', recordId: 'ALSO-GONE', record: null },
    ],
  });
  assertEq(r.length, 0, `the op log must not produce findings: ${JSON.stringify(r)}`);
});

test('checkIntegrity: tombstones are not scanned as if they were records', () => {
  const r = checkIntegrity({
    ...CLEAN,
    tombstones: [
      { id: 'birds:GONE', store: 'birds', recordId: 'GONE', at: '2026-01-01T00:00:00.000Z' },
      { id: 'pairs:ALSO', store: 'pairs', recordId: 'ALSO', at: '2026-01-01T00:00:00.000Z' },
    ],
  });
  assertEq(r.length, 0, JSON.stringify(r));
});

test('checkIntegrity: still tolerates a database with no tombstone store at all', () => {
  assertEq(checkIntegrity(CLEAN).length, 0);
  assertEq(checkIntegrity({ ...CLEAN, tombstones: [] }).length, 0);
});
