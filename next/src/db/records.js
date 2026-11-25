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
 *
 * A PLACEHOLDER parent (RULED 2026-11-23, src/family.js) is always external: the flag never travels without it.
 */
export function newBird(partial = {}) {
  const external = partial.external === true || partial.status === REFERENCE_STATUS || partial.placeholder === true;
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
  return classifySave(bird, getBird, allBirds(), { ...opts, pairs: state.pairs.values() });
}

/**
 * The same pre-flight for SEVERAL birds that will be written together (saveBirds): each is judged against the flock
 * AS IT WILL BE once all of them are written, so a parent made in the same save is seen by the child that names it.
 * Returns one verdict per bird, in order.
 */
export function checkBirds(birds, opts = {}) {
  const view = together(birds);
  return birds.map((bird) => classifySave(bird, view.get, view.all, { ...opts, pairs: state.pairs.values() }));
}
function together(birds) {
  const next = new Map(birds.map((b) => [b.id, b]));
  return { get: (id) => next.get(id) || getBird(id), all: [...allBirds().filter((b) => !next.has(b.id)), ...next.values()] };
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
  const verdict = classifySave(bird, getBird, allBirds(), { allowWarnings, force, pairs: state.pairs.values() });
  if (!verdict.ok) throw new ValidationError(verdict.errors, verdict.warnings);
  const previous = state.birds.get(bird.id) || null;
  // B4 (RULED 2026-11-24): a save that changes or clears a parent may leave a placeholder parent with no child. It goes
  // in THIS save's transaction (placeholdersLeft, below). A save that drops no placeholder is written as it always was.
  const dropped = parentsDropped([bird]);
  if (dropped.length) {
    const left = await placeholdersLeft(dropped, new Set(), new Map([[bird.id, bird]]));
    if (left.going.length || left.freed.length) {
      await writeBirds([bird], left);
      emitChange({ type: 'bird', id: bird.id });
      return bird;
    }
  }
  stamp(bird);
  await idbPut('birds', bird);
  state.birds.set(bird.id, bird);
  await logOp({ origin: 'user', store: 'birds', op: 'put', recordId: bird.id,
                record: bird, changed: diffFields(previous, bird) });
  emitChange({ type: 'bird', id: bird.id });
  return bird;
}

/**
 * SEVERAL BIRDS, ONE TRANSACTION (RULED 2026-11-23, the sibling link). Recording a bird as the sibling of another
 * writes up to four records — the bird, the other bird, and a placeholder for each parent neither of them has. Written
 * one after another, a failure or a closed tab in between left a bird naming a parent that was never stored, or one
 * sibling linked and the other not. Here every record, and its operation, is written together or not at all.
 *
 * Each entry is `{ bird, allowWarnings }`. All are validated FIRST, against the flock as it will be (checkBirds), and
 * one that fails stops the whole save before anything is written. Strict by default, as saveBird.
 * @throws {ValidationError}
 */
export async function saveBirds(entries) {
  const view = together(entries.map((e) => e.bird));
  for (const { bird, allowWarnings = false } of entries) {
    const verdict = classifySave(bird, view.get, view.all, { allowWarnings, pairs: state.pairs.values() });
    if (!verdict.ok) throw new ValidationError(verdict.errors, verdict.warnings);
  }
  // B4 (RULED 2026-11-24): a placeholder parent this save leaves with no child goes in the same transaction
  const birds = entries.map((e) => e.bird);
  const dropped = parentsDropped(birds);
  const left = dropped.length ? await placeholdersLeft(dropped, new Set(), new Map(birds.map((b) => [b.id, b]))) : NONE_LEFT;
  await writeBirds(birds, left);
  for (const { bird } of entries) emitChange({ type: 'bird', id: bird.id });
  return entries.map((e) => e.bird);
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
    // `rec` is the record being deleted; it is kept in the tombstone only when it is a placeholder parent (C1, keptOf)
    tomb: (store, id, seq, rec) => h.put('tombstones', tombstoneRecord(store, id, seq, undefined, keptOf(store, rec))),
    untomb: (store, id) => h.del('tombstones', tombstoneKey(store, id)),
    then: (f) => { after.push(f); },
    // PHOTO SYNC, STAGE 2 (RULED 2026-11-19): a deleted media record that was marked stored has an object on the
    // server. Its id is queued HERE, in the transaction that deletes it, for the photo pass to remove (photos.js).
    // Device-local (`photoRemovals`), never synced: only the device that made the deletion removes the object.
    unstore: async (media) => {
      const add = (media || []).filter((m) => m && m.stored).map((m) => ({ id: m.id, at: nowISO() }));
      if (!add.length) return;
      const have = Array.isArray(state.settings.photoRemovals) ? state.settings.photoRemovals : [];
      state.settings.photoRemovals = [...have.filter((q) => !add.some((x) => x.id === q.id)), ...add];
      await h.put('settings', { key: 'photoRemovals', value: state.settings.photoRemovals });
    },
  }));
  for (const f of after) f();
  return out;
}

