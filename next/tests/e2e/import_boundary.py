#!/usr/bin/env python3
"""The import size boundary — that the refusal fires, and that it says something true.

OPT-IN (--boundary). It seeds ~537 MB of media and writes a file of the same order, so it is
slow and disk-hungry. It is not part of the default gate for that reason, and for no other.

WHY IT EXISTS. V8 caps a string at 536,870,888 bytes (2**29 - 24). `File.text()` does NOT
throw past that — it resolves with an EMPTY STRING, and `JSON.parse("")` then reports
«Unexpected end of JSON input», which describes an empty file and sends a fancier hunting for
a broken download. Measured:

    536,870,888 bytes -> the whole string      536,870,889+ -> length 0, no error at all

`new Response(file).json()` fails identically, measured on a 587 MB file whose largest single
value was 2.8 MB — so the cap is on the total decoded text, not on any one value.

Before the guard, the port showed NOTHING: no file, no toast, no counts, an unhandled
rejection. Vanilla at least catches and toasts (js/views/tools.js:116-118).

SEEDED BY BYTES, not by photo count, because the boundary is a byte boundary. A photo-count
fixture would drift the moment anything changes what a photo weighs — which the downscale
work just did.

Binds to data-testid only. Provisions its own servers (R6)."""
import os
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
NEXT_OUT = os.path.abspath(os.path.join(HERE, '..', '..', 'out'))

CAP = 2 ** 29 - 24          # 536,870,888 — the measured boundary
passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


def serve_dir(path):
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '-d', path, '--bind', '127.0.0.1'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.9)
    return srv, f'http://127.0.0.1:{port}/'


# seeded by TARGET BYTES: as many photos as it takes to reach the target, each one large
SEED_BYTES = """async ([targetBytes, perPhoto]) => {
  const db = await window.__zajilDb;
  for (const b of db.allBirds()) await db.deleteBird(b.id);
  const loft = db.currentLoft().id;
  let total = 0, i = 0;
  while (total < targetBytes) {
    const bird = await db.saveBird(db.newBird({ name: 'b' + i, sex: 'cock', loftId: loft }));
    const size = Math.min(perPhoto, targetBytes - total);
    const buf = new Uint8Array(size);
    for (let o = 0; o < size; o += 65536)
      crypto.getRandomValues(buf.subarray(o, Math.min(o + 65536, size)));
    await db.addMedia(bird.id, 'photo', 'bird', 'p' + i + '.png', new Blob([buf], { type: 'image/png' }));
    total += size; i++;
  }
  return { bytes: total, photos: i };
}"""

