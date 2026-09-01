// tools/idmap.js — turn the generators' readable keys into real uuids.
//
// WHY. The shipped datasets used readable ids (`b-barq`, `g5-faris26`). That
// contradicted the project's own rule — HANDOFF §14, "UUIDs only" — and the
// contradiction was invisible until v1.9 typed the server's `record_id` column
// `uuid` and every push from a loft that had loaded the examples was rejected
// whole. The column is `text` now (client ids are opaque to the server), so
// this is no longer a sync problem; it is a "the shipped data should obey the
// project's own convention" problem, and a convention the data breaks is one
// that will mislead someone again.
//
// HOW, and why not just write uuids in the generators. The readable keys are
// documentation: `sireId: 'b-barq'` says what the line means and a uuid does
// not. So the generators keep their keys, and the payload is remapped
// mechanically on the way out — every id and every reference, in one pass, with
// no hand-maintained list of which fields are references.
//
// DETERMINISTIC, because HANDOFF requires the datasets regenerate reproducibly.
// A random uuid per run would churn both files on every regeneration. These are
// RFC 4122 version 5 uuids — SHA-1 over a fixed namespace plus the readable key
// — so the same key always yields the same uuid, and Python's `uuid.uuid5()`
// derives the identical value from the same inputs. That is what lets the
// browser suites keep saying `bird_id('g5-faris26')` instead of carrying an
// opaque literal around.

import { createHash } from 'node:crypto';

/** Zajil's own namespace. Any fixed uuid works; this one is ours and must
 *  never change, or every shipped id changes with it. */
export const ID_NAMESPACE = '7f3c9a54-2b18-4d6e-9c05-1a2b3c4d5e6f';

/** RFC 4122 v5: sha1(namespace bytes ++ name), version and variant pinned. */
export function uuidFor(key) {
  const ns = Buffer.from(ID_NAMESPACE.replace(/-/g, ''), 'hex');
  const hash = createHash('sha1').update(Buffer.concat([ns, Buffer.from(String(key), 'utf8')])).digest();
  const b = Buffer.from(hash.subarray(0, 16));
  b[6] = (b[6] & 0x0f) | 0x50;          // version 5
  b[8] = (b[8] & 0x3f) | 0x80;          // RFC 4122 variant
  const h = b.toString('hex');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Every `id` in the payload, at every depth — records, notes, rounds, eggs. */
function collectKeys(value, keys = new Set()) {
  if (Array.isArray(value)) { for (const v of value) collectKeys(v, keys); return keys; }
  if (value && typeof value === 'object') {
    if (typeof value.id === 'string' && value.id && !UUID_RE.test(value.id)) keys.add(value.id);
    for (const v of Object.values(value)) collectKeys(v, keys);
  }
  return keys;
}

/**
 * Rewrite ids and every reference to them.
 *
 * Deliberately a GENERIC deep walk rather than a list of reference fields
 * (`sireId`, `damId`, `birdId`, `chickId`, `loftId`, …). A hand-maintained list
 * is one forgotten entry away from a dangling reference, and the next field
 * someone adds would not be on it. Any string that is EXACTLY a known key is a
 * reference to it — prose never matches, because prose is a sentence and a key
 * is a token.
 */
export function remapIds(payload) {
  const keys = collectKeys(payload);
  const map = new Map([...keys].map((k) => [k, uuidFor(k)]));
  const walk = (v) => {
    if (typeof v === 'string') return map.get(v) ?? v;
    if (Array.isArray(v)) return v.map(walk);
    if (v && typeof v === 'object') {
      return Object.fromEntries(Object.entries(v).map(([k, val]) => [k, walk(val)]));
    }
    return v;
  };
  return { payload: walk(payload), map };
}
