#!/usr/bin/env python3
"""A photo picked on a phone is stored DOWNSCALED, not as the camera produced it.

WHY THIS EXISTS. Photos used to be stored exactly as the picker handed them over
(`app/bird/form.tsx` passed the raw File to addMedia). A current phone produces 3-12 MB a
photo, and the export/import path has a hard ceiling at 403 MB of photo bytes — V8 caps a
string at 536,870,888 bytes and the export runs 1.3337x source. Measured on a REAL
photograph, 3176x2117 at 5.18 MB, that is 77 photos before a loft can no longer be moved
between origins. Seventy-seven is a normal loft.

`src/components/media.ts` caps the longest edge at 2048px on the way in. Measured through
that same pipeline, the same photograph becomes 0.44 MB — 904 photos before the wall.

This suite asserts the cap actually applies to what is STORED, by reading the blob back out
of IndexedDB and decoding it. Asserting on the picked File would prove nothing: the point is
what survives into the database.

Binds to data-testid only. Provisions its own server (R6)."""
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
ROOT = HARNESS.replace('test-harness.html', '')

# A large source image, built in the page: 4000x3000 (12 MP), well over the 2048 cap. It is
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
        pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(800)
        pg.evaluate("async () => { await window.__zajilReady; }")
        pg.evaluate("async () => { const db = await window.__zajilDb; for (const x of db.allBirds()) await db.deleteBird(x.id); }")

        big = pg.evaluate(MAKE_BIG, 'image/jpeg')
        check('the fixture is a genuinely large source image', big['w'] == 4000 and big['bytes'] > 700_000,
              f"{big['w']}x{big['h']}, {big['bytes'] / 1e6:.2f} MB")

        # picked through the REAL form, exactly as a fancier would
        form = ctx.new_page(); form.on('pageerror', lambda e: errs.append(str(e)))
        form.goto(f'{ROOT}bird/new.html', wait_until='load'); form.wait_for_timeout(1200)
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
            check('[downscale] the STORED image is capped at 2048px on its longest edge',
                  max(m['w'], m['h']) <= 2048, f"{m['w']}x{m['h']}")
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
        form2 = ctx.new_page(); form2.on('pageerror', lambda e: errs.append(str(e)))
        form2.goto(f'{ROOT}bird/new.html', wait_until='load'); form2.wait_for_timeout(1200)
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

        check('zero page errors', not errs, '; '.join(errs[:2]))
        b.close()
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
