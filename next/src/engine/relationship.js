// engine/relationship.js — name the relationship between two birds and give
// the hypothetical COI of mating them. Pure; i18n happens in the UI layer
// (we return a stable `key` plus params).

import { ancestorDepths, truncatedGraph } from './pedigree.js';
import { makeKinship } from './coi.js';

/**
 * Describe how A and B are related.
 * Returns {
 *   key,            // i18n key, e.g. 'rel.fullSiblings'
 *   params,         // e.g. { n: 2 } for generation counts
 *   kinship,        // coefficient of kinship f(A,B)
 *   hypotheticalCOI // COI of offspring if A × B (=== kinship)
 * }
 */
export function describeRelationship(getBird, aId, bId, maxDepth = 8) {
  const { parents } = truncatedGraph(getBird, [aId, bId], maxDepth + 1, 0);
  const f = makeKinship(parents);
  const kin = aId && bId ? f(aId, bId) : 0;
  const base = { kinship: kin, hypotheticalCOI: kin };

  if (!aId || !bId) return { key: 'rel.unknown', params: {}, ...base };
  if (aId === bId) return { key: 'rel.sameBird', params: {}, ...base };

  const aAnc = ancestorDepths(getBird, [aId], maxDepth, 0); // includes self at 0
  const bAnc = ancestorDepths(getBird, [bId], maxDepth, 0);

  // Direct line? Keys describe what B is *to* A.
  if (aAnc.has(bId)) return directLine('rel.ancestor', aAnc.get(bId), base);   // B is A's ancestor
  if (bAnc.has(aId)) return directLine('rel.descendant', bAnc.get(aId), base); // B is A's descendant

  // Common ancestors and the closest (minimum da+db, then min max)
  let best = null;
  const commons = [];
  for (const [id, da] of aAnc) {
    if (!bAnc.has(id)) continue;
    const db = bAnc.get(id);
    commons.push({ id, da, db });
    if (!best || da + db < best.da + best.db) best = { id, da, db };
  }
  if (!best) {
    return kin > 0
      ? { key: 'rel.related', params: {}, ...base }
      : { key: 'rel.unrelated', params: {}, ...base };
  }

  const a = getBird(aId), b = getBird(bId);
  const { da, db } = best;
  if (da === 1 && db === 1) {
    const shareSire = a && b && a.sireId && a.sireId === b.sireId;
    const shareDam = a && b && a.damId && a.damId === b.damId;
    if (shareSire && shareDam) return { key: 'rel.fullSiblings', params: {}, ...base };
    return { key: 'rel.halfSiblings', params: {}, ...base };
  }
  if ((da === 1 && db === 2) || (da === 2 && db === 1)) {
    return { key: 'rel.avuncular', params: {}, ...base }; // uncle/aunt ↔ nephew/niece
  }
  if (da === 2 && db === 2) return { key: 'rel.firstCousins', params: {}, ...base };
  if ((da === 2 && db === 3) || (da === 3 && db === 2)) {
    return { key: 'rel.firstCousinsOnceRemoved', params: {}, ...base };
  }
  if (da === 3 && db === 3) return { key: 'rel.secondCousins', params: {}, ...base };
  return { key: 'rel.commonAncestors', params: { n: commons.length, da, db }, ...base };
}

function directLine(kind, n, base) {
  // kind 'rel.ancestor': B is A's parent/grandparent/…
  // kind 'rel.descendant': B is A's offspring/grandchild/…
  const near = kind === 'rel.ancestor' ? '.parent' : '.offspring';
  const mid = kind === 'rel.ancestor' ? '.grandparent' : '.grandchild';
  if (n === 1) return { key: kind + near, params: {}, ...base };
  if (n === 2) return { key: kind + mid, params: {}, ...base };
  return { key: kind + '.great', params: { n: n - 2 }, ...base };
}

/** Suggested warning level for a pairing. Thresholds are conventional. */
export function pairingWarningLevel(coi) {
  if (coi >= 0.25) return 'severe';   // parent×offspring / full sibs or worse
  if (coi >= 0.125) return 'high';    // grandparent level
  if (coi >= 0.0625) return 'moderate';
  if (coi > 0) return 'info';
  return 'none';
}
