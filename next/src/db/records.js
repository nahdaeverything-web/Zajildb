// db/records.js — the write boundary: birds, the generic stores, and media.
//
// Every mutation the user can make lands here, and every one of them is
// validated, stamped, logged and announced in the same order. That uniformity
// is the point: a view cannot write an invalid record by forgetting to check,
// and cannot write a silent one by forgetting to emit.
//
// Import from `js/db.js`, never from here directly — the facade is the API.

import { classifySave } from '../engine/validate.js';
import {
  REFERENCE_STATUS, allBirds, emitChange, ensureCurrentLoft, getBird, idbAtomic, idbDelete, idbGet, idbGetAll, idbPut, nowISO, stamp, state, uuid,
} from './storage.js';
import { buildOp, diffFields, logOp, tombstoneKey, tombstoneRecord } from './oplog.js';

/**
 * THE bird factory. Every bird record in the app is minted here.
 *
 * Ownership and status are two views of one fact, so the factory derives them
 * rather than trusting each caller to remember: an external bird (a
 * never-owned ancestor from someone else's pedigree) always carries
 * REFERENCE_STATUS, and asking for REFERENCE_STATUS means the bird is
 * external. Four call sites used to mint birds independently and only one of
 * them knew this rule, so ancestors created inline arrived as 'stock' and the
 * register mislabelled and misfiltered them.
 */
export function newBird(partial = {}) {
  const external = partial.external === true || partial.status === REFERENCE_STATUS;
  const status = external ? REFERENCE_STATUS : (partial.status || 'stock');
  return stamp({
    id: uuid(),
    rings: [],            // [{country, union, year, serial, raw, type}]
    name: '',
    sex: 'unknown',       // cock | hen | unknown
    hatchDate: '',
    colour: '',
    strain: '',
    eyeSign: '',
    status: 'stock',
    sireId: null,
    damId: null,
    external: false,      // ancestor never owned by the user — still a real record
    breeder: '',
    owner: '',
    acquiredFrom: '',
    acquiredDate: '',
    notes: [],            // [{id, at, text}]
    // Append-only history of what happened to this bird. provenance[0] is the
    // creation event — that, not `deviceId`, identifies the creating device.
    // A caller may supply an existing history (a shared or imported bird) and
    // it is kept verbatim: the spread below wins.
    provenance: [{ event: 'created', at: nowISO(), deviceId: state.settings.deviceId || null }],
    createdAt: nowISO(),
    ...partial,
    // derived last so a caller cannot contradict the invariant by omission
    // or by passing a stale pair of values
    external,
    status,
  });
}

/**
 * Thrown by saveBird when a record fails validation. Carries the i18n keys so
 * a view can render them; never a pre-rendered string.
 */
export class ValidationError extends Error {
  constructor(errors, warnings) {
    super('zajil/validation-failed');
    this.name = 'ValidationError';
    this.errors = errors;
    this.warnings = warnings;
  }
}

/**
 * Pre-flight check, bound to the live flock. Views use this to show errors and
 * to ask the user to confirm warnings BEFORE writing. It is the same single
 * implementation saveBird enforces — not a second copy of the rules.
 */
export function checkBird(bird, opts = {}) {
  return classifySave(bird, getBird, allBirds(), opts);
}

/**
 * THE write boundary for birds. Validation happens here, so no view can write
 * an invalid record by forgetting to check — that is how "ring chick" used to
 * create duplicate rings and impossible parent links.
 *
 * Strict by default. Pass { allowWarnings: true } once the user has confirmed
 * them, or { force: true } from importAll / dataset loaders only.
 * @throws {ValidationError}
 */
export async function saveBird(bird, { allowWarnings = false, force = false } = {}) {
  const verdict = classifySave(bird, getBird, allBirds(), { allowWarnings, force });
  if (!verdict.ok) throw new ValidationError(verdict.errors, verdict.warnings);
  const previous = state.birds.get(bird.id) || null;
  stamp(bird);
  await idbPut('birds', bird);
  state.birds.set(bird.id, bird);
  await logOp({ origin: 'user', store: 'birds', op: 'put', recordId: bird.id,
                record: bird, changed: diffFields(previous, bird) });
  emitChange({ type: 'bird', id: bird.id });
  return bird;
}

