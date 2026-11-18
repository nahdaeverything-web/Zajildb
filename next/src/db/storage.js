// db/storage.js — IndexedDB access and the in-memory mirror.
//
// The bottom of the db layer: it imports nothing from its siblings, so the
// dependency graph is a straight line (storage <- oplog <- records <- io) and
// no cycle is possible.
//
// The mirror is why `getBird` is synchronous. The COI engine calls it
// thousands of times inside recursive memoised traversals; an async read there
// would make a 6-generation coefficient a network of promises.
//
// Import from `js/db.js`, never from here directly — the facade is the API.

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

/**
 * RF-26 (RULED 2026-11-18): ONE readwrite transaction over several stores, so a decision and the write it leads to
 * cannot have another write land between them. `fn(h)` is called at once, inside the transaction, and may await ONLY
 * the requests it makes through `h` — awaiting anything else lets the transaction close under it. What `fn` returns
 * is the result once the transaction has COMMITTED; if `fn` throws, the transaction is aborted and nothing is written.
 */
export function idbAtomic(stores, fn) {
  return openDB().then((db) => new Promise((resolve, reject) => {
    const t = db.transaction(stores, 'readwrite');
    const req = (r) => new Promise((res, rej) => { r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
    const h = {
      get: (s, k) => req(t.objectStore(s).get(k)),
      put: (s, v) => req(t.objectStore(s).put(v)),
      del: (s, k) => req(t.objectStore(s).delete(k)),
      /** primary keys of the ops above `seq`, without reading the ops themselves */
      opIdsAbove: (seq) => req(t.objectStore('oplog').index('seq').getAllKeys(IDBKeyRange.lowerBound(seq, true))),
    };
    let out, failure = null;
    t.oncomplete = () => resolve(out);
    t.onerror = () => reject(failure || t.error);
    t.onabort = () => reject(failure || t.error || new Error('transaction aborted'));
    let running;
    try { running = Promise.resolve(fn(h)); } catch (err) { running = Promise.reject(err); }
    running.then((v) => { out = v; }, (err) => { failure = err; try { t.abort(); } catch { /* already finished */ } });
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
  // RF-14 (RULED 2026-10-14): a stored currentLoftId is a device setting that nothing re-checked, so a
  // loft removed here or by a pulled tombstone left it dangling — currentLoft() null, the loft card
  // empty, every new bird filed under an id no loft has, and a reload kept it. Validated here and
  // after every loft removal (records.js); never trusted again.
  await ensureCurrentLoft();

  // Device identity. Generated ONCE and never regenerated: it is what lets a
  // future sync layer attribute an op to the machine that made it, and what
  // makes the per-device `seq` monotonic sequence meaningful.
  if (!state.settings.deviceId) await setSetting('deviceId', uuid());
  if (state.settings.deviceName === undefined) await setSetting('deviceName', '');
  if (typeof state.settings.opSeq !== 'number') await setSetting('opSeq', 0);

  state.ready = true;
}

export function currentLoft() { return state.lofts.get(state.currentLoftId) || null; }

/**
 * RF-14: make currentLoftId point at a loft that exists, or do nothing if it already does.
 *
 * Exactly one loft on the device → it is adopted (there is nothing to guess). Otherwise — none,
 * or several with the current one gone — a fresh pristine loft is created and made current, as
 * on a first run: a clear state the fancier can act on (name it, or file under it), and one that
 * `isPristineLoft()` recognises, so a later adoption can still drop it. Choosing among several
 * remaining lofts is the guess R4 refuses to make. A new bird is never filed under an id no loft
 * has: `newBird()` takes state.currentLoftId, and this is what keeps it real.
 *
 * @returns the id adopted or created, or null when nothing needed doing.
 */
export async function ensureCurrentLoft() {
  if (state.lofts.get(state.currentLoftId)) return null;
  let id;
  if (state.lofts.size === 1) {
    id = [...state.lofts.keys()][0];
  } else {
    const loft = { id: uuid(), name: '', location: '', statuses: DEFAULT_STATUSES, createdAt: nowISO(), updatedAt: nowISO() };
    await idbPut('lofts', loft);
    state.lofts.set(loft.id, loft);
    id = loft.id;
  }
  await setSetting('currentLoftId', id);
  state.currentLoftId = id;
  emitChange({ type: 'loft', id });
  return id;
}
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
  // RF-25 (RULED 2026-11-17): a value storage refuses does not stay in memory. Memory is written first, as it always
  // was — callers and the snapshot timer read it the moment this is called — and is put back if the write fails.
  // (Storage-first was tried, 9ac7e7a: it left a gap in which «آخر نسخة تلقائية» was stored-but-not-yet-in-memory, and
  // auto_backup.py failed on it one run in six.) Put back only if nothing newer has been set meanwhile.
  const had = Object.prototype.hasOwnProperty.call(state.settings, key); const before = state.settings[key];
  state.settings[key] = value;
  try { await idbPut('settings', { key, value }); }
  catch (e) {
    if (state.settings[key] === value) { if (had) state.settings[key] = before; else delete state.settings[key]; }
    throw e;
  }
}

/**
 * Stamp a record on its way to storage.
 * `deviceId` is the LAST writing device by design — it changes every time the
 * record is written anywhere. For the CREATING device read provenance[0].
 * Deliberately does NOT touch `provenance`: pre-v1.8 records have none, and
 * inventing a 'created' event would assert a history that did not happen.
 */
export function stamp(record) {
  record.updatedAt = nowISO();
  record.deviceId = state.settings.deviceId || null;
  if (!record.loftId) record.loftId = state.currentLoftId;
  return record;
}

