// tests/writeboundary.test.js — validation belongs at the WRITE boundary.
//
// The decision logic lives in a pure engine function so it is testable in node
// (db.js itself needs IndexedDB). saveBird() calls it and throws; a browser
// check in tests/e2e/data_loss.py proves saveBird refuses a bad record when
// called directly with no view involved.

import { test, assert, assertEq } from './harness.js';
import { classifySave } from '../js/engine/validate.js';

function flock(spec) {
  const map = new Map();
  for (const [id, def] of Object.entries(spec)) map.set(id, { id, sireId: null, damId: null, ...def });
  return { getBird: (id) => map.get(id) || null, all: () => [...map.values()] };
}

const BASE = flock({
  HEN: { sex: 'hen', hatchDate: '2020-01-01', rings: [{ raw: 'JO-2020-111', type: 'national' }] },
  COCK: { sex: 'cock', hatchDate: '2020-01-01', rings: [{ raw: 'JO-2020-222', type: 'national' }] },
});

test('classifySave: a clean record is savable', () => {
  const r = classifySave({ id: 'NEW', sex: 'cock', sireId: 'COCK', damId: 'HEN', rings: [] }, BASE.getBird, BASE.all());
  assert(r.ok, JSON.stringify(r));
  assertEq(r.errors.length, 0);
});

test('classifySave: a hen as sire is REFUSED (hard error)', () => {
  const r = classifySave({ id: 'NEW', sex: 'cock', sireId: 'HEN', damId: null, rings: [] }, BASE.getBird, BASE.all());
  assert(!r.ok);
  assert(r.errors.some((e) => e.key === 'val.sireIsHen'), JSON.stringify(r.errors));
});

test('classifySave: a duplicate ring is REFUSED unless the caller confirms', () => {
  const dupe = { id: 'NEW', sex: 'cock', sireId: null, damId: null, rings: [{ raw: 'JO-2020-111', type: 'national' }] };
  const strict = classifySave(dupe, BASE.getBird, BASE.all());
  assert(!strict.ok, 'strict-by-default: an unconfirmed warning must block the write');
  assert(strict.warnings.some((w) => w.key === 'val.dupRing'));
  assertEq(strict.errors.length, 0, 'a duplicate ring is a warning, not an error');
  const confirmed = classifySave(dupe, BASE.getBird, BASE.all(), { allowWarnings: true });
  assert(confirmed.ok, 'the caller may proceed once the user has confirmed');
});

test('classifySave: allowWarnings never overrides a hard error', () => {
  const r = classifySave({ id: 'NEW', sex: 'cock', sireId: 'HEN', damId: null, rings: [] },
    BASE.getBird, BASE.all(), { allowWarnings: true });
  assert(!r.ok, 'errors are not waivable by the caller');
});

test('classifySave: a pedigree cycle is REFUSED', () => {
  const f = flock({ A: { sex: 'cock', sireId: 'B' }, B: { sex: 'cock', sireId: null } });
  const r = classifySave({ ...f.getBird('B'), sireId: 'A' }, f.getBird, f.all());
  assert(!r.ok);
  assert(r.errors.some((e) => e.key === 'val.cycle'));
});

test('classifySave: a parent younger than the bird is REFUSED', () => {
  const f = flock({
    YOUNG: { sex: 'cock', hatchDate: '2026-01-01' },
    OLD: { sex: 'cock', hatchDate: '2020-01-01' },
  });
  const r = classifySave({ id: 'X', sex: 'cock', hatchDate: '2021-01-01', sireId: 'YOUNG', rings: [] },
    f.getBird, f.all());
  assert(!r.ok);
  assert(r.errors.some((e) => e.key === 'val.parentYounger'));
});

test('classifySave: force skips every check (import path only)', () => {
  const r = classifySave({ id: 'NEW', sex: 'cock', sireId: 'HEN', damId: null,
    rings: [{ raw: 'JO-2020-111', type: 'national' }] }, BASE.getBird, BASE.all(), { force: true });
  assert(r.ok, 'imports must be able to land a payload verbatim');
  assertEq(r.errors.length, 0);
  assertEq(r.warnings.length, 0);
});

test('classifySave: returns i18n keys and params, never rendered strings', () => {
  const r = classifySave({ id: 'NEW', sex: 'cock', sireId: 'HEN', damId: null, rings: [] }, BASE.getBird, BASE.all());
  for (const e of [...r.errors, ...r.warnings]) {
    assert(typeof e.key === 'string' && e.key.includes('.'), `not a key: ${JSON.stringify(e)}`);
    assert(typeof e.params === 'object' && e.params !== null, 'params must be an object');
  }
});
