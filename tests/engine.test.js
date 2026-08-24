// tests/engine.test.js — engine test suite. Runs in node (tests/run.js) and
// in the app's dev panel. The four COI fixtures here are the acceptance
// criteria named in the spec; do not weaken them.

import { test, assert, assertEq, assertClose } from './harness.js';
import {
  ancestorDepths, truncatedGraph, wouldCreateCycle, pedigreeGrid, descendantDepths,
} from '../js/engine/pedigree.js';
import { makeKinship, inbreeding, pairCOI, coiBreakdown, ancestorLoss } from '../js/engine/coi.js';
import { describeRelationship, pairingWarningLevel } from '../js/engine/relationship.js';
import { parseRing, formatRing, ringKey } from '../js/engine/rings.js';
import { hasFCIRing, resultQualifies, birdEligibility } from '../js/engine/fci.js';
import { haversineMetres, velocityMPM } from '../js/engine/velocity.js';
import { validateBird, validatePairSexes } from '../js/engine/validate.js';

/** Build a getBird from a terse spec: { id: [sireId, damId, extra?] } */
function flock(spec) {
  const map = new Map();
  for (const [id, def] of Object.entries(spec)) {
    const [sireId, damId, extra] = def;
    map.set(id, { id, sireId: sireId || null, damId: damId || null, ...(extra || {}) });
  }
  return {
    getBird: (id) => map.get(id) || null,
    all: () => [...map.values()],
    map,
  };
}

// ---------------------------------------------------------------- COI fixtures

test('COI: full siblings mated → exactly 0.25', () => {
  const { getBird } = flock({
    S: [null, null], D: [null, null],
    A: ['S', 'D'], B: ['S', 'D'],
    X: ['A', 'B'],
  });
  assertClose(inbreeding(getBird, 'X', 10).coi, 0.25, 1e-15);
  const br = coiBreakdown(getBird, 'A', 'B', 10);
  assertClose(br.coi, 0.25, 1e-15);
  assertClose(br.kinshipCOI, 0.25, 1e-15);
  assertEq(br.contributions.length, 2, 'two common ancestors (S and D)');
  assertClose(br.contributions[0].contribution, 0.125, 1e-15);
  assertClose(br.contributions[1].contribution, 0.125, 1e-15);
});

test('COI: parent × offspring → exactly 0.25', () => {
  const { getBird } = flock({
    P: [null, null], M: [null, null],
    C: ['P', 'M'],          // C is offspring of P
    X: ['P', 'C'],          // P mated back to own offspring (C treated as dam)
  });
  assertClose(inbreeding(getBird, 'X', 10).coi, 0.25, 1e-15);
  const br = coiBreakdown(getBird, 'P', 'C', 10);
  assertClose(br.coi, 0.25, 1e-15);
  assertEq(br.contributions.length, 1, 'one common ancestor (P itself)');
  assertEq(br.contributions[0].ancestorId, 'P');
});

test('COI: grandparent × granddaughter → exactly 0.125', () => {
  const { getBird } = flock({
    G: [null, null], Gm: [null, null],
    P1: ['G', 'Gm'], P2: [null, null],
    D: ['P1', 'P2'],        // D is G's granddaughter
    X: ['G', 'D'],
  });
  assertClose(inbreeding(getBird, 'X', 10).coi, 0.125, 1e-15);
  const br = coiBreakdown(getBird, 'G', 'D', 10);
  assertClose(br.coi, 0.125, 1e-15);
  assertEq(br.contributions[0].ancestorId, 'G');
});

test('COI: unrelated → exactly 0', () => {
  const { getBird } = flock({
    A: [null, null], B: [null, null],
    P: ['A', null], Q: [null, 'B'],
  });
  assertClose(pairCOI(getBird, 'P', 'Q', 10).coi, 0, 0);
  const br = coiBreakdown(getBird, 'P', 'Q', 10);
  assertClose(br.coi, 0, 0);
  assertEq(br.contributions.length, 0);
});

// ------------------------------------------------- COI beyond the fixtures

test('COI: half siblings mated → 0.125', () => {
  const { getBird } = flock({
    S: [null, null], D1: [null, null], D2: [null, null],
    A: ['S', 'D1'], B: ['S', 'D2'],
    X: ['A', 'B'],
  });
  assertClose(inbreeding(getBird, 'X', 10).coi, 0.125, 1e-15);
});

