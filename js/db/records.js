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
  REFERENCE_STATUS, allBirds, emitChange, getBird, idbDelete, idbGet, idbGetAll, idbPut, nowISO, stamp, state, uuid,
} from './storage.js';
import { clearTombstone, diffFields, getTombstone, logOp, writeTombstone } from './oplog.js';

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
export async function deleteBird(id) {
  const bird = state.birds.get(id);
  const media = await idbGetAll('media', 'birdId', id);
  const affectedOriginals = [];   // offspring whose parent link is cleared
  const removedRaces = [];
  const removedHealth = [];
  const removedPairs = [];
  const affectedPairs = [];       // pairs that merely referenced it from an egg

  for (const b of state.birds.values()) {
    if (b.sireId === id || b.damId === id) {
      affectedOriginals.push({ ...b });
      const copy = { ...b };
      if (copy.sireId === id) copy.sireId = null;
      if (copy.damId === id) copy.damId = null;
      stamp(copy);
      await idbPut('birds', copy);
      state.birds.set(copy.id, copy);
      await logOp({ origin: 'user', store: 'birds', op: 'put', recordId: copy.id,
                    record: copy, changed: diffFields(affectedOriginals[affectedOriginals.length - 1], copy) });
    }
  }
  for (const r of [...state.raceResults.values()]) {
    if (r.birdId === id) {
      removedRaces.push({ ...r });
      await idbDelete('raceResults', r.id); state.raceResults.delete(r.id);
      const seq = await logOp({ origin: 'user', store: 'raceResults', op: 'delete', recordId: r.id, record: r });
      await writeTombstone('raceResults', r.id, seq);
    }
  }
  for (const e of [...state.healthEvents.values()]) {
    if (e.birdId === id) {
      removedHealth.push({ ...e });
      await idbDelete('healthEvents', e.id); state.healthEvents.delete(e.id);
      const seq = await logOp({ origin: 'user', store: 'healthEvents', op: 'delete', recordId: e.id, record: e });
      await writeTombstone('healthEvents', e.id, seq);
    }
  }
  for (const p of [...state.pairs.values()]) {
    if (p.sireId === id || p.damId === id) {
      removedPairs.push(JSON.parse(JSON.stringify(p)));
      await idbDelete('pairs', p.id);
      state.pairs.delete(p.id);
      const seq = await logOp({ origin: 'user', store: 'pairs', op: 'delete', recordId: p.id, record: p });
      await writeTombstone('pairs', p.id, seq);
      continue;
    }
    const referencesBird = (p.rounds || []).some((r) =>
      (r.eggs || []).some((e) => e.chickId === id));
    if (referencesBird) {
      affectedPairs.push(JSON.parse(JSON.stringify(p)));   // snapshot BEFORE mutating
      for (const round of p.rounds || []) {
        for (const egg of round.eggs || []) {
          if (egg.chickId === id) { egg.chickId = null; egg.ringed = false; }
        }
      }
      stamp(p);
      await idbPut('pairs', p);
      await logOp({ origin: 'user', store: 'pairs', op: 'put', recordId: p.id,
                    record: p, changed: ['rounds'] });
    }
  }

  // A1: the cascade hard-deletes media rows directly rather than via
  // deleteMedia(), so each one is logged here.
  for (const m of media) {
    await idbDelete('media', m.id);
    const seq = await logOp({ origin: 'user', store: 'media', op: 'delete', recordId: m.id, record: m });
    await writeTombstone('media', m.id, seq);   // A1: the cascade deletes media directly
  }
  await idbDelete('birds', id);
  state.birds.delete(id);
  const birdSeq = await logOp({ origin: 'user', store: 'birds', op: 'delete', recordId: id, record: bird });
  await writeTombstone('birds', id, birdSeq);
  emitChange({ type: 'bird', id });
  return { bird, media, affectedOriginals, removedRaces, removedHealth, removedPairs, affectedPairs };
}

