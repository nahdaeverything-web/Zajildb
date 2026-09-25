#!/usr/bin/env python3
"""GitHub Pages serves this project from a subdirectory, so the app must work under one.

    cd next && python3 tests/pwa/subpath_hosting.py

WHY THIS LIVES IN tests/pwa/ AND NOT tests/e2e/ — it needs a DIFFERENT BUILD of the app
than every other suite. `basePath` is baked into a static export at build time, and
`output: 'export'` forbids the rewrites that could normalise a prefix at request time, so
one build serves exactly one prefix. Every suite under tests/e2e/ shares one server over
one out/, which this would have to replace. So it builds its own, snapshots it, and puts
the root harness build back before it finishes — pass or fail.

A copy of the root suite. Five kinds of change and no others:
  · the build — `NEXT_PUBLIC_BASE_PATH=/zajil npm run build:harness`, snapshotted, with the
    root harness build restored in a finally;
  · the DOM tokens — `.nav-link` -> `[data-testid=nav-link]`, counted inside the ONE nav
    that is on screen (both navs render the same six tabs and CSS picks; a plain count is
    12), `.bird-row` -> `[data-testid=bird-row]`, `.coi-headline .coi-badge` ->
    `[data-testid=coi-headline] [data-testid=coi-badge]`;
  · the routes — `#/pedigree/<id>` -> `pedigree/?id=<id>`, and the export is flat so a
    bare visit to the prefix lands on index.html;
  · the seed — through the harness route's `window.__zajilDb`, since the port's data layer
    is bundled;
  · `wait_until='load'`, never 'networkidle': a page controlled by a service worker never
    goes idle.

The server is provisioned here, as the root suite learned to do: its document root was
once a stale COPY of the repo made by hand, and the suite passed against a week-old tree
for eight days without saying so. Here the root holds a symlink to the snapshot, so it is
the tree that was built, by construction.
"""
import functools
import http.server
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import uuid as _uuid

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
NEXT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(NEXT, 'out')
PREFIX = 'zajil'

_ID_NS = _uuid.UUID('7f3c9a54-2b18-4d6e-9c05-1a2b3c4d5e6f')
def bird_id(key):
    return str(_uuid.uuid5(_ID_NS, key))

ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')


