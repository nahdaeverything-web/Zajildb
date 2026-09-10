// engine/validate.js — data validation rules. Pure; returns i18n keys + params.

import { wouldCreateCycle } from './pedigree.js';
import { ringKey, formatRing } from './rings.js';

/**
 * Validate a bird record against the rest of the flock before save.
 * `bird` is the record as it would be saved; `getBird` resolves ids;
 * `allBirds` iterable for duplicate ring detection.
 * Returns { errors: [...], warnings: [...] }, each { key, params }.
 * Errors block the save; warnings need user confirmation.
 */
export function validateBird(bird, getBird, allBirds) {
  const errors = [];
  const warnings = [];

  // Cycles — hard error, name the link.
  for (const [role, pid] of [['sire', bird.sireId], ['dam', bird.damId]]) {
    if (!pid) continue;
    if (pid === bird.id) {
      errors.push({ key: 'val.selfParent', params: { role } });
      continue;
    }
    const c = wouldCreateCycle(getBird, bird.id, pid);
    if (c.cycle) {
      errors.push({ key: 'val.cycle', params: { role, path: c.path } });
    }
  }

  // Sex contradictions — sire must not be a hen, dam must not be a cock.
  const sire = bird.sireId ? getBird(bird.sireId) : null;
  const dam = bird.damId ? getBird(bird.damId) : null;
  if (sire && sire.sex === 'hen') errors.push({ key: 'val.sireIsHen', params: { id: bird.sireId } });
  if (dam && dam.sex === 'cock') errors.push({ key: 'val.damIsCock', params: { id: bird.damId } });
  if (bird.sireId && bird.sireId === bird.damId) {
    errors.push({ key: 'val.sameSireDam', params: {} });
  }

  // Impossible ages — parent hatched on/after the child. Warning (dates are
  // often approximate) unless the parent is *younger*, which is an error.
  if (bird.hatchDate) {
    for (const [role, parent] of [['sire', sire], ['dam', dam]]) {
      if (parent && parent.hatchDate) {
        if (parent.hatchDate > bird.hatchDate) {
          errors.push({ key: 'val.parentYounger', params: { role, id: parent.id } });
        } else if (parent.hatchDate === bird.hatchDate) {
          warnings.push({ key: 'val.parentSameDay', params: { role, id: parent.id } });
        }
      }
    }
  }

  // Duplicate rings — warning (re-used rings do exist, e.g. re-ringed birds).
  if (Array.isArray(bird.rings)) {
    const mine = new Map();
    for (const r of bird.rings) {
      const k = ringKey(r);
      if (!k) continue;
      if (mine.has(k)) warnings.push({ key: 'val.dupRingSameBird', params: { ring: formatRing(r) } });
      mine.set(k, r);
    }
    for (const other of allBirds || []) {
      if (other.id === bird.id || !Array.isArray(other.rings)) continue;
      for (const r of other.rings) {
        const k = ringKey(r);
        if (k && mine.has(k)) {
          warnings.push({ key: 'val.dupRing', params: { ring: formatRing(r), otherId: other.id, otherName: other.name || '' } });
        }
      }
    }
  }

  return { errors, warnings };
}

/** Sex sanity for pair creation: returns error keys (empty = fine). */
export function validatePairSexes(sire, dam) {
  const errors = [];
  if (sire && sire.sex === 'hen') errors.push({ key: 'val.pairSireIsHen', params: { id: sire.id } });
  if (dam && dam.sex === 'cock') errors.push({ key: 'val.pairDamIsCock', params: { id: dam.id } });
  if (sire && dam && sire.id === dam.id) errors.push({ key: 'val.pairSameBird', params: {} });
  return errors;
}

/**
 * The save decision, in one pure place.
 *
 * Validation lives at the WRITE boundary (db.js saveBird) rather than in each
 * view, because a view that forgets to call it writes bad data silently — which
 * is exactly how "ring chick" came to create duplicate rings and impossible
 * parent links that the bird form would have refused.
 *
 * Strict by default: BOTH hard errors and unconfirmed warnings block the write.
 * A caller that has shown the warnings to the user and had them confirmed
 * passes { allowWarnings: true }. Errors are never waivable.
 * { force: true } skips everything and exists only for importAll and the
 * bundled dataset loaders, which must land a payload verbatim.
 *
 * @returns {{ok: boolean, errors: Array, warnings: Array}} i18n keys + params
 */
export function classifySave(bird, getBird, allBirds, { allowWarnings = false, force = false } = {}) {
  if (force) return { ok: true, errors: [], warnings: [] };
  const { errors, warnings } = validateBird(bird, getBird, allBirds);
  const ok = errors.length === 0 && (allowWarnings || warnings.length === 0);
  return { ok, errors, warnings };
}