// ── PLACEHOLDER PARENTS LEFT WITH NO CHILD (RULED 2026-11-23, item 6; RULED 2026-11-24, B4 and B5) ──
// A placeholder parent is the record the app made for a parent nobody knows (src/family.js). Nothing lists one and no
// picker offers one, so one that no bird names any more can be neither reached nor removed. It therefore goes WITH THE
// WRITE THAT LEAVES IT CHILDLESS — the deletion of its last child (deleteBird), or a save that changes or clears that
// child's parent (saveBird, saveBirds; B4) — in that write's own transaction, with its own operation and tombstone.
// So does a placeholder parent of ITS that is left childless in turn.
//
// B5: ONE THAT HOLDS ANYTHING OF ITS OWN IS NEVER DELETED THIS WAY. A photo or a document, a result, a health event, a
// pair, a note, a colour — any field that is not what it was made with — is something the fancier recorded, and it is
// not this write's to remove. Its flag is cleared instead, in the same transaction: it stays, as a reference bird the
// register lists, and whatever it holds stays with it.

/** What newBird() gives a placeholder for the fields that are not empty when it is made. */
const PLACEHOLDER_MADE_WITH = Object.freeze({ status: REFERENCE_STATUS, external: true, placeholder: true });
// Not compared. Who it stands for and where and when it was made are not something it holds: `name` and `sex` are the
// role it was made for (the record does not keep what they were, and a rename through the form already clears the
// flag); the parent links are followed below instead.
const PLACEHOLDER_NOT_COMPARED = new Set(['id', 'name', 'sex', 'sireId', 'damId', 'loftId', 'createdAt', 'updatedAt', 'deviceId', 'provenance']);
const isEmpty = (v) => v == null || v === '' || v === false || (Array.isArray(v) && v.length === 0);

/** B5: does this placeholder hold anything of its own? Reads the media store, so it is asked BEFORE the transaction. */
async function holdsOwn(p) {
  for (const key of Object.keys(p)) {
    if (PLACEHOLDER_NOT_COMPARED.has(key)) continue;
    // G2 (RULED 2026-11-25): `mainPhotoId` names a photo; it is held only while that photo is stored for this record.
    // A build without the field (4acbf2a) deletes a photo and leaves the field naming it — a photo no longer stored
    // is not something the placeholder holds. One that is stored is held through the media check below as well.
    if (key === 'mainPhotoId') { const m = p[key] ? await idbGet('media', p[key]) : null; if (m && m.birdId === p.id) return true; continue; }
    if (key in PLACEHOLDER_MADE_WITH ? p[key] !== PLACEHOLDER_MADE_WITH[key] : !isEmpty(p[key])) return true;
  }
  // a parent the fancier named for it is something it holds; a parent that is itself a placeholder is not — that one
  // is followed, and goes or stays by this same rule
  for (const pid of [p.sireId, p.damId]) {
    if (pid && !(state.birds.get(pid) && state.birds.get(pid).placeholder === true)) return true;
  }
  for (const r of state.raceResults.values()) if (r.birdId === p.id) return true;
  for (const e of state.healthEvents.values()) if (e.birdId === p.id) return true;
  for (const pair of state.pairs.values()) {
    if (pair.sireId === p.id || pair.damId === p.id) return true;
    for (const round of pair.rounds || []) for (const egg of round.eggs || []) if (egg.chickId === p.id) return true;
  }
  return (await idbGetAll('media', 'birdId', p.id)).length > 0;
}

