// src/example-data.js — the example data the dataset loaders put in, and the one action that takes it out.
//
// RULED 2026-10-14. A fancier opens Zajil, taps «تحميل سرب تعليمي» from the empty state, then wants his own
// birds instead — and had no way to remove it (RF-16): 38 example pigeons for good, and the only control
// offered was deleting birds one at a time, which is also what breaks pedigrees. This is NOT general
// loft management: it is scoped to exactly what the loaders put in, identified by the datasets' own ids.
//
// THE IDS ARE DERIVED, NOT TYPED. tools/idmap.js makes every dataset id as RFC 4122 v5 — sha1 over
// ID_NAMESPACE and the readable key — and the pre-v1.9.1 datasets shipped the readable key itself as
// the id. Both generations of both datasets exist on real devices (RF-17), so all four are named here,
// computed from the two keys and the one namespace. A wrong derivation finds nothing to remove; it
// never removes the wrong thing.
import {
  Health, Lofts, Pairs, Races, REFERENCE_STATUS, deleteBird, emitChange, idbGetAll, saveBird, state,
} from './db.js';

/** The two dataset lofts, as tools/gen-example-large.js and the small example name them. */
export const EXAMPLE_KEYS = ['loft-irbid-demo', 'loft-zarqa'];
/** tools/idmap.js — Zajil's own namespace; it must never change, or every shipped id changes with it. */
export const ID_NAMESPACE = '7f3c9a54-2b18-4d6e-9c05-1a2b3c4d5e6f';