/**
 * Delete a bird and every reference to it, leaving the database referentially
 * consistent (assert with checkIntegrity). Everything touched is snapshotted so
 * undo restores the whole picture, not just the bird.
 *
 * Offspring keep their records and lose the parent link; race results, health
 * events and pairs that name the bird are removed, because a race result for a
 * bird that does not exist is not a record of anything. Eggs in OTHER pairs
 * that pointed at this bird as their chick are unlinked.
 */
// ── RF-27 (RULED 2026-11-19): A LOCAL DELETE, AND ITS UNDO, ARE ONE TRANSACTION ──
// A delete used to remove the record, then log its operation, then write its tombstone — three transactions. A pulled
// row applied between the first and the rest saw no operation and no tombstone, and put the record back (measured).
// An undo had the mirror image: the record back, its operation not logged, the echoed deletion took it away again.
// Now every record change of one delete or one undo, its operations, and its tombstones are written together: a
// pulled row is either before all of it or after all of it. The mirror is changed only once the transaction has
// committed, so memory never shows a write the store did not take.
async function atomicWrite(stores, fn) {
  const after = [];                                  // mirror changes, applied in order after the commit
  const out = await idbAtomic([...new Set([...stores, 'oplog', 'tombstones', 'settings'])], async (h) => fn({
    put: (store, value) => h.put(store, value),
    del: (store, key) => h.del(store, key),
    log: async (entry) => {                          // what logOp() does, inside this transaction
      const op = buildOp(entry);
      await h.put('settings', { key: 'opSeq', value: state.settings.opSeq });
      await h.put('oplog', op);
      return op.seq;
    },
    tomb: (store, id, seq) => h.put('tombstones', tombstoneRecord(store, id, seq)),
    untomb: (store, id) => h.del('tombstones', tombstoneKey(store, id)),
    then: (f) => { after.push(f); },
  }));
  for (const f of after) f();
  return out;
}

export async function deleteBird(id) {
  const bird = state.birds.get(id);
  const media = await idbGetAll('media', 'birdId', id);
  const affectedOriginals = [];   // offspring whose parent link is cleared
  const removedRaces = [];
  const removedHealth = [];
  const removedPairs = [];
  const affectedPairs = [];       // pairs that merely referenced it from an egg

  await atomicWrite(['birds', 'pairs', 'raceResults', 'healthEvents', 'media'], async (w) => {   // the whole deletion
    for (const b of state.birds.values()) {
      if (b.sireId === id || b.damId === id) {
        affectedOriginals.push({ ...b });
        const copy = { ...b };
        if (copy.sireId === id) copy.sireId = null;
        if (copy.damId === id) copy.damId = null;
        stamp(copy);
        await w.put('birds', copy);
        w.then(() => state.birds.set(copy.id, copy));
        await w.log({ origin: 'user', store: 'birds', op: 'put', recordId: copy.id,
                      record: copy, changed: diffFields(affectedOriginals[affectedOriginals.length - 1], copy) });
      }
    }
    for (const r of [...state.raceResults.values()]) {
      if (r.birdId === id) {
        removedRaces.push({ ...r });
        await w.del('raceResults', r.id); w.then(() => state.raceResults.delete(r.id));
        const seq = await w.log({ origin: 'user', store: 'raceResults', op: 'delete', recordId: r.id, record: r });
        await w.tomb('raceResults', r.id, seq);
      }
    }
    for (const e of [...state.healthEvents.values()]) {
      if (e.birdId === id) {
        removedHealth.push({ ...e });
        await w.del('healthEvents', e.id); w.then(() => state.healthEvents.delete(e.id));
        const seq = await w.log({ origin: 'user', store: 'healthEvents', op: 'delete', recordId: e.id, record: e });
        await w.tomb('healthEvents', e.id, seq);
      }
    }
    for (const p of [...state.pairs.values()]) {
      if (p.sireId === id || p.damId === id) {
        removedPairs.push(JSON.parse(JSON.stringify(p)));
        await w.del('pairs', p.id);
        w.then(() => state.pairs.delete(p.id));
        const seq = await w.log({ origin: 'user', store: 'pairs', op: 'delete', recordId: p.id, record: p });
        await w.tomb('pairs', p.id, seq);
        continue;
      }
      const referencesBird = (p.rounds || []).some((r) =>
        (r.eggs || []).some((e) => e.chickId === id));
      if (referencesBird) {
        affectedPairs.push(JSON.parse(JSON.stringify(p)));   // snapshot BEFORE changing
        const copy = JSON.parse(JSON.stringify(p));           // the mirror's own object is not touched before the commit
        for (const round of copy.rounds || []) {
          for (const egg of round.eggs || []) {
            if (egg.chickId === id) { egg.chickId = null; egg.ringed = false; }
          }
        }
        stamp(copy);
        await w.put('pairs', copy);
        w.then(() => state.pairs.set(copy.id, copy));
        await w.log({ origin: 'user', store: 'pairs', op: 'put', recordId: copy.id,
                      record: copy, changed: ['rounds'] });
      }
    }

    // A1: the cascade hard-deletes media rows directly rather than via
    // deleteMedia(), so each one is logged here.
    for (const m of media) {
      await w.del('media', m.id);
      const seq = await w.log({ origin: 'user', store: 'media', op: 'delete', recordId: m.id, record: m });
      await w.tomb('media', m.id, seq);   // A1: the cascade deletes media directly
    }
    await w.del('birds', id);
    w.then(() => state.birds.delete(id));
    const birdSeq = await w.log({ origin: 'user', store: 'birds', op: 'delete', recordId: id, record: bird });
    await w.tomb('birds', id, birdSeq);
  });
  emitChange({ type: 'bird', id });
  return { bird, media, affectedOriginals, removedRaces, removedHealth, removedPairs, affectedPairs };
}

