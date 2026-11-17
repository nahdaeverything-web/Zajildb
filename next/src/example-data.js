// src/example-data.js — the example data the dataset loaders put in, and the one action that takes it out.
//
// RULED 2026-10-14. A fancier opens Zajil, taps «تحميل سرب تعليمي» from the empty state, then wants his own
// birds instead — and had no way to remove it (RF-16): 38 example pigeons for good, and the only control
// offered was deleting birds one at a time, which is also what breaks pedigrees. This is NOT general
// loft management: it is scoped to exactly what the loaders put in, identified by the datasets' own ids.
//
// WHAT IS EXAMPLE DATA (RF-22): a record whose id is one the datasets shipped — src/example-ids.js, exampleIds() below.
//
// THE LOFT IDS ARE DERIVED, NOT TYPED. tools/idmap.js makes every dataset id as RFC 4122 v5 — sha1 over
// ID_NAMESPACE and the readable key — and the pre-v1.9.1 datasets shipped the readable key itself as
// the id. Both generations of both datasets exist on real devices (RF-17), so all four are named here,
// computed from the two keys and the one namespace. A wrong derivation finds nothing to remove; it
// never removes the wrong thing.
import {
  Health, Lofts, Pairs, Races, REFERENCE_STATUS, deleteBird, emitChange, idbGetAll, nowISO, saveBird, state,
} from './db.js';
import { EXAMPLE_ID_KEYS } from './example-ids.js';
import { clearTombstone, getTombstone } from './db/oplog.js';
import { importAll } from './db/io.js';

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

let setsPromise = null;
/**
 * THE MEMBERSHIP SET (RF-22, RULED 2026-11-01): the shipped datasets' own ids, by store — every key of
 * src/example-ids.js as it shipped before v1.9.1, and its uuid5 as it has shipped since. A record is example data when
 * its id is in here and for no other reason. NOT the loft it is filed in: a teaching bird pulled or moved into another
 * loft is still a teaching bird. NOT the shape of its id: a fancier's record that is not a v4 uuid (made before v1.4.0,
 * or edited by hand) is his, wherever it is filed.
 */
export function exampleIds() {
  if (!setsPromise) {
    setsPromise = (async () => {
      const out = {};
      for (const [store, keys] of Object.entries(EXAMPLE_ID_KEYS)) out[store] = new Set([...keys, ...(await Promise.all(keys.map(uuid5)))]);
      return out;
    })();
  }
  return setsPromise;
}

/** How many of the birds that cause a keep the question names before it says «و{n} غيرها». */
export const BECAUSE_SHOWN = 5;

/**
 * What the example data on this device amounts to, or null when there is nothing of it to remove.
 *
 * `keep` is the ruled exception: example birds that a bird of the fancier's own descends from. They are genuinely part
 * of that bird's pedigree now, so they are kept as reference birds rather than deleted — the whole ancestor chain of
 * them, so no kept bird loses a parent when the rest go (deleteBird clears the parent links of offspring).
 * `because` is the birds that cause it: every bird that is not example data and has an example bird as a parent.
 * `own` is everything filed under a dataset loft that is NOT a dataset record: the fancier's records, re-filed to the
 * loft that is current once the dataset lofts are gone (RF-14's recovery decides which), never deleted.
 */
