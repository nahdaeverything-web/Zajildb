#!/usr/bin/env python3
"""A photo picked on a phone is stored DOWNSCALED, not as the camera produced it.

WHY THIS EXISTS. Photos used to be stored exactly as the picker handed them over
(`app/bird/form.tsx` passed the raw File to addMedia). A current phone produces 3-12 MB a
photo, and the export/import path has a hard ceiling at 403 MB of photo bytes — V8 caps a
string at 536,870,888 bytes and the export runs 1.3337x source. Measured on a REAL
photograph, 3176x2117 at 5.18 MB, that is 77 photos before a loft can no longer be moved
between origins. Seventy-seven is a normal loft.

`src/components/media.ts` caps the longest edge at 1600px (2048 until 2026-11-18) on the way in. Measured through
that same pipeline, the same photograph becomes 0.44 MB — 904 photos before the wall.

This suite asserts the cap actually applies to what is STORED, by reading the blob back out
of IndexedDB and decoding it. Asserting on the picked File would prove nothing: the point is
what survives into the database.

Binds to data-testid only. Provisions its own server (R6)."""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr   # TF-12: a page error is recorded with its stack, address, device and step
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sync'))
from _serve import serve

passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness/', '')

# A large source image, built in the page: 4000x3000 (12 MP), well over the 1600 cap. It is
# drawn with structure rather than flat colour so the JPEG encoder has something to do — a
# flat image would compress to nothing and the "did it shrink" assertion would be vacuous.
MAKE_BIG = """async (mime) => {
  const c = document.createElement('canvas'); c.width = 4000; c.height = 3000;
  const x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, c.width, c.height);
  g.addColorStop(0, '#7fa8d0'); g.addColorStop(0.5, '#d8c49a'); g.addColorStop(1, '#33452f');
  x.fillStyle = g; x.fillRect(0, 0, c.width, c.height);
  for (let i = 0; i < 4000; i++) {
    x.globalAlpha = 0.05 + (i % 11) / 40;
    x.fillStyle = i % 3 ? '#222' : '#f2ead6';
    x.beginPath();
    x.ellipse((i * 149) % c.width, (i * 97) % c.height, 4 + (i % 31), 2 + (i % 13), i, 0, 7);
    x.fill();
  }
  x.globalAlpha = 1;
  const blob = await new Promise(r => c.toBlob(r, mime, 0.95));
  return { bytes: blob.size, w: c.width, h: c.height,
           dataURL: await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(blob); }) };
}"""

