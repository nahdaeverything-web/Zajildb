// engine/clutch.js — who hatched together. Pure: no DOM, no IndexedDB. Port-only (RULED 2026-11-23).
//
// A clutch (بطن) is what one hen lays in one round, normally two eggs. The register says two birds hatched from the
// same clutch in either of two ways, and this is the one place that reads both:
//
//   · they carry the same `clutchId` — a group id (a uuid), written when a fancier records birds that have no pair
//     record as hatched together. It points at no record, so deleting one bird leaves nothing dangling;
//   · their ids are the `chickId` of eggs in the same round of a pair.
//
// Nothing writes clutchId when a chick is ringed from an egg: the round IS that record.

/**
 * The birds recorded as hatched from the same clutch as `bird` — never the bird itself.
 *
 * @param bird     the record (as stored, or as it would be saved)
 * @param birds    iterable of every bird, for the clutchId group
 * @param pairs    iterable of every pair, for the rounds
 * @param getBird  resolves a chick id
 */
export function clutchMates(bird, birds, pairs, getBird) {
  const mates = new Map();
  if (!bird || !bird.id) return [];
  if (bird.clutchId) {
    for (const b of birds || []) {
      if (b && b.id !== bird.id && b.clutchId === bird.clutchId) mates.set(b.id, b);
    }
  }
  for (const p of pairs || []) {
    for (const round of (p && p.rounds) || []) {
      const chicks = (round.eggs || []).map((e) => e.chickId).filter(Boolean);
      if (!chicks.includes(bird.id)) continue;
      for (const id of chicks) {
        if (id === bird.id || mates.has(id)) continue;
        const b = getBird ? getBird(id) : null;
        if (b) mates.set(id, b);
      }
    }
  }
  return [...mates.values()];
}
