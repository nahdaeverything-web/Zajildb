// tests/auth.test.js — the parts of auth that need no browser.
//
// Everything here is pure: configuration resolution, header shape, error
// classification, and the export filter. The flows that touch IndexedDB or the
// network — sign-in, refresh, the multi-instance race — are in
// tests/e2e/auth.py, because faking IndexedDB in node would be testing the
// fake.

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, assert, assertEq } from './harness.js';
import {
  state, syncConfig, authHeaders, AuthError, isSignedIn, authState,
  exportableSettings, SENSITIVE_SETTING_PREFIXES, AUTH_SETTING_KEYS,
} from '../js/db.js';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Run with a stubbed config and session, then put everything back. */
function withSession(config, settings, fn) {
  const savedConfig = globalThis.ZAJIL_SYNC_CONFIG;
  const savedSettings = state.settings;
  globalThis.ZAJIL_SYNC_CONFIG = config;
  state.settings = { ...settings };
  try { return fn(); } finally {
    globalThis.ZAJIL_SYNC_CONFIG = savedConfig;
    state.settings = savedSettings;
  }
}

const STUB = { url: 'https://stub.zajil.test', publishableKey: 'sb_publishable_STUB' };

test('auth: a stock build is unconfigured, and says so rather than throwing', () => {
  withSession(undefined, {}, () => {
    const c = syncConfig();
    assertEq(c.configured, false, 'a shipped build must not point anywhere');
    assertEq(c.url, '', `url should be empty, got ${c.url}`);
    assertEq(c.publishableKey, '', 'publishable key should be empty');
  });
});

test('auth: the config override wins and a trailing slash is normalised away', () => {
  withSession({ url: 'https://x.supabase.co///', publishableKey: 'sb_publishable_K' }, {}, () => {
    const c = syncConfig();
    assertEq(c.url, 'https://x.supabase.co', `trailing slashes must go or every URL doubles up: ${c.url}`);
    assertEq(c.configured, true);
  });
});

test('auth: the publishable key travels in apikey and NEVER as a Bearer value', () => {
  // SPIKE §1: the new-style keys are rejected as Authorization: Bearer, and
  // the failure is confusing rather than obvious. Assert the shape directly.
  withSession(STUB, { authAccessToken: 'access-token-abc' }, () => {
    const h = authHeaders();
    assertEq(h.apikey, 'sb_publishable_STUB', 'the project key belongs in apikey');
    assertEq(h.Authorization, 'Bearer access-token-abc', 'the USER token belongs in Authorization');
    assert(!String(h.Authorization).includes('sb_publishable'),
      'an API key must never appear as a Bearer value');
    assert(!String(h.apikey).startsWith('Bearer'), 'apikey must not be prefixed');
  });
});

test('auth: with no access token there is no Authorization header at all', () => {
  withSession(STUB, {}, () => {
    const h = authHeaders();
    assertEq(h.apikey, 'sb_publishable_STUB');
    assertEq('Authorization' in h, false, 'an empty Bearer is worse than none — it looks like a session');
  });
});

test('auth: signed-in is keyed on the REFRESH token, not the access token', () => {
  // an expired access token with a live refresh token is still a session;
  // treating it otherwise would sign people out every hour
  withSession(STUB, { authRefreshToken: 'r1', authEmail: 'a@b.test', authUserId: 'u1' }, () => {
    assertEq(isSignedIn(), true, 'a refresh token alone is a session');
    assertEq(authState().email, 'a@b.test');
    assertEq(authState().userId, 'u1');
  });
  withSession(STUB, { authAccessToken: 'a1' }, () => {
    assertEq(isSignedIn(), false, 'an access token alone is a leftover, not a session');
  });
});

test('auth: authState never carries a token', () => {
  withSession(STUB, { authAccessToken: 'ACCESS', authRefreshToken: 'REFRESH', authEmail: 'e@f.test' }, () => {
    const json = JSON.stringify(authState());
    assert(!json.includes('ACCESS') && !json.includes('REFRESH'),
      `authState leaked a token: ${json}`);
  });
});

test('auth: AuthError separates network failure from rejection', () => {
  const net = new AuthError('network', null, 'failed to fetch');
  const rej = new AuthError('rejected', 400, 'invalid grant');
  assertEq(net.kind, 'network');
  assertEq(rej.kind, 'rejected');
  assertEq(rej.status, 400);
  assertEq(net.name, 'AuthError');
  assertEq(net.message, 'zajil/auth-network');
});

test('auth: every session key is covered by the export filter', () => {
  // a fifth session key added without extending the prefixes would walk
  // straight into an export
  const uncovered = AUTH_SETTING_KEYS.filter(
    (k) => !SENSITIVE_SETTING_PREFIXES.some((p) => k.startsWith(p)));
  assertEq(uncovered.length, 0,
    `these session keys are not caught by SENSITIVE_SETTING_PREFIXES: ${uncovered.join(', ')}`);
});

test('auth: exportableSettings strips every auth key and keeps the rest', () => {
  const filtered = exportableSettings({
    authAccessToken: 'ACCESS', authRefreshToken: 'REFRESH', authUserId: 'u1', authEmail: 'e@f.test',
    lang: 'ar', coiDepth: 6, deviceId: 'dev-1', currentLoftId: 'loft-1',
  });
  const leaked = Object.keys(filtered).filter((k) => k.startsWith('auth'));
  assertEq(leaked.length, 0, `credentials survived the filter: ${leaked.join(', ')}`);
  assertEq(Object.keys(filtered).sort().join(','), 'coiDepth,currentLoftId,deviceId,lang',
    'the filter must not eat ordinary settings');
  assertEq(JSON.stringify(filtered).includes('ACCESS'), false);
});

test('guard: no secret or service-role key anywhere in the client source', () => {
  // The secret key bypasses row-level security entirely. It belongs on a
  // server or in a throwaway spike script, never in anything a browser loads.
  const files = [];
  (function walk(dir) {
    for (const name of readdirSync(dir)) {
      const p = join(dir, name);
      if (statSync(p).isDirectory()) walk(p);
      else if (name.endsWith('.js')) files.push({ rel: relative(ROOT, p), src: readFileSync(p, 'utf8') });
    }
  })(join(ROOT, 'js'));
  const hits = [];
  for (const f of files) {
    f.src.split('\n').forEach((line, i) => {
      if (/^\s*(\/\/|\*)/.test(line)) return;                 // prose may name them
      if (/sb_secret_|service_role|SUPABASE_SECRET|SERVICE_ROLE/.test(line))
        hits.push(`${f.rel}:${i + 1}  ${line.trim().slice(0, 80)}`);
    });
  }
  assertEq(hits.length, 0, `a secret key must never reach the client:\n  ${hits.join('\n  ')}`);
});

test('guard: js/sync-config.js ships with no endpoint filled in', () => {
  // A live project URL in a public repository is a release-time decision, not
  // something that arrives by accident in a feature commit.
  const src = readFileSync(join(ROOT, 'js', 'sync-config.js'), 'utf8');
  const url = /export const SUPABASE_URL = '([^']*)'/.exec(src);
  const key = /export const SUPABASE_PUBLISHABLE_KEY = '([^']*)'/.exec(src);
  assert(url && key, 'sync-config.js must declare both constants as plain string literals');
  assertEq(url[1], '', `SUPABASE_URL is filled in: ${url[1].slice(0, 24)}…`);
  assertEq(key[1], '', 'SUPABASE_PUBLISHABLE_KEY is filled in');
});