/** Undo a deleteBird: puts back the bird AND everything the cascade removed. */
export async function restoreBird(snapshot) {
  const { bird, media, affectedOriginals, removedRaces, removedHealth,
          removedPairs, affectedPairs } = snapshot || {};
  if (!bird) return;
  // an undo restores exactly what was there; it is not a new edit to re-judge
  await atomicWrite(['birds', 'pairs', 'raceResults', 'healthEvents', 'media'], async (w) => {   // the whole undo
    const back = async (store, mirror, rec) => {
      await w.put(store, rec);
      if (mirror) w.then(() => state[mirror].set(rec.id, rec));
      await w.log({ origin: 'restore', store, op: 'put', recordId: rec.id, record: rec });
      await w.untomb(store, rec.id);
    };
    await back('birds', 'birds', bird);
    for (const orig of affectedOriginals || []) await back('birds', 'birds', orig);
    for (const r of removedRaces || []) await back('raceResults', 'raceResults', r);
    for (const e of removedHealth || []) await back('healthEvents', 'healthEvents', e);
    for (const p of [...(removedPairs || []), ...(affectedPairs || [])]) await back('pairs', 'pairs', p);
    for (const m of media || []) await back('media', null, m);
  });
  emitChange({ type: 'bird', id: bird.id });
}

export function makeGeneric(storeName, stateMap, typeName) {
  return {
    async save(rec) {
      const previous = rec.id ? (state[stateMap].get(rec.id) || null) : null;
      stamp(rec);
      if (!rec.id) rec.id = uuid();
      await idbPut(storeName, rec);
      state[stateMap].set(rec.id, rec);
      await logOp({ origin: 'user', store: storeName, op: 'put', recordId: rec.id,
                    record: rec, changed: diffFields(previous, rec) });
      emitChange({ type: typeName, id: rec.id });
      return rec;
    },
    async remove(id) {
      const rec = state[stateMap].get(id);
      await atomicWrite([storeName], async (w) => {       // RF-27: the removal, its operation and its tombstone together
        await w.del(storeName, id);
        w.then(() => state[stateMap].delete(id));
        const seq = await w.log({ origin: 'user', store: storeName, op: 'delete', recordId: id, record: rec });
        await w.tomb(storeName, id, seq);
      });
      if (storeName === 'lofts') await ensureCurrentLoft();   // RF-14: removing the current loft must not leave it dangling
      emitChange({ type: typeName, id });
      return rec;
    },
    async restore(rec) {
      await atomicWrite([storeName], async (w) => {       // RF-27
        await w.put(storeName, rec);
        w.then(() => state[stateMap].set(rec.id, rec));
        await w.log({ origin: 'restore', store: storeName, op: 'put', recordId: rec.id, record: rec });
        await w.untomb(storeName, rec.id);
      });
      emitChange({ type: typeName, id: rec.id });
    },
  };
}

