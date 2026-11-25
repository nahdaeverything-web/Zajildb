// db/photos.js — photo and document BYTES, to and from the project's storage. PORT-ONLY (no vanilla counterpart).
//
// PHOTO SYNC, STAGE 1 (RULED 2026-11-18). Records sync through the op log and the table (sync.js); a media record's
// bytes never enter either (SYNC-DESIGN §7). This file moves the bytes:
//
//   UP    after a record cycle has succeeded, the coordinator starts ONE pass here and does not wait for it. The pass
//         uploads, one at a time, every media record on this device that holds bytes and is not yet marked `stored`.
//         A successful upload writes `stored` on the record THROUGH THE OP LOG, so the marker syncs like any field.
//   DOWN  a device that holds a media record with the marker and without bytes fetches them when a screen asks
//         (the bird's profile, on first view) and keeps them.
//
// THE INVARIANT: nothing in this file ever writes a media record with fewer bytes than the device held. An upload
// that fails, is refused, or meets a project with no bucket leaves the record exactly as it was.
//
// NEVER HOT: a pass is started only by a completed record cycle; a pass that fails backs off on the coordinator's own
// schedule (backoffDelay) and automatic passes before that moment do nothing. «مزامنة الآن» clears the wait, as it
// does for records.
//
// Object path: <owner uuid>/<media id> in the private bucket `photos` (owner-only policies; supabase/photo-storage.sql
// when it lands). Plain fetch, like the rest of sync — no client library.
import { emitChange, idbGet, idbGetAll, idbPut, nowISO, setSetting, state } from './storage.js';
import { logOp } from './oplog.js';
import { authHeaders, backoffDelay, dataOwner, ensureAccessToken, isSignedIn, refreshSession, syncConfig } from './sync.js';

export const PHOTO_BUCKET = 'photos';
/** The bucket's per-file limit (RULED 2026-11-18): 5 MiB. Checked here first, so an oversize file is never sent. */
export const PHOTO_MAX_BYTES = 5 * 1024 * 1024;
/** The bucket's allow-list: images and PDF, as the storage SQL names them. */
export const PHOTO_TYPES = Object.freeze(['image/jpeg', 'image/png', 'image/webp', 'application/pdf']);

/** Files this device was told will not be stored, by media id: 'size' | 'type'. Per device, out of sync scope. */
const refusedMap = () => (state.settings.photoRefused && typeof state.settings.photoRefused === 'object' ? state.settings.photoRefused : {});

/**
 * STAGE 2 (RULED 2026-11-19). A queued object removal is sent only once it is this old. The «تراجع» notice lasts 6
 * seconds; inside this time an undo must find the object still there, because the other device has already dropped
 * its bytes on the tombstone and the object may be the only copy this device can fetch.
 */
export const PHOTO_REMOVE_GRACE_MS = 60 * 1000;
/** Media ids whose object this device is to remove: [{ id, at }]. Written by the delete itself (records.js). */
const removalQueue = () => (Array.isArray(state.settings.photoRemovals) ? state.settings.photoRemovals : []);
const dequeue = (id) => setSetting('photoRemovals', removalQueue().filter((q) => q.id !== id));

let pass = null;             // the one pass in flight, or null
let attempt = 0;             // consecutive passes that ended in a failure
let notBefore = 0;           // ms epoch: automatic passes before this do nothing
let last = null;             // what the last pass did, for الأدوات and the suites
let waiting = null;          // how many files hold bytes here and are not on the server; null until counted
let full = false;            // the last upload was refused because storage is full


/**
 * STAGE 3 (ORDERED 2026-11-20): every photo whose bytes are on the server and not on this device comes down in the
 * background, so an export, a share or a certificate made on EITHER device is complete. Only while the device is online
 * and the app is in front — never from a pocket, never into a dead network — one at a time, after the uploads, on the
 * pass's own backoff; record sync never waits for it (the pass is not awaited).
 */
/**
 * RULED 2026-11-20: A STUCK DOWNLOAD MUST NOT HOLD THE QUEUE. One download is given this long; then it is abandoned —
 * that file fails and waits out its own backoff, and the next file goes. 60 s (APPROVED 2026-11-20) — a 1600 px photo (0.3–0.5 MB)
 * comes down in seconds on a slow phone line, and a 5 MiB document needs about 40 s at 1 Mbit/s.
 */
export const PHOTO_DOWNLOAD_TIMEOUT_MS = 60 * 1000;
const downloadAllowed = () => (typeof navigator === 'undefined' || navigator.onLine !== false)
  && (typeof document === 'undefined' || document.visibilityState !== 'hidden');