export async function examplePresence() {
  const IDS = await exampleIds();
  const present = (await exampleLoftIds()).filter((id) => state.lofts.has(id));
  const SET = new Set(present);
  // example records are example records WHEREVER they are filed; the fancier's own are his even inside a dataset loft
  const split = (map, store) => ({ ex: [...map.values()].filter((r) => IDS[store].has(r.id)),
                                   own: [...map.values()].filter((r) => SET.has(r.loftId) && !IDS[store].has(r.id)) });
  const birds = split(state.birds, 'birds'), pairs = split(state.pairs, 'pairs'), races = split(state.raceResults, 'raceResults'), health = split(state.healthEvents, 'healthEvents');
  const example = new Set(birds.ex.map((b) => b.id));
  const keep = new Set();                                  // example birds that are ancestors of the fancier's own birds
  const because = [];                                      // the fancier's birds with an example parent: the cause of every keep
  for (const b of state.birds.values()) {
    if (example.has(b.id)) continue;                       // every bird that is not example data, wherever it is filed
    if (example.has(b.sireId) || example.has(b.damId)) because.push({ id: b.id, name: b.name || '', ring: ((b.rings || [])[0] || {}).raw || '' });
    const stack = [b.sireId, b.damId];
    while (stack.length) {
      const id = stack.pop();
      if (!id || keep.has(id) || !example.has(id)) continue;
      keep.add(id);
      const a = state.birds.get(id);
      stack.push(a.sireId, a.damId);
    }
  }
  // named in the question in an order the fancier can read, not in the order of their ids
  because.sort((x, y) => (x.name || x.ring).localeCompare(y.name || y.ring, 'ar', { numeric: true }));
  // nothing to remove: no dataset loft, and every example bird still here is one a bird of the fancier's descends from
  if (!present.length && birds.ex.length === keep.size && !pairs.ex.length && !races.ex.length && !health.ex.length) return null;
  const media = (await idbGetAll('media')).filter((m) => example.has(m.birdId) && !keep.has(m.birdId));
  // TF-12 (RULED 2026-11-15): the read above is an await, and a removal or a pulled tombstone can take a loft away
  // across it — `state.lofts.get(id).name` then threw. Re-checked here; a loft that went is simply not listed.
  const still = present.filter((id) => state.lofts.has(id));
  if (present.length && !still.length) return null;
  const STILL = new Set(still);
  const own = birds.own.length + pairs.own.length + races.own.length + health.own.length;
  return {
    ids: still,
    lofts: still.map((id) => ({ id, name: state.lofts.get(id).name || '',
      birds: birds.ex.filter((b) => b.loftId === id).length, pairs: pairs.ex.filter((r) => r.loftId === id).length,
      races: races.ex.filter((r) => r.loftId === id).length, health: health.ex.filter((r) => r.loftId === id).length })),
    elsewhere: birds.ex.filter((b) => !SET.has(b.loftId)).length,          // example birds filed outside the dataset lofts
    // RULED 2026-11-17 (H3 decision 4): example records of ANY kind filed outside the lofts the question names. While
    // there is one, the question names no loft at all — naming one would claim a place that is not the whole truth.
    outside: [birds, pairs, races, health].reduce((n, k) => n + k.ex.filter((r) => !STILL.has(r.loftId)).length, 0),
    birds: birds.ex.length - keep.size, pairs: pairs.ex.length, races: races.ex.length, health: health.ex.length, media: media.length,
    kept: keep.size, keep, because, own, ownBirds: birds.own.length,
    current: SET.has(state.currentLoftId),
  };
}

// RULED 2026-10-30: the removal's internal re-saves pass allowWarnings — and ONLY these (guard `allow-warnings-bounded`).
// The records already exist exactly as they are. The warning that blocked the removal on every real device (RF-18) was
// val.dupRing: with both dataset generations present every kept ancestor has a twin wearing its ring — a twin this
// same action deletes. Errors still block, unchanged.
// THE A-SET (RULED, built 2026-11-16): the option is FROZEN, it has exactly one user — resave() below — and resave()
// refuses to alter anything but the reference flag (`external` and the status that goes with it) and `loftId`.
const INTERNAL = Object.freeze({ allowWarnings: true });
const RESAVE_MAY_ALTER = Object.freeze(['external', 'status', 'loftId']);
const mayAlter = (patch) => { for (const k of Object.keys(patch)) if (!RESAVE_MAY_ALTER.includes(k)) throw new Error(`example-removal: a re-save may not alter «${k}»`); };
/** The removal's one way of writing a bird it does not delete: the record as it stands NOW, plus the patch, and nothing else. */
async function resave(id, patch) {
  mayAlter(patch);
  return saveBird({ ...state.birds.get(id), ...patch }, INTERNAL);
}

/**
 * Remove it — through deleteBird(), the generic remove() and Lofts.remove(), never a raw write, so every deletion is
 * logged and tombstoned and syncs like one the fancier made by hand.
 * Deletes only dataset records, by their ids: the fancier's own are re-filed, the kept ancestors become references.
 * Returns the counts, or null when there was nothing to remove.
 */
