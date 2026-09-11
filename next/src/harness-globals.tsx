// src/harness-globals.ts — STUB. This is the shipped file: it renders nothing
// and assigns nothing. `npm run build:harness` overwrites it with
// harness/HarnessGlobals.tsx for the duration of one build and restores this
// stub in its finally. The postbuild guard fails a normal build whose chunks
// mention __zajilDb, so a leak cannot ship quietly. Do not edit by hand.
export default function HarnessGlobals() { return null; }
