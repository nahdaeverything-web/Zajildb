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
import { clearTombstone, diffFields, logOp, writeTombstone } from './oplog.js';

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

