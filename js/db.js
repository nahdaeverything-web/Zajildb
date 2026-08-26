// db.js — IndexedDB layer. IndexedDB is the source of truth; the app never
// blocks on the network. An in-memory Map of birds is kept in sync so the
// pure engine (which needs a synchronous getBird) stays fast with 1000+ birds.
//
// Sync-readiness (club mode hook): every record carries `loftId`, `updatedAt`
// (device clock, ISO) and `deviceId`. If sync is added later it must be
// per-field last-write-wins — never whole-record overwrite.
//
// CONFLICT ORDER COMES FROM THE OP LOG, NOT FROM `updatedAt`.
// This supersedes the earlier note that said updatedAt keys LWW. The reason is
// concrete: restoreBird deliberately reinstates a record's ORIGINAL timestamps
// (an undo restores what was there; it is not a new edit). So after any
// delete+undo the surviving record carries an old updatedAt, and any
// updatedAt-keyed resolution would let a stale remote copy win. Order comes
// instead from the op log's per-device monotonic `seq`, which only ever
// increases and is unaffected by restores.
//
// PROVENANCE. Records carry `provenance: [{ event, at, deviceId }]` — an
// append-only history of what happened to the record itself, as opposed to
// the op log which records what this device DID. newBird() seeds it with a
// 'created' event; promote-to-loft and ownership transfers will append later.
//
// ACCEPTED LIMITATION (v1.8): an op and the record it describes are written in
// SEPARATE transactions, so a crash between them can drop an op. This is
// tolerated deliberately: ops carry the full record, so server reconciliation
// is self-healing, and multi-store transactions would mean restructuring every
// write path. Revisit only if a real inconsistency is observed.
//
// OUT OF SYNC SCOPE (no ops, no tombstones): the `settings` store, which is
// per-device preference rather than loft data; and the `backups` store, whose
// snapshots are local safety nets. See setSetting() and autoBackup().

import { classifySave } from './engine/validate.js';

const DB_NAME = 'zajil';
const DB_VERSION = 2;

export const STORES = ['birds', 'pairs', 'raceResults', 'healthEvents', 'lofts', 'media', 'settings', 'backups', 'oplog', 'tombstones'];

let _db = null;

export function uuid() {
  return crypto.randomUUID ? crypto.randomUUID() :
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
}

export function nowISO() { return new Date().toISOString(); }

export function openDB() {
  if (_db) return Promise.resolve(_db);
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      // idempotent: an existing store is left exactly as it is, so upgrading a
      // v1 database only ADDS the new stores and touches no existing record
      const mk = (name, indexes = [], keyPath = null) => {
        if (db.objectStoreNames.contains(name)) return;
        const store = db.createObjectStore(name, {
          keyPath: keyPath || (name === 'settings' ? 'key' : 'id'),
        });
        for (const [idx, path] of indexes) store.createIndex(idx, path);
      };
      mk('birds', [['sireId', 'sireId'], ['damId', 'damId'], ['status', 'status'], ['loftId', 'loftId']]);
      mk('pairs', [['sireId', 'sireId'], ['damId', 'damId'], ['season', 'season'], ['loftId', 'loftId']]);
      mk('raceResults', [['birdId', 'birdId'], ['date', 'date'], ['loftId', 'loftId']]);
      mk('healthEvents', [['birdId', 'birdId'], ['date', 'date'], ['loftId', 'loftId']]);
      mk('lofts');
      mk('media', [['birdId', 'birdId']]);
      mk('settings');
      mk('backups');
      // v2 — sync shape. Both are device-local and additive.
      mk('oplog', [['seq', 'seq']], 'opId');
      mk('tombstones');
    };
    req.onsuccess = () => { _db = req.result; resolve(_db); };
    req.onerror = () => reject(req.error);
  });
}

