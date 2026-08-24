// tests/sample.test.js — validates sample-data.json against the engine
// (node-only: reads the file from disk).

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { test, assert, assertEq, assertClose } from './harness.js';
import { inbreeding, pairCOI, coiBreakdown } from '../js/engine/coi.js';
import { wouldCreateCycle } from '../js/engine/pedigree.js';
import { validateBird } from '../js/engine/validate.js';
import { birdEligibility } from '../js/engine/fci.js';
import { velocityMPM } from '../js/engine/velocity.js';

const data = JSON.parse(readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), '..', 'sample-data.json'), 'utf8'));
const byId = new Map(data.birds.map((b) => [b.id, b]));
const getBird = (id) => byId.get(id) || null;

test('sample data: hand-verified case — برق (full-sib mating) COI = 0.25', () => {
  assertClose(inbreeding(getBird, 'b-barq', 10).coi, 0.25, 1e-15);
  const br = coiBreakdown(getBird, byId.get('b-barq').sireId, byId.get('b-barq').damId, 10);
  assertEq(br.contributions.length, 2, 'the two Belgian grandparents');
});

test('sample data: hand-verified case — سهم × شقراء hypothetical COI = 0.28125', () => {
  assertClose(pairCOI(getBird, 'c-sahm', 'c-shaqra', 10).coi, 0.28125, 1e-15);
});

test('sample data: every bird validates cleanly (no cycles, ages, sexes ok)', () => {
  for (const b of data.birds) {
    const { errors } = validateBird(b, getBird, data.birds);
    assertEq(errors.length, 0, `bird ${b.id} (${b.name}): ${JSON.stringify(errors)}`);
    for (const pid of [b.sireId, b.damId]) {
      if (pid) assert(!wouldCreateCycle(getBird, b.id, pid).cycle, `cycle at ${b.id}`);
    }
  }
});

test('sample data: pairs reference real birds; chick links resolve', () => {
  for (const p of data.pairs) {
    assert(byId.has(p.sireId), `pair ${p.id} sire missing`);
    assert(byId.has(p.damId), `pair ${p.id} dam missing`);
    for (const r of p.rounds || []) {
      for (const e of r.eggs || []) {
        if (e.chickId) {
          const chick = byId.get(e.chickId);
          assert(chick, `chick ${e.chickId} missing`);
          assertEq(chick.sireId, p.sireId, 'chick auto-link sire');
          assertEq(chick.damId, p.damId, 'chick auto-link dam');
          assertEq(chick.hatchDate, e.hatchDate, 'chick hatch date matches egg');
        }
      }
    }
  }
});

test('sample data: FCI checker — نجم qualifies, وضاح does not', () => {
  const results = (id) => data.raceResults.filter((r) => r.birdId === id);
  const najm = birdEligibility(byId.get('y-najm'), results('y-najm'));
  assert(najm.hasRing, 'نجم carries an FCI ring');
  assertEq(najm.qualifyingResults.length, 1, 'the national Aqaba race qualifies');
  const wadhah = birdEligibility(byId.get('y-wadhah'), results('y-wadhah'));
  assert(!wadhah.hasRing);
  assertEq(wadhah.qualifyingResults.length, 0);
});

test('sample data: stored velocities match engine recomputation', () => {
  for (const r of data.raceResults) {
    if (!r.velocity || !r.releasePoint || !r.loftPoint) continue;
    const v = velocityMPM(r.releasePoint, r.loftPoint, r.releaseTime, r.arrivalTime);
    assertClose(Math.round(v), r.velocity, 0, `race ${r.id}`);
  }
});

test('sample data: import format round-trips through JSON identically', () => {
  const re = JSON.parse(JSON.stringify(data));
  assertEq(JSON.stringify(re), JSON.stringify(data));
  assertEq(data.format, 'zajil-export');
});