export const Pairs = makeGeneric('pairs', 'pairs', 'pair');
export const Races = makeGeneric('raceResults', 'raceResults', 'race');
export const Health = makeGeneric('healthEvents', 'healthEvents', 'health');
export const Lofts = makeGeneric('lofts', 'lofts', 'loft');

// ---------------------------------------------------------------------- media

export async function addMedia(birdId, kind, subtype, name, blob) {
  const m = { id: uuid(), birdId, kind, subtype, name, blob, addedAt: nowISO() };
  await idbPut('media', m);
  // metadata only — a Blob never enters the op log
  await logOp({ origin: 'user', store: 'media', op: 'put', recordId: m.id, record: m,
                changed: ['id', 'birdId', 'kind', 'subtype', 'name', 'addedAt'] });
  emitChange({ type: 'media', id: m.id, birdId });
  return m;
}
/**
 * THE PHOTO INVARIANT (RULED 2026-11-16): a media record that holds bytes is never replaced by one that does not.
 * Photos have no server copy (DF-4), so the bytes on a device are the only ones. Every writer that can meet a media
 * record WITHOUT bytes — a pulled row, an imported row — passes it through here first: if the device already holds
 * bytes under that id, the record written carries them.
 */
export async function withHeldBytes(m) {
  if (!m || m.blob) return m;
  const have = await idbGet('media', m.id);
  return have && have.blob ? { ...m, blob: have.blob } : m;
}
export function mediaForBird(birdId) { return idbGetAll('media', 'birdId', birdId); }
/** Put a media record back after a delete (undo). Emits, so views refresh. */
export async function restoreMedia(m) {
  if (!m) return null;
  await atomicWrite(['media'], async (w) => {             // RF-27
    await w.put('media', m);
    await w.log({ origin: 'restore', store: 'media', op: 'put', recordId: m.id, record: m });
    await w.untomb('media', m.id);
  });
  emitChange({ type: 'media', id: m.id, birdId: m.birdId });
  return m;
}

export async function deleteMedia(id) {
  const m = await idbGet('media', id);
  await atomicWrite(['media'], async (w) => {             // RF-27
    await w.del('media', id);
    const seq = await w.log({ origin: 'user', store: 'media', op: 'delete', recordId: id, record: m });
    await w.tomb('media', id, seq);
  });
  emitChange({ type: 'media', id, birdId: m && m.birdId });
  return m;
}


// ─────────────────────── applying a pulled record ───────────────────────
// A remote record is written HERE, through the boundary, so the in-memory
// mirror stays in step and views are told (SYNC-DESIGN §3). It is never a raw
// idbPut from the pull loop.
//
// Three things differ from a local write, all deliberate:
//
//   1. NO OP IS LOGGED. Echo prevention, and the single most load-bearing line
//      in the design: a pulled change that logged an op would be pushed
//      straight back, and two devices would trade the same record forever.
//   2. NO stamp(). stamp() writes `updatedAt = now` and THIS device's id onto
//      whatever it touches. A pulled record put through it would become
//      locally-authored with a fresh timestamp, beat the very version it came
//      from in every later comparison, and claim this device as its last
//      writer when another device wrote it. LWW corrupted, audit trail
//      falsified. It follows restoreBird's precedent, not saveBird's: applying
//      a remote record is not authorship.
//   3. VALIDATION DIAGNOSES BUT DOES NOT BLOCK. A record already on the server
//      is a historical fact, not a new edit to re-judge — the reasoning that
//      made importAll a force path in v1.7. One that fails local rules is
//      applied AND reported, never silently dropped: dropping it would make
//      the mirror diverge from the server invisibly, which is worse than
//      holding a record the local rules dislike.

