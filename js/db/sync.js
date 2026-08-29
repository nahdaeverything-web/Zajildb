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

import { state, setSetting, idbGet } from './storage.js';
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