function tx(store, mode, fn) {
  return openDB().then((db) => new Promise((resolve, reject) => {
    const t = db.transaction(store, mode);
    const s = t.objectStore(store);
    let result;
    try { result = fn(s); } catch (err) { reject(err); return; }
    t.oncomplete = () => resolve(result && result.result !== undefined ? result.result : result);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error || new Error('transaction aborted'));
  }));
}

export function idbGet(store, key) {
  return openDB().then((db) => new Promise((resolve, reject) => {
    const r = db.transaction(store).objectStore(store).get(key);
    r.onsuccess = () => resolve(r.result ?? null);
    r.onerror = () => reject(r.error);
  }));
}

export function idbGetAll(store, indexName, key) {
  return openDB().then((db) => new Promise((resolve, reject) => {
    const s = db.transaction(store).objectStore(store);
    const src = indexName ? s.index(indexName) : s;
    const r = key !== undefined ? src.getAll(key) : src.getAll();
    r.onsuccess = () => resolve(r.result || []);
    r.onerror = () => reject(r.error);
  }));
}

export function idbPut(store, value) { return tx(store, 'readwrite', (s) => s.put(value)); }
export function idbDelete(store, key) { return tx(store, 'readwrite', (s) => s.delete(key)); }
export function idbClear(store) { return tx(store, 'readwrite', (s) => s.clear()); }

// ------------------------------------------------------------- state & events

export const state = {
  birds: new Map(),      // id -> bird (no media blobs)
  pairs: new Map(),
  raceResults: new Map(),
  healthEvents: new Map(),
  lofts: new Map(),
  settings: {},
  currentLoftId: null,
  ready: false,
};

const listeners = new Set();
export function onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }
export function emitChange(what) { for (const fn of listeners) fn(what); }

export function getBird(id) { return state.birds.get(id) || null; }
export function allBirds() { return [...state.birds.values()]; }

const DEFAULT_STATUSES = ['breeder', 'race team', 'young bird', 'stock', 'sold', 'lost', 'dead'];
// A never-owned ancestor has no loft status — it exists only to carry pedigree.
// Kept out of DEFAULT_STATUSES so it can't be picked by accident for a real
// bird, and appended for existing lofts so their stored list never needs a
// destructive migration.
export const REFERENCE_STATUS = 'reference';

export async function initDB() {
  await openDB();
  const [birds, pairs, races, health, lofts, settingsRows] = await Promise.all([
    idbGetAll('birds'), idbGetAll('pairs'), idbGetAll('raceResults'),
    idbGetAll('healthEvents'), idbGetAll('lofts'), idbGetAll('settings'),
  ]);
  state.birds = new Map(birds.map((b) => [b.id, b]));
  state.pairs = new Map(pairs.map((p) => [p.id, p]));
  state.raceResults = new Map(races.map((r) => [r.id, r]));
  state.healthEvents = new Map(health.map((h) => [h.id, h]));
  state.lofts = new Map(lofts.map((l) => [l.id, l]));
  state.settings = Object.fromEntries(settingsRows.map((s) => [s.key, s.value]));

  // First run: create the default loft. Club mode later hangs off loftId.
  if (state.lofts.size === 0) {
    const loft = { id: uuid(), name: '', location: '', statuses: DEFAULT_STATUSES, createdAt: nowISO(), updatedAt: nowISO() };
    await idbPut('lofts', loft);
    state.lofts.set(loft.id, loft);
    await setSetting('currentLoftId', loft.id);
  }
  state.currentLoftId = state.settings.currentLoftId || [...state.lofts.keys()][0];

  // Device identity. Generated ONCE and never regenerated: it is what lets a
  // future sync layer attribute an op to the machine that made it, and what
  // makes the per-device `seq` monotonic sequence meaningful.
  if (!state.settings.deviceId) await setSetting('deviceId', uuid());
  if (state.settings.deviceName === undefined) await setSetting('deviceName', '');
  if (typeof state.settings.opSeq !== 'number') await setSetting('opSeq', 0);

  state.ready = true;
}