/** Stores with an in-memory mirror. `media` has none — it holds blobs. */
const SYNC_MIRROR = {
  birds: 'birds', pairs: 'pairs', raceResults: 'raceResults',
  healthEvents: 'healthEvents', lofts: 'lofts',
};

/** Every store a pulled row may name. Anything else is refused rather than guessed. */
export const SYNC_STORES = [...Object.keys(SYNC_MIRROR), 'media'];

// ── RF-26 (RULED 2026-11-18): THE COMPARISON AND THE WRITE ARE ONE TRANSACTION ──
// A pull page used to decide last-write-wins against the operations that were pending WHEN THE PAGE STARTED, and
// then write each row without looking at the device. A save made after the page started was therefore invisible:
// an older row — typically this device's own echo — was written over it, and the next local save of that record
// read the reverted version and pushed it as the newest. Every device then converged on the wrong record.
//
// Now, for each row, ONE IndexedDB transaction over the record's store, the op log and the tombstones:
//   1. reads the operations for this record that are not yet pushed — the page's index plus every op logged since;
//   2. reads the record on the device;
//   3. decides; and only then supersedes the losing ops and writes.
// A local write is either committed before this transaction (and is seen) or queued behind it (and lands on top).

/**
 * Does the incoming row beat the local unpushed op?
 *
 * Tie-break is lexicographic on deviceId — arbitrary, but STABLE, which is the
 * only property that matters. A tie means the same millisecond on two devices,
 * and both must reach the same verdict without talking to each other.
 */
export function remoteWins(row, local) {
  if (!local) return true;
  const remoteAt = String(row.updated_at || '');
  const localAt = String(local.at || '');
  if (remoteAt !== localAt) return remoteAt > localAt;
  return String(row.device_id || '') > String(local.deviceId || '');
}

/**
 * Is the record on this device a LOCAL write newer than the incoming row?
 *
 * This covers the one moment the op log cannot: a local save writes its record first and logs its op after, so for
 * a few milliseconds the newer record is on the device with no op to speak for it. Only a record this device
 * stamped counts (`deviceId`), and only when its stamp is strictly after the row's operation time. A record that
 * arrived by pull carries its author's device id and never blocks a later row; a restored record carries its
 * original, older stamp (restoreBird) and never blocks one either.
 */
function locallyNewer(have, at) {
  const me = state.settings.deviceId;
  return !!(have && me && have.deviceId === me && String(have.updatedAt || '') > String(at || ''));
}

/**
 * The shared decision. Runs INSIDE the transaction. Returns `{ skip }` or `{ lost, have, tomb }` to go on and write.
 * `ctx.pending` is the page's index entry for this record and `ctx.seen` the op ids that index was built from; a
 * caller with neither (a direct call) has every unpushed op read here instead.
 */
async function decide(h, store, id, at, ctx) {
  const local = ctx.pending ? { at: ctx.pending.at, deviceId: ctx.pending.deviceId, opIds: [...ctx.pending.opIds] } : null;
  let mine = local;
  const acked = state.settings.lastAckedSeq || 0;
  for (const opId of await h.opIdsAbove(acked)) {
    if (ctx.seen && ctx.seen.has(opId)) continue;               // already weighed when the page's index was built
    const op = await h.get('oplog', opId);
    if (!op || op.superseded || op.store !== store || op.recordId !== id) continue;
    if (!mine) mine = { at: op.at, deviceId: op.deviceId || '', opIds: [op.opId] };
    else { mine.opIds.push(op.opId); if (op.at > mine.at) { mine.at = op.at; mine.deviceId = op.deviceId || ''; } }
  }
  if (mine && !remoteWins({ updated_at: at, device_id: ctx.deviceId }, mine)) return { skip: 'local-op' };
  const have = (await h.get(store, id)) || null;
  if (locallyNewer(have, at)) return { skip: 'local-record' };

  // The row wins. Any local op it beat is SUPERSEDED — otherwise push would send the loser straight afterwards
  // and overwrite the version that just won. They are not deleted (§4): only their right to be pushed goes.
  let lost = 0;
  for (const opId of (mine ? mine.opIds : [])) {
    const op = await h.get('oplog', opId);
    if (!op || op.superseded) continue;
    await h.put('oplog', { ...op, superseded: true });
    lost++;
  }
  const tomb = (await h.get('tombstones', tombstoneKey(store, id))) || null;
  return { skip: null, lost, have, tomb };
}