/** RFC 4122 v5: sha1(namespace bytes ++ utf8 key), version and variant pinned. Same arithmetic as tools/idmap.js. */
export async function uuid5(key) {
  const ns = Uint8Array.from(ID_NAMESPACE.replace(/-/g, '').match(/../g).map((h) => parseInt(h, 16)));
  const name = new TextEncoder().encode(String(key));
  const bytes = new Uint8Array(ns.length + name.length);
  bytes.set(ns, 0); bytes.set(name, ns.length);
  const b = new Uint8Array(await crypto.subtle.digest('SHA-1', bytes)).slice(0, 16);
  b[6] = (b[6] & 0x0f) | 0x50;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

let idsPromise = null;
/** The four ids: each key as shipped before v1.9.1, and its uuid5 as shipped since. */
export function exampleLoftIds() {
  if (!idsPromise) idsPromise = Promise.all(EXAMPLE_KEYS.map(uuid5)).then((u) => [...EXAMPLE_KEYS, ...u]);
  return idsPromise;
}

/** The app mints every id as uuid v4 (storage.js uuid()); the datasets never did — v5 from tools/idmap.js, or the readable
 *  key before v1.9.1. So inside a dataset loft, a v4 id is a record the FANCIER made there (on a fresh device the teaching
 *  loft becomes current when loaded — RF-12 — so his first birds land in it), and it is his to keep. */
const V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export const isExampleId = (id) => !V4.test(String(id));

/**
 * What the example data on this device amounts to, or null when there is none.
 *
 * `keep` is the ruled exception: example birds that a bird of the fancier's own descends from. They are genuinely part
 * of that bird's pedigree now, so they are kept as reference birds rather than deleted — the whole ancestor chain of
 * them, so no kept bird loses a parent when the rest go (deleteBird clears the parent links of offspring).
 * `own` is everything with a v4 id filed under a dataset loft: the fancier's records, re-filed to the loft that is
 * current once the dataset lofts are gone (RF-14's recovery decides which), never deleted.
 */
export async function examplePresence() {
  const present = (await exampleLoftIds()).filter((id) => state.lofts.has(id));
  if (!present.length) return null;
  const SET = new Set(present);
  const inLofts = (map) => [...map.values()].filter((r) => SET.has(r.loftId));
  const split = (rows) => ({ ex: rows.filter((r) => isExampleId(r.id)), own: rows.filter((r) => !isExampleId(r.id)) });
  const birds = split(inLofts(state.birds)), pairs = split(inLofts(state.pairs)), races = split(inLofts(state.raceResults)), health = split(inLofts(state.healthEvents));
  const example = new Set(birds.ex.map((b) => b.id));
  const keep = new Set();                                  // example birds that are ancestors of the fancier's own birds
  for (const b of state.birds.values()) {
    if (example.has(b.id)) continue;                       // every bird that is not example data, wherever it is filed
    const stack = [b.sireId, b.damId];
    while (stack.length) {
      const id = stack.pop();
      if (!id || keep.has(id) || !example.has(id)) continue;
      keep.add(id);
      const a = state.birds.get(id);
      stack.push(a.sireId, a.damId);
    }
  }
  const media = (await idbGetAll('media')).filter((m) => example.has(m.birdId) && !keep.has(m.birdId));
  const own = birds.own.length + pairs.own.length + races.own.length + health.own.length;
  return {
    ids: present,
    lofts: present.map((id) => ({ id, name: state.lofts.get(id).name || '',
      birds: birds.ex.filter((b) => b.loftId === id).length, pairs: pairs.ex.filter((r) => r.loftId === id).length,
      races: races.ex.filter((r) => r.loftId === id).length, health: health.ex.filter((r) => r.loftId === id).length })),
    birds: birds.ex.length - keep.size, pairs: pairs.ex.length, races: races.ex.length, health: health.ex.length, media: media.length,
    kept: keep.size, keep, own, ownBirds: birds.own.length,
    current: SET.has(state.currentLoftId),
  };
}

/**
 * Remove it — through deleteBird(), the generic remove() and Lofts.remove(), never a raw write, so every deletion is
 * logged and tombstoned and syncs like one the fancier made by hand. Touches nothing outside the named lofts, and
 * inside them only dataset records: the fancier's own are re-filed, the kept ancestors become references.
 * Returns the counts, or null when there was nothing to remove.
 */
export async function removeExampleData() {
  const p = await examplePresence();
  if (!p) return null;
  const SET = new Set(p.ids);
  // RULED 2026-10-30: these internal re-saves pass allowWarnings — and ONLY these (guard `allow-warnings-bounded`).
  // The records already exist exactly as they are; the removal flips two fields or a loftId. The warning that
  // blocked it on every real device (RF-18) was val.dupRing: with both dataset generations present every kept
  // ancestor has a twin wearing its ring — a twin this same action deletes. Errors still block, unchanged.
  const INTERNAL = { allowWarnings: true };
  for (const id of p.keep) {                               // kept ancestors first, so nothing below can touch them
    const b = state.birds.get(id);
    await saveBird({ ...b, external: true, status: REFERENCE_STATUS }, INTERNAL);
  }
  let birds = 0;
  for (const b of [...state.birds.values()]) {
    if (SET.has(b.loftId) && isExampleId(b.id) && !p.keep.has(b.id)) { await deleteBird(b.id); birds++; }
  }
  const sweep = async (map, api) => { let n = 0; for (const r of [...map.values()]) { if (SET.has(r.loftId) && isExampleId(r.id)) { await api.remove(r.id); n++; } } return n; };
  const pairs = await sweep(state.pairs, Pairs), races = await sweep(state.raceResults, Races), health = await sweep(state.healthEvents, Health);
  for (const id of p.ids) await Lofts.remove(id);          // RF-14: remove() re-points currentLoftId if it was one of these
  // the fancier's own records, and the kept references, move to the loft that is current now
  const target = state.currentLoftId;
  let moved = 0;
  const refile = async (map, api) => { for (const r of [...map.values()]) { if (SET.has(r.loftId)) { await api.save({ ...r, loftId: target }); moved++; } } };
  for (const b of [...state.birds.values()]) { if (SET.has(b.loftId)) { await saveBird({ ...b, loftId: target }, INTERNAL); moved++; } }
  await refile(state.pairs, Pairs); await refile(state.raceResults, Races); await refile(state.healthEvents, Health);
  emitChange({ type: 'import' });
  // what was removed in all — the presence counts; the sweep only catches what deleteBird's cascade did not reach
  return { lofts: p.ids.length, birds, pairs: p.pairs, races: p.races, health: p.health, swept: { pairs, races, health }, kept: p.kept, moved, target };
}
