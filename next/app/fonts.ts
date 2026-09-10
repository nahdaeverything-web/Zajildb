import localFont from 'next/font/local';

/**
 * Self-hosted, deliberately.
 *
 * The approved specs load Alexandria and IBM Plex Mono from Google's CDN. An
 * offline-first app cannot let first paint depend on a CDN: on a loft with no
 * signal the fallback stack would render instead of the brand face, and the
 * layout would shift the moment a connection came back. Both families are
 * OFL 1.1 — licence text sits beside each face under public/fonts/.
 *
 * Alexandria is ONE variable file, not six weights. Google's CSS API served a
 * byte-identical woff2 for every weight the specs requested (hashes checked),
 * so the six declarations were aliases of a single variable font. It is
 * subset here to exactly Google's own `arabic` + `latin` unicode ranges — the
 * same coverage the specs rendered with — which is why it is one file rather
 * than the per-script pair the CDN serves: `next/font/local` has no
 * per-source `unicode-range`, so two same-weight files would shadow each
 * other.
 *
 * Plex Mono carries only the two static weights the specs actually load
 * (500, 600). Four spec rules ask it for 700/800; the CDN never supplied
 * those, so the specs faux-bolded them. Reproducing that faithfully means
 * not adding faces the specs did not have — raised in the phase report.
 */
export const alexandria = localFont({
  src: '../public/fonts/alexandria/alexandria-var.woff2',
  weight: '400 900',
  style: 'normal',
  display: 'swap',
  variable: '--font-alexandria',
  fallback: ['system-ui', 'sans-serif'],
});

export const plexMono = localFont({
  src: [
    { path: '../public/fonts/ibm-plex-mono/ibm-plex-mono-latin-500.woff2', weight: '500', style: 'normal' },
    { path: '../public/fonts/ibm-plex-mono/ibm-plex-mono-latin-600.woff2', weight: '600', style: 'normal' },
  ],
  display: 'swap',
  variable: '--font-plex-mono',
  fallback: ['monospace'],
});
