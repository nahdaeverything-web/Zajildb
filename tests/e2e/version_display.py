import os, re
from playwright.sync_api import sync_playwright
BASE = os.environ.get('ZAJIL_URL', 'http://127.0.0.1:8123/')
ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')

# the value the SW should report, read from source — the test must not hardcode it
SW_VERSION = re.search(r"const VERSION = '([^']+)'", open('sw.js').read()).group(1)

with sync_playwright() as p:
    br = p.chromium.launch(); page = br.new_page(); page.set_default_timeout(25000)
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    # a service worker needs a secure context; 127.0.0.1 counts as one
    page.goto(BASE, wait_until='load'); page.wait_for_timeout(2500)
    page.evaluate("() => navigator.serviceWorker.ready")
    page.reload(wait_until='load'); page.wait_for_timeout(2000)   # ensure a CONTROLLER exists

    controlled = page.evaluate("() => !!navigator.serviceWorker.controller")
    check('the page is controlled by a service worker', controlled)

    page.goto(BASE + '#/tools', wait_until='load'); page.wait_for_timeout(2500)
    row = page.locator('.about-version')
    check('Settings renders an About version row', row.count() == 1, str(row.count()))
    shown = row.inner_text().strip()
    check('the row is never blank', shown != '', repr(shown))

    # THE POINT: it must equal what the live SW reports, not a constant in js/
    reported = page.evaluate("""async () => {
        const sw = navigator.serviceWorker.controller;
        if (!sw) return null;
        return await new Promise((resolve) => {
            const ch = new MessageChannel();
            const t = setTimeout(() => resolve(null), 3000);
            ch.port1.onmessage = (e) => { clearTimeout(t); resolve(e.data && e.data.version); };
            sw.postMessage({ type: 'GET_VERSION' }, [ch.port2]);
        });
    }""")
    check('the SW answers a GET_VERSION message', reported is not None, str(reported))
    check('the SW reports the version in sw.js source', reported == SW_VERSION, f'{reported} vs {SW_VERSION}')
    check('the displayed string contains that exact version', reported in shown, f'{shown!r} lacks {reported!r}')
    check('it is not the unknown fallback', 'غير معروف' not in shown, shown)

    # no constant in js/ may carry the app version — the screen must ask the SW
    leaked = page.evaluate("""async () => {
        const files = ['./js/views/tools.js', './js/db.js', './js/app.js', './js/i18n.js'];
        const out = [];
        for (const f of files) {
            const src = await (await fetch(f)).text();
            if (/zajil-v\\d+\\.\\d+\\.\\d+/.test(src)) out.push(f);
        }
        return out;
    }""")
    check('no js/ file hardcodes an app version string', leaked == [], str(leaked))

    # graceful fallback where there is no service worker at all
    ctx2 = br.new_context()
    p2 = ctx2.new_page()
    p2.add_init_script("Object.defineProperty(navigator, 'serviceWorker', { get: () => undefined });")
    p2.goto(BASE + '#/tools', wait_until='load'); p2.wait_for_timeout(2500)
    fb = p2.locator('.about-version')
    check('without a service worker the row still renders', fb.count() == 1)
    check('…showing the unknown fallback, not a blank', 'غير معروف' in fb.inner_text(), fb.inner_text())
    ctx2.close()

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
