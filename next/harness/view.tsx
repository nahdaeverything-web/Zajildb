'use client';
import { useEffect, useState } from 'react';
import * as db from '@/src/db.js';
import { initDB } from '@/src/components/boot';
import * as coi from '@/src/engine/coi.js';
import * as fci from '@/src/engine/fci.js';
import * as integrity from '@/src/engine/integrity.js';
import * as pedigree from '@/src/engine/pedigree.js';
import * as relationship from '@/src/engine/relationship.js';
import * as rings from '@/src/engine/rings.js';
import * as validate from '@/src/engine/validate.js';
import * as velocity from '@/src/engine/velocity.js';
import { useZajilStore, selectBirds } from '@/src/db/react';

// The vanilla suites reach the data layer with `await import('./js/db.js')`
// inside page.evaluate. The port exposes the same module namespace on
// window, synchronously at bundle evaluation so it is present the moment the
// page's scripts run — the suites wait a fixed 2 s after goto, not on an
// event. The engine is exposed the same way for the three suites that import
// integrity.js directly.
if (typeof window !== 'undefined') {
  window.__zajilDb = db;
  window.__zajilEngine = { coi, fci, integrity, pedigree, relationship, rings, validate, velocity };
}

// Renders THROUGH the bridge. The 2.4 proof saves a bird via window.__zajilDb
// (the layer, not React) and asserts this component re-rendered.
function BridgeDemo() {
  const birds = useZajilStore(selectBirds);
  const last = birds[birds.length - 1];
  return (
    <p>bridge: <span id="bridge-count">{birds.length}</span> birds · last: <span id="bridge-last">{last ? last.name : '—'}</span></p>
  );
}

export default function HarnessView() {
  const [status, setStatus] = useState('booting');
  // The sync loop is NOT started here any more (`?sync=1` is gone, 2026-11-13): the coordinator in the root layout
  // starts it at boot on every route, this one included — src/components/SyncCoordinator.tsx. A suite CAN switch it off
  // with the harness-only global (harness/HarnessGlobals.tsx); as of this date none needs to, and only the two that test the switch do.
  useEffect(() => {
    window.__zajilReady = initDB().then(() => { setStatus('ready'); }, (e: unknown) => setStatus('failed: ' + String(e)));
  }, []);
  return (
    <section style={{ padding: 24 }} dir="ltr">
      <h1>test-harness</h1>
      <p id="harness-status">{status}</p>
      <p>window.__zajilDb ({Object.keys(db).length} exports) · window.__zajilEngine (8 modules)</p>
      <BridgeDemo />
    </section>
  );
}
