// dates.js — local-calendar date handling.
//
// WHY THIS MODULE EXISTS
// Zajil stores dates as ISO Gregorian strings, and most of them are date-ONLY
// ("2026-03-14": a hatch date, a laying date). JavaScript gets both ends of
// that wrong by default:
//
//   1. `new Date().toISOString().slice(0,10)` is the UTC date. East of
//      Greenwich, between local midnight and the UTC offset, it names
//      YESTERDAY. In Jordan (UTC+3) an egg logged at 01:00 was dated to the
//      previous day.
//   2. `new Date("2026-03-14")` is parsed as UTC midnight. West of Greenwich
//      that instant is still the 13th locally, so a stored date RENDERS one
//      day early.
//
// A calendar date has no timezone — it is a label, not an instant. Everything
// in the app must go through here so the two mistakes cannot be reintroduced;
// tests/guards.test.js fails the build if a raw UTC slice appears elsewhere.
//
// This module is dependency-free and pure, so the node suite can exercise it
// directly with fixed instants.

/**
 * The LOCAL calendar date as "YYYY-MM-DD".
 * @param {Date} [at] instant to read (defaults to now; injectable for tests)
 */
export function todayISO(at = new Date()) {
  const y = at.getFullYear();
  const m = String(at.getMonth() + 1).padStart(2, '0');
  const d = String(at.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** Is this a bare "YYYY-MM-DD" (no time component)? */
export function isDateOnly(iso) {
  return typeof iso === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(iso);
}

/**
 * Parse a stored date for DISPLAY.
 * A bare date becomes local midnight of that calendar day, so it renders as
 * the day it says at any offset. Anything with a time component keeps its
 * instant semantics (a race arrival time is a real moment, not a label).
 * Invalid input yields an invalid Date rather than throwing, matching `new Date`.
 */
export function parseLocalDate(iso) {
  if (isDateOnly(iso)) {
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(y, m - 1, d);
  }
  if (typeof iso !== 'string' || !iso) return new Date(NaN);
  return new Date(iso);
}