const NONE_LEFT = Object.freeze({ going: Object.freeze([]), freed: Object.freeze([]) });

/** B4: the placeholder parents these birds named as stored and, as they are about to be saved, name no longer. */
function parentsDropped(birds) {
  const out = [];
  for (const bird of birds) {
    const was = state.birds.get(bird.id);
    if (!was) continue;
    for (const pid of [was.sireId, was.damId]) {
      if (!pid || pid === bird.sireId || pid === bird.damId) continue;
      const parent = state.birds.get(pid);
      if (parent && parent.placeholder === true) out.push(pid);
    }
  }
  return out;
}

/**
 * Which placeholder parents does a write leave with no child?
 *
 * @param candidates  the parent ids the write stops naming
 * @param gone        ids the write deletes — every placeholder that goes is ADDED to it
 * @param next        id → the record as the write leaves it (a save); empty for a deletion
 * @returns {{ going: object[], freed: object[] }} `going` are deleted, in order; `freed` hold something of their own
 *          (B5) and lose the flag instead. Each is the record as stored now.
 */
async function placeholdersLeft(candidates, gone, next) {
  const going = [], freed = [], settled = new Set();
  const named = (pid) => {
    for (const c of state.birds.values()) {
      if (gone.has(c.id)) continue;
      const now = next.get(c.id) || c;
      if (now.sireId === pid || now.damId === pid) return true;
    }
    for (const c of next.values()) if (!state.birds.has(c.id) && (c.sireId === pid || c.damId === pid)) return true;
    return false;
  };
  const queue = [...candidates];
  while (queue.length) {
    const pid = queue.shift();
    const parent = pid ? state.birds.get(pid) : null;
    if (!parent || parent.placeholder !== true || gone.has(pid) || settled.has(pid) || next.has(pid)) continue;
    if (named(pid)) continue;                        // it still has a child: asked again if that child goes too
    settled.add(pid);
    if (await holdsOwn(parent)) { freed.push(parent); continue; }
    gone.add(pid); going.push(parent);
    queue.push(parent.sireId, parent.damId);         // its own placeholder parents, left childless in turn
  }
  return { going, freed };
}

// ── C1 (RULED 2026-11-24): NO BIRD MAY BE LEFT NAMING A PLACEHOLDER THAT NO DEVICE HOLDS ──
// Sync is per record. One device deletes a placeholder parent that has no child left THERE (item 6, B4) while another,
// offline, has given it a second child: after both sync, that child named a father no device held (measured
// 2026-11-24). So a placeholder that is deleted is KEPT IN ITS TOMBSTONE — the record itself, as this device held it —
// and after every pull the device looks for a bird that names an id it holds no record for. Where the tombstone of
// that id keeps a placeholder, the placeholder is put back: the same record, the same id, the flag set, with an
// operation of its own so that it is pushed and every device gets it back.
//
// HOW THE CODE KNOWS THE DELETED RECORD WAS A PLACEHOLDER: only a record carrying `placeholder: true` is ever kept
// (keptOf), and it is read from the record itself at the moment it is deleted — by this device's own deletion
// (atomicWrite's tomb) or by a pulled one (applySyncDelete, from the copy this device held). The tombstone of an
// ordinary bird keeps nothing, so a fancier's deliberate deletion of a bird is never undone by this.
// NOTHING IS GUESSED: a tombstone that keeps no record — an ordinary bird's, or one written before this rule — is
// left alone, and the bird that names it stays as it is, as before. The placeholder is then put back by the device
// that does hold it, when the deletion reaches it.

/** The record a tombstone keeps: the record itself when it is a placeholder parent, nothing otherwise. */
const keptOf = (store, rec) => (store === 'birds' && rec && rec.placeholder === true ? rec : null);

/**
 * Put back every placeholder parent that a bird on this device names and this device has deleted. Called after a
 * pull, before the push of the same cycle (sync.js syncOnce), so the record travels at once. Follows the chain: a
 * placeholder put back may itself name a placeholder parent that went with it.
 *
 * The record is put back VERBATIM — as restoreBird puts a record back — so two devices that both put it back hold the
 * same record; the operation is what carries the time. A pulled copy of the same record then applies without logging
 * anything, which is why this cannot go back and forth between devices.
 *
 * @returns {Promise<number>} how many were put back
 */
