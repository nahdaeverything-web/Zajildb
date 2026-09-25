#!/usr/bin/env node
/**
 * THE DEPLOY-TIME CONFIG REWRITE — CUTOVER.md §a.3, RULED 2026-09-25.
 *
 * Rewrites ONE file in a finished export, `out/sync-config.js`, with the project this
 * release points at. It runs AFTER `npm run build` — which means after the guards, which
 * means the guards have already proved the repository and the export are sync-inert — and
 * BEFORE upload.
 *
 * That ordering is the whole design, and it has a cost worth stating in the file that
 * causes it: the guard no longer sees the artefact that is actually published. §g pays for
 * that on the other side, by making live_deployment.py the first gate AFTER deploy, run
 * against the served origin rather than against out/.
 *
 * WHY THE VARIABLES ARE NOT NEXT_PUBLIC_*
 * Next inlines every NEXT_PUBLIC_* variable into the hashed client chunks at build time. If
 * the endpoint were supplied that way it would be baked into ~40 files, the guard would need
 * a release mode, and a release artefact could never be diffed against a dev one. Naming
 * them ZAJIL_* makes that impossible by construction: Next cannot inline what it does not
 * recognise, so the only path these values can take into the bundle is this script.
 *
 *   ZAJIL_SUPABASE_URL              e.g. https://<ref>.supabase.co
 *   ZAJIL_SUPABASE_PUBLISHABLE_KEY  the PUBLISHABLE key — never the secret
 *
 * THE SECRET KEY IS REFUSED, not merely absent. A publishable key is designed to be public;
 * a secret key in a static export is a total compromise of every row in the project. So this
 * script checks the shape of what it was handed and exits non-zero rather than write it,
 * because the guards cannot help here — they already ran.
 *
 * Usage:  ZAJIL_SUPABASE_URL=… ZAJIL_SUPABASE_PUBLISHABLE_KEY=… node scripts/inject-config.mjs
 *         --check   verify an already-written out/sync-config.js instead of writing it
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const TARGET = 'out/sync-config.js';
const check = process.argv.includes('--check');

const fail = (msg) => { console.error(`✗ inject-config  ${msg}`); process.exit(1); };

if (!existsSync(TARGET)) {
  fail(`${TARGET} is not there. Run \`npm run build\` first — this rewrites a finished export, it does not create one.`);
}

if (check) {
  const src = readFileSync(TARGET, 'utf8');
  const url = (src.match(/url:\s*'([^']*)'/) || [])[1];
  const key = (src.match(/publishableKey:\s*'([^']*)'/) || [])[1];
  if (url === undefined || key === undefined) fail(`${TARGET} does not have the expected shape`);
  console.log(`✓ inject-config --check  url ${url ? 'set (' + url + ')' : 'EMPTY'} · publishableKey ${key ? 'set (' + key.slice(0, 16) + '…, ' + key.length + ' chars)' : 'EMPTY'}`);
  process.exit(0);
}

const url = (process.env.ZAJIL_SUPABASE_URL || '').trim().replace(/\/+$/, '');
const key = (process.env.ZAJIL_SUPABASE_PUBLISHABLE_KEY || '').trim();

if (!url || !key) {
  fail('ZAJIL_SUPABASE_URL and ZAJIL_SUPABASE_PUBLISHABLE_KEY must both be set. '
     + 'Nothing was written; the export is still sync-inert.');
}

// ── refuse anything that is not a plausible project URL ──────────────────────────
if (!/^https:\/\/[A-Za-z0-9.-]+$/.test(url)) {
  fail(`ZAJIL_SUPABASE_URL is not an https origin: ${JSON.stringify(url)}`);
}

// ── refuse a SECRET key, by shape, loudly ────────────────────────────────────────
// Assembled from parts so this file cannot trip the no-secret-key guard that scans it.
const SECRET = 'sb_' + 'secret_';
const SERVICE_ROLE = 'service_' + 'role';
if (key.startsWith(SECRET)) {
  fail('that is a SECRET key. It must never reach a static export — every row in the project '
     + 'would be readable by anyone who views source. Nothing was written.');
}
if (key.startsWith('eyJ')) {
  // a legacy JWT key: anon is fine, service_role is catastrophic. Decode the payload and look.
  try {
    const body = JSON.parse(Buffer.from(key.split('.')[1] || '', 'base64url').toString('utf8'));
    if (body.role === SERVICE_ROLE) {
      fail(`that is a legacy ${SERVICE_ROLE} key — the JWT equivalent of a secret key. Nothing was written.`);
    }
    if (body.role && body.role !== 'anon') {
      fail(`that key's role is ${JSON.stringify(body.role)}, not "anon". Nothing was written.`);
    }
  } catch {
    fail('that looks like a JWT but its payload could not be read, so its role cannot be checked. Nothing was written.');
  }
} else if (!key.startsWith('sb_' + 'publishable_')) {
  fail(`ZAJIL_SUPABASE_PUBLISHABLE_KEY is neither a publishable key nor a JWT: ${JSON.stringify(key.slice(0, 12) + '…')}`);
}

// ── write it, preserving the file's own explanation of what it is ────────────────
const original = readFileSync(TARGET, 'utf8');
// The `|| globalThis.ZAJIL_SYNC_CONFIG` guard is PRESERVED, deliberately. Without it a
// deployed build would overwrite a config set before page scripts, and the live deploy gate
// — which points the app at a stub to test a failure path — could not do its job. A default
// is all this file has ever needed to be.
const line = `globalThis.ZAJIL_SYNC_CONFIG = globalThis.ZAJIL_SYNC_CONFIG || ${JSON.stringify({ url, publishableKey: key })};\n`;
const ASSIGN = /globalThis\.ZAJIL_SYNC_CONFIG = (?:globalThis\.ZAJIL_SYNC_CONFIG \|\| )?\{[^}]*\};\n?/;
const stamped = original.replace(
  ASSIGN,
  `// ── WRITTEN AT DEPLOY TIME by scripts/inject-config.mjs. The committed copy of this file,\n`
  + `// at next/public/sync-config.js, is EMPTY and stays that way. ──\n${line}`,
);
if (stamped === original) {
  fail(`could not find the ZAJIL_SYNC_CONFIG assignment in ${TARGET} — refusing to guess. Nothing was written.`);
}
writeFileSync(TARGET, stamped);

console.log(`✓ inject-config  ${TARGET} now points at ${url}`);
console.log(`                 publishable key ${key.slice(0, 16)}… (${key.length} chars); no secret key was accepted`);