/**
 * Write a pulled record VERBATIM.
 *
 * @param ctx  from the pull page: `{ deviceId, pending, seen }`. Optional.
 * @returns {{applied: boolean, skipped: string|null, anomaly: object|null, superseded: number}}
 *   `skipped: 'tombstone'` when a newer local deletion wins (§3, the v1.8
 *   merge-import rule reused unchanged rather than re-derived);
 *   `'local-op'` when an unpushed local operation is newer; `'local-record'`
 *   when a local save newer than the row is on the device and its op is not logged yet.
 */
export async function applySyncPut(store, record, at, recordId, ctx = {}) {
  if (!SYNC_STORES.includes(store)) {
    return { applied: false, skipped: 'unknown-store', anomaly: { reason: 'unknown-store', store }, superseded: 0 };
  }
  if (!record || typeof record.id !== 'string' || !record.id) {
    return { applied: false, skipped: 'no-id', anomaly: { reason: 'no-id', store }, superseded: 0 };
  }

  // ── THE SERVER'S IDENTITY WINS ──
  // `record_id` is the row's primary key: it is what the cursor, the upsert and
  // the DELETE all key on. Keying the local write on the body's `id` instead
  // means a row whose body disagrees lands under an identity the server does
  // not know — and is then unreachable by every future sync, including its own
  // deletion, which arrives keyed on `record_id`. The device holds it forever
  // while every layer reports success.
  //
  // Found by the first real user, whose loft kept a record no amount of syncing
  // could remove. Reconcile to the server's identity and REPORT, per §3: a
  // remote record is applied and reported, never silently dropped.
  const id = recordId || record.id;
  let body = record;
  let anomaly = null;
  if (recordId && record.id !== recordId) {
    body = { ...record, id: recordId };
    anomaly = { reason: 'id-mismatch', store, recordId, bodyId: record.id };
  }

  // Diagnose without force so the real verdict is available, then apply anyway.
  // Before the transaction: it reads the in-memory flock, and nothing but the transaction's own requests may be
  // awaited inside it.
  let invalid = null;
  if (store === 'birds') {
    const verdict = classifySave(body, getBird, allBirds(), {});
    if (!verdict.ok) {
      invalid = {
        reason: 'validation',
        store,
        recordId: id,
        errors: (verdict.errors || []).map((e) => e.key),
        warnings: (verdict.warnings || []).map((w) => w.key),
      };
    }
  }

  const done = await idbAtomic([store, 'oplog', 'tombstones'], async (h) => {
    const d = await decide(h, store, id, at, ctx);
    if (d.skip) return { skipped: d.skip, lost: 0 };
    // A deletion newer than this version of the record wins, and the record stays
    // gone. Identical to what importAll does with a merge payload — reusing the
    // rule rather than writing a second, subtly different one.
    if (d.tomb && (d.tomb.at || '') > (at || '')) return { skipped: 'tombstone', lost: d.lost };
    // RF-23 (RULED 2026-11-16): a pulled media row is metadata only (§7) — and it used to replace the stored record
    // whole, so the first cycle after a photo was taken removed its bytes from the device that took it.
    // withHeldBytes(), with the record this transaction has already read.
    let written = body;
    if (store === 'media' && !body.blob && d.have && d.have.blob) written = { ...body, blob: d.have.blob };
    await h.put(store, written);
    // THE COROLLARY (§2a): a winning record clears the tombstone. Leaving it
    // would let the record be re-suppressed by the next merge-import or
    // comparison, and the device would flip between states. restoreBird already
    // does this on undo; this is the same rule reached from the other direction.
    if (d.tomb) await h.del('tombstones', d.tomb.id);
    return { skipped: null, lost: d.lost, written };
  });

  if (done.skipped) {
    return { applied: false, skipped: done.skipped, anomaly: done.skipped === 'tombstone' ? anomaly : null, superseded: done.lost };
  }
  if (invalid) anomaly = anomaly ? { ...anomaly, alsoInvalid: invalid } : invalid;
  // The mirror follows the store, in the same order: every local writer puts to the store first and sets the mirror
  // after, so a local write queued behind this transaction also sets the mirror after this line has run.
  const mirror = SYNC_MIRROR[store];
  if (mirror) state[mirror].set(id, done.written);

  emitChange({ type: 'sync', store, id });
  return { applied: true, skipped: null, anomaly, superseded: done.lost };
}

