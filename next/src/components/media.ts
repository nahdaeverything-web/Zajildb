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
 *   @2048 q0.85       2048×1365   0.44 MB     904 photos      ← what this did until 2026-11-18
 *   @1600 q0.85       1600×1066   0.30 MB    1331 photos      ← what this does (RULED 2026-11-18)
 *
 * WHAT IT COSTS, plainly:
 *   · it is LOSSY and IRREVERSIBLE — the original bytes are never stored, so a fancier
 *     cannot get the full-resolution image back out of Zajil later;
 *   · it applies to NEW photos only. Nothing already in a loft is touched, so an existing
 *     loft keeps whatever ceiling it already has;
 *   · 1600px on the longest edge is ~1.7 MP: enough for a phone screen and a certificate, not
 *     an archival copy. Whether a ring number stays legible at it is being checked on real photos.
 *
 * WHAT IT PRESERVES: the original filename, and PNG as PNG — a scanned pedigree arrives as PNG
 * and stays PNG, because JPEG rings badly on text. Anything that is not an image the browser
 * can decode (a PDF, say) passes through untouched. An image of a type outside JPEG, PNG and
 * WebP is converted to JPEG — see downscaleImage.
 */

/** The longest edge a stored image may have. RULED 2026-11-18 with photo sync: ONE size, 1600 px (≈ 1.7 MP), for NEW
 *  photos; a photo already stored at 2048 px stays and uploads as it is. The reviewer revises it only if a ring number
 *  proves illegible at 1600 px on Samir's own photos. It was 2048 until then. */
export const MAX_EDGE = 1600;
/** Quality for the JPEG re-encode. 0.85 measured at 0.44 MB for a 6.7 MP source. */
const JPEG_QUALITY = 0.85;

/** The name to store a picked file under: the converted file's own name when downscaleImage() renamed it. */
export function storedName(picked: File, out: Blob | File): string {
  return (out instanceof File && out.name) || picked.name;
}

/** The image types kept as they are picked: the storage allow-list's three image types. */
const KEPT_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

/**
 * RULED 2026-11-19 (the allow-list): an image of ANY OTHER type that the browser can decode — GIF, BMP, AVIF, HEIC
 * where the browser reads it, SVG where it does — is converted to JPEG at MAX_EDGE when picked, whatever its size,
 * because storage would refuse it as it is. One the browser cannot decode is stored as it is: it stays on this
 * device, and the upload pass tells the user so («نوع الملف … غير مسموح برفعه»). A converted file takes a `.jpg`
 * name, since its bytes are no longer what its old extension says.
 */
export async function downscaleImage(file: File): Promise<Blob | File> {
  if (!file.type.startsWith('image/')) return file;          // a PDF, or anything else
  const convert = !KEPT_TYPES.includes(file.type);

  let bmp: ImageBitmap;
  try {
    bmp = await createImageBitmap(file);
  } catch {
    return file;                                             // undecodable here — store as-is; it stays on this device
  }
  try {
    const longest = Math.max(bmp.width, bmp.height);
    if (!convert && longest <= MAX_EDGE) return file;        // already small enough

    const k = Math.min(1, MAX_EDGE / longest);               // a converted image is never enlarged
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bmp.width * k));
    canvas.height = Math.max(1, Math.round(bmp.height * k));
    const ctx = canvas.getContext('2d');
    if (!ctx) return file;
    if (convert) { ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height); }   // JPEG has no transparency: white, not black
    ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height);

    // keep PNG as PNG: a scanned pedigree is text, and JPEG rings on text
    const outType = !convert && file.type === 'image/png' ? 'image/png' : 'image/jpeg';
    const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, outType, JPEG_QUALITY));
    if (!blob) return file;
    // never make it worse: a small source can re-encode LARGER than it arrived. Not for a conversion — the point
    // there is the type, not the size.
    if (!convert && blob.size >= file.size) return file;
    const name = convert ? `${file.name.replace(/\.[^.\/\\]*$/, '')}.jpg` : file.name;
    return new File([blob], name, { type: outType, lastModified: file.lastModified });
  } finally {
    bmp.close();
  }
}