# what is actually in the store, decoded
STORED = """async () => {
  const rows = await new Promise((res, rej) => {
    const r = indexedDB.open('zajil');
    r.onsuccess = () => { const d = r.result;
      const tx = d.transaction('media', 'readonly').objectStore('media').getAll();
      tx.onsuccess = () => { res(tx.result); d.close(); }; tx.onerror = () => rej(tx.error); };
    r.onerror = () => rej(r.error);
  });
  const out = [];
  for (const m of rows) {
    const bmp = await createImageBitmap(m.blob);
    out.push({ id: m.id, name: m.name, type: m.blob.type, bytes: m.blob.size, w: bmp.width, h: bmp.height });
    bmp.close();
  }
  return out;
}"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context()
        errs = []
        pg = ctx.new_page(); pg.on('pageerror', lambda e, _p=pg: errs.append(perr(e, _p)))
        pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(800)
        pg.evaluate("async () => { await window.__zajilReady; }")
        pg.evaluate("async () => { const db = await window.__zajilDb; for (const x of db.allBirds()) await db.deleteBird(x.id); }")

        big = pg.evaluate(MAKE_BIG, 'image/jpeg')
        check('the fixture is a genuinely large source image', big['w'] == 4000 and big['bytes'] > 700_000,
              f"{big['w']}x{big['h']}, {big['bytes'] / 1e6:.2f} MB")

        # picked through the REAL form, exactly as a fancier would
        form = ctx.new_page(); form.on('pageerror', lambda e, _p=form: errs.append(perr(e, _p)))
        form.goto(f'{ROOT}bird/new/', wait_until='load'); form.wait_for_timeout(1200)
        raw = pg.evaluate("(d) => { const b = atob(d.split(',')[1]); const u = new Uint8Array(b.length);"
                          " for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return [...u]; }", big['dataURL'])
        form.set_input_files('input[type=file][accept="image/*"]',
                             files=[{'name': 'camera-original.jpg', 'mimeType': 'image/jpeg', 'buffer': bytes(raw)}])
        form.wait_for_timeout(400)
        check('the picked file is listed on the form before saving',
              form.locator('[data-testid=pending-media]').count() == 1,
              form.locator('[data-testid=pending-media]').inner_text() if form.locator('[data-testid=pending-media]').count() else '')

        form.fill('[data-testid=f-name]', 'طائر الصورة')
        form.click('[data-testid=save-btn]')
        form.wait_for_timeout(2500)

        stored = form.evaluate(STORED)
        check('exactly one photo was stored', len(stored) == 1, str(len(stored)))
        if stored:
            m = stored[0]
            check('[downscale] the STORED image is 1600px on its longest edge — exactly the ruled size, not merely under a cap (M-2048 fails here)',
                  max(m['w'], m['h']) == 1600, f"{m['w']}x{m['h']}")
            check('[downscale] …and it is materially smaller than what the camera produced',
                  m['bytes'] < big['bytes'] / 2,
                  f"{big['bytes'] / 1e6:.2f} MB -> {m['bytes'] / 1e6:.2f} MB "
                  f"({big['bytes'] / m['bytes']:.1f}x)")
            check('[downscale] …and the ORIGINAL FILENAME is kept', m['name'] == 'camera-original.jpg', m['name'])
            check('[downscale] …and the aspect ratio is preserved',
                  abs((m['w'] / m['h']) - (big['w'] / big['h'])) < 0.01, f"{m['w'] / m['h']:.4f}")

        # a small image must pass through UNTOUCHED — downscaling must never make things worse
        small = pg.evaluate("""async () => {
            const c = document.createElement('canvas'); c.width = 800; c.height = 600;
            const x = c.getContext('2d'); x.fillStyle = '#128C6E'; x.fillRect(0, 0, 800, 600);
            const blob = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.9));
            return { bytes: blob.size,
                     dataURL: await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(blob); }) }; }""")
        raw2 = pg.evaluate("(d) => { const b = atob(d.split(',')[1]); const u = new Uint8Array(b.length);"
                           " for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return [...u]; }", small['dataURL'])
        form2 = ctx.new_page(); form2.on('pageerror', lambda e, _p=form2: errs.append(perr(e, _p)))
        form2.goto(f'{ROOT}bird/new/', wait_until='load'); form2.wait_for_timeout(1200)
        form2.set_input_files('input[type=file][accept="image/*"]',
                              files=[{'name': 'small.jpg', 'mimeType': 'image/jpeg', 'buffer': bytes(raw2)}])
        form2.wait_for_timeout(300)
        form2.fill('[data-testid=f-name]', 'طائر صغير')
        form2.click('[data-testid=save-btn]'); form2.wait_for_timeout(2500)
        after = form2.evaluate(STORED)
        tiny = [m for m in after if m['name'] == 'small.jpg']
        check('[downscale] an image already under the cap is stored UNCHANGED, byte for byte',
              len(tiny) == 1 and tiny[0]['bytes'] == small['bytes'],
              f"{small['bytes']} -> {tiny[0]['bytes'] if tiny else 'missing'}")

        # ═══ THE ALLOW-LIST (RULED 2026-11-19): an image type outside JPEG/PNG/WebP that the browser can decode is
        # converted to JPEG at the ruled size when picked; one it cannot decode is stored as it is ═══
        import struct
        FIX = os.path.join(HERE, 'fixtures')
        def bmp(w, h):
            """An uncompressed 24-bit BMP built here, byte by byte: a drawn gradient, no camera, no person."""
            row = b''.join(bytes(((x * 255) // w, 128, 255 - (x * 255) // w)) for x in range(w)); pad = b'\0' * ((4 - (w * 3) % 4) % 4)
            data = (row + pad) * h
            return b'BM' + struct.pack('<IHHI', 54 + len(data), 0, 0, 54) + struct.pack('<IiiHHIIiiII', 40, w, h, 1, 24, 0, len(data), 2835, 2835, 0, 0) + data
        picks = [
            {'name': 'animated.gif', 'mimeType': 'image/gif', 'buffer': open(os.path.join(FIX, 'picked-synthetic.gif'), 'rb').read()},
            {'name': 'new-format.avif', 'mimeType': 'image/avif', 'buffer': open(os.path.join(FIX, 'picked-synthetic.avif'), 'rb').read()},
            {'name': 'scanner.big.bmp', 'mimeType': 'image/bmp', 'buffer': bmp(2400, 1800)},
            {'name': 'IMG_0001.HEIC', 'mimeType': 'image/heic', 'buffer': b'\0\0\0\x18ftypheic' + bytes(range(256)) * 8},   # NOT a real HEIC: bytes no browser can decode
        ]
        form3 = ctx.new_page(); form3.on('pageerror', lambda e, _p=form3: errs.append(perr(e, _p)))
        form3.goto(f'{ROOT}bird/new/', wait_until='load'); form3.wait_for_timeout(1200)
        form3.set_input_files('input[type=file][accept="image/*"]', files=picks); form3.wait_for_timeout(400)
        form3.fill('[data-testid=f-name]', 'طائر الأنواع'); form3.click('[data-testid=save-btn]'); form3.wait_for_timeout(3000)
        RAWSTORE = """async () => { const db = await window.__zajilDb; const out = {};
          for (const m of await db.idbGetAll('media')) { let w = null, h = null;
            try { const b = await createImageBitmap(m.blob); w = b.width; h = b.height; b.close(); } catch { }
            out[m.name] = { type: m.blob.type, bytes: m.blob.size, w, h }; }
          return out; }"""
        got = pg.evaluate(RAWSTORE)
        g = got.get('animated.jpg')
        check('[allow-list · M-noconvert fails here] a picked GIF is stored as a JPEG, under a .jpg name, at its own size (never enlarged)',
              g is not None and g['type'] == 'image/jpeg' and (g['w'], g['h']) == (64, 48) and 'animated.gif' not in got, str({k: v for k, v in got.items() if 'animated' in k}))
        a = got.get('new-format.jpg')
        check('[allow-list] a picked AVIF is stored as a JPEG', a is not None and a['type'] == 'image/jpeg' and (a['w'], a['h']) == (64, 48), str(a))
        m = got.get('scanner.big.jpg')
        check('[allow-list] a picked 2400×1800 BMP is stored as a JPEG at 1600 px on its longest edge — only the last extension is replaced',
              m is not None and m['type'] == 'image/jpeg' and (m['w'], m['h']) == (1600, 1200), str(m))
        hc = got.get('IMG_0001.HEIC')
        check('[allow-list] an image the browser cannot decode is stored AS IT IS — same bytes, same type, same name — so it stays on the device',
              hc is not None and hc['type'] == 'image/heic' and hc['bytes'] == len(picks[3]['buffer']) and hc['w'] is None, str(hc))
        keep = pg.evaluate("""async () => { const db = await window.__zajilDb; return (await db.photosAwaitingUpload()).map(m => m.name).sort(); }""")
        check('[allow-list] the three converted files are of a type storage accepts; the undecodable one is the only one it will refuse',
              all(n in keep for n in ('animated.jpg', 'new-format.jpg', 'scanner.big.jpg')) and 'IMG_0001.HEIC' in keep, str(keep))

        check('zero page errors', not errs, '; '.join(errs[:2]))
        b.close()
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
