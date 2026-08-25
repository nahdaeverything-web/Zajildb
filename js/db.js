// db.js — IndexedDB layer. IndexedDB is the source of truth; the app never
// blocks on the network. An in-memory Map of birds is kept in sync so the
// pure engine (which needs a synchronous getBird) stays fast with 1000+ birds.
//
// Sync-readiness (club mode hook): every record carries `loftId` and
// `updatedAt` (device clock, ISO). If sync is added later it must be
// per-field last-write-wins keyed on these — never whole-record overwrite.

import { classifySave } from './engine/validate.js';

const DB_NAME = 'zajil';
const DB_VERSION = 1;

export const STORES = ['birds', 'pairs', 'raceResults', 'healthEvents', 'lofts', 'media', 'settings', 'backups'];

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
      const mk = (name, indexes = []) => {
        if (db.objectStoreNames.contains(name)) return;
        const store = db.createObjectStore(name, { keyPath: name === 'settings' ? 'key' : 'id' });
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
  state.ready = true;
}

export function currentLoft() { return state.lofts.get(state.currentLoftId) || null; }
export function loftStatuses({ includeReference = false } = {}) {
  const l = currentLoft();
  const base = (l && Array.isArray(l.statuses) && l.statuses.length) ? l.statuses : DEFAULT_STATUSES;
  if (!includeReference) return base.filter((s) => s !== REFERENCE_STATUS);
  return base.includes(REFERENCE_STATUS) ? base : [...base, REFERENCE_STATUS];
}

export async function setSetting(key, value) {
  state.settings[key] = value;
  await idbPut('settings', { key, value });
}

// ---------------------------------------------------------------- record CRUD

function stamp(record) {
  record.updatedAt = nowISO();
  if (!record.loftId) record.loftId = state.currentLoftId;
  return record;
}

export function newBird(partial = {}) {
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
  stamp(bird);
  await idbPut('birds', bird);
  state.birds.set(bird.id, bird);
  emitChange({ type: 'bird', id: bird.id });
  return bird;
}

export async function deleteBird(id) {
  // Detach as parent from offspring; keep their records intact.
  // Original snapshots of every touched record are returned so the UI can undo.
  const affectedOriginals = [];
  const bird = state.birds.get(id);
  const media = await idbGetAll('media', 'birdId', id);
  for (const b of state.birds.values()) {
    if (b.sireId === id || b.damId === id) {
      affectedOriginals.push({ ...b });
      const copy = { ...b };
      if (copy.sireId === id) copy.sireId = null;
      if (copy.damId === id) copy.damId = null;
      stamp(copy);
      await idbPut('birds', copy);
      state.birds.set(copy.id, copy);
    }
  }
  for (const m of media) await idbDelete('media', m.id);
  await idbDelete('birds', id);
  state.birds.delete(id);
  emitChange({ type: 'bird', id });
  return { bird, media, affectedOriginals };
}

export async function restoreBird({ bird, media, affectedOriginals }) {
  // an undo restores exactly what was there; it is not a new edit to re-judge
  await idbPut('birds', bird);
  state.birds.set(bird.id, bird);
  for (const orig of affectedOriginals || []) {
    await idbPut('birds', orig);
    state.birds.set(orig.id, orig);
  }
  for (const m of media || []) await idbPut('media', m);
  emitChange({ type: 'bird', id: bird.id });
}

export function makeGeneric(storeName, stateMap, typeName) {
  return {
    async save(rec) {
      stamp(rec);
      if (!rec.id) rec.id = uuid();
      await idbPut(storeName, rec);
      state[stateMap].set(rec.id, rec);
      emitChange({ type: typeName, id: rec.id });
      return rec;
    },
    async remove(id) {
      const rec = state[stateMap].get(id);
      await idbDelete(storeName, id);
      state[stateMap].delete(id);
      emitChange({ type: typeName, id });
      return rec;
    },
    async restore(rec) {
      await idbPut(storeName, rec);
      state[stateMap].set(rec.id, rec);
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
  emitChange({ type: 'media', id: m.id, birdId });
  return m;
}
export function mediaForBird(birdId) { return idbGetAll('media', 'birdId', birdId); }
/** Put a media record back after a delete (undo). Emits, so views refresh. */
export async function restoreMedia(m) {
  if (!m) return null;
  await idbPut('media', m);
  emitChange({ type: 'media', id: m.id, birdId: m.birdId });
  return m;
}

export async function deleteMedia(id) {
  const m = await idbGet('media', id);
  await idbDelete('media', id);
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
export async function exportAll() {
  const media = await idbGetAll('media');
  const mediaOut = [];
  for (const m of media) {
    mediaOut.push({ ...m, blob: undefined, dataURL: await blobToDataURL(m.blob) });
  }
  return {
    format: 'zajil-export',
    version: 1,
    exportedAt: nowISO(),
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
  // Automatic snapshots deliberately carry no media (blobs would make them
  // huge), so wiping the media store on restore would destroy every photo and
  // scanned pedigree the payload cannot put back. Keep media in that case.
  const carriesMedia = payload.kind !== 'auto-backup';
  if (mode === 'replace') {
    const stores = ['birds', 'pairs', 'raceResults', 'healthEvents', 'lofts'];
    if (carriesMedia) stores.push('media');
    for (const s of stores) await idbClear(s);
    state.birds.clear(); state.pairs.clear(); state.raceResults.clear();
    state.healthEvents.clear(); state.lofts.clear();
  }
  const put = async (storeName, mapName, rec) => {
    const existing = state[mapName] && state[mapName].get(rec.id);
    if (mode === 'merge' && existing && (existing.updatedAt || '') >= (rec.updatedAt || '')) {
      counts.skipped++;
      return;
    }
    await idbPut(storeName, rec);
    if (state[mapName]) state[mapName].set(rec.id, rec);
    counts[storeName === 'raceResults' ? 'raceResults' : storeName]++;
  };
  for (const l of payload.lofts || []) await put('lofts', 'lofts', l);
  for (const b of payload.birds || []) await put('birds', 'birds', b);
  for (const p of payload.pairs || []) await put('pairs', 'pairs', p);
  for (const r of payload.raceResults || []) await put('raceResults', 'raceResults', r);
  for (const h of payload.healthEvents || []) await put('healthEvents', 'healthEvents', h);
  for (const m of payload.media || []) {
    const existing = await idbGet('media', m.id);
    if (mode === 'merge' && existing) { counts.skipped++; continue; }
    const blob = await dataURLToBlob(m.dataURL);
    await idbPut('media', { id: m.id, birdId: m.birdId, kind: m.kind, subtype: m.subtype, name: m.name, blob, addedAt: m.addedAt });
    counts.media++;
  }
  // An export from another device carries its own loft ids, so the stored
  // currentLoftId can end up pointing at a loft that no longer exists — which
  // silently breaks the loft settings card and every new record's loftId.
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
  const payload = await exportAll();
  // Media can be huge; interval backups keep data only. Full exports include media.
  payload.media = [];
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
