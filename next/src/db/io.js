// db/io.js — export, import, bird sharing, and the local backup rotation.
//
// The boundary where loft data crosses into and out of files other people can
// hold. Two rules live here and are asserted in tests/e2e/resurrection.py:
// tombstones TRAVEL with an export (so a deletion survives a round trip), and
// the op log does NOT (it is this device's own history, not shared loft data).
//
// Import from `js/db.js`, never from here directly — the facade is the API.

import {
  emitChange, ensureCurrentLoft, getBird, idbClear, idbDelete, idbGet, idbGetAll, idbPut, nowISO, setSetting, state,
} from './storage.js';
import { clearTombstone, diffFields, getTombstone, logOp, writeTombstone } from './oplog.js';
import { mediaForBird, isPristineLoft, dropPristineLoft } from './records.js';

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

/**
 * Settings that must never leave the device, by key prefix.
 *
 * `authAccessToken` and `authRefreshToken` are bearer credentials. In an
 * export they would travel in every JSON backup a fancier shares — over
 * WhatsApp, to a club administrator, anywhere — and whoever received the file
 * could act as that user until the tokens expired.
 */
export const SENSITIVE_SETTING_PREFIXES = ['auth'];

/**
 * THE funnel a setting must pass through to enter an export.
 *
 * Nothing calls it today, and that is the point worth stating plainly:
 * `exportAll` carries no `settings` key at all, so no setting of any kind is
 * exported and there is nothing yet to filter. This is a REGRESSION GUARD, not
 * a fix — the risk it exists for is a future release adding settings to an
 * export for some reasonable-sounding purpose (remembering a COI depth across
 * a restore, say) and carrying credentials out with it. When that day comes,
 * this is the function to route through, and tests/e2e/auth.py fails first if
 * it is forgotten.
 */