/** Media records marked stored whose bytes are not here: the ones that failed least first, then oldest first. */
export async function photosAwaitingDownload() {
  const tries = (m) => (failedAt.get(m.id) || { n: 0 }).n;
  return (await idbGetAll('media'))
    .filter((m) => m && !m.blob && m.stored)
    .sort((a, b) => tries(a) - tries(b) || String(a.addedAt || '').localeCompare(String(b.addedAt || '')));
}

const objectUrl = (kind, owner, id) => `${syncConfig().url}/storage/v1/object/${kind}${PHOTO_BUCKET}/${encodeURIComponent(owner)}/${encodeURIComponent(id)}`;

/** Media records that hold bytes here and are not on the server yet, oldest first. Refused files are not in it. */
export async function photosAwaitingUpload() {
  const refused = refusedMap();
  return (await idbGetAll('media'))
    .filter((m) => m && m.blob && !m.stored && !refused[m.id])
    .sort((a, b) => String(a.addedAt || '').localeCompare(String(b.addedAt || '')));
}

// what this pass refused. The shell shows at most two notices at a time, so one notice per file would lose all
// but the last two; the pass says them in ONE event when it ends, however it ends.
let told = [];
async function refuse(m, reason) {
  await setSetting('photoRefused', { ...refusedMap(), [m.id]: reason });
  told.push({ id: m.id, name: m.name || '', reason });   // said ONCE per pass, together — see run()
  emitChange({ type: 'media', id: m.id, birdId: m.birdId });
}

async function readError(res) {
  let body = null;
  try { body = await res.json(); } catch { /* not JSON: the status is all there is */ }
  const code = String((body && (body.code || body.error)) || '');
  const message = String((body && body.message) || '');
  return { status: res.status, code, message };
}

/**
 * Send one record's bytes. Resolves 'stored' | 'refused' | 'gone'; THROWS on anything that may succeed later
 * (no network, no bucket, a server fault, a session that would not refresh).
 */
async function uploadOne(m, owner) {
  const type = m.blob.type || '';
  if (!PHOTO_TYPES.includes(type)) { await refuse(m, 'type'); return 'refused'; }
  if (m.blob.size > PHOTO_MAX_BYTES) { await refuse(m, 'size'); return 'refused'; }
  const send = () => fetch(objectUrl('', owner, m.id), {
    method: 'POST',
    headers: { ...authHeaders(), 'content-type': type, 'x-upsert': 'true' },   // upsert: a retry of a sent-but-unacknowledged upload overwrites itself
    body: m.blob,
  });
  let res = await send();
  if (!res.ok) {
    let err = await readError(res);
    if (err.status === 401 || err.code === 'InvalidJWT' || /jwt/i.test(err.message)) {       // reactive refresh, once — as for records
      const again = await refreshSession();
      if (again && again.ok) { res = await send(); err = res.ok ? null : await readError(res); }
    }
    if (err) {
      if (err.status === 413 || err.code === 'EntityTooLarge') { await refuse(m, 'size'); return 'refused'; }
      if (err.code === 'InvalidMimeType' || /mime/i.test(err.message)) { await refuse(m, 'type'); return 'refused'; }
      // STAGE 2: storage that is FULL. Supabase documents no error for it (its list of storage codes has none), so
      // this is what such an answer would most plausibly look like — HTTP 402 or 507, or a code or message that
      // names a quota — and it is UNVERIFIED against the real service. It is not a verdict on the file: nothing is
      // marked refused, the bytes stay, and the pass tries again later.
      if (err.status === 402 || err.status === 507 || /quota|insufficient.?storage|storage.{0,12}(full|exceed)/i.test(`${err.code} ${err.message}`)) {
        throw Object.assign(new Error(`photo-upload storage full (${err.status} ${err.code || err.message})`.trim()), { status: err.status, code: 'StorageFull' });
      }
      throw Object.assign(new Error(`photo-upload ${err.status} ${err.code || err.message}`.trim()), { status: err.status, code: err.code });
    }
  }
  // A 2xx is not yet an acknowledgement: a captive portal or a proxy answers 200 with a page of its own. Storage
  // answers with the object's key; anything else is «not stored», tried again later, and the record stays unmarked.
  let ack = null;
  try { ack = await res.json(); } catch { ack = null; }
  if (!ack || ack.Key !== `${PHOTO_BUCKET}/${owner}/${m.id}`) throw Object.assign(new Error('photo-upload unacknowledged'), { status: res.status, code: 'Unacknowledged' });
  // the bytes are on the server. Mark the record AS IT STANDS NOW — never the copy read before the upload.
  const cur = await idbGet('media', m.id);
  if (!cur) {                                               // deleted while it was being sent: the object just written has no record
    await setSetting('photoRemovals', [...removalQueue().filter((q) => q.id !== m.id), { id: m.id, at: nowISO() }]);
    return 'gone';
  }
  const rec = { ...cur, stored: { at: nowISO(), size: m.blob.size, type } };
  await idbPut('media', rec);
  await logOp({ origin: 'user', store: 'media', op: 'put', recordId: rec.id, record: rec, changed: ['stored'] });
  emitChange({ type: 'media', id: rec.id, birdId: rec.birdId });
  return 'stored';
}

