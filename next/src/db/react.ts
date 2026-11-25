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
// the register a fancier reads: without the placeholder parents the app makes for unknown ancestors (RULED 2026-11-23, src/family.js)
export const selectListedBirds = (s: State) => [...s.birds.values()].filter((b) => !db.isPlaceholder(b));
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
    // Clearing the list when the bird id goes away is not a cascade: there is nothing to
    // render for an id that is gone, and the list itself is an ASYNC read of IndexedDB, so
    // it cannot be a render-time value.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!birdId) { setMedia([]); return; }
    let live = true;
    // THE ORDER (RULED 2026-11-24, E4) is the layer's: mediaForBird() returns the main photo first, then by `addedAt`.
    // It rests on the bird's `mainPhotoId`, so the list is read again when THAT changes — set on the profile, set by the
    // certificate's «تغيير», cleared with the photo it named, or pulled from another device — and only then: a re-read
    // makes every thumbnail's object URL anew, which an unrelated edit of the bird must not do.
    const mainNow = () => ((db.getBird(birdId) as { mainPhotoId?: string } | undefined)?.mainPhotoId || null);
    let main = mainNow();
    const load = () => db.mediaForBird(birdId).then((rows: Array<Record<string, unknown>>) => {
      // `hasBlob` says whether the bytes are on this device (SYNC-DESIGN §7: metadata syncs, blobs do not) — the profile
      // gallery decides placeholder vs photo from it, then fetches the blob itself (idbGet) only for the rows it renders
      if (live) setMedia(rows.map((m) => { const { blob, ...meta } = m; return { ...meta, hasBlob: !!blob }; }));
    });
    load();
    // STAGE 3 (2026-11-20, measured): a PULLED media row arrives as a `sync` event with no bird id. Re-read on it too, or
    // an open profile keeps showing what was there before the pull until it is opened again.
    // ONE read for one write. A write that touches both the photo and the bird — the certificate's «تغيير», the deletion
    // of the main photo — announces both, one after the other; two reads would make every thumbnail's object URL twice
    // and revoke the first while it was still loading (measured: «Failed to load resource» on the certificate).
    let asked = false;
    const ask = () => { if (asked) return; asked = true; Promise.resolve().then(() => { asked = false; if (live) { main = mainNow(); load(); } }); };
    const off = db.onChange((ev: ChangeEvent) => {
      if (!ev) return;
      if ((ev.type === 'media' && ev.birdId === birdId) || (ev.type === 'sync' && ev.store === 'media')) ask();
      else if (((ev.type === 'bird' && ev.id === birdId) || (ev.type === 'sync' && ev.store === 'birds')) && mainNow() !== main) ask();
    });
    return () => { live = false; off(); };
  }, [birdId]);
  return media;
}
