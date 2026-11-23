// src/family.js — placeholder parents, clutches and the sibling link (RULED 2026-11-23). Port-only: the vanilla app has
// no counterpart.
//
// A PLACEHOLDER is the record the app itself makes for a parent nobody knows, so that two birds can be recorded as
// siblings: kinship is derived from shared sireId / damId and from nothing else, so "the same unknown father" has to be
// a record both birds point to. It is a real bird record — external, with the reference status — and it carries
// `placeholder: true`. A record without the flag is not a placeholder: missing means false, and nothing is guessed
// from a name.
//
// The flag says ONE thing: "the app made this, and nobody has said who it is". So the register a fancier reads — the
// bird list and everything fed by it, the bird counts, every picker — leaves these records out, and the pedigree, the
// profile and the certificate print «غير معروف» for them in the language of the screen instead of the name stored when
// they were made. The duplicate-ring search and the integrity check still see them: they are records.
import { allBirds, getBird, state, uuid } from './db/storage.js';
import { newBird } from './db/records.js';
import { ancestorDepths } from './engine/pedigree.js';
import { clutchMates as matesIn } from './engine/clutch.js';

/** Is this bird a placeholder parent? Missing means false. */
export const isPlaceholder = (bird) => !!bird && bird.placeholder === true;

/** Every bird a fancier would call a bird: the register without its placeholder parents. */
export const listedBirds = () => allBirds().filter((b) => !isPlaceholder(b));

// ───────────────────────────── clutches and siblings ─────────────────────────────

/**
 * The birds recorded as hatched from the same clutch as this one: those sharing its `clutchId`, and those whose ids
 * are `chickId` in the same round of a pair as this bird (engine/clutch.js — the one implementation, bound here to
 * the register). Nothing writes clutchId when a chick is ringed from an egg; the round is that record.
 */
export function clutchMates(bird) {
  return matesIn(bird, allBirds(), state.pairs.values(), getBird);
}

/**
 * Full and half siblings, derived as the engine derives them (engine/relationship.js): the same sire AND the same dam
 * is a full sibling, one of the two a half sibling. Placeholder parents count — that is what they are for — and a
 * placeholder is never listed as a sibling itself.
 */
export function siblingsOf(bird) {
  const full = [], half = [];
  if (!bird || (!bird.sireId && !bird.damId)) return { full, half };
  for (const b of allBirds()) {
    if (b.id === bird.id || isPlaceholder(b)) continue;
    const sire = !!bird.sireId && b.sireId === bird.sireId;
    const dam = !!bird.damId && b.damId === bird.damId;
    if (sire && dam) full.push(b); else if (sire || dam) half.push(b);
  }
  return { full, half };
}

/**
 * Is `x` an ancestor or a descendant of `bird`? `bird` is the record as it would be saved and need not be stored yet,
 * so the walk upward starts from the parents it names.
 * @returns {'ancestor'|'descendant'|null}
 */
export function lineageBetween(bird, x) {
  if (!bird || !x) return null;
  if (ancestorDepths(getBird, [bird.sireId, bird.damId], 99, 1).has(x.id)) return 'ancestor';
  if (ancestorDepths(getBird, [x.sireId, x.damId], 99, 1).has(bird.id)) return 'descendant';
  return null;
}

/**
 * THE SIBLING LINK, AS A PLAN (RULED 2026-11-23). «أخ/أخت لطير مسجَّل…» on the bird form: this bird is a sibling of X
 * through both parents, the father only or the mother only, and optionally from the same clutch (which forces both).
 * NOTHING IS WRITTEN HERE. The form holds the choice until it is saved, and hands what this returns to saveBirds(),
 * which writes all of it in one transaction — so cancelling the form writes nothing at all.
 *
 * For each parent chosen:
 *   · X has it                     → this bird is given X's;
 *   · X lacks it, this bird has it → X is given this bird's (PROPOSED, not ruled: the two then share the parent that
 *                                    is recorded, and nothing of either bird is replaced);
 *   · neither has it               → a new placeholder, given to both.
 * A parent of this bird that differs from X's is NOT replaced here: it is reported in `conflicts`, the form asks, naming
 * both, and plans again with the answer. `reject` is set when X is this bird, a placeholder, or its ancestor or
 * descendant.
 *
 * Same clutch: X's clutchId is copied, or this bird's given to X, or a new one made for both; an empty hatch date takes
 * X's, two different hatch dates are a warning, and so is a clutch that would hold more than two birds.
 *
 * @param bird    the record the form is about to save
 * @param x       the recorded bird, as stored now
 * @param choice  { sire, dam, clutch }
 * @param names   { sire, dam } — what a new placeholder is stored under (the display never reads it)
 * @returns {{ reject: string|null, conflicts: Array, bird: object, x: object|null, placeholders: Array, warnings: Array }}
 */
export function planSiblingLink(bird, x, choice = {}, names = {}) {
  const want = { sire: !!choice.sire || !!choice.clutch, dam: !!choice.dam || !!choice.clutch };
  const plan = { reject: null, conflicts: [], bird: { ...bird }, x: null, placeholders: [], warnings: [] };
  if (!x || x.id === bird.id || isPlaceholder(x)) { plan.reject = 'target'; return plan; }
  const line = lineageBetween(bird, x);
  if (line) { plan.reject = line; return plan; }

  const other = { ...x };
  let otherChanged = false;
  for (const [role, key, sex] of [['sire', 'sireId', 'cock'], ['dam', 'damId', 'hen']]) {
    if (!want[role]) continue;
    const mine = plan.bird[key] || null, theirs = x[key] || null;
    if (theirs) {
      if (mine && mine !== theirs) plan.conflicts.push({ role, mine, theirs });
      else plan.bird[key] = theirs;
    } else if (mine) {
      other[key] = mine; otherChanged = true;
    } else {
      const made = newBird({ name: names[role] || '', sex, placeholder: true });
      plan.placeholders.push(made);
      plan.bird[key] = made.id; other[key] = made.id; otherChanged = true;
    }
  }

  if (choice.clutch) {
    const clutchId = x.clutchId || plan.bird.clutchId || uuid();
    plan.bird.clutchId = clutchId;
    if (other.clutchId !== clutchId) { other.clutchId = clutchId; otherChanged = true; }
    if (!plan.bird.hatchDate && x.hatchDate) plan.bird.hatchDate = x.hatchDate;
    else if (plan.bird.hatchDate && x.hatchDate && plan.bird.hatchDate !== x.hatchDate) {
      plan.warnings.push({ key: 'sib.warn.hatchDiffers', params: { mine: plan.bird.hatchDate, theirs: x.hatchDate, otherId: x.id, otherName: x.name || '' } });
    }
    // everyone the clutch would hold: the two birds, whoever already carries the group id, and each one's round-mates
    const held = new Set([plan.bird.id, x.id]);
    for (const m of clutchMates(other)) held.add(m.id);
    for (const m of clutchMates(plan.bird)) held.add(m.id);
    if (held.size > 2) plan.warnings.push({ key: 'sib.warn.clutchSize', params: { n: held.size } });
  }
  if (otherChanged) plan.x = other;
  return plan;
}