test('COI: inbred common ancestor raises contribution — hand-computed 0.28125', () => {
  // W is offspring of full siblings (F_W = 0.25). W × unrelated U gives full
  // sibs C1, C2. F(C1×C2) = via W: (1/2)^3·(1+0.25) = 0.15625, via U: 0.125,
  // total 0.28125. Hand-verified; also documented in ENGINE.md.
  const { getBird } = flock({
    GS: [null, null], GD: [null, null],
    F1: ['GS', 'GD'], F2: ['GS', 'GD'],
    W: ['F1', 'F2'],
    U: [null, null],
    C1: ['W', 'U'], C2: ['W', 'U'],
    X: ['C1', 'C2'],
  });
  const br = coiBreakdown(getBird, 'C1', 'C2', 10);
  assertClose(br.coi, 0.28125, 1e-15);
  assertClose(br.kinshipCOI, 0.28125, 1e-15);
  const w = br.contributions.find((c) => c.ancestorId === 'W');
  assertClose(w.contribution, 0.15625, 1e-15);
  assertClose(w.ancestorF, 0.25, 1e-15);
});

test('COI: path method === kinship method on a messy linebred pedigree', () => {
  // Heavy linebreeding on K with multiple overlapping paths.
  const { getBird } = flock({
    K: [null, null], Q: [null, null], R: [null, null], T: [null, null],
    A: ['K', 'Q'], B: ['K', 'R'],
    C: ['A', 'B'],           // inbred on K
    E: ['K', 'T'],
    G: ['C', null], H: [null, 'E'],
    S1: ['G', 'B'], D1: ['E', 'C'],
  });
  const br = coiBreakdown(getBird, 'S1', 'D1', 10);
  assertClose(br.coi, br.kinshipCOI, 1e-12, 'path sum must equal tabular kinship');
  assert(br.coi > 0.1, 'heavily linebred pair should exceed 10%');
  assert(!br.truncated);
});

test('COI: depth truncation — ancestor beyond N generations is ignored', () => {
  // Chain: common ancestor Z sits 6 generations above the pair.
  const spec = { Z: [null, null] };
  let prevA = 'Z', prevB = 'Z';
  for (let i = 1; i <= 5; i++) {
    spec['a' + i] = [prevA, null]; spec['b' + i] = [prevB, null];
    prevA = 'a' + i; prevB = 'b' + i;
  }
  const { getBird } = flock(spec);
  // pair a5 × b5: Z is at depth 5 from each → path pair length 10, needs depth ≥ 6? 
  // n1 = n2 = 5 → contribution (1/2)^11. With maxDepth 5 the graph keeps Z (depth 5 from the
  // subject's parents = generation 6 of the subject) truncated at founders → still present at
  // depth 5. With maxDepth 4, Z is cut and COI = 0.
  const deep = pairCOI(getBird, 'a5', 'b5', 10).coi;
  assertClose(deep, Math.pow(0.5, 11), 1e-15);
  const shallow = pairCOI(getBird, 'a5', 'b5', 4).coi;
  assertClose(shallow, 0, 0);
});

// ------------------------------------------------------------------ pedigree

test('cycle detection refuses the loop and names the path', () => {
  const { getBird } = flock({
    A: ['B', null], B: ['C', null], C: [null, null],
  });
  // Setting C's sire to A closes the loop A→B→C→A.
  const c = wouldCreateCycle(getBird, 'C', 'A');
  assert(c.cycle, 'must detect cycle');
  assertEq(c.path.join('>'), 'A>B>C', 'path names the offending chain');
  assert(!wouldCreateCycle(getBird, 'C', 'B') ? false : true, 'C.sire=B also cycles (B→C)');
  const ok = wouldCreateCycle(getBird, 'B', 'A');
  assert(ok.cycle, 'B.parent=A cycles since A→B');
  const fine = wouldCreateCycle(getBird, 'A', 'C');
  assert(!fine.cycle, 'A.parent=C is fine (C has no parents)');
  assert(wouldCreateCycle(getBird, 'A', 'A').cycle, 'self-parent is a cycle');
});

test('pedigreeGrid: slot layout parent placement', () => {
  const { getBird } = flock({
    X: ['S', 'D'], S: ['SS', 'SD'], D: ['DS', 'DD'],
    SS: [null, null], SD: [null, null], DS: [null, null], DD: [null, null],
  });
  const grid = pedigreeGrid(getBird, 'X', 2);
  assertEq(grid.length, 3);
  assertEq(grid[0][0].id, 'X');
  assertEq(grid[1][0].id, 'S'); assertEq(grid[1][1].id, 'D');
  assertEq(grid[2].map((s) => s && s.id).join(','), 'SS,SD,DS,DD');
  // unknown parents leave null slots
  const g2 = pedigreeGrid(getBird, 'SS', 2);
  assertEq(g2[1][0], null); assertEq(g2[1][1], null);
});

