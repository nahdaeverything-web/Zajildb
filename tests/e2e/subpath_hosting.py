import os
from playwright.sync_api import sync_playwright

# The shipped datasets carry real uuids (v1.9.1). Python's uuid5 derives exactly
# what tools/idmap.js derives from the same namespace and key, so these suites
# keep naming birds by the readable key that documents what they are.
import uuid as _uuid
_ID_NS = _uuid.UUID('7f3c9a54-2b18-4d6e-9c05-1a2b3c4d5e6f')
def bird_id(key):
    return str(_uuid.uuid5(_ID_NS, key))
# GitHub Pages serves this project from a subdirectory, so the app must work
# under one. This suite PROVISIONS ITS OWN SERVER rather than assuming one is
# running: the document root was once a stale COPY of the repo made by hand, and
# the suite passed against a week-old tree for eight days without saying so. A
# test that depends on something it did not start can be green about the wrong
# thing.
#
# The root is a temp directory holding a SYMLINK to the repo, so it is the live
# tree by construction and cannot drift.
import functools, http.server, os, socketserver, tempfile, threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_root = tempfile.mkdtemp(prefix='zajil-subpath-')
os.symlink(REPO, os.path.join(_root, 'zajil'))

class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

_httpd = _Server(('127.0.0.1', 0), functools.partial(_Quiet, directory=_root))
threading.Thread(target=_httpd.serve_forever, daemon=True).start()
URL = f'http://127.0.0.1:{_httpd.server_address[1]}/zajil/' 
ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(); page = ctx.new_page()
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    failed = []
    page.on('response', lambda r: failed.append(f'{r.status} {r.url}') if r.status >= 400 else None)
    page.goto(URL, wait_until='networkidle'); page.wait_for_timeout(2000)
    check('app boots under /zajil/', page.locator('.nav-link').count() == 6)
    check('no 4xx/5xx responses', not failed, '; '.join(failed[:4]))
    sw = page.evaluate("""async () => {
        const r = await navigator.serviceWorker.getRegistration();
        return r ? r.scope : 'none';
    }""")
    check('service worker scoped to the subdirectory', sw.endswith('/zajil/'), sw)
    check('manifest resolves', page.evaluate("""async () => {
        const r = await fetch(document.querySelector('link[rel=manifest]').href);
        return r.ok;
    }"""))
    # import example data and exercise the app
    page.evaluate("""async () => {
        const db = await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(), 'merge');
    }""")
    page.reload(); page.wait_for_timeout(1200)
    check('38 birds under subpath', page.locator('.bird-row').count() == 38)
    page.goto(URL + '#/pedigree/'+bird_id('g5-faris26')); page.wait_for_timeout(1000)
    check('pedigree + COI work under subpath', '12.5' in page.locator('.coi-headline .coi-badge').inner_text())
    # OFFLINE under the subpath — the real GitHub Pages payoff
    page.wait_for_timeout(1500)
    ctx.set_offline(True)
    page.goto(URL, wait_until='load'); page.wait_for_timeout(1500)
    check('OFFLINE reload works under subpath', page.locator('.bird-row').count() == 38,
          str(page.locator('.bird-row').count()))
    check('zero page errors', not errs, '; '.join(errs[:2]))
    b.close()
print(f'\n{ok} passed, {fail} failed')
exit(1 if fail else 0)
