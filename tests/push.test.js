// tests/push.test.js — the pure half of push: the op-to-row mapping and the
// collapse. Both are ordinary functions over ordinary data, so they are tested
// here rather than through a browser.
//
// The network half — batching, the affected-row ack, poison bisection,
// compaction — is tests/e2e/push.py, because it needs IndexedDB and a server
// to answer.

import { test, assert, assertEq } from './harness.js';
import { opToRow, collapseOps, PUSH_BATCH, OPLOG_KEEP } from '../js/db.js';

const op = (over = {}) => ({
  opId: 'op-1', seq: 1, deviceId: 'dev-1', actorId: null,
  at: '2026-08-29T10:05:00.000Z', origin: 'user', store: 'birds', op: 'put',
  recordId: 'bird-1', changed: ['name'],
  record: { id: 'bird-1', name: 'برق', updatedAt: '2026-06-01T09:00:00.000Z' },
  ...over,
});

test('push: updated_at is the OP time, never record.updatedAt', () => {
  // THE rule of §2a. restoreBird deliberately reinstates a record's ORIGINAL
  // timestamps, so record.updatedAt can move BACKWARDS; operation time cannot.
  // A sync layer that trusted the record field would diverge permanently.
  const row = opToRow(op());
  assertEq(row.updated_at, '2026-08-29T10:05:00.000Z', 'updated_at must be the op time');
  assert(row.updated_at !== row.data.updatedAt,
    'this fixture exists precisely so the two differ — if they match, it proves nothing');
});

test('push: the undo case that the timestamp rule exists for', () => {
  // A restore reinstates updatedAt = 09:00 while the op happens at 10:05. The
  // row must carry 10:05, or another device's 10:00 tombstone wins and the two
  // never converge.
  const restore = op({
    origin: 'restore', at: '2026-08-29T10:05:00.000Z',
    record: { id: 'bird-1', name: 'برق', updatedAt: '2026-08-29T09:00:00.000Z' },
  });
  const row = opToRow(restore);
  assert(row.updated_at > '2026-08-29T10:00:00.000Z',
    `an undo must beat a 10:00 tombstone, got ${row.updated_at}`);
});

test('push: owner and server_seq are never sent', () => {
  const row = opToRow(op());
  assertEq('owner' in row, false, 'owner is defaulted server-side to auth.uid()');
  assertEq('server_seq' in row, false, 'server_seq is assigned by the trigger');
  assertEq(Object.keys(row).sort().join(','),
    'data,deleted,device_id,op_seq,record_id,store,updated_at',
    'the row shape is the §2a table exactly');
});

test('push: a delete is an upsert carrying the last-known body', () => {
  const row = opToRow(op({ op: 'delete' }));
  assertEq(row.deleted, true);
  assertEq(row.data.name, 'برق', 'the body is kept, not nulled — it makes an audit possible');
});

test('push: an op with no record still produces a valid row', () => {
  // `data` is NOT NULL on the server. An op that captured no record (deleting
  // something already gone) would otherwise produce a row the server refuses,
  // and one refused row is a poison record blocking the queue.
  const row = opToRow(op({ op: 'delete', record: null }));
  assertEq(JSON.stringify(row.data), '{}');
  assertEq(row.deleted, true);
});

test('push: collapse keeps the LAST op per record', () => {
  const rows = collapseOps([
    op({ seq: 1, at: '2026-08-29T10:00:00.000Z', record: { id: 'bird-1', name: 'first' } }),
    op({ seq: 2, at: '2026-08-29T10:01:00.000Z', record: { id: 'bird-1', name: 'second' } }),
    op({ seq: 3, at: '2026-08-29T10:02:00.000Z', record: { id: 'bird-1', name: 'third' } }),
  ]);
  assertEq(rows.length, 1, 'three edits to one bird are one upsert');
  assertEq(rows[0].data.name, 'third');
  assertEq(rows[0].op_seq, 3, 'the highest seq');
  assertEq(rows[0].updated_at, '2026-08-29T10:02:00.000Z', 'the last op time');
});

test('push: a put followed by a delete collapses to the delete', () => {
  const rows = collapseOps([
    op({ seq: 1, op: 'put' }),
    op({ seq: 2, op: 'delete', at: '2026-08-29T10:09:00.000Z' }),
  ]);
  assertEq(rows.length, 1);
  assertEq(rows[0].deleted, true, 'a record created and then deleted must arrive deleted');
  assertEq(rows[0].op_seq, 2);
});

test('push: the same record id in different stores does NOT collapse', () => {
  // ids are client-generated uuids and collision across stores is not expected,
  // but the primary key is (owner, store, record_id) and the collapse key must
  // match it or two different rows would silently become one.
  const rows = collapseOps([
    op({ seq: 1, store: 'birds', recordId: 'shared-id' }),
    op({ seq: 2, store: 'pairs', recordId: 'shared-id' }),
  ]);
  assertEq(rows.length, 2, 'the collapse key must be (store, record), not record alone');
  assertEq(rows.map((r) => r.store).sort().join(','), 'birds,pairs');
});

test('push: collapse preserves oldest-record-first order', () => {
  const rows = collapseOps([
    op({ seq: 1, recordId: 'a' }), op({ seq: 2, recordId: 'b' }),
    op({ seq: 3, recordId: 'a' }), op({ seq: 4, recordId: 'c' }),
  ]);
  assertEq(rows.map((r) => r.record_id).join(','), 'a,b,c',
    'a later edit must not move a record to the end of the batch');
});

test('push: collapse of nothing is nothing', () => {
  assertEq(collapseOps([]).length, 0);
});

test('push: the tuned constants are what §2 and §11 specify', () => {
  assertEq(PUSH_BATCH, 200, 'batch size is 200 records per push (§11)');
  assertEq(OPLOG_KEEP, 500, 'the forensic tail is 500 ops (§2 compaction)');
});
