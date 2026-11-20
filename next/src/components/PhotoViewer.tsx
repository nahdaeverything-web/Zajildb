'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import * as db from '@/src/db.js';
import { t } from '@/src/i18n.ext.js';
import { useScrollLock } from './scrim';
import s from './PhotoViewer.module.css';

/**
 * THE PHOTO VIEWER (ORDERED 2026-11-20, found by Samir on both devices: tapping a photo did nothing).
 *
 * A tap on a photo's tile — the bird's profile or the edit form's strip — opens it full screen. Swipe between the
 * bird's photos (right-to-left: the next photo comes from the left, as the tiles run), pinch to zoom on a phone, and
 * close by a tap, a swipe down, the back button or the close button in the top corner. RULED 2026-11-20: a tap closes
 * only at 1× — zoomed in, a tap does nothing and a double tap returns to 1×; the close button is there on every screen,
 * because older users will not discover gestures; the counter is «2 / 5» in Western digits whatever the numerals setting. A photo whose bytes are not on this device opens in the tile's own
 * words — «جارٍ تنزيل الصورة…» — and becomes the photo when the bytes land (src/db/photos.js fetchPhotoBytes, the one
 * fetch per id the profile and the background pass share). Documents are not shown here: they open in the browser's
 * own viewer from their tile.
 *
 * The back button: one history entry is pushed when the viewer opens; going back pops it and closes the viewer, and a
 * close from inside the viewer takes the entry back off. The page underneath is never navigated.
 */
export type ViewerItem = { key: string; id?: string; url?: string; name?: string };
type Shown = { state: 'loading' | 'photo' | 'fetching' | 'failed' | 'pending' | 'elsewhere'; url?: string };
const STATE_KEY: Record<string, string> = { fetching: 'media.fetching', failed: 'media.fetchFailed', pending: 'media.notUploadedYet', elsewhere: 'media.elsewhere' };
const MAX_SCALE = 4;

/** What to draw for one item: its bytes if they are here, else the fetch — the same words as the tile. */
function useShown(item: ViewerItem | undefined): Shown {
  const [shown, setShown] = useState<Shown>({ state: 'loading' });
  const key = item ? item.key : '';
  useEffect(() => {
    if (!item) return;
    if (item.url) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShown({ state: 'photo', url: item.url }); return;
    }
    const id = item.id as string;
    let live = true; let made: string | null = null;
    const fromHere = async (): Promise<boolean | { stored?: unknown } | null> => {
      const row = (await db.idbGet('media', id)) as { blob?: Blob; stored?: unknown } | undefined;
      if (!live) return true;
      if (row && row.blob) {
        if (made) URL.revokeObjectURL(made);
        made = URL.createObjectURL(row.blob); setShown({ state: 'photo', url: made }); return true;
      }
      return row || null;
    };
    setShown({ state: 'loading' });
    (async () => {
      const row = await fromHere();
      if (row === true || !live) return;
      if (!row) { setShown({ state: 'failed' }); return; }
      if (!row.stored) { setShown({ state: db.isSignedIn() ? 'pending' : 'elsewhere' }); return; }
      setShown({ state: 'fetching' });
      const r = await db.fetchPhotoBytes(id);
      if (!live) return;
      if (r === 'here') await fromHere(); else setShown({ state: 'failed' });
    })();
    // the bytes may land by another route (the background pass, the profile's own fetch): show them when they do
    const off = db.onChange((ev: { type?: string; id?: string }) => { if (ev && ev.type === 'media' && ev.id === id) fromHere(); });
    return () => { live = false; off(); if (made) URL.revokeObjectURL(made); };
  }, [key]);   // eslint-disable-line react-hooks/exhaustive-deps
  return shown;
}

