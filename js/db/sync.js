// db/sync.js — accounts and the Supabase session.
//
// v1.9 Phase 2 installs the auth half: sign-in, sign-out, and the refresh
// loop. Push and pull land here in Phases 3 and 4 (SYNC-DESIGN §8).
//
// THE RULE THAT SHAPES THIS FILE: auth is required to SYNC, not to FUNCTION.
// Nothing here is on the path of any existing feature. The register, pedigrees,
// COI, breeding, certificates — all of it runs against IndexedDB and does not
// know this file exists. A device that can never reach the network, or was
// never configured at all, is a fully working Zajil. Every function below can
// fail, and none of those failures may reach the app.
//
// NETWORK FAILURE IS NOT AN AUTH VERDICT.
// This is the distinction the whole file is built around, because conflating
// the two is how apps sign people out for no reason. `fetch` rejecting means
// the phone is in a loft with no signal; a 5xx means the server is unwell.
// Neither says anything about whether the session is valid, so neither may
// ever clear a token. Only a 4xx with an auth body is the server actually
// saying "no", and only that clears the session.
//
// AN API KEY IS NEVER A BEARER VALUE (SPIKE §1). The publishable key travels
// in the `apikey` header and nowhere else; `Authorization: Bearer` carries the
// user's access token and nothing else. They are different kinds of thing, and
// the one time they were swapped in the spike the server's refusal was
// confusing rather than obvious.

import {
  state, setSetting, idbGet, idbGetAll, idbDelete, nowISO, allBirds, emitChange,
} from './storage.js';
import { findDuplicateRings } from '../engine/rings.js';
import { getOpsSinceSeq, logOp, markOpsSuperseded } from './oplog.js';
import { applySyncPut, applySyncDelete } from './records.js';
import { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } from '../sync-config.js';

/**
 * The four settings keys that hold the session.
 *
 * Named as a list because two other things depend on the exact set: signing
 * out must clear all of them, and the export boundary must refuse to carry any
 * of them (SYNC-DESIGN §9). A fifth key added here without updating those is
 * caught by tests/e2e/auth.py.
 */
export const AUTH_SETTING_KEYS = ['authAccessToken', 'authRefreshToken', 'authUserId', 'authEmail'];

/**
 * Thrown by the token endpoint helper. `kind` is the whole point:
 *
 *   'network'   fetch rejected, or the server returned 5xx. The session is
 *               untouched and the caller should back off and retry.
 *   'rejected'  the server answered 4xx: this credential is genuinely refused.
 *   'config'    no project URL or publishable key on this device. Not a
 *               failure of anything — sync simply is not set up here.
 */
export class AuthError extends Error {
  constructor(kind, status, detail) {
    super(`zajil/auth-${kind}`);
    this.name = 'AuthError';
    this.kind = kind;
    this.status = status ?? null;
    this.detail = detail ?? null;
  }
}

/**
 * Where this device syncs to. `globalThis.ZAJIL_SYNC_CONFIG` wins over the
 * shipped constants so a test can point at a stub and a self-hosted deployment
 * can point at its own project without a rebuild.
 *
 * `configured` is false on a stock build, and everything below is written to
 * do nothing quietly in that case rather than throw into the app.
 */
export function syncConfig() {
  const override = (typeof globalThis !== 'undefined' && globalThis.ZAJIL_SYNC_CONFIG) || {};
  const url = String(override.url ?? SUPABASE_URL ?? '').replace(/\/+$/, '');
  const publishableKey = String(override.publishableKey ?? SUPABASE_PUBLISHABLE_KEY ?? '');
  return { url, publishableKey, configured: Boolean(url && publishableKey) };
}

/** Is there a session on this device? Keyed on the REFRESH token, not the
 *  access token: an expired access token with a live refresh token is still a
 *  signed-in user, and treating it otherwise would sign people out hourly. */
export function isSignedIn() { return Boolean(state.settings.authRefreshToken); }

/** The session as the UI should describe it. Never includes a token. */
export function authState() {
  return {
    signedIn: isSignedIn(),
    email: state.settings.authEmail || null,
    userId: state.settings.authUserId || null,
  };
}

/**
 * Headers for a DATA request. The publishable key identifies the project; the
 * access token identifies the user. Both are required — Supabase rejects a
 * request carrying only one — and they are never interchangeable.
 */
export function authHeaders() {
  const { publishableKey } = syncConfig();
  const headers = { apikey: publishableKey };
  const access = state.settings.authAccessToken;
  if (access) headers.Authorization = `Bearer ${access}`;
  return headers;
}