srv = None
try:
    srv, ORIGIN = serve_dir(NEXT_OUT)
    with sync_playwright() as pw:
        br = pw.chromium.launch(args=['--js-flags=--max-old-space-size=4096'])

        # ── 1. the platform fact this all rests on, re-measured every run ──────────────
        p0 = br.new_page(); p0.set_default_timeout(900000)
        p0.goto(ORIGIN + 'tools/', wait_until='load'); p0.wait_for_timeout(1200)
        probe = p0.evaluate("""async (cap) => {
            const mk = (n) => { const chunk = new Uint8Array(1024 * 1024).fill(65); const parts = [];
              let left = n; while (left > 0) { const take = Math.min(left, chunk.length);
                parts.push(take === chunk.length ? chunk : chunk.subarray(0, take)); left -= take; }
              return new File(parts, 'x.json', { type: 'application/json' }); };
            const at = async (n) => { const f = mk(n); const t = await f.text();
              return { size: f.size, len: t.length }; };
            return { atCap: await at(cap), justOver: await at(cap + 1024) };
        }""", CAP)
        check('at exactly the cap, File.text() still returns the whole file',
              probe['atCap']['len'] == CAP, str(probe['atCap']))
        check('ONE KB PAST THE CAP it returns an EMPTY STRING, and does not throw',
              probe['justOver']['len'] == 0, str(probe['justOver']))
        p0.close()

        # ── 2. the guard refuses, and says something true ──────────────────────────────
        ctx = br.new_context(accept_downloads=True)
        g = ctx.new_page(); g.set_default_timeout(900000)
        gerr = []; g.on('pageerror', lambda e: gerr.append(str(e)))
        g.goto(ORIGIN + 'tools/', wait_until='load'); g.wait_for_timeout(2000)
        for _ in range(30):
            if g.locator('[data-testid=toast]').count() == 0:
                break
            time.sleep(1)
        oversize = os.path.join('/tmp', 'zajil-boundary-oversize.json')
        with open(oversize, 'wb') as fh:                       # a valid-looking file, one KB too big
            fh.write(b'{"format":"zajil-export","version":1,"pad":"')
            block = b'A' * (1024 * 1024)
            written = 0
            while written < CAP + 1024:
                take = min(len(block), CAP + 1024 - written)
                fh.write(block[:take]); written += take
            fh.write(b'"}')
        g.set_input_files('[data-testid=file-input]', files=[oversize])
        g.wait_for_timeout(500)
        g.click('[data-testid=import-file]')
        g.wait_for_selector('[data-testid=toast]', timeout=60000)
        g.wait_for_timeout(500)
        msg = ' '.join(g.locator('[data-testid=toast]').all_inner_texts())
        import math
        # the UI ceils the size and floors the limit, so a barely-over file does not read
        # «512 MB, limit 512 MB» — assert the same arithmetic rather than a bare round()
        size_mb = str(math.ceil(os.path.getsize(oversize) / 1048576))
        limit_mb = str(math.floor(CAP / 1048576))
        check('[boundary] an oversize file is REFUSED with a message, not silence',
              len(msg) > 0, msg[:90])
        check('[boundary] …the message names the actual size AND the limit, and they differ',
              size_mb in msg and limit_mb in msg and size_mb != limit_mb,
              f'looking for {size_mb} and {limit_mb} in: {msg[:80]}')
        check('[boundary] …and it does NOT reuse the misleading «Unexpected end of JSON input»',
              'Unexpected end of JSON input' not in msg and 'نهاية' not in msg, msg[:80])
        check('[boundary] …and nothing was imported', g.evaluate("async () => (await window.__zajilDb).allBirds().length") == 0)
        check('[boundary] …and no unhandled page error escaped', not gerr, '; '.join(gerr[:2]))
        os.remove(oversize)
        ctx.close()

        # ── 3. a loft just UNDER the boundary still makes the whole round trip ─────────
        srv_b, ORIGIN_B = serve_dir(NEXT_OUT)
        try:
            ctx_a = br.new_context(accept_downloads=True)
            a = ctx_a.new_page(); a.set_default_timeout(1800000)
            a.goto(ORIGIN + 'test-harness/', wait_until='load'); a.wait_for_timeout(900)
            a.evaluate("async () => { await window.__zajilReady; }")
            # aim the FILE just under the cap: the file runs ~1.3337x the source bytes
            target_src = int((CAP - 8 * 1024 * 1024) / 1.3337)
            seeded = a.evaluate(SEED_BYTES, [target_src, 4 * 1024 * 1024])
            ta = ctx_a.new_page(); ta.set_default_timeout(1800000)
            ta.goto(ORIGIN + 'tools/', wait_until='load'); ta.wait_for_timeout(1500)
            with ta.expect_download(timeout=1800000) as dl:
                ta.click('[data-testid=export-all]')
            near = '/tmp/zajil-boundary-near.json'
            dl.value.save_as(near)
            nbytes = os.path.getsize(near)
            check('[boundary] a loft sized to sit just under the cap exports to a file under it',
                  nbytes <= CAP, f'{nbytes} bytes vs cap {CAP} (source {seeded["bytes"]}, {seeded["photos"]} photos)')
            ctx_a.close()

            ctx_b = br.new_context(accept_downloads=True)
            b2 = ctx_b.new_page(); b2.set_default_timeout(1800000)
            berr = []; b2.on('pageerror', lambda e: berr.append(str(e)))
            b2.goto(ORIGIN_B + 'tools/', wait_until='load'); b2.wait_for_timeout(2000)
            for _ in range(30):
                if b2.locator('[data-testid=toast]').count() == 0:
                    break
                time.sleep(1)
            b2.set_input_files('[data-testid=file-input]', files=[near])
            b2.wait_for_timeout(600)
            b2.click('[data-testid=import-file]')
            b2.wait_for_selector('[data-testid=toast]', timeout=600000)
            b2.wait_for_timeout(2000)
            landed = b2.evaluate("async () => (await window.__zajilDb).allBirds().length")
            check('[boundary] …and it IMPORTS at a second origin, right up against the limit',
                  landed == seeded['photos'], f'{landed} of {seeded["photos"]} birds')
            check('[boundary] …with no page error', not berr, '; '.join(berr[:2]))
            os.remove(near)
        finally:
            srv_b.terminate()
        br.close()
finally:
    if srv:
        srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