export function currentLoft() { return state.lofts.get(state.currentLoftId) || null; }
export function loftStatuses({ includeReference = false } = {}) {
  const l = currentLoft();
  const base = (l && Array.isArray(l.statuses) && l.statuses.length) ? l.statuses : DEFAULT_STATUSES;
  if (!includeReference) return base.filter((s) => s !== REFERENCE_STATUS);
  return base.includes(REFERENCE_STATUS) ? base : [...base, REFERENCE_STATUS];
}

/**
 * Per-device preference. Deliberately OUT of sync scope: no op, no tombstone.
 * Language, numerals, COI depth, the device's own identity — none of it is
 * loft data, and syncing it would fight the user across devices.
 */
export async function setSetting(key, value) {
  state.settings[key] = value;
  await idbPut('settings', { key, value });
}

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
async function logOp({ origin, store, op, recordId, record, changed }) {
  const seq = await nextSeq();          // persisted before the op counts as logged
  await idbPut('oplog', {
    opId: uuid(),
    seq,
    deviceId: state.settings.deviceId || null,
    actorId: null,                      // becomes real when authentication exists
    at: nowISO(),
    origin,                             // 'user' | 'import' | 'restore'
    store,
    op,                                 // 'put' | 'delete'
    recordId,
    changed: changed || [],
    record: opRecord(record),
  });
  return seq;                            // shared with the tombstone of the same deletion
}

export function listOps() { return idbGetAll('oplog'); }
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

async function writeTombstone(store, recordId, seq) {
  await idbPut('tombstones', {
    id: tombstoneId(store, recordId),
    store,
    recordId,
    at: nowISO(),
    deviceId: state.settings.deviceId || null,
    seq,
  });
}

/** An undone deletion never happened, so its tombstone must go. */
async function clearTombstone(store, recordId) {
  await idbDelete('tombstones', tombstoneId(store, recordId));
}

function stamp(record) {
  record.updatedAt = nowISO();
  if (!record.loftId) record.loftId = state.currentLoftId;
  return record;
}

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

// ------------------------------------------------------------- export/import

function blobToDataURL(blob) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);
  });
}

export async function dataURLToBlob(dataURL) {
  const res = await fetch(dataURL);
  return res.blob();
}

/** Full export: everything, media as data URLs. Round-trip tested. */
export async function exportAll({ includeMedia = true } = {}) {
  const mediaOut = [];
  if (includeMedia) {
    for (const m of await idbGetAll('media')) {
      mediaOut.push({ ...m, blob: undefined, dataURL: await blobToDataURL(m.blob) });
    }
  }
  return {
    format: 'zajil-export',
    version: 1,
    exportedAt: nowISO(),
    // Tombstones travel with an export so a deletion survives a round trip
    // through another device. The OP LOG deliberately does NOT: it is this
    // device's own history, not shared loft data, and leaking it into files
    // people exchange would expose per-device activity. Asserted in
    // tests/e2e/resurrection.py.
    tombstones: await idbGetAll('tombstones'),
    lofts: [...state.lofts.values()],
    birds: [...state.birds.values()],
    pairs: [...state.pairs.values()],
    raceResults: [...state.raceResults.values()],
    healthEvents: [...state.healthEvents.values()],
    media: mediaOut,
  };
}

/**
 * Import an export payload. mode 'merge' keeps newer records by updatedAt;
 * mode 'replace' wipes first. Returns counts.
 */
