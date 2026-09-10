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
const nextConfig: NextConfig = {
  output: 'export',

  // Photos are device-local blobs rendered from object URLs, never remote
  // sources — and the default next/image loader needs a server it will not
  // have. Nothing here should reach the optimizer.
  images: { unoptimized: true },
};

export default nextConfig;