/** Undo a deleteBird: puts back the bird AND everything the cascade removed. */
export async function restoreBird(snapshot) {
  const { bird, media, affectedOriginals, removedRaces, removedHealth,
          removedPairs, affectedPairs } = snapshot || {};
  if (!bird) return;
  // an undo restores exactly what was there; it is not a new edit to re-judge
  await idbPut('birds', bird);
  state.birds.set(bird.id, bird);
  await logOp({ origin: 'restore', store: 'birds', op: 'put', recordId: bird.id, record: bird });
  await clearTombstone('birds', bird.id);
  for (const orig of affectedOriginals || []) {
    await idbPut('birds', orig);
    state.birds.set(orig.id, orig);
    await logOp({ origin: 'restore', store: 'birds', op: 'put', recordId: orig.id, record: orig });
    await clearTombstone('birds', orig.id);
  }
  for (const r of removedRaces || []) {
    await idbPut('raceResults', r); state.raceResults.set(r.id, r);
    await logOp({ origin: 'restore', store: 'raceResults', op: 'put', recordId: r.id, record: r });
    await clearTombstone('raceResults', r.id);
  }
  for (const e of removedHealth || []) {
    await idbPut('healthEvents', e); state.healthEvents.set(e.id, e);
    await logOp({ origin: 'restore', store: 'healthEvents', op: 'put', recordId: e.id, record: e });
    await clearTombstone('healthEvents', e.id);
  }
  for (const p of [...(removedPairs || []), ...(affectedPairs || [])]) {
    await idbPut('pairs', p);
    state.pairs.set(p.id, p);
    await logOp({ origin: 'restore', store: 'pairs', op: 'put', recordId: p.id, record: p });
    await clearTombstone('pairs', p.id);
  }
  for (const m of media || []) {
    await idbPut('media', m);
    await logOp({ origin: 'restore', store: 'media', op: 'put', recordId: m.id, record: m });
    await clearTombstone('media', m.id);
  }
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
      await idbDelete(storeName, id);
      state[stateMap].delete(id);
      const seq = await logOp({ origin: 'user', store: storeName, op: 'delete', recordId: id, record: rec });
      await writeTombstone(storeName, id, seq);
      emitChange({ type: typeName, id });
      return rec;
    },
    async restore(rec) {
      await idbPut(storeName, rec);
      state[stateMap].set(rec.id, rec);
      await logOp({ origin: 'restore', store: storeName, op: 'put', recordId: rec.id, record: rec });
      await clearTombstone(storeName, rec.id);
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
export function mediaForBird(birdId) { return idbGetAll('media', 'birdId', birdId); }
/** Put a media record back after a delete (undo). Emits, so views refresh. */
export async function restoreMedia(m) {
  if (!m) return null;
  await idbPut('media', m);
  await logOp({ origin: 'restore', store: 'media', op: 'put', recordId: m.id, record: m });
  await clearTombstone('media', m.id);
  emitChange({ type: 'media', id: m.id, birdId: m.birdId });
  return m;
}

export async function deleteMedia(id) {
  const m = await idbGet('media', id);
  await idbDelete('media', id);
  const seq = await logOp({ origin: 'user', store: 'media', op: 'delete', recordId: id, record: m });
  await writeTombstone('media', id, seq);
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

/**
 * Write a pulled record VERBATIM.
 *
 * @returns {{applied: boolean, skipped: string|null, anomaly: object|null}}
 *   `skipped: 'tombstone'` when a newer local deletion wins (§3, the v1.8
 *   merge-import rule reused unchanged rather than re-derived).
 */
export async function applySyncPut(store, record, at) {
  if (!SYNC_STORES.includes(store)) {
    return { applied: false, skipped: 'unknown-store', anomaly: { reason: 'unknown-store', store } };
  }
  if (!record || typeof record.id !== 'string' || !record.id) {
    return { applied: false, skipped: 'no-id', anomaly: { reason: 'no-id', store } };
  }

  // A deletion newer than this version of the record wins, and the record stays
  // gone. Identical to what importAll does with a merge payload — reusing the
  // rule rather than writing a second, subtly different one.
  const tomb = await getTombstone(store, record.id);
  if (tomb && (tomb.at || '') > (at || '')) {
    return { applied: false, skipped: 'tombstone', anomaly: null };
  }

  // Diagnose without force so the real verdict is available, then apply anyway.
  let anomaly = null;
  if (store === 'birds') {
    const verdict = classifySave(record, getBird, allBirds(), {});
    if (!verdict.ok) {
      anomaly = {
        reason: 'validation',
        store,
        recordId: record.id,
        errors: (verdict.errors || []).map((e) => e.key),
        warnings: (verdict.warnings || []).map((w) => w.key),
      };
    }
  }

  await idbPut(store, record);
  const mirror = SYNC_MIRROR[store];
  if (mirror) state[mirror].set(record.id, record);

  // THE COROLLARY (§2a): a winning record clears the tombstone. Leaving it
  // would let the record be re-suppressed by the next merge-import or
  // comparison, and the device would flip between states. restoreBird already
  // does this on undo; this is the same rule reached from the other direction.
  if (tomb) await clearTombstone(store, record.id);

  emitChange({ type: 'sync', store, id: record.id });
  return { applied: true, skipped: null, anomaly };
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
export async function applySyncDelete(store, recordId, at) {
  if (!SYNC_STORES.includes(store)) {
    return { applied: false, skipped: 'unknown-store', anomaly: { reason: 'unknown-store', store } };
  }
  await idbDelete(store, recordId);
  const mirror = SYNC_MIRROR[store];
  if (mirror) state[mirror].delete(recordId);
  // seq is null: there is no local op behind this deletion. `at` is the remote
  // operation time, so the tombstone claims the moment the delete happened.
  await writeTombstone(store, recordId, null, at);
  emitChange({ type: 'sync', store, id: recordId });
  return { applied: true, skipped: null, anomaly: null };
}
