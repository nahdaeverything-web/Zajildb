// engine/rings.js — ring number parsing & formatting.
// Ring numbers ALWAYS render Western digits, LTR (UI wraps in <bdi dir="ltr">).

export const RING_TYPES = ['national', 'FCI', 'club', 'private'];

/**
 * Parse a raw ring string like "JO-2024-12345", "JOR 24 A 5512",
 * "FCI-JO-2023-00871". Best effort; keeps `raw` verbatim always.
 * Returns { country, union, year, serial, raw, type }.
 */
export function parseRing(raw, type = 'national') {
  const ring = { country: '', union: '', year: null, serial: '', raw: String(raw || '').trim(), type };
  if (!ring.raw) return ring;
  const parts = ring.raw.split(/[\s\-\/._]+/).filter(Boolean);
  for (const part of parts) {
    if (part.toUpperCase() === 'FCI') {
      ring.type = 'FCI';
    } else if (/^\d{4}$/.test(part) && +part > 1950 && +part < 2100 && ring.year == null) {
      ring.year = +part;
    } else if (/^\d{2}$/.test(part) && ring.year == null && parts.length > 1) {
      const yy = +part;
      ring.year = yy > 50 ? 1900 + yy : 2000 + yy;
    } else if (/^[A-Za-z]{2,4}$/.test(part) && !ring.country) {
      ring.country = part.toUpperCase();
    } else if (/^\d{1,7}$/.test(part)) {
      ring.serial = ring.serial ? ring.serial + part : part;
    } else if (!ring.union) {
      ring.union = part;
    }
  }
  return ring;
}

/** Canonical display string. Western digits only, by design. */
export function formatRing(ring) {
  if (!ring) return '';
  if (ring.raw) return ring.raw;
  return [ring.country, ring.union, ring.year, ring.serial].filter(Boolean).join('-');
}

/** Normalise for duplicate detection: strip separators, uppercase. */
export function ringKey(ring) {
  const s = typeof ring === 'string' ? ring : (ring && ring.raw) || formatRing(ring);
  return s.toUpperCase().replace(/[^A-Z0-9٠-٩]/g, '')
    // Eastern Arabic digits typed by the user normalise to Western
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660));
}

/**
 * Birds sharing a normalised ring number, grouped.
 *
 * Real lofts do re-ring birds, so a duplicate is a warning and never an error.
 * Extracted from the الأدوات card in v1.9 because the post-first-sync notice
 * needs the same answer: two devices that never synced generate DIFFERENT ids
 * for the same physical bird, so the first sync can surface pairs that are one
 * bird wearing two records. Only the user can say which — but they can only
 * say it if they are told.
 *
 * @returns [{ key, raw, birds: [...] }] — groups of two or more, in the order
 *   the rings were first seen, so the display is stable between runs.
 */
export function findDuplicateRings(birds) {
  const groups = new Map();
  for (const bird of birds || []) {
    for (const ring of bird.rings || []) {
      const key = ringKey(ring);
      if (!key) continue;
      if (!groups.has(key)) groups.set(key, { key, raw: ring.raw, birds: [] });
      const group = groups.get(key);
      if (!group.birds.includes(bird)) group.birds.push(bird);
    }
  }
  return [...groups.values()].filter((g) => g.birds.length > 1);
}