/**
 * Remove one object. Resolves 'removed' | 'absent' (there was nothing there: done all the same) | 'kept' (the record
 * exists on this device again — an undo — so nothing is removed); THROWS on anything that may succeed later.
 */
async function removeOne(id, owner) {
  if (await idbGet('media', id)) return 'kept';
  const send = () => fetch(objectUrl('', owner, id), { method: 'DELETE', headers: authHeaders() });
  let res = await send();
  if (!res.ok) {
    let err = await readError(res);
    if (err.status === 401 || err.code === 'InvalidJWT' || /jwt/i.test(err.message)) {
      const again = await refreshSession();
      if (again && again.ok) { res = await send(); err = res.ok ? null : await readError(res); }
    }
    if (err) {
      // a missing OBJECT is the end of the matter; a missing BUCKET is not (the object may exist once it is back)
      const missing = err.code !== 'NoSuchBucket' && !/bucket not found/i.test(err.message)
        && (err.code === 'NoSuchKey' || err.code === 'not_found' || /object not found/i.test(err.message));
      if (missing) return 'absent';
      throw Object.assign(new Error(`photo-remove ${err.status} ${err.code || err.message}`.trim()), { status: err.status, code: err.code });
    }
  }
  // as for an upload: a 2xx that is not storage's own JSON (a captive portal's page) removed nothing
  let ack = null;
  try { ack = await res.json(); } catch { ack = null; }
  if (!ack || typeof ack !== 'object') throw Object.assign(new Error('photo-remove unacknowledged'), { status: res.status, code: 'Unacknowledged' });
  return 'removed';
}

/** Count the files that hold bytes here and are not on the server, and say so if the number changed. */
export async function refreshPhotoWaiting() {
  let n = 0;
  if (syncConfig().configured && isSignedIn()) n = (await photosAwaitingUpload()).length;
  if (n !== waiting) { waiting = n; emitChange({ type: 'photo-status' }); }
  return n;
}
/** For syncStatus(): the count (0 until counted) and whether storage refused the last upload as full. */
export function photoStatus() { return { waiting: waiting || 0, full }; }

async function run(manual) {
  const out = { ran: false, stored: 0, refused: 0, removed: 0, downloaded: 0, timedOut: 0, failed: null, skipped: null };
  if (!syncConfig().configured || !isSignedIn()) { out.skipped = 'hidden'; return out; }
  if (manual) { attempt = 0; notBefore = 0; }
  if (Date.now() < notBefore) { out.skipped = 'backoff'; return out; }
  const owner = (await dataOwner()).id;
  if (!owner || owner !== state.settings.authUserId) { out.skipped = 'owner'; return out; }   // never another account's folder
  const queue = await photosAwaitingUpload();
  const due = removalQueue().filter((q) => Date.parse(q.at) <= Date.now() - PHOTO_REMOVE_GRACE_MS);
  const down = downloadAllowed() ? await photosAwaitingDownload() : [];
  if (!queue.length && !due.length && !down.length) { attempt = 0; return out; }
  if (!(await ensureAccessToken())) { out.skipped = 'session'; return out; }
  out.ran = true; told = [];
  const stop = (err) => {
    // stop the pass: the next file would meet the same wall. The bytes are untouched.
    out.failed = { status: (err && err.status) || null, code: (err && err.code) || null, message: String((err && err.message) || err) };
    notBefore = Date.now() + backoffDelay(attempt); attempt++;
    return out;
  };
  try {
    // REMOVALS FIRST: they free space, and an upload that storage refuses as full must not hold them back.
    for (const q of due) {
      try {
        const r = await removeOne(q.id, owner);
        await dequeue(q.id);
        if (r === 'removed') out.removed++;
      } catch (err) { return stop(err); }          // the entry stays queued
    }
    for (const m of queue) {
      try {
        const r = await uploadOne(m, owner);
        if (r === 'stored') out.stored++; else if (r === 'refused') out.refused++;
      } catch (err) {
        if (err && err.code === 'StorageFull' && !full) { full = true; emitChange({ type: 'photo-storage-full' }); }   // SAID once, when it begins
        return stop(err);
      }
    }
    if (queue.length && full) { full = false; emitChange({ type: 'photo-status' }); }   // an upload went through: no longer full
    // STAGE 3: then the bytes this device lacks, ONE AT A TIME, re-checking before each that the device is still online
    // and in front. A failed download stops the pass on the same backoff as an upload; a file whose own last try failed
    // is passed over until its own wait is out ('waiting'), so one bad object cannot hold the others back.
    for (const m of down) {
      if (!downloadAllowed()) { out.skipped = 'background'; break; }
      const r = await fetchPhotoBytes(m.id);
      if (r === 'here') out.downloaded++;
      else if (r === 'timeout') out.timedOut++;     // given up on: it waits out its own backoff, and the next one goes
      else if (r === 'failed') return stop(Object.assign(new Error('photo-download failed'), { code: 'DownloadFailed' }));
    }
    attempt = 0; notBefore = 0;
    return out;
  } finally {
    if (told.length) { const files = told; told = []; emitChange({ type: 'photo-refused', files }); }
    await refreshPhotoWaiting().catch(() => {});
  }
}

