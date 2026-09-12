import type { NextConfig } from 'next';

/**
 * Zajil has no server.
 *
 * Records live in IndexedDB on the device, sync talks to Supabase directly
 * from the browser, and hosting is a static file server. `output: 'export'`
 * is therefore not a deployment preference — it is the shape of the product,
 * and it enforces itself: with it set, Next refuses route handlers, cookies,
 * middleware/proxy, redirects, rewrites, headers, ISR and server actions at
 * build time, so a server dependency cannot be added by accident.
 *
 * Record views take their id from a query parameter (/bird?id=…), never a
 * dynamic [id] segment: user data has no build-time-knowable set of ids, so
 * `generateStaticParams()` could not enumerate it and the segment could not
 * be exported.
 */
/**
 * basePath comes from the environment because it is a BUILD-TIME constant: one build
 * serves one prefix, and `output: 'export'` forbids the rewrites that could normalise it
 * at request time. The default build is root-hosted; a subdirectory deployment is
 * `NEXT_PUBLIC_BASE_PATH=/zajil npm run build`, which is what the subpath suite does.
 *
 * assetPrefix would not be enough: it prefixes /_next assets but neither routes nor
 * next/link hrefs, and every page in this export links to /birds, /tools and the rest.
 * The same value reaches the service worker (scripts/build-sw.mjs) so its precache list
 * and its scope agree with the export it was generated from.
 */
const BASE_PATH = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/$/, '');

const nextConfig: NextConfig = {
  output: 'export',
  ...(BASE_PATH ? { basePath: BASE_PATH } : {}),

  // Photos are device-local blobs rendered from object URLs, never remote
  // sources — and the default next/image loader needs a server it will not
  // have. Nothing here should reach the optimizer.
  images: { unoptimized: true },
};

export default nextConfig;
