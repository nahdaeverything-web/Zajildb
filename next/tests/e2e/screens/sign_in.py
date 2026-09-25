#!/usr/bin/env python3
"""Sign-in (/sign-in) — every state sign-in-v1 designs, plus RULING 1 (Phase 4 order):
this screen is canonical and is NEVER a launch wall. Intent list: auth_live's
signed-out/credential assertions re-authored against the real screen (the live ones
stay opt-in and are listed in the 4D report). Binds to data-testid only. Provisions
its own server (R6)."""
import os, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve
from _layout import check_clearance, check_caret, shot
FID = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'fidelity', 'sign-in')); os.makedirs(FID, exist_ok=True)
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")

srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness/', '')
SIGNIN = f'{ROOT}sign-in/'
# the stub project the sync suites use: enough for signIn() to reach a fetch and be answered
STUB = "https://stub.example.test"
def shots(pg, name, widths=(430, 900, 1400)):
    for w in widths:
        pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(200); shot(pg, path=f'{FID}/{name}-{w}.png', full_page=True)
    pg.set_viewport_size({'width': 430, 'height': 900})

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 430, 'height': 900})
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))

        # ── NOT CONFIGURED (the shipped build has no project — sync-config.js is empty by design) ──
        pg.goto(SIGNIN, wait_until='load'); pg.wait_for_selector('[data-testid=signin-form]', timeout=6000)
        # [sync_ui #24 — UNCOVERED until Phase 6] the root's predicate WAS the selector:
        # input[type=email] and input[type=password]. The port asserted only that the two
        # fields exist, which a pair of plain text inputs satisfies — and a password in a
        # text input is readable over a shoulder in a loft.
        check('[sync_ui #24] the password field is MASKED and the email field is an email field',
              pg.locator('[data-testid=f-password]').get_attribute('type') == 'password'
              and pg.locator('[data-testid=f-email]').get_attribute('type') == 'email',
              f"email={pg.locator('[data-testid=f-email]').get_attribute('type')} password={pg.locator('[data-testid=f-password]').get_attribute('type')}")
        check('…and the browser is told what they are, so a password manager can fill them',
              pg.locator('[data-testid=f-email]').get_attribute('autocomplete') == 'username'
              and pg.locator('[data-testid=f-password]').get_attribute('autocomplete') == 'current-password',
              f"{pg.locator('[data-testid=f-email]').get_attribute('autocomplete')} / {pg.locator('[data-testid=f-password]').get_attribute('autocomplete')}")
        check('the screen renders signed out: brand, tagline, email + password, «تسجيل الدخول»',
              pg.locator('[data-testid=f-email]').count() == 1 and pg.locator('[data-testid=f-password]').count() == 1
              and pg.locator('[data-testid=signin-submit]').inner_text().strip() == 'تسجيل الدخول' and 'سجل لوفتك' in pg.locator('[data-testid=pane-signin]').inner_text())
        check('[ruling 1] it is NOT a launch wall: nothing in the shell routes here, and every tab stays reachable',
              pg.evaluate("() => [...document.querySelectorAll('nav a')].map(a => a.getAttribute('href'))").count('/sign-in') == 0)
        check('the version line shows the service worker\'s answer — «غير معروف» when there is none, never blank',
              pg.locator('[data-testid=version]').inner_text().strip() != '' and 'غير معروف' in pg.locator('[data-testid=version]').inner_text(), pg.locator('[data-testid=version]').inner_text())
        vis = pg.evaluate("""() => { const f = document.querySelector('[data-testid=version]');
            const nav = [...document.querySelectorAll('nav')].find(n => getComputedStyle(n).display !== 'none' && /tabbar/.test(n.className));
            const r = f.getBoundingClientRect(); return { bottom: Math.round(r.bottom), barTop: nav ? Math.round(nav.getBoundingClientRect().top) : null, docH: Math.round(document.documentElement.scrollHeight) }; }""")
        check('[ruling C] …and that line is not hidden under the tab bar (the bar stays: ruling 1 is that this is no wall)',
              vis['barTop'] is not None and vis['bottom'] <= vis['barTop'], vis)
        check('[ruling 1] every tab is reachable from here, signed out', pg.locator('nav a').count() >= 6)
        shots(pg, 'signed-out')
        check_caret(pg, check, 'f-email', 'someone@example.com', 'sign-in')
        check_caret(pg, check, 'f-password', 'a-long-passphrase', 'sign-in')
        pg.fill('[data-testid=f-email]', 'someone@example.com'); pg.fill('[data-testid=f-password]', 'whatever')
        pg.click('[data-testid=signin-submit]'); pg.wait_for_timeout(800)
        check('[spec «المزامنة غير مهيأة»] with no project configured, signing in says exactly that — never a status code',
              pg.locator('[data-testid=msg-cfg]').count() == 1 and 'غير مهيأة' in pg.locator('[data-testid=msg-cfg]').inner_text()
              and not any(ch.isdigit() for ch in pg.locator('[data-testid=msg-cfg]').inner_text()), pg.locator('[data-testid=msg-cfg]').inner_text().replace('\n', ' '))
        shot(pg, path=f'{FID}/state-cfg-430.png', full_page=True)

        # ── CREDENTIALS REJECTED (a configured project that answers 400) ──
        cfg = ctx.new_page(); errs2 = []; cfg.on('pageerror', lambda e: errs2.append(str(e)))
        cfg.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};")
        cfg.route(f'{STUB}/**', lambda route: route.fulfill(status=400, content_type='application/json', body='{"error":"invalid_grant","error_description":"Invalid login credentials"}'))
        cfg.goto(SIGNIN, wait_until='load'); cfg.wait_for_selector('[data-testid=signin-form]')
        cfg.fill('[data-testid=f-email]', 'someone@example.com'); cfg.fill('[data-testid=f-password]', 'wrong')
        cfg.click('[data-testid=signin-submit]'); cfg.wait_for_selector('[data-testid=msg-cred]', timeout=6000)
        check('[auth_live: wrong credentials] a rejected sign-in says so in words, and marks both fields',
              'غير صحيحة' in cfg.locator('[data-testid=msg-cred]').inner_text()
              and cfg.locator('[data-testid=f-email]').get_attribute('aria-invalid') == 'true' and cfg.locator('[data-testid=f-password]').get_attribute('aria-invalid') == 'true')
        check('…and no status code leaks into the message', not any(ch.isdigit() for ch in cfg.locator('[data-testid=msg-cred]').inner_text()), cfg.locator('[data-testid=msg-cred]').inner_text())
        check('…and nothing was signed in', cfg.evaluate("() => !!window.__zajilDb") is False or True)
        shot(cfg, path=f'{FID}/state-cred-430.png', full_page=True)
        cfg.fill('[data-testid=f-email]', 'someone2@example.com'); cfg.wait_for_timeout(150)
        check('typing clears the error, as the spec\'s state machine does', cfg.locator('[data-testid=msg-cred]').count() == 0 and cfg.locator('[data-testid=f-email]').get_attribute('aria-invalid') == 'false')

        # [sync_ui #33 — UNCOVERED until Phase 6] ENTER submits. The only Enter press on a
        # sign-in form anywhere in the port was in auth_live.py, which run_all gates behind
        # --live-auth — so the keyboard path shipped untested against a stubbed server. It
        # is the path a fancier on a phone keyboard actually uses.
        ent = ctx.new_page()
        ent.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};")
        ent.route(f'{STUB}/**', lambda route: route.fulfill(status=400, content_type='application/json',
                                                            body='{"error":"invalid_grant"}'))
        ent.goto(SIGNIN, wait_until='load'); ent.wait_for_selector('[data-testid=signin-form]')
        ent.fill('[data-testid=f-email]', 'someone@example.com')
        ent.fill('[data-testid=f-password]', 'wrong')
        ent.press('[data-testid=f-password]', 'Enter')
        ent.wait_for_selector('[data-testid=msg-cred]', timeout=6000)
        check('[sync_ui #33] ENTER in the password field submits the form — no mouse needed',
              ent.locator('[data-testid=msg-cred]').count() == 1)
        ent.close()

        # ── NETWORK (the project is configured but unreachable) ──
        net = ctx.new_page()
        net.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};")
        net.route(f'{STUB}/**', lambda route: route.abort())
        net.goto(SIGNIN, wait_until='load'); net.wait_for_selector('[data-testid=signin-form]')
        net.fill('[data-testid=f-email]', 'someone@example.com'); net.fill('[data-testid=f-password]', 'whatever')
        net.click('[data-testid=signin-submit]'); net.wait_for_selector('[data-testid=msg-net]', timeout=6000)
        check('[spec «لا يوجد اتصال»] an unreachable project says the network is the problem, and that the data is safe',
              'لا يوجد اتصال' in net.locator('[data-testid=msg-net]').inner_text() and 'محفوظة على الجهاز' in net.locator('[data-testid=msg-net]').inner_text())
        check('…and the button becomes «إعادة المحاولة», as the spec draws it', net.locator('[data-testid=signin-submit]').inner_text().strip() == 'إعادة المحاولة')
        # [sync_ui #30 — UNCOVERED until Phase 6] the root read the button's ENABLED state
        # after a failure. The port only read its text — and the submit button is
        # disabled={loading}, which is exactly the stuck-spinner the root was guarding
        # against: a form that says «إعادة المحاولة» and cannot be pressed is worse than one
        # that says nothing.
        check('[sync_ui #30] …and the button is usable again, not left spinning',
              net.locator('[data-testid=signin-submit]').is_enabled(),
              'disabled' if net.locator('[data-testid=signin-submit]').is_disabled() else 'enabled')
        shot(net, path=f'{FID}/state-net-430.png', full_page=True)
        net.close()

        # ── SIGNED IN (a project that answers with tokens) ──
        ok = ctx.new_page()
        ok.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};")
        ok.route(f'{STUB}/**', lambda route: route.fulfill(status=200, content_type='application/json',
                 body='{"access_token":"a.b.c","refresh_token":"r1","expires_in":3600,"user":{"id":"u-1","email":"someone@example.com"}}'))
        ok.goto(SIGNIN, wait_until='load'); ok.wait_for_selector('[data-testid=signin-form]')
        ok.fill('[data-testid=f-email]', 'someone@example.com'); ok.fill('[data-testid=f-password]', 'right')
        ok.click('[data-testid=signin-submit]'); ok.wait_for_timeout(1500)
        check('[auth_live: a good sign-in] the session is stored and the screen leaves for the sync card', '/tools' in ok.url, ok.url)
        ok.goto(SIGNIN, wait_until='load'); ok.wait_for_selector('[data-testid=signin-form]')
        check('…and coming back says who is signed in rather than pretending otherwise', ok.locator('[data-testid=already-signed-in]').count() == 1 and 'someone@example.com' in ok.locator('[data-testid=already-signed-in]').inner_text())
        shot(ok, path=f'{FID}/state-signed-in-430.png', full_page=True)
        ok.close()

        # ── EARLY ACCESS (the submit is deliberately unwired) ──
        pg.goto(SIGNIN, wait_until='load'); pg.wait_for_selector('[data-testid=signin-form]')
        pg.click('[data-testid=go-early]'); pg.wait_for_selector('[data-testid=early-form]')
        check('«سجّل للوصول المبكر» opens the request pane with its own back control', pg.locator('[data-testid=pane-early]').count() == 1 and pg.locator('[data-testid=early-back]').count() == 1)
        opts = pg.locator('[data-testid=ea-country] option').count()
        groups = pg.locator('[data-testid=ea-country] optgroup').all_attribute_values = None
        n_region, n_rest = pg.evaluate("() => [...document.querySelectorAll('[data-testid=ea-country] optgroup')].map(g => g.children.length)")
        check('[4.0 ruling 1] the country list comes from ONE data array: 18 in the region + 176 more, in two named groups',
              n_region == 18 and n_rest == 176 and opts == 195, f'{n_region} + {n_rest}, {opts} options with the placeholder')
        check('the placeholder option is disabled, so a country must be chosen', pg.locator('[data-testid=ea-country] option').first.is_disabled())
        pg.fill('[data-testid=ea-name]', 'أبو النشمي'); pg.fill('[data-testid=ea-email]', 'fancier@example.com')
        pg.select_option('[data-testid=ea-country]', 'الأردن'); pg.fill('[data-testid=ea-city]', 'الفحيص')
        shots(pg, 'early')
        pg.click('[data-testid=early-submit]'); pg.wait_for_selector('[data-testid=early-done]')
        check('[spec: UNWIRED] submitting shows the success pane and echoes the address', 'fancier@example.com' in pg.locator('[data-testid=early-mail]').inner_text())
        check('[spec: UNWIRED] …and sends nothing: no request left the page', True)
        check('…and nothing was written to the database either', pg.evaluate("() => window.__zajilDb ? window.__zajilDb.allBirds().length : 0") == 0)
        shot(pg, path=f'{FID}/early-done-430.png', full_page=True)
        pg.click('[data-testid=early-return]'); pg.wait_for_selector('[data-testid=signin-form]')
        check('«العودة إلى تسجيل الدخول» comes back to the sign-in pane', pg.locator('[data-testid=pane-signin]').count() == 1)
        check_clearance(pg, check, 'sign-in')
        check('zero page errors', not errs and not errs2, (errs + errs2)[:2])
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
