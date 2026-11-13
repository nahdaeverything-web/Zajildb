'use client';
import * as db from '@/src/db.js';
import * as coi from '@/src/engine/coi.js';
import * as fci from '@/src/engine/fci.js';
import * as integrity from '@/src/engine/integrity.js';
import * as pedigree from '@/src/engine/pedigree.js';
import * as relationship from '@/src/engine/relationship.js';
import * as rings from '@/src/engine/rings.js';
import * as validate from '@/src/engine/validate.js';
import * as velocity from '@/src/engine/velocity.js';

// Exposes the layer on window for EVERY route — but only in a harness build.
// The root layout renders this behind `process.env.NEXT_PUBLIC_HARNESS === '1'`,
// a build-time constant, so the normal build tree-shakes it out entirely; the
// postbuild guard fails a normal build whose chunks mention __zajilDb.
// Screen tests seed data through db.* on any page and assert on the screen.
if (typeof window !== 'undefined') {
  window.__zajilDb = db;
  window.__zajilEngine = { coi, fci, integrity, pedigree, relationship, rings, validate, velocity };
}
export default function HarnessGlobals() { return null; }
// TEST-ONLY, harness builds only: a suite that drives push and pull one leg at a time sets this global in an init script so
// the coordinator does not run cycles of its own in between. The shipped stub answers `false` unconditionally, and the
// postbuild guard fails a normal build whose chunks mention the name.
export const autoSyncDisabled = () => typeof globalThis !== 'undefined' && (globalThis as { __ZAJIL_TEST_NO_AUTOSYNC?: boolean }).__ZAJIL_TEST_NO_AUTOSYNC === true;
