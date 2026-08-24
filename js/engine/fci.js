// engine/fci.js — FCI eligibility rules.
// FCI standard for results counting toward international awards: the race
// must have at least 20 fanciers and 150 pigeons entered, and the bird must
// carry an FCI ring.

export const FCI_MIN_FANCIERS = 20;
export const FCI_MIN_BIRDS = 150;

export function hasFCIRing(bird) {
  return !!(bird && Array.isArray(bird.rings) && bird.rings.some((r) => r.type === 'FCI'));
}

/**
 * Does a single race result meet the FCI qualifying minimum?
 * Returns { qualifies, reasons: [keys] } — reasons name what failed.
 */
export function resultQualifies(result) {
  const reasons = [];
  if (!result) return { qualifies: false, reasons: ['fci.noResult'] };
  const fanciers = Number(result.fanciersEntered);
  const birds = Number(result.birdsEntered);
  if (!(fanciers >= FCI_MIN_FANCIERS)) reasons.push('fci.tooFewFanciers');
  if (!(birds >= FCI_MIN_BIRDS)) reasons.push('fci.tooFewBirds');
  if (result.raceType === 'training') reasons.push('fci.trainingNotEligible');
  return { qualifies: reasons.length === 0, reasons };
}

/**
 * Eligibility summary for one bird given its race results.
 * Returns { hasRing, qualifyingResults, nonQualifying: [{result, reasons}] }.
 */
export function birdEligibility(bird, results) {
  const hasRing = hasFCIRing(bird);
  const qualifyingResults = [];
  const nonQualifying = [];
  for (const r of results || []) {
    const q = resultQualifies(r);
    if (q.qualifies) qualifyingResults.push(r);
    else nonQualifying.push({ result: r, reasons: q.reasons });
  }
  return { hasRing, qualifyingResults, nonQualifying };
}