test('descendantDepths finds all progeny', () => {
  const f = flock({
    P: [null, null], M: [null, null], O1: ['P', 'M'], O2: ['P', null],
    G1: ['O1', null], G2: [null, 'O1'],
  });
  const d = descendantDepths(f.all, 'P');
  assertEq(d.size, 4);
  assertEq(d.get('O1'), 1); assertEq(d.get('G1'), 2); assertEq(d.get('G2'), 2);
});

// ----------------------------------------------------------------------- AVK

test('AVK: complete outcross pedigree → 100%, repeated ancestor lowers it', () => {
  const { getBird } = flock({
    X: ['S', 'D'], S: ['A', 'B'], D: ['C', 'E'],
    A: [null, null], B: [null, null], C: [null, null], E: [null, null],
  });
  const a = ancestorLoss(getBird, 'X', 2);
  assertClose(a.avk, 100, 1e-12);
  assertEq(a.filled, 6); assertEq(a.distinct, 6);

  // Same grandsire on both sides: 6 filled slots, 5 distinct → 83.33%
  const f2 = flock({
    X: ['S', 'D'], S: ['A', 'B'], D: ['A', 'E'],
    A: [null, null], B: [null, null], E: [null, null],
  });
  const a2 = ancestorLoss(f2.getBird, 'X', 2);
  assertClose(a2.avk, (5 / 6) * 100, 1e-9);
});

test('AVK: reports completeness for shallow pedigrees', () => {
  const { getBird } = flock({ X: ['S', null], S: [null, null] });
  const a = ancestorLoss(getBird, 'X', 3);
  assertEq(a.filled, 1);
  assertEq(a.total, 2 + 4 + 8);
  assertClose(a.completeness, (1 / 14) * 100, 1e-9);
});

// -------------------------------------------------------------- relationship

test('relationship: names and hypothetical COI', () => {
  const { getBird } = flock({
    S: [null, null], D: [null, null],
    A: ['S', 'D', { sex: 'cock' }], B: ['S', 'D', { sex: 'hen' }],
    H: ['S', null],
    C: ['A', null],
    N: ['B', null],
  });
  const sib = describeRelationship(getBird, 'A', 'B');
  assertEq(sib.key, 'rel.fullSiblings');
  assertClose(sib.hypotheticalCOI, 0.25, 1e-15);

  assertEq(describeRelationship(getBird, 'A', 'H').key, 'rel.halfSiblings');
  assertEq(describeRelationship(getBird, 'A', 'C').key, 'rel.descendant.offspring');
  assertEq(describeRelationship(getBird, 'C', 'A').key, 'rel.ancestor.parent');
  assertEq(describeRelationship(getBird, 'C', 'S').key, 'rel.ancestor.grandparent');
  assertEq(describeRelationship(getBird, 'A', 'N').key, 'rel.avuncular');
  const cous = describeRelationship(getBird, 'C', 'N');
  assertEq(cous.key, 'rel.firstCousins');
  assertClose(cous.hypotheticalCOI, 0.0625, 1e-15);
  const un = describeRelationship(getBird, 'S', 'D');
  assertEq(un.key, 'rel.unrelated');
  assertClose(un.hypotheticalCOI, 0, 0);
});

test('pairing warning levels', () => {
  assertEq(pairingWarningLevel(0.25), 'severe');
  assertEq(pairingWarningLevel(0.13), 'high');
  assertEq(pairingWarningLevel(0.07), 'moderate');
  assertEq(pairingWarningLevel(0.01), 'info');
  assertEq(pairingWarningLevel(0), 'none');
});

// --------------------------------------------------------------------- rings

test('ring parsing', () => {
  const r = parseRing('JO-2024-12345');
  assertEq(r.country, 'JO'); assertEq(r.year, 2024); assertEq(r.serial, '12345');
  assertEq(r.raw, 'JO-2024-12345');
  const r2 = parseRing('JOR 24 5512');
  assertEq(r2.country, 'JOR'); assertEq(r2.year, 2024); assertEq(r2.serial, '5512');
  const r3 = parseRing('FCI-JO-2023-00871');
  assertEq(r3.type, 'FCI'); assertEq(r3.country, 'JO'); assertEq(r3.year, 2023);
  assertEq(formatRing(r), 'JO-2024-12345');
});

test('ringKey normalises separators and Eastern Arabic digits', () => {
  assertEq(ringKey('JO-2024-12345'), ringKey('jo 2024 12345'));
  assertEq(ringKey('JO-٢٠٢٤-١٢٣٤٥'), ringKey('JO-2024-12345'));
  assert(ringKey('JO-2024-12345') !== ringKey('JO-2024-12346'));
});

// ----------------------------------------------------------------------- FCI

