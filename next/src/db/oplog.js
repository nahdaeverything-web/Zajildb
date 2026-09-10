// db/oplog.js — what THIS DEVICE DID, in order, and the tombstones that make
// deletions visible.
//
// A future sync layer needs intent, not just final state: which fields a write
// touched, that a delete happened at all, and a total order it can trust.
// Conflict order comes from `seq` — see the header of js/db.js for why it is
// not `updatedAt`.
//
// `logOp` is exported only so its siblings in js/db/ can reach it. It is NOT
// part of the public API and must never escape this directory: a view writing
// to the log directly would record something that never went through the write
// path. Enforced by tests/guards.test.js.
//
// Import from `js/db.js`, never from here directly — the facade is the API.

import { idbDelete, idbGet, idbGetAll, idbPut, nowISO, state, uuid } from './storage.js';

// ---------------------------------------------------------------- record CRUD

// ─────────────────────────────── the op log ───────────────────────────────
// What THIS DEVICE DID, in order. A future sync layer needs intent, not just
// final state: which fields a write touched, that a delete happened at all,
// and a total order it can trust. Conflict order comes from `seq` — see the
// header comment for why not `updatedAt`.
//
// Compaction is a SYNC-TIME concern, deliberately not done here: ops can be
// dropped once a server has acknowledged them. Until sync exists there is
// nothing to acknowledge against, so the log simply grows. At loft scale
// (hundreds of records, a few edits a day) that is negligible.

/**
 * Top-level field names that differ between two versions of a record.
 * A nested or array change surfaces as its top-level field — enough for a sync
 * layer to merge per field without storing a structural diff.
 * Exported only so the node suite can test it; not for use outside db.js.
 */
export function diffFields(prev, next) {
  if (!prev) return Object.keys(next || {}).filter((k) => next[k] !== undefined);
  const keys = new Set([...Object.keys(prev), ...Object.keys(next || {})]);
  const changed = [];
  for (const k of keys) {
    const a = prev[k], b = (next || {})[k];
    if (a === undefined && b === undefined) continue;
    if (JSON.stringify(a) !== JSON.stringify(b)) changed.push(k);
  }
  return changed;
}

/** A record as it should be stored in an op: never a Blob. */
export function opRecord(record) {
  if (!record) return null;
  if (!('blob' in record)) return record;
  const { blob, ...rest } = record;   // media metadata only — blobs stay in their store
  return rest;
}

/**
 * Claim the next sequence number.
 *
 * The claim is SYNCHRONOUS — `state.settings.opSeq` is incremented before any
 * await — so two writes started in the same tick can never receive the same
 * number, which would silently corrupt conflict ordering. Persistence then
 * writes whatever the highest claimed value currently is (not the captured
 * one), so out-of-order completion still leaves the stored counter at the
 * maximum rather than a lower value that would hand the number out twice
 * after a reload.
 */
async function nextSeq() {
  const n = (state.settings.opSeq || 0) + 1;
  state.settings.opSeq = n;
  await idbPut('settings', { key: 'opSeq', value: state.settings.opSeq });
  return n;
}

/**
 * Append one op. Internal to db.js by design — a view must never write to the
 * log directly, or the log stops being a faithful record of the write path.
 * Enforced by tests/guards.test.js.
 */
export async function logOp({ origin, store, op, recordId, record, changed, at }) {
  const seq = await nextSeq();          // persisted before the op counts as logged
  await idbPut('oplog', {
    opId: uuid(),
    seq,
    deviceId: state.settings.deviceId || null,
    // The signed-in user, once there is one. Ops written BEFORE sign-in keep
    // null and are pushed as-is: they were genuinely made by an unidentified
    // actor on this device, and back-filling an id would be a lie in the audit
    // trail (SYNC-DESIGN §5).
    actorId: state.settings.authUserId || null,
    // When the operation happened. Defaults to now; supplied explicitly only
    // by the first-login synthetic ops, which carry each record's own
    // `updatedAt` because that is what this device knew, as of when it knew it
    // (SYNC-DESIGN §6).
    at: at || nowISO(),
    origin,                             // 'user' | 'import' | 'restore'
    store,
    op,                                 // 'put' | 'delete'
    recordId,
    changed: changed || [],
    record: opRecord(record),
  });
  return seq;                            // shared with the tombstone of the same deletion
}

/**
 * Ops in sequence order.
 *
 * TRAP, found the hard way: idbGetAll('oplog') returns records in KEY order,
 * and the key is `opId` — a random uuid. So the raw result is effectively
 * shuffled, and anything that slices or assumes "the last N" gets arbitrary
 * ops. Always read through here, never idbGetAll('oplog') directly.
 */
export async function getOpsSinceSeq(since = 0) {
  const ops = await idbGetAll('oplog');
  return ops.filter((o) => o.seq > since).sort((a, b) => a.seq - b.seq);
}

/**
 * Mark ops as superseded: they lost a conflict and must never be pushed.
 *
 * They are NOT deleted. §4 promises that "the losing version remains in the op
 * log", which is what makes a clock-skew mistake recoverable rather than fatal
 * — so the record stays and only its right to be pushed is withdrawn.
 */
export async function markOpsSuperseded(opIds) {
  let marked = 0;
  for (const opId of opIds || []) {
    const op = await idbGet('oplog', opId);
    if (!op || op.superseded) continue;
    await idbPut('oplog', { ...op, superseded: true });
    marked++;
  }
  return marked;
}

/** Every op, in sequence order. */
export function listOps() { return getOpsSinceSeq(0); }
export function listTombstones() { return idbGetAll('tombstones'); }

// ─────────────────────────────── tombstones ───────────────────────────────
// A delete is the one change that leaves no trace in final state: a record
// that is simply absent is indistinguishable from one that never arrived. Without
// a tombstone, any merge of an older export silently resurrects deleted birds.
//
// Keyed `store:recordId` so a repeat delete overwrites rather than accumulating.
// The `seq` is the SAME number as the op that recorded the deletion — they are
// one logical operation.

const tombstoneId = (store, recordId) => `${store}:${recordId}`;

/**
 * @param at  when the deletion HAPPENED. Defaults to now for a local delete.
 *   A sync-applied delete passes the remote row's `updated_at` instead: the
 *   tombstone must claim the time the deletion actually occurred, or every
 *   later tombstone-versus-record comparison is made against a time that never
 *   happened. Same reasoning as §2a's timestamp rule, reached from the other
 *   side. `seq` is null for a sync-applied delete — there is no local op.
 */
export async function writeTombstone(store, recordId, seq, at = nowISO()) {
  await idbPut('tombstones', {
    id: tombstoneId(store, recordId),
    store,
    recordId,
    at,
    deviceId: state.settings.deviceId || null,
    seq,
  });
}

/** The tombstone for one record, or null. */
export function getTombstone(store, recordId) {
  return idbGet('tombstones', tombstoneId(store, recordId));
}

/** An undone deletion never happened, so its tombstone must go. */
export async function clearTombstone(store, recordId) {
  await idbDelete('tombstones', tombstoneId(store, recordId));
}