export default function PhotoViewer({ items, start, onClose }: { items: ViewerItem[]; start: number; onClose: () => void }) {
  useScrollLock();                                    // the page behind does not scroll under the viewer
  const n = items.length;
  const [i, setI] = useState(Math.max(0, Math.min(start, n - 1)));
  const [zoom, setZoom] = useState({ scale: 1, x: 0, y: 0 });
  const [drag, setDrag] = useState({ x: 0, y: 0, live: false });
  const shown = useShown(items[i]);
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; }, [onClose]);

  // THE BACK BUTTON closes the viewer
  const pushed = useRef(false);
  useEffect(() => {
    try { window.history.pushState({ zajilViewer: true }, ''); pushed.current = true; } catch { pushed.current = false; }
    const onPop = () => { if (pushed.current) { pushed.current = false; closeRef.current(); } };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);
  const close = useCallback(() => {
    if (pushed.current) { pushed.current = false; window.history.back(); }
    closeRef.current();
  }, []);
  const go = useCallback((d: number) => {
    setI((v) => Math.max(0, Math.min(n - 1, v + d)));
    setZoom({ scale: 1, x: 0, y: 0 });
  }, [n]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
      else if (e.key === 'ArrowLeft') go(1);          // right-to-left: the next photo is to the left
      else if (e.key === 'ArrowRight') go(-1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [close, go]);

  // GESTURES — pointer events, so a finger and a mouse are one code path. One pointer: a tap closes; a sideways swipe
  // changes photo; a swipe down closes; when zoomed in, it pans. Two pointers: pinch to zoom, 1× to 4×.
  const pts = useRef(new Map<number, { x: number; y: number }>());
  const g = useRef<{ x0: number; y0: number; t0: number; multi: boolean; axis: '' | 'x' | 'y'; dist0: number; scale0: number; px: number; py: number } | null>(null);
  const lastTap = useRef(0);                       // when the last tap landed while zoomed in: a second one soon after is a double tap
  const zoomRef = useRef(zoom);
  useEffect(() => { zoomRef.current = zoom; }, [zoom]);
  const spread = () => { const [a, b] = [...pts.current.values()]; return a && b ? Math.hypot(a.x - b.x, a.y - b.y) : 0; };
  const onDown = (e: React.PointerEvent<HTMLDivElement>) => {
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* a synthetic pointer */ }
    pts.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const z = zoomRef.current;
    if (pts.current.size === 1) g.current = { x0: e.clientX, y0: e.clientY, t0: Date.now(), multi: false, axis: '', dist0: 0, scale0: z.scale, px: z.x, py: z.y };
    else if (pts.current.size === 2 && g.current) { g.current.multi = true; g.current.dist0 = spread(); g.current.scale0 = z.scale; setDrag({ x: 0, y: 0, live: false }); }
  };
  const onMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!pts.current.has(e.pointerId) || !g.current) return;
    pts.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const gg = g.current;
    if (pts.current.size >= 2) {
      if (gg.dist0 > 0) { const scale = Math.max(1, Math.min(MAX_SCALE, gg.scale0 * (spread() / gg.dist0))); setZoom((z) => ({ ...z, scale })); }
      return;
    }
    if (gg.multi) return;                              // the second finger lifted: the gesture stays a pinch
    const dx = e.clientX - gg.x0, dy = e.clientY - gg.y0;
    if (zoomRef.current.scale > 1) { setZoom((z) => ({ ...z, x: gg.px + dx, y: gg.py + dy })); return; }
    if (!gg.axis && Math.hypot(dx, dy) > 10) gg.axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
    if (gg.axis === 'x') setDrag({ x: dx, y: 0, live: true });
    else if (gg.axis === 'y') setDrag({ x: 0, y: Math.max(0, dy), live: true });
  };
  const onUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!pts.current.has(e.pointerId)) return;
    pts.current.delete(e.pointerId);
    if (pts.current.size > 0) return;                  // a pinch ends when the last finger lifts
    const gg = g.current; g.current = null;
    setDrag({ x: 0, y: 0, live: false });
    if (!gg) return;
    const dx = e.clientX - gg.x0, dy = e.clientY - gg.y0;
    if (gg.multi) { if (zoomRef.current.scale < 1.05) setZoom({ scale: 1, x: 0, y: 0 }); return; }
    if (Math.hypot(dx, dy) < 10 && Date.now() - gg.t0 < 500) {                       // a tap
      if (zoomRef.current.scale > 1) {                // zoomed in: a tap does nothing; a double tap returns to 1×
        const now = Date.now();
        if (now - lastTap.current < 350) { lastTap.current = 0; setZoom({ scale: 1, x: 0, y: 0 }); } else lastTap.current = now;
        return;
      }
      close(); return;
    }
    if (zoomRef.current.scale > 1) return;
    if (gg.axis === 'x' && Math.abs(dx) > 60) { go(dx > 0 ? 1 : -1); return; }       // right-to-left
    if (gg.axis === 'y' && dy > 100) close();
  };
  const onCancel = (e: React.PointerEvent<HTMLDivElement>) => { pts.current.delete(e.pointerId); if (!pts.current.size) { g.current = null; setDrag({ x: 0, y: 0, live: false }); } };

  const item = items[i];
  const tx = drag.x + zoom.x, ty = drag.y + zoom.y;
  return (
    <div className={s.viewer} role="dialog" aria-modal="true" aria-label={t('bird.photos')} data-testid="viewer" data-index={i}>
      <div className={s.stage} data-testid="viewer-stage" data-scale={zoom.scale.toFixed(2)} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onCancel}
        style={{ opacity: drag.y > 0 ? Math.max(0.35, 1 - drag.y / 400) : 1 }}>
        {shown.state === 'photo' && shown.url
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={shown.url} alt={item && item.name ? item.name : ''} draggable={false} data-testid="viewer-img"
              className={drag.live ? s.live : undefined} style={{ transform: `translate(${tx}px, ${ty}px) scale(${zoom.scale})` }} />
          : shown.state === 'loading' ? null
          : <div className={s.state} data-testid="viewer-state" data-where={shown.state}><span>{t(STATE_KEY[shown.state])}</span>{item && item.name && <small>{item.name}</small>}</div>}
      </div>
      <div className={s.top}>
        <span className={s.count} dir="ltr" data-testid="viewer-count">{n > 1 ? `${i + 1} / ${n}` : ''}</span>
        <button type="button" className={s.btn} onClick={close} aria-label={t('act.close')} data-testid="viewer-close">✕</button>
      </div>
      {n > 1 && i > 0 && <button type="button" className={`${s.btn} ${s.prev}`} onClick={() => go(-1)} aria-label={t('viewer.prev')} data-testid="viewer-prev">›</button>}
      {n > 1 && i < n - 1 && <button type="button" className={`${s.btn} ${s.next}`} onClick={() => go(1)} aria-label={t('viewer.next')} data-testid="viewer-next">‹</button>}
    </div>
  );
}