async function storeSession(payload) {
  await setSetting('authAccessToken', payload.access_token || null);
  await setSetting('authRefreshToken', payload.refresh_token || null);
  // A refresh response does not always carry the user object. Absence means
  // "unchanged", so identity is only written when the server actually sends it
  // — overwriting it with null would lose the actorId on every refresh.
  if (payload.user) {
    await setSetting('authUserId', payload.user.id || null);
    await setSetting('authEmail', payload.user.email || null);
  }
}

async function clearSession() {
  for (const key of AUTH_SETTING_KEYS) await setSetting(key, null);
}

/**
 * Re-read the session from IndexedDB into the in-memory mirror.
 *
 * Deliberately reads the STORE, not `state.settings`: the whole reason to call
 * this is that a DIFFERENT instance on this device — the installed app while a
 * browser tab is open, or the reverse — wrote a fresher session that this
 * instance's memory has never seen.
 */
async function adoptStoredSession() {
  for (const key of AUTH_SETTING_KEYS) {
    const row = await idbGet('settings', key);
    state.settings[key] = row ? row.value : null;
  }
}

/**
 * POST to the token endpoint, classifying every failure as network or
 * rejection. This function is where the distinction is actually made; every
 * caller above just reads `err.kind`.
 */
async function tokenRequest(grantType, body) {
  const { url, publishableKey, configured } = syncConfig();
  if (!configured) throw new AuthError('config', null, 'no project URL or publishable key on this device');

  let res;
  try {
    res = await fetch(`${url}/auth/v1/token?grant_type=${grantType}`, {
      method: 'POST',
      headers: { apikey: publishableKey, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (err) {
    // fetch rejects ONLY on a network-level failure. This is the loft with no
    // signal, and it must never cost the user their session.
    throw new AuthError('network', null, String((err && err.message) || err));
  }
  if (res.status >= 500) {
    // the server answered, but not with a verdict on this credential
    throw new AuthError('network', res.status, 'server error');
  }
  let payload = null;
  try { payload = await res.json(); } catch { /* an error body is not reliably JSON */ }
  if (!res.ok) {
    const detail = payload && (payload.error_description || payload.msg || payload.error || null);
    throw new AuthError('rejected', res.status, detail);
  }
  return payload;
}

/**
 * Sign in with a password. Accounts are created by us through the admin API —
 * public signups are disabled, which is what makes "invite-only" true rather
 * than aspirational (SYNC-DESIGN §5).
 *
 * @throws {AuthError} kind 'network' (retry later), 'rejected' (wrong
 *   credentials), or 'config' (sync not set up on this device).
 */
export async function signIn(email, password) {
  const payload = await tokenRequest('password', { email, password });
  if (!payload || !payload.access_token || !payload.refresh_token) {
    // a 200 with no tokens is not a session, whatever else it is
    throw new AuthError('rejected', 200, 'the response carried no tokens');
  }
  await storeSession(payload);
  return authState();
}

/**
 * Sign out. Local only, and deliberately so: revoking server-side would need a
 * network call, and a sign-out that fails because the user is offline is a
 * sign-out that has failed at the one moment it is most likely to be wanted.
 * The refresh token is discarded here and expires on its own.
 */
export async function signOut() {
  await clearSession();
  return authState();
}

/**
 * Exchange the refresh token for a new pair.
 *
 * Never throws — the caller is a background loop, and an exception there would
 * be an app-level failure caused by the network. Returns:
 *
 *   { ok: true,  reason: 'refreshed' }   new tokens stored
 *   { ok: true,  reason: 'adopted' }     another instance won the race; its
 *                                        session was adopted and is valid
 *   { ok: false, reason: 'signed-out' }  nothing to refresh
 *   { ok: false, reason: 'network' }     offline or 5xx — TOKENS KEPT
 *   { ok: false, reason: 'config' }      sync not set up — TOKENS KEPT
 *   { ok: false, reason: 'rejected' }    genuinely refused — session cleared
 *
 * THE REFRESH TOKEN IS ROTATED. Every successful refresh returns a new one and
 * spends the old, so the stored value must be replaced, not kept.
 */
export async function refreshSession() {
  const sent = state.settings.authRefreshToken;
  if (!sent) return { ok: false, reason: 'signed-out', status: null };

  let payload;
  try {
    payload = await tokenRequest('refresh_token', { refresh_token: sent });
  } catch (err) {
    if (err.kind !== 'rejected') {
      // network or unconfigured: NOT a verdict on the session. Keep it.
      return { ok: false, reason: err.kind, status: err.status };
    }
    // ── re-read before declaring the session dead ──
    // The installed app and a browser tab share one IndexedDB, so both can
    // attempt a refresh with the same token and one loses. Supabase applies a
    // reuse grace interval for exactly this case. Before concluding the
    // session is gone, look at what is actually stored: if it is no longer the
    // token we sent, the other instance already refreshed successfully and
    // wrote a live pair. Signing out here would sign out BOTH instances over a
    // race that resolved itself.
    const row = await idbGet('settings', 'authRefreshToken');
    const stored = row ? row.value : null;
    if (stored && stored !== sent) {
      await adoptStoredSession();
      return { ok: true, reason: 'adopted', status: err.status };
    }
    await clearSession();
    return { ok: false, reason: 'rejected', status: err.status };
  }

  if (!payload || !payload.access_token || !payload.refresh_token) {
    return { ok: false, reason: 'rejected', status: 200 };
  }
  await storeSession(payload);
  return { ok: true, reason: 'refreshed', status: null };
}

/**
 * An access token to make a data request with, or null.
 *
 * Refresh is REACTIVE, not scheduled: there is no stored expiry to watch and
 * no timer to drift. A caller uses this token, and on a 401 refreshes once and
 * retries. Storing an expiry would add a settings key to hold a number the
 * server already tells us the truth about.
 */
export async function ensureAccessToken() {
  if (!isSignedIn()) return null;
  if (state.settings.authAccessToken) return state.settings.authAccessToken;
  const result = await refreshSession();
  return result.ok ? (state.settings.authAccessToken || null) : null;
}

// ─────────────────────────────── push ───────────────────────────────
// The op log is already an ordered, complete record of what this device did.
// Push replays it (SYNC-DESIGN §2). Nothing here invents state: every row sent
// is derived from an op that was written at the moment the user acted.

/** Ops taken per cycle. Small because a failed batch is retried whole, and 200
 *  records of jsonb is a comfortable request on a weak connection (§11). */
export const PUSH_BATCH = 200;

/** Acked ops are prunable, but this many most-recent ops are kept regardless,
 *  as a forensic tail (§2 compaction). */
export const OPLOG_KEEP = 500;

/** Identical short counts before a batch is presumed poisoned and bisected. */
const POISON_ATTEMPTS = 3;

/** syncAnomalies is a diagnostic surface, not a log. Newest kept. */
const MAX_ANOMALIES = 100;

/**
 * One op to one server row (§2a).
 *
 * THE TIMESTAMP RULE: `updated_at` is the OP's `at` — when the operation
 * happened — and NEVER `record.updatedAt`.
 *
 * This is not a detail. `restoreBird` deliberately reinstates a record's
 * ORIGINAL timestamps, because an undo restores what was there rather than
 * making a new edit. So `record.updatedAt` can move BACKWARDS, and a sync layer
 * that trusted it would diverge permanently: an undo stamped 09:00 loses to
 * another device's 10:00 tombstone, that device skips the restore, and the two
 * never converge. Operation time cannot move backwards, so it can be trusted.
 *
 * `owner` is omitted deliberately — the server defaults it to auth.uid(), which
 * is what stops a client writing into someone else's rows even if it tried.
 * `server_seq` is omitted because the trigger assigns it.
 */
export function opToRow(op) {
  return {
    store: op.store,
    record_id: op.recordId,
    // a delete carries the record's last-known body rather than null: it costs
    // little and makes an audit or a server-side undo possible later. `{}` only
    // when an op genuinely captured no record, since the column is NOT NULL.
    data: op.record || {},
    deleted: op.op === 'delete',
    updated_at: op.at,
    device_id: op.deviceId,
    op_seq: op.seq,
  };
}

/**
 * Collapse ops to one row per (store, record). Replaying three edits to one
 * bird is three round trips for one final state.
 *
 * The LAST op wins — its `at`, `data` and `seq` — which is why the input must
 * be in seq order. Map insertion order is preserved, so the request body still
 * reads oldest-record-first and a failing batch is easier to read.
 */
export function collapseOps(ops) {
  const byRecord = new Map();
  for (const op of ops) byRecord.set(`${op.store} ${op.recordId}`, opToRow(op));
  return [...byRecord.values()];
}

/** POST rows, classifying the outcome the same way the token endpoint does. */
async function sendRows(rows, { allowRefresh = true } = {}) {
  const { url, configured } = syncConfig();
  if (!configured) return { kind: 'config', landed: 0, status: null, body: null };

  let res;
  try {
    res = await fetch(`${url}/rest/v1/sync_records`, {
      method: 'POST',
      headers: {
        ...authHeaders(),
        'Content-Type': 'application/json',
        Prefer: 'resolution=merge-duplicates,return=representation',
      },
      body: JSON.stringify(rows),
    });
  } catch (err) {
    return { kind: 'network', landed: 0, status: null, body: String((err && err.message) || err) };
  }

  if (res.status === 401 && allowRefresh) {
    // The access token expired mid-cycle. Refresh is REACTIVE — this is the
    // 401 it reacts to — and the batch is retried once, never acked on the way.
    const refreshed = await refreshSession();
    if (refreshed.ok) return sendRows(rows, { allowRefresh: false });
    // NOT 'rejected'. A rejection means the SERVER refused this record, and
    // that is what bisection hunts for and eventually marks poison. A session
    // that could not be refreshed says nothing about any record: treating it
    // as a rejection would let a expiring session mark a whole batch poisoned,
    // ack past it and prune the ops — losing writes that never left the device.
    return { kind: 'auth', landed: 0, status: 401,
             body: `session could not be refreshed (${refreshed.reason})` };
  }
  if (res.status >= 500) return { kind: 'network', landed: 0, status: res.status, body: 'server error' };

  const text = await res.text();
  if (!res.ok) return { kind: 'rejected', landed: 0, status: res.status, body: text.slice(0, 300) };

  // THE ACK CONDITION (§2, SPIKE §4d). A write blocked by row-level security
  // returns 200 with ZERO rows, so a 200 alone must never advance the cursor.
  // Count the rows that actually came back.
  let returned = [];
  try { returned = JSON.parse(text); } catch { returned = []; }
  const landed = Array.isArray(returned) ? returned.length : 0;
  return { kind: 'ok', landed, status: res.status, body: text.slice(0, 300), rows: returned };
}

/**
 * Isolate the offender in log2(n) round trips.
 *
 * Reached only after POISON_ATTEMPTS identical short counts, so a healthy batch
 * never pays for it. A half that lands whole is done; a half that comes back
 * short is split again; a SINGLE row that comes back short is the poison.
 */
async function bisect(rows) {
  const poison = [];
  const stack = [rows];
  while (stack.length) {
    const chunk = stack.pop();
    const result = await sendRows(chunk);
    // Only a 200 that omits the row identifies a poison record. Every other
    // outcome — offline, 5xx, expired session, 4xx — is request-level and says
    // nothing about any record, so bisection abandons rather than concluding.
    if (result.kind !== 'ok') return { resolved: false, poison };
    if (result.kind === 'ok' && result.landed === chunk.length) continue;   // this half is fine
    if (chunk.length === 1) { poison.push({ row: chunk[0], result }); continue; }
    const mid = Math.floor(chunk.length / 2);
    stack.push(chunk.slice(0, mid), chunk.slice(mid));
  }
  return { resolved: true, poison };
}

/** Newest first, capped. A diagnostic surface for الأدوات, not a log. */
export function listSyncAnomalies() {
  const list = state.settings.syncAnomalies;
  return Array.isArray(list) ? list : [];
}

async function recordAnomaly(entry) {
  await setSetting('syncAnomalies', [entry, ...listSyncAnomalies()].slice(0, MAX_ANOMALIES));
}

/**
 * Drop ops the server has verifiably taken (§2 compaction — the v1.8 deferral).
 *
 * An op with `seq <= lastAckedSeq` is prunable. The most recent OPLOG_KEEP ops
 * are kept regardless of ack state as a forensic tail. Tombstones are NEVER
 * pruned: they are the resurrection protection and they are cheap.
 *
 * A device that has never synced has lastAckedSeq = 0 and prunes nothing, so
 * its history is exactly what v1.8 kept.
 */
export async function pruneOplog() {
  const acked = state.settings.lastAckedSeq || 0;
  if (!acked) return 0;
  const ops = await getOpsSinceSeq(0);                       // seq order
  const tail = new Set(ops.slice(-OPLOG_KEEP).map((o) => o.opId));
  let pruned = 0;
  for (const op of ops) {
    if (op.seq > acked || tail.has(op.opId)) continue;
    await idbDelete('oplog', op.opId);
    pruned++;
  }
  return pruned;
}

async function ackThrough(seq) {
  await setSetting('lastAckedSeq', seq);
  await setSetting('lastSyncAt', nowISO());
  await setSetting('lastSyncError', null);
  return pruneOplog();
}

// Identical short counts are counted against the batch that produced them, so
// an unrelated batch never inherits another's suspicion. Module state, not
// persisted: a reload restarts the count, which errs toward retrying rather
// than toward declaring a record poisoned.
let attempts = { key: null, count: 0 };

/**
 * One push cycle: take ops, collapse, send, verify, ack.
 *
 * Never throws — the caller is a background loop. Returns:
 *
 *   { ok: true,  reason: 'idle' }        nothing to push
 *   { ok: true,  reason: 'acked' }       every row landed; cursor advanced
 *   { ok: true,  reason: 'bisected' }    poison isolated, recorded, acked past
 *   { ok: false, reason: 'short-count' } retry this batch (attempt N of 3)
 *   { ok: false, reason: 'network' }     offline or 5xx — cursor NOT advanced
 *   { ok: false, reason: 'config' }      sync not set up
 *   { ok: false, reason: 'signed-out' }  nothing to push as
 */
export async function pushOnce() {
  if (!syncConfig().configured) return { ok: false, reason: 'config', pushed: 0 };
  if (!isSignedIn()) return { ok: false, reason: 'signed-out', pushed: 0 };

  const since = state.settings.lastAckedSeq || 0;
  const ops = (await getOpsSinceSeq(since)).slice(0, PUSH_BATCH);
  if (!ops.length) return { ok: true, reason: 'idle', pushed: 0, rows: 0 };

  const maxSeq = ops[ops.length - 1].seq;
  // A superseded op lost a conflict at pull time. It stays in the log as
  // history (§4) but must never be sent, or it would overwrite the very
  // version that beat it.
  const live = ops.filter((op) => !op.superseded);
  const rows = collapseOps(live);
  if (!rows.length) {
    // every op in the window lost. Nothing to send, but the window is handled.
    const pruned = await ackThrough(maxSeq);
    return { ok: true, reason: 'acked', pushed: 0, rows: 0, ops: ops.length,
             superseded: ops.length, lastAckedSeq: maxSeq, pruned };
  }
  const result = await sendRows(rows);

  if (result.kind === 'network' || result.kind === 'config') {
    await setSetting('lastSyncError', { key: 'sync.err.network', status: result.status, at: nowISO() });
    return { ok: false, reason: result.kind, status: result.status, pushed: 0, rows: rows.length };
  }

  // The session expired and could not be renewed. Deliberately NOT counted as
  // a short count: the batch is untouched, the cursor does not move, and
  // nothing is suspected of being poison. The next cycle sees a signed-out
  // device and stops before sending anything.
  if (result.kind === 'auth') {
    await setSetting('lastSyncError', { key: 'sync.err.session', status: result.status, at: nowISO() });
    return { ok: false, reason: 'auth', status: result.status, pushed: 0, rows: rows.length };
  }

  if (result.kind === 'ok' && result.landed === rows.length) {
    attempts = { key: null, count: 0 };
    const pruned = await ackThrough(maxSeq);
    return { ok: true, reason: 'acked', pushed: rows.length, rows: rows.length,
             ops: ops.length, lastAckedSeq: maxSeq, pruned };
  }

  // ── a 4xx is a REQUEST-level failure, never a verdict on a record ──
  // This distinction was learned from the live server, and it is load-bearing.
  // Row-level security does NOT reject with a status: a blocked write comes
  // back 200 with the row simply ABSENT (SPIKE §4d). So a short count is the
  // only signal that identifies a poison RECORD, and a 4xx is something else
  // entirely — a misconfigured grant, a malformed request, a revoked policy.
  // All of them affect every record equally and none of them are anyone's
  // fault but ours.
  //
  // Treating a 4xx as "a short count of zero" (which this did at first) means
  // three retries, then bisection down to single rows, then EVERY record marked
  // poison, acked past and pruned — the entire queue discarded because the
  // server was misconfigured. A real 403 during live testing did exactly that.
  // So it stops here: loud, not acked, nothing blamed on a record.
  if (result.kind === 'rejected') {
    await setSetting('lastSyncError', { key: 'sync.err.rejected', status: result.status,
                                        body: result.body, at: nowISO() });
    return { ok: false, reason: 'rejected', status: result.status, body: result.body,
             pushed: 0, rows: rows.length };
  }

  // Keyed on the first op's opId — a uuid — not on its seq. Seq-based keys can
  // repeat across genuinely different batches (any device whose counter is ever
  // reset), and a batch inheriting another's suspicion would bisect on its first
  // short count instead of its third.
  const key = `${ops[0].opId}-${maxSeq}-${rows.length}`;
  attempts = (attempts.key === key) ? { key, count: attempts.count + 1 } : { key, count: 1 };
  if (attempts.count < POISON_ATTEMPTS) {
    await setSetting('lastSyncError', { key: 'sync.err.short', status: result.status, at: nowISO() });
    return { ok: false, reason: 'short-count', attempt: attempts.count,
             landed: result.landed, expected: rows.length, pushed: 0, rows: rows.length };
  }

  // Three identical short counts: bisect. "Retried rather than acked" is
  // correct exactly once. Repeated forever it is a deadlock — one permanently
  // rejected record blocks all sync, for every store, indefinitely, and the
  // user sees only a sync that never completes.
  const { resolved, poison } = await bisect(rows);
  if (!resolved) {
    return { ok: false, reason: 'network', pushed: 0, rows: rows.length, bisecting: true };
  }
  for (const p of poison) {
    await recordAnomaly({
      at: nowISO(),
      store: p.row.store,
      recordId: p.row.record_id,
      status: p.result.status,
      body: p.result.body,
    });
  }
  attempts = { key: null, count: 0 };
  // An anomaly is loud but never a roadblock: advance past the poison so the
  // rest of the queue drains. A correct-looking queue that never empties is
  // worse than a visible, named failure the fancier can be asked about.
  const pruned = await ackThrough(maxSeq);
  return { ok: true, reason: 'bisected', pushed: rows.length - poison.length, rows: rows.length,
           ops: ops.length, poison: poison.length, lastAckedSeq: maxSeq, pruned };
}

/**
 * Push until the queue is drained or something stops it.
 *
 * `maxCycles` is a backstop, not a policy: real pacing (backoff, jitter,
 * reconnect detection) is §11 and lands with the sync loop in Phase 6. A
 * short-count result ends the run rather than spinning, because the retry it
 * asks for is supposed to arrive after a backoff, not immediately.
 */
export async function pushAll({ maxCycles = 50 } = {}) {
  let pushed = 0, cycles = 0, poison = 0;
  while (cycles < maxCycles) {
    cycles++;
    const r = await pushOnce();
    pushed += r.pushed || 0;
    poison += r.poison || 0;
    if (r.reason === 'idle') return { ok: true, reason: 'idle', pushed, cycles, poison };
    if (!r.ok) return { ...r, pushed, cycles, poison };
  }
  return { ok: false, reason: 'max-cycles', pushed, cycles, poison };
}

// ─────────────────────────────── pull ───────────────────────────────
// A cursor on server_seq, and nothing else. server_seq is assigned per row by
// the trigger, so a row updated after our cursor moves ABOVE it and is
// re-delivered — which is why the trigger fires on UPDATE and not only on
// INSERT (SYNC-DESIGN §3).

/** Rows per pull page. Larger than a push batch: a pull is cheap to redo and
 *  benefits from fewer round trips (§11). */
export const PULL_PAGE = 500;

/**
 * Fetch one page of rows above the cursor.
 *
 * Classified exactly as push classifies its outcomes, and for the same reason:
 * offline is not a verdict on anything.
 */
async function fetchPage(cursor, { allowRefresh = true } = {}) {
  const { url, configured } = syncConfig();
  if (!configured) return { kind: 'config', rows: [], status: null, body: null };

  const query = `select=*&server_seq=gt.${encodeURIComponent(cursor)}` +
                `&order=server_seq.asc&limit=${PULL_PAGE}`;
  let res;
  try {
    res = await fetch(`${url}/rest/v1/sync_records?${query}`, { headers: authHeaders() });
  } catch (err) {
    return { kind: 'network', rows: [], status: null, body: String((err && err.message) || err) };
  }
  if (res.status === 401 && allowRefresh) {
    const refreshed = await refreshSession();
    if (refreshed.ok) return fetchPage(cursor, { allowRefresh: false });
    return { kind: 'auth', rows: [], status: 401, body: 'session could not be refreshed' };
  }
  if (res.status >= 500) return { kind: 'network', rows: [], status: res.status, body: 'server error' };

  const text = await res.text();
  if (!res.ok) return { kind: 'rejected', rows: [], status: res.status, body: text.slice(0, 300) };
  let rows = [];
  try { rows = JSON.parse(text); } catch { rows = []; }
  if (!Array.isArray(rows)) rows = [];
  return { kind: 'ok', rows, status: res.status, body: null };
}

/**
 * Apply one page of rows, in server_seq order.
 *
 * THE CURSOR ADVANCES ONLY OVER ROWS ACTUALLY APPLIED — and a row deliberately
 * skipped (a newer local tombstone wins) counts as handled, because re-fetching
 * it forever would never change the outcome. A row that THREW is not handled:
 * the cursor stops below it so the next pull sees it again.
 */
async function applyPage(rows) {
  let applied = 0, skipped = 0, cursor = null, lost = 0;
  const anomalies = [];
  const pending = await pendingOpIndex();
  for (const row of rows) {
    try {
      // ── §4, per-record last-write-wins ──
      // The incoming row meets whatever this device has written but not yet
      // pushed. If the local op is newer, the row loses and is left alone: our
      // push will carry the winner. If the row wins, any local op it beat is
      // SUPERSEDED — otherwise push would send the loser straight afterwards
      // and overwrite the version that just won.
      const local = pending.get(`${row.store} ${row.record_id}`);
      if (local && !remoteWins(row, local)) {
        skipped++;
        cursor = row.server_seq;
        continue;
      }
      if (local) { lost += await markOpsSuperseded(local.opIds); }

      const result = row.deleted
        ? await applySyncDelete(row.store, row.record_id, row.updated_at)
        : await applySyncPut(row.store, row.data, row.updated_at);
      if (result.applied) applied++; else skipped++;
      if (result.anomaly) {
        anomalies.push({ at: nowISO(), store: row.store, recordId: row.record_id,
                         status: null, body: JSON.stringify(result.anomaly).slice(0, 300) });
      }
    } catch (err) {
      // Stop the cursor BELOW this row. Advancing past a row that failed to
      // apply would lose it permanently: nothing ever re-delivers a row the
      // cursor has passed.
      anomalies.push({ at: nowISO(), store: row.store, recordId: row.record_id,
                       status: null, body: `apply failed: ${String((err && err.message) || err)}`.slice(0, 300) });
      return { applied, skipped, cursor, anomalies, lost, stoppedAt: row.server_seq };
    }
    cursor = row.server_seq;
  }
  return { applied, skipped, cursor, anomalies, lost, stoppedAt: null };
}

/**
 * One pull cycle. Never throws.
 *
 *   { ok: true,  reason: 'idle' }      nothing above the cursor
 *   { ok: true,  reason: 'applied' }   a page was applied; cursor advanced
 *   { ok: false, reason: 'network' }   offline or 5xx — cursor unmoved
 *   { ok: false, reason: 'rejected' }  request-level failure — cursor unmoved
 *   { ok: false, reason: 'auth' }      session gone — cursor unmoved
 *   { ok: false, reason: 'config' | 'signed-out' }
 */
export async function pullOnce() {
  if (!syncConfig().configured) return { ok: false, reason: 'config', applied: 0 };
  if (!isSignedIn()) return { ok: false, reason: 'signed-out', applied: 0 };

  const cursor = state.settings.syncCursor || 0;
  const page = await fetchPage(cursor);
  if (page.kind !== 'ok') {
    await setSetting('lastSyncError', { key: `sync.err.${page.kind}`, status: page.status, at: nowISO() });
    return { ok: false, reason: page.kind, status: page.status, applied: 0, cursor };
  }
  if (!page.rows.length) return { ok: true, reason: 'idle', applied: 0, skipped: 0, cursor, more: false };

  const result = await applyPage(page.rows);
  for (const anomaly of result.anomalies) await recordAnomaly(anomaly);
  if (result.cursor !== null) await setSetting('syncCursor', result.cursor);
  await setSetting('lastSyncAt', nowISO());
  if (!result.anomalies.length) await setSetting('lastSyncError', null);

  return {
    ok: true,
    reason: result.stoppedAt !== null ? 'stalled' : 'applied',
    applied: result.applied,
    skipped: result.skipped,
    superseded: result.lost,
    rows: page.rows.length,
    cursor: state.settings.syncCursor || cursor,
    anomalies: result.anomalies.length,
    // a full page means there is probably more behind it
    more: result.stoppedAt === null && page.rows.length === PULL_PAGE,
  };
}

/** Pull until a short page arrives or something stops it. */
export async function pullAll({ maxPages = 100 } = {}) {
  let applied = 0, skipped = 0, pages = 0;
  while (pages < maxPages) {
    pages++;
    const r = await pullOnce();
    applied += r.applied || 0;
    skipped += r.skipped || 0;
    if (!r.ok) return { ...r, applied, skipped, pages };
    if (r.reason === 'idle' || !r.more) return { ok: true, reason: 'idle', applied, skipped, pages };
  }
  return { ok: false, reason: 'max-pages', applied, skipped, pages };
}


// ───────────────────── conflicts: per-record last-write-wins ─────────────────
// Both sides carry the op that produced the record, so both sides carry a time
// the operation HAPPENED. Compare those (SYNC-DESIGN §4). Per record, not per
// field: for one fancier editing their own bird on two devices, "the later one
// is what they meant" is almost always right, and per-field merge is machinery
// for a conflict that does not arise.

/**
 * The latest UNPUSHED op per record, indexed by `${store} ${recordId}`.
 *
 * Built once per page rather than queried per row: a 500-row page against a
 * few thousand ops would otherwise be a quadratic scan on a phone.
 *
 * Superseded ops are excluded — they already lost, and a loser must not go on
 * winning arguments.
 */
async function pendingOpIndex() {
  const since = state.settings.lastAckedSeq || 0;
  const index = new Map();
  for (const op of await getOpsSinceSeq(since)) {
    if (op.superseded) continue;
    const key = `${op.store} ${op.recordId}`;
    const seen = index.get(key);
    if (seen) { seen.opIds.push(op.opId); if (op.at > seen.at) { seen.at = op.at; seen.deviceId = op.deviceId; } }
    else index.set(key, { at: op.at, deviceId: op.deviceId || '', opIds: [op.opId] });
  }
  return index;
}

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

// ───────────────────────────── first login (§6) ─────────────────────────────

/**
 * Enqueue every local record as a synthetic op, so records made before this
 * device knew about an account still reach the server.
 *
 * THE `at` IS EACH RECORD'S OWN `updatedAt`, NOT now(). A laptop last used
 * months ago holds stale copies; stamping its synthetic ops with today's time
 * would make every one of them beat the fresher data in LWW, and the stale
 * device would silently overwrite edits made on the phone last week — simply
 * by logging in. Using the record's own time says what is true: this is what
 * this device knew, as of when it knew it. Fresh data then wins.
 *
 * Ordinary `origin: 'user'` ops. Nothing is special-cased in push itself.
 */
export async function enqueueFirstSyncOps() {
  let count = 0;
  const stores = [['lofts', 'lofts'], ['birds', 'birds'], ['pairs', 'pairs'],
                  ['raceResults', 'raceResults'], ['healthEvents', 'healthEvents']];
  for (const [store, mirror] of stores) {
    for (const record of state[mirror].values()) {
      await logOp({ origin: 'user', store, op: 'put', recordId: record.id, record,
                    changed: Object.keys(record),
                    at: record.updatedAt || record.createdAt || nowISO() });
      count++;
    }
  }
  // media metadata only — opRecord strips the blob, and blobs do not sync (§7)
  for (const m of await idbGetAll('media')) {
    await logOp({ origin: 'user', store: 'media', op: 'put', recordId: m.id, record: m,
                  changed: ['id', 'birdId', 'kind', 'subtype', 'name', 'addedAt'],
                  at: m.addedAt || nowISO() });
    count++;
  }
  return count;
}

/** Has this device ever completed a sync? */
export function hasEverSynced() { return Boolean(state.settings.lastSyncAt); }

/**
 * Birds that share a ring after a sync — very likely one physical bird wearing
 * two records.
 *
 * Records carry client-generated uuids, so two devices that never synced
 * generated DIFFERENT ids for the same bird. After the first sync both records
 * exist, both valid, both surviving. That is not automatically solvable and
 * guessing would be worse: a ring is the natural business key but deliberately
 * is NOT identity — birds carry several rings and rings get reused.
 *
 * So: count them, say so once, and let the fancier decide. Only they know
 * whether two records are one bird.
 */
export function duplicateRingCount() {
  return findDuplicateRings(allBirds()).length;
}

/**
 * A full cycle.
 *
 * ORDER: pull, resolve, then push — EXCEPT on a device that has never synced
 * and holds local data, which pushes first (§6).
 *
 * Steady state pulls first because that is the only ordering under which §4's
 * last-write-wins actually decides anything. Pushing first sends a possibly
 * stale record into a blind upsert, which overwrites fresher server data
 * before any comparison happens; pulling first lets the comparison run, so the
 * loser is superseded rather than pushed. Echo prevention is what makes this
 * safe — a pulled record logs no op, so pulling first cannot cause
 * server-derived data to be pushed back.
 */
export async function syncOnce() {
  if (!syncConfig().configured) return { ok: false, reason: 'config' };
  if (!isSignedIn()) return { ok: false, reason: 'signed-out' };

  if (!hasEverSynced()) {
    // First login. Local records reach the server before anything overwrites
    // them, carrying each record's own time so freshness still decides.
    const enqueued = await enqueueFirstSyncOps();
    const push = await pushAll();
    const pull = await pullAll();
    const duplicates = duplicateRingCount();
    await setSetting('syncDuplicateNotice', duplicates || null);
    emitChange({ type: 'sync-complete', firstLogin: true, duplicates });
    return { ok: Boolean(push.ok && pull.ok), firstLogin: true, enqueued, push, pull, duplicates };
  }

  const pull = await pullAll();
  const push = await pushAll();
  emitChange({ type: 'sync-complete', firstLogin: false, duplicates: 0 });
  return { ok: Boolean(pull.ok && push.ok), firstLogin: false, push, pull };
}

/**
 * The one-time notice after a first sync, or null.
 *
 * Read once and cleared: it is a notice, not a state. The duplicates remain
 * findable in الأدوات for as long as they exist.
 */
export async function takeSyncDuplicateNotice() {
  const n = state.settings.syncDuplicateNotice;
  if (!n) return null;
  await setSetting('syncDuplicateNotice', null);
  return n;
}
