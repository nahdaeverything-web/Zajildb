// tests/factory.test.js — ONE record factory.
//
// Bird records were being minted at four sites (the form, the picker's inline
// create, the add-sibling placeholders, ring-chick), and only the form knew
// that an external bird must carry REFERENCE_STATUS. The others produced
// external birds with status 'stock', so the register mislabelled and
// misfiltered them. newBird() now derives status from external, so no caller
// can get it wrong by omission.

import { test, assert, assertEq } from './harness.js';
import { newBird, REFERENCE_STATUS } from '../js/db.js';

test('newBird: an external bird always carries REFERENCE_STATUS', () => {
  assertEq(newBird({ external: true }).status, REFERENCE_STATUS);
});

test('newBird: derivation holds even when a caller passes a contradictory status', () => {
  // omission is the common bug, but an explicit wrong value must not win either
  assertEq(newBird({ external: true, status: 'stock' }).status, REFERENCE_STATUS);
  assertEq(newBird({ external: true, status: 'breeder' }).status, REFERENCE_STATUS);
});

test('newBird: an owned bird keeps its requested status, defaulting to stock', () => {
  assertEq(newBird({}).status, 'stock');
  assertEq(newBird({ external: false }).status, 'stock');
  assertEq(newBird({ status: 'breeder' }).status, 'breeder');
  assertEq(newBird({ external: false, status: 'race team' }).status, 'race team');
});

test('newBird: an owned bird never lands on REFERENCE_STATUS by accident', () => {
  const b = newBird({ status: REFERENCE_STATUS });
  assertEq(b.external, true, 'asking for the reference status means the bird is external');
  assertEq(b.status, REFERENCE_STATUS);
});

test('newBird: every record has the fields the schema promises', () => {
  const b = newBird({});
  for (const f of ['id', 'rings', 'name', 'sex', 'hatchDate', 'status', 'sireId',
                   'damId', 'external', 'notes', 'createdAt', 'updatedAt']) {
    assert(f in b, `missing ${f}`);
  }
  assertEq(b.sex, 'unknown');
  assert(Array.isArray(b.rings) && Array.isArray(b.notes));
});

test('newBird: ids are unique', () => {
  const ids = new Set(Array.from({ length: 200 }, () => newBird({}).id));
  assertEq(ids.size, 200);
});