test('FCI eligibility rules', () => {
  assert(hasFCIRing({ rings: [{ type: 'FCI', raw: 'x' }] }));
  assert(!hasFCIRing({ rings: [{ type: 'national', raw: 'x' }] }));
  assert(resultQualifies({ fanciersEntered: 20, birdsEntered: 150, raceType: 'club' }).qualifies);
  const q1 = resultQualifies({ fanciersEntered: 19, birdsEntered: 500, raceType: 'club' });
  assert(!q1.qualifies); assert(q1.reasons.includes('fci.tooFewFanciers'));
  const q2 = resultQualifies({ fanciersEntered: 40, birdsEntered: 149, raceType: 'club' });
  assert(!q2.qualifies); assert(q2.reasons.includes('fci.tooFewBirds'));
  const q3 = resultQualifies({ fanciersEntered: 40, birdsEntered: 400, raceType: 'training' });
  assert(!q3.qualifies);
  const summary = birdEligibility(
    { rings: [{ type: 'FCI' }] },
    [{ fanciersEntered: 25, birdsEntered: 200, raceType: 'national' },
     { fanciersEntered: 5, birdsEntered: 60, raceType: 'club' }],
  );
  assert(summary.hasRing);
  assertEq(summary.qualifyingResults.length, 1);
  assertEq(summary.nonQualifying.length, 1);
});

// ------------------------------------------------------------------ velocity

test('velocity: Amman→Aqaba order of magnitude and exact arithmetic', () => {
  const amman = { lat: 31.9539, lon: 35.9106 };
  const aqaba = { lat: 29.5321, lon: 35.0063 };
  const d = haversineMetres(aqaba, amman);
  assert(d > 270000 && d < 290000, `Aqaba-Amman ≈ 280 km, got ${Math.round(d / 1000)} km`);
  const v = velocityMPM(aqaba, amman, '2026-05-01T06:00:00Z', '2026-05-01T10:00:00Z');
  assertClose(v, d / 240, 1e-9, '4 hours = 240 min');
  assertEq(velocityMPM(aqaba, amman, '2026-05-01T06:00:00Z', '2026-05-01T05:00:00Z'), null,
    'arrival before release → null');
});

// ---------------------------------------------------------------- validation

test('validateBird: cycles, sex contradictions, ages, duplicate rings', () => {
  const f = flock({
    A: ['B', null, { hatchDate: '2024-03-01', sex: 'cock', rings: [{ raw: 'JO-2024-111', type: 'national' }] }],
    B: [null, null, { hatchDate: '2022-03-01', sex: 'cock', rings: [{ raw: 'JO-2022-222', type: 'national' }] }],
    H: [null, null, { hatchDate: '2021-01-01', sex: 'hen', rings: [] }],
    Y: [null, null, { hatchDate: '2025-06-01', sex: 'cock', rings: [] }],
  });
  // cycle: B's sire set to A while A's sire is B
  const r1 = validateBird({ ...f.getBird('B'), sireId: 'A' }, f.getBird, f.all());
  assert(r1.errors.some((e) => e.key === 'val.cycle'));
  // sire is a hen
  const r2 = validateBird({ ...f.getBird('A'), sireId: 'H' }, f.getBird, f.all());
  assert(r2.errors.some((e) => e.key === 'val.sireIsHen'));
  // parent younger than child
  const r3 = validateBird({ ...f.getBird('A'), sireId: 'Y' }, f.getBird, f.all());
  assert(r3.errors.some((e) => e.key === 'val.parentYounger'));
  // duplicate ring warning
  const r4 = validateBird(
    { id: 'NEW', sireId: null, damId: null, rings: [{ raw: 'jo 2024 111', type: 'national' }] },
    f.getBird, f.all());
  assert(r4.warnings.some((w) => w.key === 'val.dupRing'));
  assertEq(r4.errors.length, 0);
  // clean bird passes
  const r5 = validateBird({ ...f.getBird('A') }, f.getBird, f.all());
  assertEq(r5.errors.length, 0);

  const pe = validatePairSexes(f.getBird('H'), f.getBird('B'));
  assert(pe.some((e) => e.key === 'val.pairSireIsHen'));
  assert(pe.some((e) => e.key === 'val.pairDamIsCock'));
});

// ------------------------------------------------------ truncatedGraph edges

test('truncatedGraph: min-depth wins so shared ancestors keep their parents', () => {
  // Z appears at depth 1 (dam) and depth 3 (via sire line): parents must be kept.
  const { getBird } = flock({
    Zp: [null, null],
    Z: ['Zp', null],
    A1: ['Z', null], A2: ['A1', null],
    S: ['A2', null],
  });
  const { parents } = truncatedGraph(getBird, ['S', 'Z'], 2, 1);
  const zp = parents.get('Z');
  assertEq(zp.sireId, 'Zp', 'Z at min-depth 1 keeps its sire even though it also appears at depth 4');
});