export async function removeExampleData() {
  const p = await examplePresence();
  if (!p) return null;
  const IDS = await exampleIds();
  const SET = new Set(p.ids);
  for (const id of p.keep) await resave(id, { external: true, status: REFERENCE_STATUS });   // kept ancestors first, so nothing below can touch them
  let birds = 0;
  for (const b of [...state.birds.values()]) {
    if (IDS.birds.has(b.id) && !p.keep.has(b.id)) { await deleteBird(b.id); birds++; }
  }
  const sweep = async (map, api, store) => { let n = 0; for (const r of [...map.values()]) { if (IDS[store].has(r.id)) { await api.remove(r.id); n++; } } return n; };
  const pairs = await sweep(state.pairs, Pairs, 'pairs'), races = await sweep(state.raceResults, Races, 'raceResults'), health = await sweep(state.healthEvents, Health, 'healthEvents');
  for (const id of p.ids) await Lofts.remove(id);          // RF-14: remove() re-points currentLoftId if it was one of these
  // the fancier's own records, and the kept references, that were filed in a dataset loft move to the loft that is
  // current now; a kept reference filed anywhere else stays where it is
  const target = state.currentLoftId;
  let moved = 0;
  const refile = async (map, api) => { for (const r of [...map.values()]) { if (SET.has(r.loftId)) { const patch = { loftId: target }; mayAlter(patch); await api.save({ ...r, ...patch }); moved++; } } };
  for (const b of [...state.birds.values()]) { if (SET.has(b.loftId)) { await resave(b.id, { loftId: target }); moved++; } }
  await refile(state.pairs, Pairs); await refile(state.raceResults, Races); await refile(state.healthEvents, Health);
  emitChange({ type: 'import' });
  // what was removed in all — the presence counts; the sweep only catches what deleteBird's cascade did not reach
  return { lofts: p.ids.length, birds, pairs: p.pairs, races: p.races, health: p.health, swept: { pairs, races, health }, kept: p.kept, moved, target };
}

/** The stores a dataset file carries records for. */
const DATASET_STORES = Object.freeze(['lofts', 'birds', 'pairs', 'raceResults', 'healthEvents']);

/**
 * THE DATASET LOADERS (RF-16, RULED 2026-11-18): someone who removed the teaching data can load it again.
 *
 * The removal tombstones every example record, and a merge refuses a record whose deletion is newer than it — so
 * loading the same dataset afterwards imported nothing, without a word. A loader therefore FORGETS the tombstones of
 * the records it loads, and only those: an id that is BOTH in the file AND in the shipped-id membership set
 * (exampleIds()). A fancier's own deleted record is never in that set, so no file — whatever it carries — can make
 * this bring one back.
 *
 * NOT in importAll: importing a backup must keep honouring deletions. This is the loaders' act alone
 * (guards/run.mjs `example-loader-only`).
 * KEPT REFERENCES STAY REFERENCES (same ruling): an example bird the removal kept was never deleted, has no tombstone,
 * and is newer than the file's copy, so the merge skips it — the loader does not touch a record the fancier's birds
 * point at.
 *
 * THE ORDER, and why (measured 2026-11-18; the ruling says "forget", the order is this file's — reported).
 * Forgetting FIRST and merging after lost data: a device's own pushed deletions sit above its cursor, an automatic
 * pull landed between the two steps and wrote the tombstones back, and the merge then skipped those records — 11 of
 * 68 gone again in one run of eight, on the device, the server and a second device alike. So nothing is forgotten
 * before the data is in:
 *   1. a shipped record that has a tombstone is handed to the merge STAMPED as made now (later than its deletion,
 *      whatever clock wrote that) — it IS a newer act than its removal, and the merge's own rule then admits it;
 *   2. importAll merges, exactly as it always has;
 *   3. the tombstone of every such record that is now on the device is cleared — a winning record clears its
 *      tombstone, the corollary applySyncPut and restoreBird already follow.
 * A tombstone written back mid-load is older than the stamped record and is cleared in step 3. A load that fails
 * part-way clears only what did come in: every other deletion still stands.
 * A record with no tombstone is passed through untouched, so a first load is byte-for-byte what it was.
 */
export async function loadExampleDataset(payload) {
  const IDS = await exampleIds();
  const again = [];
  let fresh = payload;
  if (payload && typeof payload === 'object') {
    fresh = { ...payload };
    for (const store of DATASET_STORES) {
      if (!Array.isArray(payload[store])) continue;
      const out = [];
      for (const rec of payload[store]) {
        const tomb = rec && typeof rec.id === 'string' && IDS[store] && IDS[store].has(rec.id) ? await getTombstone(store, rec.id) : null;
        if (!tomb) { out.push(rec); continue; }
        const now = nowISO(); const after = new Date((Date.parse(tomb.at) || 0) + 1).toISOString();
        out.push({ ...rec, updatedAt: now > after ? now : after });
        again.push([store, rec.id]);
      }
      fresh[store] = out;
    }
  }
  try {
    const counts = await importAll(fresh, 'merge');
    return { ...counts, forgotten: again.length };
  } finally {
    for (const [store, id] of again) {
      if (!state[store] || !state[store].has(id)) continue;                    // it did not come in: its deletion stands
      try { await clearTombstone(store, id); } catch { /* the load's own failure, if any, is the one to report */ }
    }
  }
}