export function exportableSettings(settings) {
  return Object.fromEntries(Object.entries(settings || {})
    .filter(([key]) => !SENSITIVE_SETTING_PREFIXES.some((prefix) => key.startsWith(prefix))));
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
 * The same export, assembled as a Blob instead of a string. PORT ONLY — see
 * PORT-COMPLETE.md and the `data-layer-identity` guard's DIVERGENT list.
 *
 * WHY THIS EXISTS. `exportAll()` above returns an object; the caller then does
 * `JSON.stringify(obj, null, 1)` and wraps it in a Blob. Measured on this machine, with
 * 2 MB photos:
 *
 *   photos   source     output     peak JS heap
 *      50    105 MB     140 MB        284 MB
 *     100    210 MB     280 MB        563 MB
 *     180    378 MB     504 MB       1011 MB
 *     200    419 MB        —      **Invalid string length**
 *
 * V8 caps a string at about 512 MB, so past ~180 photos `JSON.stringify` cannot produce
 * one. And the failure is silent: the tools card awaited a promise that rejects, so a
 * fancier gets no file, NO TOAST, an unchanged «آخر تصدير», and a button that still looks
 * ready. Measured — the only trace is a pageerror nobody sees.
 *
 * This builds the JSON as a sequence of parts and folds them into Blobs as it goes, so no
 * single string is ever larger than one photo and the JS heap stays flat. A Blob's bytes
 * live outside the JS heap, which is the whole point.
 *
 * The FORMAT is unchanged — same keys, same data URLs, same `JSON.parse` result. That is
 * asserted in both directions by tests/e2e/migration.py, because a vanilla app must still
 * be able to read what the port writes.
 *
 * @param {{ onProgress?: (done: number, total: number) => void }} [opts]
 * @returns {Promise<Blob>}
 */
export async function exportAllBlob({ onProgress } = {}) {
  const media = await idbGetAll('media');
  const total = media.length;
  const parts = [];            // Blobs and strings, in order
  let pending = [];            // strings not yet folded into a Blob
  const fold = () => { if (pending.length) { parts.push(new Blob(pending)); pending = []; } };
  const push = (s) => { pending.push(s); if (pending.length >= 4) fold(); };

  const head = {
    format: 'zajil-export',
    version: 1,
    exportedAt: nowISO(),
    tombstones: await idbGetAll('tombstones'),
    lofts: [...state.lofts.values()],
    birds: [...state.birds.values()],
    pairs: [...state.pairs.values()],
    raceResults: [...state.raceResults.values()],
    healthEvents: [...state.healthEvents.values()],
  };
  // every key except media, then media streamed in one at a time
  const headText = JSON.stringify(head);
  push(headText.slice(0, -1));                 // drop the closing brace
  push(',"media":[');
  for (let i = 0; i < total; i++) {
    const m = media[i];
    const row = { ...m, blob: undefined, dataURL: await blobToDataURL(m.blob) };
    push((i ? ',' : '') + JSON.stringify(row));
    fold();                                    // release the data URL before the next read
    if (onProgress) onProgress(i + 1, total);
  }
  push(']}');
  fold();
  return new Blob(parts, { type: 'application/json' });
}

/** The five mirrored stores a replace clears, as [store, mirror]. Media is handled beside them. */
const REPLACED = [['lofts', 'lofts'], ['birds', 'birds'], ['pairs', 'pairs'],
                  ['raceResults', 'raceResults'], ['healthEvents', 'healthEvents']];

/**
 * The records a replace of `payload` would DROP: everything here that the payload does not carry.
 * PORT ONLY (RF-15, RULED 2026-11-13). An untouched default loft is not data and never travelled,
 * so it is dropped without a trace, as dropPristineLoft() drops it.
 */
function droppedByReplace(payload) {
  const out = [];
  for (const [storeName, mapName] of REPLACED) {
    const incoming = new Set((payload[storeName] || []).map((r) => r && r.id));
    for (const rec of state[mapName].values()) {
      if (incoming.has(rec.id)) continue;
      if (storeName === 'lofts' && isPristineLoft(rec)) continue;
      out.push([storeName, rec]);
    }
  }
  return out;
}

/**
 * What a replace of this payload would do, for the confirmation to say BEFORE anything is touched
 * (RF-15): how many records it removes, and which birds it brings back that are not here now.
 * A replace travels — every dropped record is tombstoned and pushed as a deletion, every record
 * in the payload is pushed as a write — so the dialog has to state both, with the counts.
 */
export function replacePreview(payload) {
  const dropped = droppedByReplace(payload || {});
  const birds = dropped.filter(([s]) => s === 'birds').length;
  const returning = ((payload && payload.birds) || []).filter((b) => b && !state.birds.has(b.id));
  return { removedBirds: birds, removedOthers: dropped.length - birds, removed: dropped.length,
           returning: returning.map((b) => ({ id: b.id, name: b.name || '', ring: ((b.rings || [])[0] || {}).raw || '' })) };
}

/**
 * The media a replace of `payload` DELETES (RULED 2026-11-16, P2): the photos and documents of a bird the replace
 * drops, unless the file itself carries them. A photo on a bird that STAYS is never deleted — a file that carries no
 * media says nothing about the media here. A restore of a snapshot deletes none: a snapshot carries no media, photos
 * have no server copy, and a restore is an undo (P1) — a dropped bird's photos stay on the device and are its photos
 * again if the bird returns.
 */
async function droppedMediaByReplace(payload) {
  if (!payload || payload.kind === 'auto-backup') return [];
  const birdsDropped = new Set(droppedByReplace(payload).filter(([s]) => s === 'birds').map(([, b]) => b.id));
  if (!birdsDropped.size) return [];
  const incoming = new Set((payload.media || []).map((m) => m && m.id));
  return (await idbGetAll('media')).filter((m) => birdsDropped.has(m.birdId) && !incoming.has(m.id));
}

/** How many photos and documents a replace of `payload` would delete, for the question to state (P3). They cannot be recovered. */
export async function replaceMediaLoss(payload) {
  return (await droppedMediaByReplace(payload || {})).length;
}

/**
 * Import an export payload. mode 'merge' keeps newer records by updatedAt;
 * mode 'replace' wipes first. Returns counts.
 */
export async function importAll(payload, mode = 'merge') {
  if (!payload || payload.format !== 'zajil-export') throw new Error('bad-format');
  const counts = { birds: 0, pairs: 0, raceResults: 0, healthEvents: 0, lofts: 0, media: 0, skipped: 0, removed: 0 };

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
      await pruneBackups();
    } catch { /* a snapshot is a safety net, not a reason to block the import */ }
  }

  // ── RF-15 (RULED 2026-11-13): A REPLACE TOMBSTONES EVERY RECORD IT DROPS ──
  //
  // Until this, a replace cleared the stores and left no trace of what it removed. Measured on the
  // deployed build: the next pull brought the whole pre-import set back — a device's own pushed rows
  // sit above its cursor — and any record another device touched afterwards returned for good; a
  // restore did the same. So the replacement now TRAVELS: every dropped record gets a tombstone and
  // a delete op, exactly as if the fancier had deleted it, and every device converges on the file.
  //
  // ORDER, and why. The tombstones are written FIRST, before the stores are cleared: a pull that
  // runs while the import is in flight then meets them and skips the old rows (applySyncPut). The
  // delete ops are logged LAST, after every record of the payload is in: an import that fails half
  // way must not leave deletions queued for records that are still here, so on a failure the
  // tombstones written here are taken back and nothing was logged. Between the two, a pull can
  // still slip a dropped record back in; the sweep at the end removes it again.
  const dropped = mode === 'replace' ? droppedByReplace(payload) : [];
  // P2 (RULED 2026-11-16): a photo is dropped ONLY with its bird. Until this, every media row the file did not carry
  // was deleted — so a file with no media deleted every photo on the device, on birds that stayed, while the question
  // said nothing would be deleted. Photos have no server copy; that was the only copy.
  if (mode === 'replace') for (const m of await droppedMediaByReplace(payload)) dropped.push(['media', m]);
  const droppedAt = nowISO();
  const priorTombstones = new Map();
  for (const [storeName, rec] of dropped) {
    priorTombstones.set(`${storeName}:${rec.id}`, await getTombstone(storeName, rec.id));
    await writeTombstone(storeName, rec.id, null, droppedAt);
  }
  try {
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
    // The media store is NOT cleared (P2): the photos of the dropped birds are deleted one by one below, with the
    // other dropped records, and every other photo stays where it is.
    for (const s of ['birds', 'pairs', 'raceResults', 'healthEvents', 'lofts']) await idbClear(s);
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
    // a record the fancier has just put back is not deleted: the corollary applySyncPut and
    // restoreBird already follow — a winning record clears its tombstone (RF-15)
    if (mode === 'replace') await clearTombstone(storeName, rec.id);
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
    if (mode === 'replace') await clearTombstone('media', m.id);
    counts.media++;
  }
  } catch (err) {
    // nothing was logged for the dropped records yet; take their tombstones back so a failed
    // replace leaves no deletion standing against a record that is still on the device
    for (const [storeName, rec] of dropped) {
      const prior = priorTombstones.get(`${storeName}:${rec.id}`);
      if (prior) await idbPut('tombstones', prior); else await clearTombstone(storeName, rec.id);
    }
    throw err;
  }
  // the payload is in. Now the deletions become real: logged, so they are pushed, and each
  // tombstone carries the seq of its own op as every local deletion does.
  for (const [storeName, rec] of dropped) {
    await idbDelete(storeName, rec.id);                      // slipped back in by a pull mid-import: dropped all the same
    if (state[storeName]) state[storeName].delete(rec.id);
    const seq = await logOp({ origin: 'import', store: storeName, op: 'delete', recordId: rec.id,
                              record: rec, at: droppedAt });
    await writeTombstone(storeName, rec.id, seq, droppedAt);
    counts.removed++;
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

  // ── ADOPT AN IMPORTED LOFT WHEN OURS IS PRISTINE (RF-12, RULED 2026-09-27) ──
  //
  // initDB() creates an unnamed default loft on first run and points currentLoftId at it.
  // Import ADDS the loft a file carries; it never adopted it. So the first thing a new
  // fancier does — load the teaching loft, then add a bird — left the register holding birds
  // of TWO lofts: the 38 imported ones under «لوفت إربد التعليمي», and their own new bird
  // under the unnamed loft that currentLoftId still named. The loft settings card edited that
  // empty one, so naming it put the name on a loft containing one bird. Nothing warned,
  // because no screen filters by loftId — the split is invisible until club mode or sync
  // attribution cares, and by then it is in everyone's data.
  //
  // This is R4's rule, which sync.js:869-875 already applies when a first sync brings a real
  // loft: if ours is PRISTINE, theirs becomes current and ours is dropped. Same rule, same
  // functions — isPristineLoft() decides and dropPristineLoft() re-checks its own guard, so
  // a loft the fancier has actually filed birds under can never be deleted by this path.
  //
  // TWO REFUSALS, both R4's, both deliberate:
  //   · ours is NOT pristine — named, placed, or holding records. Then it is theirs, and
  //     which loft is current is a question only they can answer.
  //   · the import carries SEVERAL lofts. There is no basis for choosing one, and guessing
  //     would file their next bird somewhere arbitrary.
  // In both cases nothing is adopted and nothing is dropped: the import is still correct,
  // it simply does not change whose loft this is.
  const incomingLofts = payload.lofts || [];
  if (incomingLofts.length === 1) {
    const incoming = state.lofts.get(incomingLofts[0].id);
    const mine = state.lofts.get(state.currentLoftId);
    if (incoming && mine && incoming.id !== mine.id && isPristineLoft(mine)) {
      // current first, then drop: dropPristineLoft removes the row, and currentLoftId must
      // never name a loft that is already gone
      state.currentLoftId = incoming.id;
      await setSetting('currentLoftId', incoming.id);
      await dropPristineLoft(mine.id);
    }
  }

  // An export from another device carries its own loft ids, so the stored currentLoftId can
  // still end up naming a loft that does not exist here — a different case from the above,
  // and this repair stays.
  if (!state.lofts.has(state.currentLoftId)) {
    state.currentLoftId = state.lofts.size ? [...state.lofts.keys()][0] : null;
    await setSetting('currentLoftId', state.currentLoftId);
  }
  // RF-15 gap (RULED 2026-11-15): a replace or a restore whose payload carries no loft left the device with none
  // until the next boot, and a bird saved in between was filed under no loft for good. The loft the next boot would
  // have created is created now. Only the no-loft case: the several-lofts branch above is open against RF-14.
  if (!state.lofts.size) await ensureCurrentLoft();
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

// RF-21 (RULED 2026-11-16). The numbers the restore screen states are these constants — the screen reads them from
// here, and the caller (src/components/AutoBackup.tsx) reads the interval from here.
//
// TWO KINDS, TWO LIMITS, AND NEITHER EVER EVICTS THE OTHER. An interval snapshot's id is its moment; a snapshot taken
// before a replace or a restore is `pre-import-<moment>`. Until this ruling both counted toward one limit of seven and
// only the interval ones were ever removed: measured, seven replaces left no room, and every interval snapshot was
// deleted in the call that wrote it. Now the seven newest interval snapshots are kept, and separately the three newest
// pre-import ones.
export const AUTO_BACKUP_HOURS = 12;
export const BACKUP_KEEP = 7;
export const PRE_IMPORT_KEEP = 3;
const PRE_IMPORT = 'pre-import-';
/** The moment a snapshot was taken, whichever kind it is — the one key the list and the limits order by. */
export const backupMoment = (b) => String(b.id).replace(PRE_IMPORT, '');
export const isPreImportBackup = (b) => String(b.id).startsWith(PRE_IMPORT);
async function pruneBackups() {
  const all = await idbGetAll('backups');
  for (const [mine, keep] of [[(b) => !isPreImportBackup(b), BACKUP_KEEP], [isPreImportBackup, PRE_IMPORT_KEEP]]) {
    const kind = all.filter(mine).sort((a, b) => (backupMoment(a) < backupMoment(b) ? 1 : -1));   // newest first
    for (const victim of kind.slice(keep)) await idbDelete('backups', victim.id);
  }
}
export async function autoBackup() {
  // Media can be huge; interval snapshots keep data only. Full exports include
  // media. Asking exportAll not to read the blobs at all avoids base64-encoding
  // every photo twice a day only to throw the result away.
  const payload = await exportAll({ includeMedia: false });
  payload.kind = 'auto-backup';
  const id = nowISO();
  await idbPut('backups', { id, payload });
  await pruneBackups();
  await setSetting('lastAutoBackup', id);
  // the tools row's count and the restore screen's list re-read on a layer change (RULED 2026-11-16)
  emitChange({ type: 'backup' });
  return id;
}
/** NEWEST FIRST, a pre-import snapshot placed by its moment among the interval ones (RULED 2026-11-16). */
export async function listBackups() {
  return (await idbGetAll('backups')).sort((a, b) => (backupMoment(a) < backupMoment(b) ? 1 : -1));
}

