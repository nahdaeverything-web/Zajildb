// engine/integrity.js — referential integrity over the whole database.
//
// Pure: takes plain collections, returns i18n keys + params. No DOM, no db.
//
// ┌──────────────────────────────────────────────────────────────────────────┐
// │ MAINTENANCE — this is the one piece of ongoing upkeep this design does   │
// │ NOT eliminate. Every time a new store is added, or a new field points at │
// │ another record, add it to CROSS_REFERENCES below and extend the tests.   │
// │ Nothing detects a reference this function does not know about.           │
// └──────────────────────────────────────────────────────────────────────────┘
//
// Deletion used to leave a bird's race results, health events, pairs and egg
// links pointing at a record that no longer existed. deleteBird now cascades,
// and this makes the property checkable instead of assumed.

/** Accept arrays or Maps interchangeably — db.js keeps Maps, exports keep arrays. */
function values(store) {
  if (!store) return [];
  if (store instanceof Map) return [...store.values()];
  if (Array.isArray(store)) return store;
  return Object.values(store);
}

/**
 * Every cross-record reference in the schema.
 * `each` yields { key, params } for one record's dangling references.
 */
const CROSS_REFERENCES = [
  {
    store: 'birds',
    each: (b, birdIds) => {
      const out = [];
      for (const role of ['sireId', 'damId']) {
        // null is unknown ancestry — legitimate and extremely common.
        if (b[role] && !birdIds.has(b[role])) {
          out.push({ key: 'integrity.birdParent', params: { birdId: b.id, role, missingId: b[role] } });
        }
      }
      return out;
    },
  },
  {
    store: 'pairs',
    each: (p, birdIds) => {
      const out = [];
      for (const role of ['sireId', 'damId']) {
        if (p[role] && !birdIds.has(p[role])) {
          out.push({ key: 'integrity.pairParent', params: { pairId: p.id, role, missingId: p[role] } });
        }
      }
      for (const round of p.rounds || []) {
        for (const egg of round.eggs || []) {
          if (egg.chickId && !birdIds.has(egg.chickId)) {
            out.push({ key: 'integrity.eggChick', params: { pairId: p.id, eggId: egg.id, missingId: egg.chickId } });
          }
        }
      }
      return out;
    },
  },
  {
    store: 'raceResults',
    each: (r, birdIds) => (r.birdId && !birdIds.has(r.birdId)
      ? [{ key: 'integrity.raceBird', params: { resultId: r.id, missingId: r.birdId } }] : []),
  },
  {
    store: 'healthEvents',
    // a whole-loft treatment legitimately has no bird
    each: (e, birdIds) => (e.birdId && !birdIds.has(e.birdId)
      ? [{ key: 'integrity.healthBird', params: { eventId: e.id, missingId: e.birdId } }] : []),
  },
];

/**
 * Find every dangling reference.
 * @param {{birds, pairs, raceResults, healthEvents}} stores arrays or Maps
 * @returns {Array<{key: string, params: object}>} empty when consistent
 */
export function checkIntegrity(stores = {}) {
  const birdIds = new Set(values(stores.birds).map((b) => b.id));
  const problems = [];
  for (const ref of CROSS_REFERENCES) {
    for (const record of values(stores[ref.store])) {
      problems.push(...ref.each(record, birdIds));
    }
  }
  return problems;
}
