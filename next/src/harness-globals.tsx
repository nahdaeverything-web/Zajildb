// src/harness-globals.ts — STUB. This is the shipped file: it renders nothing
// and assigns nothing. `npm run build:harness` overwrites it with
// harness/HarnessGlobals.tsx for the duration of one build and restores this
// stub in its finally. The postbuild guard fails a normal build whose chunks
// mention __zajilDb, so a leak cannot ship quietly. Do not edit by hand.
export default function HarnessGlobals() { return null; }
// The coordinator's test-only switch (src/components/SyncCoordinator.tsx). In the shipped build it is this constant:
// nothing on a real device can turn automatic sync off by this route.
export const autoSyncDisabled = () => false;