export async function importAll(payload, mode = 'merge') {
  if (!payload || payload.format !== 'zajil-export') throw new Error('bad-format');
  const counts = { birds: 0, pairs: 0, raceResults: 0, healthEvents: 0, lofts: 0, media: 0, skipped: 0 };

  // ── decode and validate EVERYTHING before touching the database ──
  // A replace-import used to clear all six stores and only then decode the
  // media blobs, so one malformed data URL — or a quota error part-way
  // through — destroyed the loft with nothing to put back. Decoding first
  // means a bad payload fails while the existing data is still intact.
  for (const key of ['lofts', 'birds', 'pairs', 'raceResults', 'healthEvents', 'media']) {
    if (payload[key] !== undefined && !Array.isArray(payload[key])) {
      throw new Error(`bad-format: ${key} is not a list`);
    }
  }
  for (const b of payload.birds || []) {
    if (!b || typeof b.id !== 'string' || !b.id) throw new Error('bad-format: a bird has no id');
  }
  const decodedMedia = [];
  for (const m of payload.media || []) {
    if (!m || typeof m.id !== 'string') throw new Error('bad-format: a media entry has no id');
    let blob;
    try {
      blob = await dataURLToBlob(m.dataURL);
    } catch (err) {
      throw new Error(`bad-media: ${m.name || m.id} could not be decoded`);
    }
    if (!blob || typeof blob.size !== 'number') throw new Error(`bad-media: ${m.name || m.id}`);
    decodedMedia.push({ id: m.id, birdId: m.birdId, kind: m.kind, subtype: m.subtype,
                        name: m.name, blob, addedAt: m.addedAt });
  }

  // ── deletion protection ──
  // A record whose deletion is NEWER than the record itself must not come
  // back. Without this, merging any older export silently resurrects every
  // bird deleted since. Tombstones from BOTH sides are considered, so the
  // protection works whether the delete happened here or on another device.
  // Replace mode deliberately ignores them: a replace is a restore of a point
  // in time, and the user has explicitly asked for that snapshot.
  const tombIndex = new Map();
  for (const t of await idbGetAll('tombstones')) tombIndex.set(t.id, t);
  for (const t of payload.tombstones || []) {
    const existing = tombIndex.get(t.id);
    // union by id, keep whichever deletion is newer
    if (!existing || (t.at || '') > (existing.at || '')) tombIndex.set(t.id, t);
  }
  const isDeleted = (storeName, rec) => {
    if (mode === 'replace') return false;
    const t = tombIndex.get(`${storeName}:${rec.id}`);
    return !!t && (t.at || '') > (rec.updatedAt || '');
  };

  // ── a rollback point, taken before anything is cleared ──
  if (mode === 'replace') {
    try {
      const snapshot = await exportAll({ includeMedia: false });
      snapshot.kind = 'auto-backup';
      await idbPut('backups', { id: `pre-import-${nowISO()}`, payload: snapshot });
    } catch { /* a snapshot is a safety net, not a reason to block the import */ }
  }
  // Automatic snapshots deliberately carry no media (blobs would make them
  // huge), so wiping the media store on restore would destroy every photo and
  // scanned pedigree the payload cannot put back. Keep media in that case.
  const carriesMedia = payload.kind !== 'auto-backup';
  if (mode === 'replace') {
    // ONLY the data stores are cleared. oplog, tombstones, settings and
    // backups are never touched: the op log is this device's own history,
    // settings are per-device preference, and backups are the local safety
    // net that a bad import is supposed to fall back on.
    //
    // A2 — a replace-import RESETS THE SYNC BASELINE. The data is wholesale
    // replaced while the op log keeps describing the records that were here
    // before, so a future sync layer must treat a replace as a new starting
    // point rather than replaying history across it. That reconciliation is a
    // v1.9 concern; nothing here depends on it yet.
    const stores = ['birds', 'pairs', 'raceResults', 'healthEvents', 'lofts'];
    if (carriesMedia) stores.push('media');
    for (const s of stores) await idbClear(s);
    state.birds.clear(); state.pairs.clear(); state.raceResults.clear();
    state.healthEvents.clear(); state.lofts.clear();
  }
  const put = async (storeName, mapName, rec) => {
    if (isDeleted(storeName, rec)) {
      counts.skipped++;
      return;                       // deleted here, and the deletion is newer
    }
    const existing = state[mapName] && state[mapName].get(rec.id);
    if (mode === 'merge' && existing && (existing.updatedAt || '') >= (rec.updatedAt || '')) {
      counts.skipped++;
      return;                       // skipped records produce no op
    }
    await idbPut(storeName, rec);
    if (state[mapName]) state[mapName].set(rec.id, rec);
    await logOp({ origin: 'import', store: storeName, op: 'put', recordId: rec.id,
                  record: rec, changed: diffFields(existing || null, rec) });
    counts[storeName]++;
  };
  for (const l of payload.lofts || []) await put('lofts', 'lofts', l);
  for (const b of payload.birds || []) await put('birds', 'birds', b);
  for (const p of payload.pairs || []) await put('pairs', 'pairs', p);
  for (const r of payload.raceResults || []) await put('raceResults', 'raceResults', r);
  for (const h of payload.healthEvents || []) await put('healthEvents', 'healthEvents', h);
  for (const m of decodedMedia) {
    const existing = await idbGet('media', m.id);
    if (mode === 'merge' && existing) { counts.skipped++; continue; }
    await idbPut('media', m);
    await logOp({ origin: 'import', store: 'media', op: 'put', recordId: m.id, record: m });
    counts.media++;
  }
  // An export from another device carries its own loft ids, so the stored
  // currentLoftId can end up pointing at a loft that no longer exists — which
  // silently breaks the loft settings card and every new record's loftId.
  // persist the union so the protection survives on this device too
  if (mode === 'merge') {
    for (const t of payload.tombstones || []) {
      const winner = tombIndex.get(t.id);
      if (winner) await idbPut('tombstones', winner);
    }
  }

  if (!state.lofts.has(state.currentLoftId)) {
    state.currentLoftId = state.lofts.size ? [...state.lofts.keys()][0] : null;
    await setSetting('currentLoftId', state.currentLoftId);
  }
  emitChange({ type: 'import' });
  return counts;
}