/**
 * Apply a pulled deletion: remove the record and write a tombstone.
 *
 * DELIBERATELY DOES NOT CASCADE, and this is not an oversight. deleteBird
 * cascades because a local delete must leave the database referentially
 * consistent. A pulled delete must not: the origin device already ran its own
 * cascade, and every record it touched produced its own op and arrives as its
 * own row, in server_seq order. Re-cascading here would delete records the
 * origin device never deleted — anything linked LOCALLY but not remotely —
 * which is data loss dressed up as consistency.
 */
export async function applySyncDelete(store, recordId, at, ctx = {}) {
  if (!SYNC_STORES.includes(store)) {
    return { applied: false, skipped: 'unknown-store', anomaly: { reason: 'unknown-store', store }, superseded: 0 };
  }
  const done = await idbAtomic([store, 'oplog', 'tombstones'], async (h) => {
    const d = await decide(h, store, recordId, at, ctx);
    if (d.skip) return { skipped: d.skip, lost: 0 };
    await h.del(store, recordId);
    // seq is null: there is no local op behind this deletion. `at` is the remote
    // operation time, so the tombstone claims the moment the delete happened.
    await h.put('tombstones', tombstoneRecord(store, recordId, null, at));
    return { skipped: null, lost: d.lost };
  });
  if (done.skipped) return { applied: false, skipped: done.skipped, anomaly: null, superseded: 0 };
  const mirror = SYNC_MIRROR[store];
  if (mirror) state[mirror].delete(recordId);
  if (store === 'lofts') await ensureCurrentLoft();   // RF-14: a loft removed on another device may be this one's current loft
  emitChange({ type: 'sync', store, id: recordId });
  return { applied: true, skipped: null, anomaly: null, superseded: done.lost };
}

// ───────────────────── the pristine default loft (R4) ─────────────────────

/**
 * Is this loft untouched — created by `initDB()` and never used?
 *
 * "Pristine" means unnamed, unplaced, AND referenced by no record on this
 * device. The reference check is the load-bearing half: a loft the fancier has
 * actually filed birds under is theirs even if they never got round to naming
 * it, and dropping it would take the birds' `loftId` with it.
 */
export function isPristineLoft(loft) {
  if (!loft) return false;
  if ((loft.name || '').trim() || (loft.location || '').trim()) return false;
  for (const mirror of ['birds', 'pairs', 'raceResults', 'healthEvents']) {
    for (const record of state[mirror].values()) {
      if (record.loftId === loft.id) return false;
    }
  }
  return true;
}

/**
 * Remove a pristine default loft when a real one has been adopted in its place.
 *
 * NO OP AND NO TOMBSTONE, deliberately, and this is the third exception in the
 * op-enumeration matrix (§8). The other two are about pulled records; this one
 * is different in kind: **the record never existed anywhere but this device.**
 * It was never pushed — `enqueueFirstSyncOps` skips pristine lofts — so there
 * is no server row for an op to describe and nothing for a tombstone to
 * suppress. Logging either would be inventing history: a deletion that no other
 * device can meaningfully receive, for a record none of them ever saw.
 *
 * Guarded by isPristineLoft() rather than trusting the caller, because a
 * silent no-op-no-tombstone delete is exactly the primitive that must never be
 * reachable for a record that HAS travelled.
 */
export async function dropPristineLoft(loftId) {
  const loft = state.lofts.get(loftId);
  if (!isPristineLoft(loft)) return false;
  await idbDelete('lofts', loftId);
  state.lofts.delete(loftId);
  emitChange({ type: 'loft', id: loftId });
  return true;
}
