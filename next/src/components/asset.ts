/**
 * The URL of a file that ships at the DEPLOYMENT ROOT — the teaching datasets, and anything
 * else dropped in `public/`.
 *
 * WHY THIS EXISTS AT ALL. These were `fetch('./example-loft-large.json')`, which is correct
 * only while every route is a flat document at the root. `trailingSlash: true` (RULED
 * 2026-09-25, so a cold visit to a deep link cannot depend on a host's .html fallback) puts
 * every screen one directory down: the loft is at `<base>/birds/`, so `./x` resolved to
 * `<base>/birds/x`. The host answered with its own 404 page and the app reported
 * «Unexpected token '<', "<!DOCTYPE "... is not valid JSON» — a JSON parser being handed
 * HTML, which says nothing about the real cause. Found by the deploy gate, not by a reader.
 *
 * Built from NEXT_PUBLIC_BASE_PATH, which is a BUILD-TIME constant, so this is depth-proof by
 * construction rather than by everyone remembering how deep their screen sits. Same variable
 * and same reason as src/components/ServiceWorker.tsx and app/layout.tsx; it lives here so
 * there is ONE rule for building these URLs instead of a copy per screen.
 *
 * Accepts './x.json', '/x.json' or 'x.json' — all three appear in the call sites it replaced.
 */
const BASE = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/$/, '');

export function asset(name: string): string {
  return `${BASE}/${name.replace(/^\.?\//, '')}`;
}
