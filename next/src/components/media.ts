/**
 * Downscale a picked image before it is stored.
 *
 * WHY. Photos were stored exactly as the picker handed them over — `app/bird/form.tsx` passed
 * the raw `File` straight to `addMedia`. A current phone produces 3–12 MB a photo, and the
 * export/import path has a hard ceiling at 403 MB of photo bytes (V8 caps a string at
 * 536,870,888 bytes and the export runs 1.3337× source). Measured on a real photograph —
 * 3176×2117, 5.18 MB — that is **77 photos** before a loft can no longer be moved between
 * origins. Seventy-seven is a normal loft, not a large one, so this is a correctness fix.
 *
 * Measured, same photograph, through this exact pipeline:
 *
 *   as stored today   3176×2117   5.18 MB      77 photos
 *   @2048 q0.85       2048×1365   0.44 MB     904 photos      ← what this does
 *   @1600 q0.85       1600×1066   0.30 MB    1331 photos
 *
 * WHAT IT COSTS, plainly:
 *   · it is LOSSY and IRREVERSIBLE — the original bytes are never stored, so a fancier
 *     cannot get the full-resolution image back out of Zajil later;
 *   · it applies to NEW photos only. Nothing already in a loft is touched, so an existing
 *     loft keeps whatever ceiling it already has;
 *   · 2048px on the longest edge is ~3 MP, which is more than a pedigree certificate or a
 *     phone screen ever shows, but it is not an archival copy.
 *
 * WHAT IT PRESERVES: the original filename, and the original format for anything that is not
 * a JPEG — a scanned pedigree arrives as PNG and stays PNG, because JPEG rings badly on text.
 * Anything that is not a raster image the browser can decode (a PDF, say) passes through
 * untouched.
 */

/** The longest edge a stored image may have. 2048px ≈ 3 MP. */
export const MAX_EDGE = 2048;
/** Quality for the JPEG re-encode. 0.85 measured at 0.44 MB for a 6.7 MP source. */
const JPEG_QUALITY = 0.85;

export async function downscaleImage(file: File): Promise<Blob | File> {
  if (!file.type.startsWith('image/')) return file;          // a PDF, or anything else
  // SVG has no pixel dimensions to cap and would be destroyed by a raster round trip
  if (file.type === 'image/svg+xml') return file;

  let bmp: ImageBitmap;
  try {
    bmp = await createImageBitmap(file);
  } catch {
    return file;                                             // undecodable here — store as-is
  }
  try {
    if (Math.max(bmp.width, bmp.height) <= MAX_EDGE) return file;   // already small enough

    const k = MAX_EDGE / Math.max(bmp.width, bmp.height);
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(bmp.width * k);
    canvas.height = Math.round(bmp.height * k);
    const ctx = canvas.getContext('2d');
    if (!ctx) return file;
    ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height);

    // keep PNG as PNG: a scanned pedigree is text, and JPEG rings on text
    const outType = file.type === 'image/png' ? 'image/png' : 'image/jpeg';
    const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, outType, JPEG_QUALITY));
    if (!blob) return file;
    // never make it worse: a small source can re-encode LARGER than it arrived
    if (blob.size >= file.size) return file;
    return new File([blob], file.name, { type: outType, lastModified: file.lastModified });
  } finally {
    bmp.close();
  }
}
