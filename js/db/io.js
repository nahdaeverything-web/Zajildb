// db/io.js — export, import, bird sharing, and the local backup rotation.
//
// The boundary where loft data crosses into and out of files other people can
// hold. Two rules live here and are asserted in tests/e2e/resurrection.py:
// tombstones TRAVEL with an export (so a deletion survives a round trip), and
// the op log does NOT (it is this device's own history, not shared loft data).
//
// Import from `js/db.js`, never from here directly — the facade is the API.

import {
  emitChange, getBird, idbClear, idbDelete, idbGet, idbGetAll, idbPut, nowISO, setSetting, state,
} from './storage.js';
import { diffFields, logOp } from './oplog.js';
import { mediaForBird } from './records.js';

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