def build(base_path):
    env = dict(os.environ)
    if base_path:
        env['NEXT_PUBLIC_BASE_PATH'] = base_path
    else:
        env.pop('NEXT_PUBLIC_BASE_PATH', None)
    label = base_path or '(root)'
    print(f'  building the harness export for {label} …')
    r = subprocess.run(['npm', 'run', 'build:harness'], cwd=NEXT, env=env,
                       capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        print((r.stdout or '')[-2000:]); print((r.stderr or '')[-2000:])
        raise SystemExit(f'  build for {label} failed')
    for line in (r.stdout or '').splitlines():
        if 'service worker' in line or 'sw-precache-sound' in line:
            print('   ', line.strip())


snapshot = tempfile.mkdtemp(prefix='zajil-subpath-build-')
served = tempfile.mkdtemp(prefix='zajil-subpath-root-')
httpd = None
try:
    build('/' + PREFIX)
    shutil.copytree(OUT, os.path.join(snapshot, 'out'))
    os.symlink(os.path.join(snapshot, 'out'), os.path.join(served, PREFIX))

    class _Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    class _Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = _Server(('127.0.0.1', 0), functools.partial(_Quiet, directory=served))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    URL = f'http://127.0.0.1:{httpd.server_address[1]}/{PREFIX}/'
    print(f'  serving the snapshot at {URL}')

    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(viewport={'width': 430, 'height': 900}); page = ctx.new_page()
        page.set_default_timeout(30000)
        errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
        # Recorded ONLY while online. Departure 2 of the worker answers an offline miss with
        # a synthetic 504 — the port's own behaviour, not a host failure — and the root
        # suite is safe from that only by accident of assertion order. This says the window
        # out loud, so the check can be repeated anywhere without lying.
        online = {'yes': True}
        failed = []
        page.on('response', lambda r: failed.append(f'{r.status} {r.url}')
                if (r.status >= 400 and online['yes']) else None)

        # a bare visit to the prefix: the export's index.html, which redirects to the loft
        page.goto(URL, wait_until='load'); page.wait_for_timeout(2500)
        # both navs render the same six tabs and CSS decides which is on screen, so the
        # count is taken inside the one that is visible
        visible_tabs = page.evaluate("""() => {
            const navs = [...document.querySelectorAll('nav[data-testid=tabbar], nav[data-testid=rail]')];
            const on = navs.filter(n => n.checkVisibility({ contentVisibilityAuto: true }));
            return on.map(n => n.querySelectorAll('[data-testid=nav-link]').length);
        }""")
        check('app boots under /zajil/, with its six tabs',
              visible_tabs and all(n == 6 for n in visible_tabs), str(visible_tabs))
        check('no 4xx/5xx responses', not failed, '; '.join(failed[:4]))
        check('every asset resolved under the prefix, not at the origin root',
              page.evaluate("() => [...document.querySelectorAll('script[src],link[href]')]"
                            ".every(e => { const u = e.src || e.href; return !u.startsWith(location.origin + '/_next'); })"))

        sw = page.evaluate("""async () => {
            const r = await navigator.serviceWorker.getRegistration();
            return r ? r.scope : 'none';
        }""")
        check('service worker scoped to the subdirectory', sw.endswith(f'/{PREFIX}/'), sw)
        check('manifest resolves', page.evaluate("""async () => {
            const l = document.querySelector('link[rel=manifest]');
            if (!l) return false;
            const r = await fetch(l.href);
            return r.ok;
        }"""))
        check('…and it is the manifest under the prefix, with a relative scope that follows it',
              page.evaluate(f"""async () => {{
                  const l = document.querySelector('link[rel=manifest]');
                  if (!l || !l.href.includes('/{PREFIX}/')) return false;
                  const m = await (await fetch(l.href)).json();
                  return m.display === 'standalone' && (m.icons || []).length >= 3
                      && new URL(m.start_url, l.href).pathname === '/{PREFIX}/';
              }}"""),
              page.evaluate("() => { const l = document.querySelector('link[rel=manifest]'); return l ? l.href : 'NONE'; }"))

        # seed through the harness route, then exercise the app under the prefix
        seed = ctx.new_page()
        seed.goto(URL + 'test-harness/', wait_until='load'); seed.wait_for_timeout(900)
        seed.evaluate("async () => { await window.__zajilReady; }")
        seed.evaluate("""async () => { const db = await window.__zajilDb;
            await db.importAll(await (await fetch(new URL('example-loft-large.json', document.querySelector('link[rel=manifest]').href))).json(), 'merge'); }""")
        seed.close()

        page.goto(URL + 'birds/', wait_until='load'); page.wait_for_timeout(2000)
        check('38 birds under subpath', page.locator('[data-testid=bird-row]').count() == 38,
              str(page.locator('[data-testid=bird-row]').count()))
        page.goto(URL + 'pedigree/?id=' + bird_id('g5-faris26'), wait_until='load')
        page.wait_for_timeout(2000)
        check('pedigree + COI work under subpath',
              '12.5' in page.locator('[data-testid=coi-headline] [data-testid=coi-badge]').inner_text(),
              page.locator('[data-testid=coi-headline]').inner_text().replace('\n', ' ')[:80])

        # a click that navigates: basePath must reach the router, not just the asset URLs
        page.goto(URL + 'birds/', wait_until='load'); page.wait_for_timeout(1500)
        page.locator('[data-testid=bird-row]').first.click(); page.wait_for_timeout(1800)
        check('a navigation inside the app stays inside the prefix',
              f'/{PREFIX}/' in page.url and '?id=' in page.url, page.url)

        # OFFLINE under the subpath — the real GitHub Pages payoff
        page.wait_for_timeout(1500)
        online['yes'] = False
        ctx.set_offline(True)
        page.goto(URL + 'birds/', wait_until='load'); page.wait_for_timeout(2000)
        check('OFFLINE reload works under subpath', page.locator('[data-testid=bird-row]').count() == 38,
              str(page.locator('[data-testid=bird-row]').count()))
        page.goto(URL + 'tools', wait_until='load'); page.wait_for_timeout(2000)
        check('OFFLINE a clean URL under the prefix finds its own document',
              page.locator('[data-testid=card-settings]').count() == 1,
              page.url.split('/')[-1])
        check('OFFLINE the version row still reports the worker under the prefix',
              'zajil-v' in page.locator('[data-testid=about-version]').inner_text(),
              page.locator('[data-testid=about-version]').inner_text())
        ctx.set_offline(False)
        online['yes'] = True
        check('…and nothing 4xx/5xx was served while ONLINE, start to finish',
              not failed, '; '.join(failed[:4]))

        check('zero page errors', not errs, '; '.join(errs[:2]))
        b.close()
finally:
    if httpd:
        httpd.shutdown()
    shutil.rmtree(snapshot, ignore_errors=True)
    shutil.rmtree(served, ignore_errors=True)
    # put out/ back the way every other suite expects to find it, pass or fail
    try:
        build('')
    except SystemExit as e:
        print(e)

print(f'\n{ok} passed, {fail} failed')
raise SystemExit(1 if fail else 0)