/**
 * Start a pass if none is running. Called by the coordinator after a record cycle that succeeded; NOT awaited there.
 * Never throws.
 */
export function runPhotoPass({ manual = false } = {}) {
  if (pass) return pass;
  pass = run(manual).catch((err) => ({ ran: false, stored: 0, refused: 0, failed: { message: String((err && err.message) || err) }, skipped: null }))
    .then((r) => { last = { ...r, at: nowISO() }; pass = null; return r; });
  return pass;
}

/** For الأدوات and the suites. Read-only. */
export function photoSyncState() {
  return { inFlight: Boolean(pass), failures: attempt, waitMs: Math.max(0, notBefore - Date.now()), last, refused: { ...refusedMap() },
           waiting, full, removals: removalQueue().map((q) => ({ ...q })) };
}

// ───────────────────────────── down ─────────────────────────────

const fetching = new Map();   // media id -> the one fetch in flight
let lane = Promise.resolve();  // STAGE 3: ONE download at a time, whoever asks (the pass, a profile, the viewer)
const oneAtATime = (fn) => { const run = lane.then(fn, fn); lane = run.catch(() => {}); return run; };
const failedAt = new Map();   // media id -> { n, notBefore } — a failed fetch is not repeated by every re-render

/**
 * Bring one record's bytes to this device and keep them. Resolves
 * 'here' (already held, or just stored) | 'not-stored' (no marker: the bytes are on another device and not uploaded)
 * | 'waiting' (a recent failure; not asked again yet) | 'failed' | 'timeout' (no answer within PHOTO_DOWNLOAD_TIMEOUT_MS)
 * | 'gone'. Never throws, never removes anything.
 */
export function fetchPhotoBytes(id) {
  if (fetching.has(id)) return fetching.get(id);
  const p = oneAtATime(async () => {
    const cur = await idbGet('media', id);
    if (!cur) return 'gone';
    if (cur.blob) return 'here';
    if (!cur.stored) return 'not-stored';
    if (!syncConfig().configured || !isSignedIn()) return 'failed';
    const f = failedAt.get(id);
    if (f && Date.now() < f.notBefore) return 'waiting';
    const owner = (await dataOwner()).id;
    if (!owner || owner !== state.settings.authUserId) return 'failed';
    const ctl = typeof AbortController === 'undefined' ? null : new AbortController();
    const timer = ctl ? setTimeout(() => ctl.abort(), PHOTO_DOWNLOAD_TIMEOUT_MS) : null;
    try {
      if (!(await ensureAccessToken())) throw new Error('no session');
      const get = () => fetch(objectUrl('authenticated/', owner, id), { headers: authHeaders(), signal: ctl ? ctl.signal : undefined });
      let res = await get();
      if (res.status === 401 || res.status === 400 || res.status === 403) {
        const again = await refreshSession();
        if (again && again.ok) res = await get();
      }
      if (!res.ok) throw new Error(`photo-fetch ${res.status}`);
      const raw = await res.blob();
      if (!raw.size) throw new Error('photo-fetch empty');
      // the marker says how many bytes were stored: an answer of another length is not this photo (a portal's page,
      // a cut transfer) and is not kept
      if (cur.stored && Number.isFinite(cur.stored.size) && raw.size !== cur.stored.size) throw new Error('photo-fetch wrong length');
      const type = (cur.stored && cur.stored.type) || raw.type || '';
      const blob = raw.type === type ? raw : new Blob([raw], { type });
      const now = await idbGet('media', id);
      if (!now) return 'gone';
      if (!now.blob) await idbPut('media', { ...now, blob });          // bytes only: no op — there is nothing to tell the server
      failedAt.delete(id);
      emitChange({ type: 'media', id, birdId: now.birdId });
      return 'here';
    } catch {
      const n = f ? f.n + 1 : 1;
      failedAt.set(id, { n, notBefore: Date.now() + backoffDelay(n - 1) });
      return ctl && ctl.signal.aborted ? 'timeout' : 'failed';
    } finally { if (timer) clearTimeout(timer); }
  }).finally(() => { fetching.delete(id); });
  fetching.set(id, p);
  return p;
}
