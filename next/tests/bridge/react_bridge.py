#!/usr/bin/env python3
"""2.4 proof: a write through the data layer (window.__zajilDb.saveBird) makes a
React component re-render — no reload, no polling, via the bridge's
subscription to the layer's existing onChange. Provisions its own server."""
import subprocess, socket, sys, time, os
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.abspath(os.path.join(HERE, '..', '..', 'out'))
assert os.path.exists(os.path.join(OUT, 'test-harness', 'index.html')), 'run `npm run build:harness` first'
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '-d', OUT, '--bind', '127.0.0.1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(0.8)
passed = failed = 0
def check(name, ok, detail=''):
    global passed, failed
    passed += ok; failed += (not ok); print(f"  {'✓' if ok else '✗'} {name}{('  ' + detail) if detail else ''}")
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(f'http://127.0.0.1:{port}/test-harness/', wait_until='load'); pg.wait_for_timeout(1500)
        pg.evaluate("async () => { const db = await window.__zajilDb; await window.__zajilReady; window.__marker = 'same-document'; }")
        c0 = pg.inner_text('#bridge-count'); l0 = pg.inner_text('#bridge-last')
        check('initial render through the bridge', c0 == '0' and l0 == '—', f'count={c0!r} last={l0!r}')
        # write through the LAYER, not React
        saved = pg.evaluate("""async () => { const db = await window.__zajilDb;
            const b = await db.saveBird(db.newBird({ name: 'برق-bridge', sex: 'cock' }));
            return { id: b.id, mirror: db.state.birds.size }; }""")
        check('saveBird via window.__zajilDb succeeded', bool(saved['id']) and saved['mirror'] == 1, str(saved))
        # React must catch up WITHOUT reload: wait on the DOM, bounded
        pg.wait_for_function("document.getElementById('bridge-count').textContent === '1'", timeout=3000)
        c1 = pg.inner_text('#bridge-count'); l1 = pg.inner_text('#bridge-last')
        check('component re-rendered: count 0 → 1', c1 == '1', f'count={c1!r}')
        check('component re-rendered: last bird name', l1 == 'برق-bridge', f'last={l1!r}')
        check('same document — no reload happened', pg.evaluate("window.__marker") == 'same-document')
        # a second write, then a delete — the bridge must follow both directions
        pg.evaluate("async () => { const db = await window.__zajilDb; await db.saveBird(db.newBird({ name: 'ثاني', sex: 'hen' })); }")
        pg.wait_for_function("document.getElementById('bridge-count').textContent === '2'", timeout=3000)
        check('second save → count 2, last updated', pg.inner_text('#bridge-count') == '2' and pg.inner_text('#bridge-last') == 'ثاني')
        pg.evaluate(f"async () => {{ const db = await window.__zajilDb; await db.deleteBird('{saved['id']}'); }}")
        pg.wait_for_function("document.getElementById('bridge-count').textContent === '1'", timeout=3000)
        check('deleteBird → count back to 1 (bridge follows deletes)', pg.inner_text('#bridge-count') == '1')
        check('zero page errors', not errs, str(errs))
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