export async function keepNamedPlaceholders() {
  let restored = 0;
  for (;;) {
    const wanted = new Set();
    for (const b of state.birds.values()) {
      for (const pid of [b.sireId, b.damId]) if (pid && !state.birds.has(pid)) wanted.add(pid);
    }
    const back = [];
    for (const pid of wanted) {
      const tomb = await idbGet('tombstones', tombstoneKey('birds', pid));
      const rec = tomb && tomb.kept;
      if (rec && rec.id === pid && rec.placeholder === true) back.push(rec);
    }
    if (!back.length) break;
    await atomicWrite(['birds'], async (w) => {
      for (const rec of back) {
        await w.put('birds', rec);
        w.then(() => state.birds.set(rec.id, rec));
        await w.log({ origin: 'restore', store: 'birds', op: 'put', recordId: rec.id, record: rec });
        await w.untomb('birds', rec.id);
      }
    });
    restored += back.length;
  }
  if (restored) emitChange({ type: 'sync', store: 'birds' });
  return restored;
}

/** Inside a transaction: delete the placeholders that go, each with its operation and tombstone; clear the flag of those that stay (B5). */
async function settlePlaceholders(w, left) {
  for (const p of left.going) {
    await w.del('birds', p.id);
    w.then(() => state.birds.delete(p.id));
    const seq = await w.log({ origin: 'user', store: 'birds', op: 'delete', recordId: p.id, record: p });
    await w.tomb('birds', p.id, seq, p);
  }
  for (const p of left.freed) {
    const kept = { ...p };
    delete kept.placeholder;                         // removed, not set to false: missing means false
    stamp(kept);
    await w.put('birds', kept);
    w.then(() => state.birds.set(kept.id, kept));
    await w.log({ origin: 'user', store: 'birds', op: 'put', recordId: kept.id, record: kept, changed: diffFields(p, kept) });
  }
}

/** Birds, and the placeholder parents their save leaves childless, written with their operations in ONE transaction. */
async function writeBirds(birds, left = NONE_LEFT) {
  await atomicWrite(['birds'], async (w) => {
    for (const bird of birds) {
      const previous = state.birds.get(bird.id) || null;
      stamp(bird);
      await w.put('birds', bird);
      w.then(() => state.birds.set(bird.id, bird));
      await w.log({ origin: 'user', store: 'birds', op: 'put', recordId: bird.id,
                    record: bird, changed: diffFields(previous, bird) });
    }
    await settlePlaceholders(w, left);
  });
}

