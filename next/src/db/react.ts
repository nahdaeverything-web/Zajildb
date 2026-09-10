// src/db/react.ts — the React subscription bridge. THE ONLY NEW CODE IN PHASE 2.
//
// The data layer already has a change-event mechanism: storage.js keeps a
// listener Set, onChange(fn) subscribes and returns an unsubscribe, and every
// write ends in emitChange(what). This bridge subscribes to THAT. It adds no
// second event system, no store, no cache — it turns the layer's existing
// signal into a React re-render.
//
// Why a version counter. useSyncExternalStore re-renders when getSnapshot
// returns a different value, compared by Object.is. The layer's mirrors
// (state.birds etc.) are Maps mutated IN PLACE — the reference never changes,
// so snapshotting them would never re-render. A counter bumped on every
// emitChange is the stable, cheap signal; selectors then read state fresh
// during render.
//
// Imports the facade, not js/db/* — the layer's own rule ("Import from db.js,
// never from here directly — the facade is the API").
import { useSyncExternalStore, useEffect, useState } from 'react';
import * as db from '../db.js';

type State = typeof db.state;
type ChangeEvent = { type: string; id?: string; birdId?: string; store?: string };

let version = 0;
const listeners = new Set<() => void>();
let unhook: (() => void) | null = null;

function subscribe(cb: () => void) {
  listeners.add(cb);
  // one subscription to the layer, fanned out — installed lazily so a
  // server render (no listeners) never touches it
  if (!unhook) unhook = db.onChange(() => { version++; for (const l of listeners) l(); });
  return () => {
    listeners.delete(cb);
    if (listeners.size === 0 && unhook) { unhook(); unhook = null; }
  };
}
const getSnapshot = () => version;
const getServerSnapshot = () => 0;

/** Re-render on any data-layer change; return `selector(state)` read fresh. */
export function useZajilStore<T>(selector: (s: State) => T): T {
  useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  return selector(db.state);
}

// ── selectors over the in-memory mirrors ──
export const selectBirds    = (s: State) => [...s.birds.values()];
export const selectPairs    = (s: State) => [...s.pairs.values()];
export const selectRaces    = (s: State) => [...s.raceResults.values()];
export const selectHealth   = (s: State) => [...s.healthEvents.values()];
export const selectLofts    = (s: State) => [...s.lofts.values()];
export const selectSettings = (s: State) => s.settings;
export const selectBird     = (id: string) => (s: State) => s.birds.get(id) ?? null;

/**
 * Media metadata. The layer keeps NO in-memory mirror for media (it holds
 * blobs; records.js SYNC_MIRROR says so), so this cannot be a synchronous
 * selector. It is an async read that re-runs when the layer emits a media
 * change for this bird — still the same onChange signal, no second system.
 * Returns metadata only; blobs stay in IndexedDB until a view asks.
 */
export function useMediaForBird(birdId: string | null) {
  const [media, setMedia] = useState<Array<Record<string, unknown>>>([]);
  useEffect(() => {
    if (!birdId) { setMedia([]); return; }
    let live = true;
    const load = () => db.mediaForBird(birdId).then((rows: Array<Record<string, unknown>>) => {
      if (live) setMedia(rows.map((m) => { const { blob: _blob, ...meta } = m; return meta; }));
    });
    load();
    const off = db.onChange((ev: ChangeEvent) => { if (ev && ev.type === 'media' && ev.birdId === birdId) load(); });
    return () => { live = false; off(); };
  }, [birdId]);
  return media;
}
