import { t } from '@/src/i18n.ext.js';

// ONE season rule, everywhere a season is DISPLAYED (ruled at 4A acceptance,
// item 6): split-year «2026 / 2027», turning over on 1 July. Profile race
// tables, the loft-home eyebrow, races and stats all read these. Breeding's
// stored `season` field stays vanilla's plain year — data, not display.

/** Start year of the season a date falls in; 0 when the date is unusable. */
export function seasonStart(d: string | Date = new Date()): number {
  const dt = typeof d === 'string' ? new Date(d.slice(0, 10) + 'T00:00:00') : d;
  if (isNaN(dt.getTime())) return 0;
  const y = dt.getFullYear();
  return dt.getMonth() + 1 >= 7 ? y : y - 1;
}

/** «موسم 2026 / 2027» for the season a date falls in (today by default). */
export function seasonLabel(d?: string | Date): string {
  const a = seasonStart(d);
  return a ? t('loft.season', { a, b: a + 1 }) : '—';
}