/**
 * Share one bird: the bird + full ancestor closure (+ optionally its race
 * results, health log, and media). Same format as exportAll, so any Zajil
 * user can import it — no account needed on either side.
 */
export async function exportBirdWithAncestry(birdId, { includeRaces = true, includeHealth = false, includeMedia = true } = {}) {
  const ids = new Set();
  const stack = [birdId];
  while (stack.length) {
    const id = stack.pop();
    if (!id || ids.has(id)) continue;
    ids.add(id);
    const b = getBird(id);
    if (b) { stack.push(b.sireId); stack.push(b.damId); }
  }
  const birds = [...ids].map((id) => getBird(id)).filter(Boolean);
  const mediaOut = [];
  if (includeMedia) {
    for (const id of ids) {
      for (const m of await mediaForBird(id)) {
        mediaOut.push({ ...m, blob: undefined, dataURL: await blobToDataURL(m.blob) });
      }
    }
  }
  return {
    format: 'zajil-export',
    version: 1,
    kind: 'bird-share',
    exportedAt: nowISO(),
    lofts: [],
    birds,
    pairs: [],
    raceResults: includeRaces ? [...state.raceResults.values()].filter((r) => ids.has(r.birdId)) : [],
    healthEvents: includeHealth ? [...state.healthEvents.values()].filter((h) => ids.has(h.birdId)) : [],
    media: mediaOut,
  };
}

// --------------------------------------------------------------- auto backup

const BACKUP_KEEP = 7;
export async function autoBackup() {
  // Media can be huge; interval snapshots keep data only. Full exports include
  // media. Asking exportAll not to read the blobs at all avoids base64-encoding
  // every photo twice a day only to throw the result away.
  const payload = await exportAll({ includeMedia: false });
  payload.kind = 'auto-backup';
  const id = nowISO();
  await idbPut('backups', { id, payload });
  const all = await idbGetAll('backups');
  all.sort((a, b) => (a.id < b.id ? -1 : 1));
  while (all.length > BACKUP_KEEP) {
    const victim = all.shift();
    await idbDelete('backups', victim.id);
  }
  await setSetting('lastAutoBackup', id);
  return id;
}
export function listBackups() { return idbGetAll('backups'); }
