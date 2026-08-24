// engine/velocity.js — race velocity from GPS coordinates.
// Pigeon racing velocity is conventionally metres per minute (m/min).

const R_EARTH = 6371008.8; // mean Earth radius, metres

/** Great-circle distance in metres between two {lat, lon} points (degrees). */
export function haversineMetres(a, b) {
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLon = rad(b.lon - a.lon);
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R_EARTH * Math.asin(Math.min(1, Math.sqrt(s)));
}

/**
 * Velocity in m/min.
 * release/arrival: ISO datetime strings or Date. Returns null when invalid.
 */
export function velocityMPM(releasePoint, loftPoint, releaseTime, arrivalTime) {
  const dist = haversineMetres(releasePoint, loftPoint);
  const t0 = new Date(releaseTime).getTime();
  const t1 = new Date(arrivalTime).getTime();
  if (!isFinite(dist) || !isFinite(t0) || !isFinite(t1) || t1 <= t0) return null;
  const minutes = (t1 - t0) / 60000;
  return dist / minutes;
}
