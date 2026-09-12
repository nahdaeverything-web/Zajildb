import * as db from '@/src/db.js';
import { ringKey, parseRing } from '@/src/engine/rings.js';
import { birdLabelText } from './BirdBits';

// The bird picker's RULES, once — js/ui.js:205 birdPicker. Each screen draws the
// picker in its own spec's grammar (a parent slot on the form, a .pick field in a
// sheet), but the rules below are the ones the root suites pin (picker_guards,
// picker_duplicates) and they must not drift between screens:
//
//   · candidates match name, strain or NORMALISED ring, so Eastern-Arabic digits
//     and Western digits are the same ring (ringKey);
//   · a query that already resolves to a real bird never offers to create a second
//     record for it — even when THIS picker cannot select that bird;
//   · a match this picker's filter excludes explains itself instead of showing an
//     empty list;
//   · creating checks once more for an exact match and selects it instead, so a
//     double tap cannot mint a duplicate;
//   · a query carrying digits (either numeral system) is a RING, not a name.
export type PickerBird = { id: string; name?: string; sex?: string; strain?: string; rings?: Array<{ raw?: string; type?: string; year?: number | string | null }> };

const hasDigit = (s: string) => /[0-9٠-٩]/.test(s);

/** Every bird whose name, strain or normalised ring contains the query (capped, as vanilla). */
export function candidates(pool: PickerBird[], q: string, limit = 30): PickerBird[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return pool.slice(0, limit);
  const rk = ringKey(q);
  return pool.filter((b) => (b.name || '').toLowerCase().includes(needle)
    || (b.strain || '').toLowerCase().includes(needle)
    || (rk && (b.rings || []).some((r) => ringKey(r as never).includes(rk)))).slice(0, limit);
}

/** ui.js exactMatch: normalised ring, exact name, or the full display label. */
export function exactMatch(list: PickerBird[], q: string): PickerBird | null {
  const needle = q.trim().toLowerCase();
  if (!needle) return null;
  const rk = ringKey(q);
  return list.find((b) => (rk && (b.rings || []).some((r) => ringKey(r as never) === rk))
    || (b.name || '').trim().toLowerCase() === needle
    || birdLabelText(b).trim().toLowerCase() === needle) || null;
}

/**
 * What the picker should show for `q`: the candidates, the bird this picker cannot
 * offer (so it can say why), and whether creating is allowed.
 * `selected` is the committed id — while one is set, creating is never offered.
 */
export function pickerModel({ all, pool, q, allowCreate = false, selected = null }:
  { all: PickerBird[]; pool: PickerBird[]; q: string; allowCreate?: boolean; selected?: string | null }) {
  const needle = q.trim();
  const cands = candidates(pool, q);
  const clash = needle ? exactMatch(all, q) : null;
  const blocked = clash && !exactMatch(pool, q) ? clash : null;
  return { cands, blocked, canCreate: !!(allowCreate && needle && !selected && !clash), clash };
}

/**
 * ui.js:306 — create, with the dedupe re-check first. Returns the existing bird when
 * the query already names one, so a second tap can never produce a second record.
 * A query with digits (either numeral system) is filed as a ring, not a name.
 */
export async function createFromQuery(q: string, sex: 'cock' | 'hen' | 'unknown' = 'unknown'): Promise<PickerBird> {
  const all = [...(db.state.birds.values() as Iterable<PickerBird>)];
  const dupe = exactMatch(all, q);
  if (dupe) return dupe;
  const digits = hasDigit(q);
  const stub = db.newBird({ external: true, sex, name: digits ? '' : q.trim(), rings: digits ? [parseRing(q.trim())] : [] }) as PickerBird;
  await db.saveBird(stub);
  return stub;
}
