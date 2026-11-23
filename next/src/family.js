// src/family.js — placeholder parents (RULED 2026-11-23). Port-only: the vanilla app has no counterpart.
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
import { allBirds } from './db/storage.js';

/** Is this bird a placeholder parent? Missing means false. */
export const isPlaceholder = (bird) => !!bird && bird.placeholder === true;

/** Every bird a fancier would call a bird: the register without its placeholder parents. */
export const listedBirds = () => allBirds().filter((b) => !isPlaceholder(b));
