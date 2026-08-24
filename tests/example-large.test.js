// tests/example-large.test.js — the teaching dataset is a deliverable: its
// COI cases are what a learner is shown, so they are asserted like fixtures.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { test, assert, assertEq, assertClose } from './harness.js';
import { validateBird, validatePairSexes } from '../js/engine/validate.js';
import { wouldCreateCycle, ancestorDepths } from '../js/engine/pedigree.js';
import { inbreeding, pairCOI, ancestorLoss } from '../js/engine/coi.js';
import { birdEligibility } from '../js/engine/fci.js';
import { velocityMPM } from '../js/engine/velocity.js';

const data = JSON.parse(readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), '..', 'example-loft-large.json'), 'utf8'));
const byId = new Map(data.birds.map((b) => [b.id, b]));
const getBird = (id) => byId.get(id) || null;

test('example loft: 38 birds, 5 pairs, all records validate cleanly', () => {
  assertEq(data.birds.length, 38);
  assertEq(data.pairs.length, 5);
  for (const b of data.birds) {
    const { errors } = validateBird(b, getBird, data.birds);
    assertEq(errors.length, 0, `${b.name}: ${JSON.stringify(errors)}`);
    for (const pid of [b.sireId, b.damId]) {
      if (pid) {
        assert(byId.has(pid), `${b.name}: dangling parent`);
        assert(!wouldCreateCycle(getBird, b.id, pid).cycle, `${b.name}: cycle`);
      }
    }
  }
  for (const p of data.pairs) {
    assertEq(validatePairSexes(getBird(p.sireId), getBird(p.damId)).length, 0, `pair ${p.id}`);
  }
});

test('example loft: the teaching COI cases hit their exact values', () => {
  assertClose(inbreeding(getBird, 'g3-sheikh', 10).coi, 0.125, 1e-15, 'double first cousins');
  assertClose(inbreeding(getBird, 'g3-khayal', 10).coi, 0.125, 1e-15, 'double first cousins');
  assertClose(inbreeding(getBird, 'g3-asif', 10).coi, 0.25, 1e-15, 'father × daughter');
  assertClose(inbreeding(getBird, 'g2-muhannad', 10).coi, 0, 0, 'outcross');
  assert(pairCOI(getBird, 'g5-faris26', 'g5-najma26', 10).coi > 0.25,
    'full-sib young birds must trigger the severe pairing warning');
});

test('example loft: pedigrees are deep enough to teach — 5 full generations', () => {
  const depths = ancestorDepths(getBird, ['g5-faris26'], 10, 0);
  assertEq(Math.max(...depths.values()), 5, 'فارس ٢٦ reaches the imported foundation');
  assertEq(depths.size - 1, 28, 'known ancestors');
  const a = ancestorLoss(getBird, 'g5-faris26', 5);
  assertClose(a.completeness, 100, 1e-9, 'no empty slots in 5 generations');
});

test('example loft: egg→chick links and stored velocities are consistent', () => {
  for (const p of data.pairs) {
    for (const r of p.rounds || []) for (const e of r.eggs || []) {
      if (!e.chickId) continue;
      const c = getBird(e.chickId);
      assert(c, `chick ${e.chickId} exists`);
      assertEq(c.sireId, p.sireId); assertEq(c.damId, p.damId);
      assertEq(c.hatchDate, e.hatchDate);
    }
  }
  for (const r of data.raceResults) {
    assert(byId.has(r.birdId), `race ${r.id} bird`);
    const v = velocityMPM(r.releasePoint, r.loftPoint, r.releaseTime, r.arrivalTime);
    assertEq(Math.round(v), r.velocity, `race ${r.id}`);
  }
});

test('example loft: FCI checker has both qualifying and non-qualifying cases', () => {
  const res = (id) => data.raceResults.filter((r) => r.birdId === id);
  const shihab = birdEligibility(getBird('g4-shihab'), res('g4-shihab'));
  assert(shihab.hasRing && shihab.qualifyingResults.length === 2, 'شهاب qualifies twice');
  const ghaima = birdEligibility(getBird('g5-ghaima26'), res('g5-ghaima26'));
  assert(!ghaima.hasRing && ghaima.qualifyingResults.length === 0, 'غيمة has no FCI ring');
});