export async function deleteBird(id) {
  const bird = state.birds.get(id);
  // RULED 2026-11-23: A PLACEHOLDER PARENT LEFT WITH NO OTHER CHILD GOES WITH THE BIRD — in this same transaction, with
  // its own operation and tombstone (placeholdersLeft, above). `going` is the bird and then each such parent, a
  // placeholder's own placeholder parents included; everything below treats the set as one deletion, and the snapshot
  // carries them for the undo. B5 (RULED 2026-11-24): one that holds anything of its own is not in `going` — it is in
  // `left.freed`, loses the flag in this transaction and stays; the snapshot carries it as it was, so the undo puts the
  // flag back.
  const gone = new Set([id]);
  const left = bird ? await placeholdersLeft([bird.sireId, bird.damId], gone, new Map()) : NONE_LEFT;
  const placeholders = left.going;
  const going = [id, ...placeholders.map((p) => p.id)];
  const media = [];
  for (const gid of going) media.push(...await idbGetAll('media', 'birdId', gid));
  const affectedOriginals = [];   // offspring whose parent link is cleared
  const removedRaces = [];
  const removedHealth = [];
  const removedPairs = [];
  const affectedPairs = [];       // pairs that merely referenced it from an egg

  await atomicWrite(['birds', 'pairs', 'raceResults', 'healthEvents', 'media'], async (w) => {   // the whole deletion
    for (const b of state.birds.values()) {
      if (gone.has(b.id)) continue;                  // going too: there is no link to clear on a record being deleted
      if (gone.has(b.sireId) || gone.has(b.damId)) {
        affectedOriginals.push({ ...b });
        const copy = { ...b };
        if (gone.has(copy.sireId)) copy.sireId = null;
        if (gone.has(copy.damId)) copy.damId = null;
        stamp(copy);
        await w.put('birds', copy);
        w.then(() => state.birds.set(copy.id, copy));
        await w.log({ origin: 'user', store: 'birds', op: 'put', recordId: copy.id,
                      record: copy, changed: diffFields(affectedOriginals[affectedOriginals.length - 1], copy) });
      }
    }
    for (const r of [...state.raceResults.values()]) {
      if (gone.has(r.birdId)) {
        removedRaces.push({ ...r });
        await w.del('raceResults', r.id); w.then(() => state.raceResults.delete(r.id));
        const seq = await w.log({ origin: 'user', store: 'raceResults', op: 'delete', recordId: r.id, record: r });
        await w.tomb('raceResults', r.id, seq);
      }
    }
    for (const e of [...state.healthEvents.values()]) {
      if (gone.has(e.birdId)) {
        removedHealth.push({ ...e });
        await w.del('healthEvents', e.id); w.then(() => state.healthEvents.delete(e.id));
        const seq = await w.log({ origin: 'user', store: 'healthEvents', op: 'delete', recordId: e.id, record: e });
        await w.tomb('healthEvents', e.id, seq);
      }
    }
    for (const p of [...state.pairs.values()]) {
      if (gone.has(p.sireId) || gone.has(p.damId)) {
        removedPairs.push(JSON.parse(JSON.stringify(p)));
        await w.del('pairs', p.id);
        w.then(() => state.pairs.delete(p.id));
        const seq = await w.log({ origin: 'user', store: 'pairs', op: 'delete', recordId: p.id, record: p });
        await w.tomb('pairs', p.id, seq);
        continue;
      }
      const referencesBird = (p.rounds || []).some((r) =>
        (r.eggs || []).some((e) => gone.has(e.chickId)));
      if (referencesBird) {
        affectedPairs.push(JSON.parse(JSON.stringify(p)));   // snapshot BEFORE changing
        const copy = JSON.parse(JSON.stringify(p));           // the mirror's own object is not touched before the commit
        for (const round of copy.rounds || []) {
          for (const egg of round.eggs || []) {
            if (gone.has(egg.chickId)) { egg.chickId = null; egg.ringed = false; }
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
    await w.unstore(media);
    await w.del('birds', id);                        // the bird…
    w.then(() => state.birds.delete(id));
    const birdSeq = await w.log({ origin: 'user', store: 'birds', op: 'delete', recordId: id, record: bird });
    await w.tomb('birds', id, birdSeq, bird);
    await settlePlaceholders(w, left);               // …then each placeholder parent that goes with it, or is freed (B5)
  });
  emitChange({ type: 'bird', id });
  return { bird, media, affectedOriginals, removedRaces, removedHealth, removedPairs, affectedPairs, placeholders, unflagged: left.freed };
}

/** Undo a deleteBird: puts back the bird AND everything the cascade removed. */
export async function restoreBird(snapshot) {
  const { bird, media, affectedOriginals, removedRaces, removedHealth,
          removedPairs, affectedPairs, placeholders, unflagged } = snapshot || {};
  if (!bird) return;
  // an undo restores exactly what was there; it is not a new edit to re-judge
  await atomicWrite(['birds', 'pairs', 'raceResults', 'healthEvents', 'media'], async (w) => {   // the whole undo
    const back = async (store, mirror, rec) => {
      await w.put(store, rec);
      if (mirror) w.then(() => state[mirror].set(rec.id, rec));
      await w.log({ origin: 'restore', store, op: 'put', recordId: rec.id, record: rec });
      await w.untomb(store, rec.id);
    };
    for (const ph of placeholders || []) await back('birds', 'birds', ph);   // the placeholder parents that went with it (2026-11-23), before the bird that names them
    for (const ph of unflagged || []) await back('birds', 'birds', ph);      // B5: the ones that stayed and lost the flag are put back as they were, flag and all
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

// ── THE MAIN PHOTO, AND THE ORDER OF A BIRD'S FILES (RULED 2026-11-24, E3–E5) ── PORT-ONLY
// A bird's files used to come back in the order of the store's key — a random id — so "the first photo" (the
// certificate's) was chance, and so was the order of the gallery and the strip (measured 2026-11-24). Now:
//   · `mainPhotoId` on the bird, OPTIONAL, names its main photo. Absent means not chosen.
//   · THE MAIN PHOTO is the photo that field names; when it names none this device holds a record for — never set, or
//     the photo is gone — it is the EARLIEST photo by `addedAt`. A document is never the main photo.
//   · THE ORDER, everywhere: the main photo first, then every file by `addedAt` ascending. Never by id — an id decides
//     only between two files stamped in the same millisecond on two devices, which nothing else can tell apart.
//   · Deleting the main photo clears the field in the transaction that deletes it; undoing that deletion puts both back.
const byAdded = (a, b) => (a.addedAt || '').localeCompare(b.addedAt || '') || String(a.id).localeCompare(String(b.id));
/** The main photo among one bird's files: the one `mainPhotoId` names, else the earliest photo, else null. */
export function mainPhotoOf(rows, mainPhotoId) {
  const photos = (rows || []).filter((m) => m && m.kind === 'photo');
  return photos.find((m) => m.id === mainPhotoId) || [...photos].sort(byAdded)[0] || null;
}
/** One bird's files in the order every screen shows them: the main photo first, then by `addedAt` ascending. */
export function orderMedia(rows, mainPhotoId) {
  const main = mainPhotoOf(rows, mainPhotoId);
  return [...(rows || [])].sort((a, b) => (main && a.id === main.id ? -1 : main && b.id === main.id ? 1 : 0) || byAdded(a, b));
}
// `addedAt` is what the order rests on, so no two files stored by this device carry the same one: files picked together
// are stored within the same millisecond often enough, and their order would then fall back to their ids.
let lastAddedAt = '';
function nextAddedAt() {
  let at = nowISO();
  if (at <= lastAddedAt) at = new Date(new Date(lastAddedAt).getTime() + 1).toISOString();
  lastAddedAt = at;
  return at;
}
/** Deleted main photos, media id → bird id, so that the undo of that deletion (restoreMedia) puts the field back. */
const clearedMain = new Map();

/**
 * @param {{ main?: boolean }} [opts] `main` (E5): the new photo becomes the bird's main photo, IN THE SAME TRANSACTION
 *   that stores it — the certificate's «تغيير». Ignored for a document, and for an owner that is not a bird (a loft's logo).
 */
export async function addMedia(birdId, kind, subtype, name, blob, opts = {}) {
  const m = { id: uuid(), birdId, kind, subtype, name, blob, addedAt: nextAddedAt() };
  const owner = opts.main === true && kind === 'photo' ? state.birds.get(birdId) : null;
  if (owner) {
    const next = stamp({ ...owner, mainPhotoId: m.id });
    await atomicWrite(['media', 'birds'], async (w) => {
      await w.put('media', m);
      await w.log({ origin: 'user', store: 'media', op: 'put', recordId: m.id, record: m,
                    changed: ['id', 'birdId', 'kind', 'subtype', 'name', 'addedAt'] });
      await w.put('birds', next);
      w.then(() => state.birds.set(next.id, next));
      await w.log({ origin: 'user', store: 'birds', op: 'put', recordId: next.id, record: next, changed: diffFields(owner, next) });
    });
    emitChange({ type: 'bird', id: next.id });
    emitChange({ type: 'media', id: m.id, birdId });
    return m;
  }
  await idbPut('media', m);
  // metadata only — a Blob never enters the op log
  await logOp({ origin: 'user', store: 'media', op: 'put', recordId: m.id, record: m,
                changed: ['id', 'birdId', 'kind', 'subtype', 'name', 'addedAt'] });
  emitChange({ type: 'media', id: m.id, birdId });
  return m;
}
/**
 * E3: make one of a bird's photos its main photo. Refused (false, nothing written) for a file that is not a photo, not
 * this bird's, or not held here. One transaction, one operation: the bird record with the field, as any other edit.
 */
export async function setMainPhoto(birdId, mediaId) {
  const bird = state.birds.get(birdId);
  const m = mediaId ? await idbGet('media', mediaId) : null;
  if (!bird || !m || m.birdId !== birdId || m.kind !== 'photo') return false;
  if (bird.mainPhotoId === mediaId) return true;
  const next = stamp({ ...bird, mainPhotoId: mediaId });
  await atomicWrite(['birds'], async (w) => {
    await w.put('birds', next);
    w.then(() => state.birds.set(next.id, next));
    await w.log({ origin: 'user', store: 'birds', op: 'put', recordId: next.id, record: next, changed: diffFields(bird, next) });
  });
  emitChange({ type: 'bird', id: birdId });
  return true;
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
/** One bird's files (or one loft's), in THE ORDER (E4): the main photo first, then by `addedAt` ascending. */
export async function mediaForBird(birdId) {
  // a screen asks for a bird's files as it mounts, which can be BEFORE the layer has filled its mirror (measured: the edit
  // form's strip came back without the main photo first on a fresh load) — so the record is read from the store then
  const owner = state.birds.get(birdId) || (birdId ? await idbGet('birds', birdId) : null);
  return orderMedia(await idbGetAll('media', 'birdId', birdId), owner ? owner.mainPhotoId : null);
}
/** Put a media record back after a delete (undo). Emits, so views refresh. */
export async function restoreMedia(m) {
  if (!m) return null;
  // E3: the undo of a main photo's deletion puts the field back with the photo — unless the bird has been given
  // another main photo since, which is the fancier's later word and stays
  const owner = clearedMain.get(m.id) === m.birdId ? state.birds.get(m.birdId) : null;
  const back = owner && !owner.mainPhotoId ? stamp({ ...owner, mainPhotoId: m.id }) : null;
  await atomicWrite(back ? ['media', 'birds'] : ['media'], async (w) => {             // RF-27
    await w.put('media', m);
    await w.log({ origin: 'restore', store: 'media', op: 'put', recordId: m.id, record: m });
    await w.untomb('media', m.id);
    if (back) {
      await w.put('birds', back);
      w.then(() => state.birds.set(back.id, back));
      await w.log({ origin: 'restore', store: 'birds', op: 'put', recordId: back.id, record: back, changed: diffFields(owner, back) });
    }
  });
  clearedMain.delete(m.id);
  if (back) emitChange({ type: 'bird', id: back.id });
  emitChange({ type: 'media', id: m.id, birdId: m.birdId });
  return m;
}

export async function deleteMedia(id) {
  const m = await idbGet('media', id);
  // E3: a bird whose main photo this is loses the field in the same transaction — removed, not emptied: absent means
  // not chosen, and the main photo is then the earliest one left (mainPhotoOf)
  const owner = m ? state.birds.get(m.birdId) : null;
  let cleared = null;
  if (owner && owner.mainPhotoId === id) { cleared = { ...owner }; delete cleared.mainPhotoId; stamp(cleared); }
  await atomicWrite(cleared ? ['media', 'birds'] : ['media'], async (w) => {             // RF-27
    await w.del('media', id);
    const seq = await w.log({ origin: 'user', store: 'media', op: 'delete', recordId: id, record: m });
    await w.tomb('media', id, seq);
    await w.unstore([m]);
    if (cleared) {
      await w.put('birds', cleared);
      w.then(() => state.birds.set(cleared.id, cleared));
      await w.log({ origin: 'user', store: 'birds', op: 'put', recordId: cleared.id, record: cleared, changed: diffFields(owner, cleared) });
    }
  });
  if (cleared) { clearedMain.set(id, cleared.id); emitChange({ type: 'bird', id: cleared.id }); }
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
    const verdict = classifySave(body, getBird, allBirds(), { pairs: state.pairs.values() });
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
    // C1: a placeholder parent this device held is kept in its tombstone, so it can be put back if a bird still names it
    // (keepNamedPlaceholders). One kept by an earlier deletion of the same id is not lost.
    await h.put('tombstones', tombstoneRecord(store, recordId, null, at, keptOf(store, d.have) || (d.tomb && d.tomb.kept) || null));
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
