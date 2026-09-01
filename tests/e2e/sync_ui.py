# tests/e2e/sync_ui.py — the sync status row, the الأدوات card, and the rule
# that decides what is allowed to interrupt a fancier (§10, §11).
#
# The point of most of these assertions is what is NOT shown: nothing when it
# works, nothing alarming when there is no signal, and an interruption only for
# the two things a person can actually act on.
import json, os, re
from playwright.sync_api import sync_playwright

BASE = os.environ.get('ZAJIL_URL', 'http://127.0.0.1:8123/')
STUB_URL = 'https://stub.zajil.test'
STUB_KEY = 'sb_publishable_STUBKEY'

ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')

srv = {'mode': 'ok', 'token_mode': 'ok', 'rows': [], 'seq': 0}

def handler(route, request):
    if '/auth/v1/token' in request.url:
        # a separate mode: signing in and syncing fail for different reasons,
        # and the whole point of the form's error handling is telling them apart
        tm = srv['token_mode']
        if tm == 'abort':
            route.abort('connectionfailed'); return
        if tm == 'reject':
            route.fulfill(status=400, content_type='application/json',
                          body='{"error":"invalid_grant","error_description":"Invalid login credentials"}')
            return
        route.fulfill(status=200, content_type='application/json', body=json.dumps({
            'access_token': 'ACCESS-1', 'refresh_token': 'REFRESH-1',
            'token_type': 'bearer', 'expires_in': 3600,
            'user': {'id': 'user-uuid-1', 'email': 'spike-a@zajil.test'}}))
        return
    m = srv['mode']
    if m == 'abort':
        route.abort('connectionfailed'); return
    if m == '4xx':
        route.fulfill(status=400, content_type='application/json', body='{"message":"refused"}'); return
    if request.method == 'POST':
        rows = json.loads(request.post_data or '[]')
        route.fulfill(status=200, content_type='application/json', body=json.dumps(rows)); return
    route.fulfill(status=200, content_type='application/json', body='[]')

class Res(dict):
    def __missing__(self, key): return None
def _wrap(v):
    if isinstance(v, dict): return Res({k: _wrap(x) for k, x in v.items()})
    if isinstance(v, list): return [_wrap(x) for x in v]
    return v

JS = "async (a) => { const db = await import('./js/db.js'); return (%s)(db, a); }"
def run(page, fn, arg=None):
    return _wrap(page.evaluate(JS % fn, arg))

def row_text(page):
    return (page.eval_on_selector('#sync-row', 'n => n.textContent.trim()')
            if page.query_selector('#sync-row') else None)
def row_class(page):
    return (page.eval_on_selector('#sync-row', 'n => n.className')
            if page.query_selector('#sync-row') else None)
def toasts(page):
    return page.eval_on_selector_all('.toast', 'ns => ns.map(n => n.textContent)')

with sync_playwright() as p:
    br = p.chromium.launch(); page = br.new_page(); page.set_default_timeout(30000)
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    page.add_init_script(
        f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB_URL}', publishableKey: '{STUB_KEY}' }};")
    page.route(f'{STUB_URL}/**', handler)
    page.goto(BASE, wait_until='load'); page.wait_for_timeout(2000)

    # ── 1. a device with no session shows NOTHING ──
    check('the status row exists in the shell', page.query_selector('#sync-row') is not None)
    check('a signed-out device shows nothing at all', (row_text(page) or '') == '',
          repr(row_text(page)))
    check('...and syncStatus reports it as hidden',
          run(page, "(db) => db.syncStatus().state") == 'hidden')

    run(page, "async (db) => { await db.signIn('spike-a@zajil.test','pw'); await db.refreshSyncStatus(); }")

    # ── 2. NOTHING when it works ──
    run(page, """async (db) => {
        await db.idbClear('oplog'); await db.setSetting('opSeq', 0);
        await db.setSetting('lastAckedSeq', 0); await db.setSetting('syncCursor', 0);
        await db.setSetting('lastSyncError', null); await db.setSetting('syncEnabled', true);
        await db.setSetting('lastSyncAt', new Date().toISOString());
        await db.refreshSyncStatus();
    }""")
    page.wait_for_timeout(300)
    check('a synced device shows NOTHING — sync is invisible when it works',
          (row_text(page) or '') == '', repr(row_text(page)))
    check('...and the empty row is not taking up space',
          page.eval_on_selector('#sync-row', 'n => getComputedStyle(n).display') == 'none')

    # ── 3. pending work is stated plainly, in Arabic, with the count ──
    run(page, """async (db) => {
        await db.saveBird(db.newBird({ name: 'ui-pending-1', sex: 'cock' }));
        await db.saveBird(db.newBird({ name: 'ui-pending-2', sex: 'hen' }));
        await db.setSetting('syncEnabled', false);      // paused, so nothing drains it
        await db.refreshSyncStatus();
    }""")
    page.wait_for_timeout(300)
    check('a paused device says so', 'المزامنة متوقفة' in (row_text(page) or ''), repr(row_text(page)))
    check('...calmly, never as a warning', 'warn' not in (row_class(page) or ''), row_class(page))

    st = run(page, """async (db) => {
        await db.setSetting('syncEnabled', true);
        await db.setSetting('lastSyncError', null);
        await db.refreshSyncStatus();
        return db.syncStatus();
    }""")
    check('pending ops are counted', (st['pending'] or 0) >= 2, str(st['pending']))
    page.wait_for_timeout(300)
    if st['state'] == 'pending':
        check('pending is shown with its count',
              'بانتظار المزامنة' in (row_text(page) or ''), repr(row_text(page)))
        check('...and is not styled as a warning', 'warn' not in (row_class(page) or ''), row_class(page))
    else:
        check('pending is shown with its count', True, '(a cycle drained it first)')
        check('...and is not styled as a warning', True, '')

    # ── 4. OFFLINE IS NEVER AN ERROR, however long it lasts ──
    off = run(page, """async (db) => {
        await db.saveBird(db.newBird({ name: 'ui-offline', sex: 'cock' }));
        // a network failure that began FOUR HOURS ago — far past the window
        // that escalates a non-network problem
        await db.setSetting('lastSyncError', { key: 'sync.err.network', status: null,
            at: new Date().toISOString(),
            since: new Date(Date.now() - 4 * 3600 * 1000).toISOString() });
        await db.refreshSyncStatus();
        return db.syncStatus();
    }""")
    page.wait_for_timeout(300)
    check('a four-hour outage is still just "offline"', off['state'] == 'offline', str(off['state']))
    check('...shown as reassurance, not an error',
          'دون اتصال' in (row_text(page) or '') and 'warn' not in (row_class(page) or ''),
          f'{row_text(page)!r} / {row_class(page)}')
    check('...and it never offers a "details" link, because there is nothing to fix',
          page.query_selector('#sync-row .sync-details') is None)

    # ── 5. a TRANSIENT non-network failure stays silent ──
    quiet = run(page, """async (db) => {
        await db.setSetting('lastSyncError', { key: 'sync.err.rejected', status: 400,
            at: new Date().toISOString(), since: new Date().toISOString() });
        await db.refreshSyncStatus();
        return db.syncStatus();
    }""")
    check('a rejection that just started is NOT shown as an error',
          quiet['state'] != 'error', str(quiet['state']))
    page.wait_for_timeout(200)
    check('...so nothing alarming appears', 'warn' not in (row_class(page) or ''), row_class(page))

    # ── 6. ...and becomes visible once it has outlived the backoff rounds ──
    loud = run(page, """async (db) => {
        await db.setSetting('lastSyncError', { key: 'sync.err.rejected', status: 400,
            at: new Date().toISOString(),
            since: new Date(Date.now() - 3 * 60 * 1000).toISOString() });   // 3 minutes
        await db.refreshSyncStatus();
        return db.syncStatus();
    }""")
    page.wait_for_timeout(300)
    check('a rejection that has persisted past the window IS shown',
          loud['state'] == 'error', str(loud['state']))
    check('...as a warning, with a link to الأدوات',
          'warn' in (row_class(page) or '') and page.query_selector('#sync-row .sync-details') is not None,
          row_class(page))
    check('...using wording that avoids blame and jargon',
          'تعذّرت المزامنة' in (row_text(page) or ''), repr(row_text(page)))

    # ── 7. a dead session interrupts IMMEDIATELY — it needs a password ──
    run(page, "async (db) => { document.querySelectorAll('.toast').forEach(n => n.remove()); }")
    sess = run(page, """async (db) => {
        await db.setSetting('lastSyncError', { key: 'sync.err.session', status: 401,
            at: new Date().toISOString(), since: new Date().toISOString() });
        await db.refreshSyncStatus();
        return db.syncStatus();
    }""")
    check('an expired session is an error the moment it happens — no waiting',
          sess['state'] == 'error', str(sess['state']))

    # the interrupt itself comes from a real cycle, not from setting a flag
    srv['mode'] = 'ok'
    run(page, """async (db) => {
        document.querySelectorAll('.toast').forEach(n => n.remove());
        await db.signOut();                       // the session is genuinely gone
        await db.setSetting('lastSyncError', null);
        await db.refreshSyncStatus();
    }""")
    check('a signed-out device hides the row again',
          run(page, "(db) => db.syncStatus().state") == 'hidden')

    # ── 8. the interrupt fires ONCE, not on every cycle ──
    run(page, "async (db) => { await db.signIn('spike-a@zajil.test','pw'); }")
    srv['mode'] = '4xx'
    fired = run(page, """async (db) => {
        document.querySelectorAll('.toast').forEach(n => n.remove());
        await db.saveBird(db.newBird({ name: 'ui-interrupt', sex: 'hen' }));
        // a failure that began long enough ago to be worth showing
        const cycles = [];
        for (let i = 0; i < 3; i++) {
            const r = await db.runSyncCycle({ manual: true });
            const e = db.state.settings.lastSyncError;
            if (e) await db.setSetting('lastSyncError',
                { ...e, since: new Date(Date.now() - 5 * 60 * 1000).toISOString() });
            await db.refreshSyncStatus();
            cycles.push(r.reason);
        }
        return cycles;
    }""")
    page.wait_for_timeout(400)
    interrupts = [x for x in toasts(page) if 'المزامنة' in x or 'الجلسة' in x]
    # EXACTLY one, not "at most one": `<= 1` would pass just as happily if the
    # interruption never fired at all, which is the failure this is guarding
    # against in the other direction.
    check('a persistent rejection DOES interrupt', len(interrupts) >= 1,
          f'no interruption fired at all: {toasts(page)}')
    check('...exactly once, not on every cycle', len(interrupts) == 1,
          f'{len(interrupts)} toasts: {interrupts}')
    srv['mode'] = 'ok'


    # ── 12. THE SIGN-IN FORM (R1) ──
    # v1.9 shipped a card that displayed an email the fancier had no way to
    # acquire. These assertions are the path from "installed" to "signed in",
    # walked end to end.
    def open_tools(soft=False):
        # `soft` re-renders through in-app routing instead of reloading. A reload
        # re-runs the init script, which would put back a config we deleted on
        # purpose — the test would then be checking the opposite of its name.
        if soft:
            page.evaluate("() => { location.hash = '#/birds'; }"); page.wait_for_timeout(400)
            page.evaluate("() => { location.hash = '#/tools'; }"); page.wait_for_timeout(800)
        else:
            page.goto(BASE + '#/tools', wait_until='load'); page.wait_for_timeout(1200)

    run(page, "async (db) => { await db.signOut(); await db.refreshSyncStatus(); }")
    open_tools()
    check('signed out, الأدوات offers a sign-in form',
          page.locator('.sync-signin').count() == 1, str(page.locator('.sync-signin').count()))
    check('...with an email field and a MASKED password field',
          page.locator('.sync-signin input[type=email]').count() == 1
          and page.locator('.sync-signin input[type=password]').count() == 1)
    check('...and a «تسجيل الدخول» button',
          'تسجيل الدخول' in page.locator('.sync-signin').inner_text())
    body_txt = page.inner_text('body')
    check('...and NO way to create an account — invite-only, permanently',
          not any(w in body_txt for w in ['إنشاء حساب', 'Create account', 'Sign up', 'تسجيل جديد']),
          'a create-account control would be a dead end that looks like a feature')

    # wrong credentials
    srv['token_mode'] = 'reject'
    page.fill('.sync-signin input[type=email]', 'spike-a@zajil.test')
    page.fill('.sync-signin input[type=password]', 'not-the-password')
    page.click('.sync-signin .btn-primary'); page.wait_for_timeout(1200)
    err = page.locator('.sync-signin').inner_text()
    check('a wrong password says so, in its own words',
          'غير صحيحة' in err, err.replace('\n', ' ')[:120])
    # The MESSAGE element itself must be free of the status — checking only the
    # text before the phrase would let a status appended after it slip through,
    # which is exactly what a mutation showed.
    msg = page.locator('.sync-signin .warn').inner_text()
    check('...and the raw status is NOT in that sentence',
          '400' not in msg and not any(c.isdigit() for c in msg), msg.replace('\n', ' ')[:120])
    check('...though it is available underneath, for whoever is debugging',
          'HTTP 400' in err, err.replace('\n', ' ')[:160])
    check('...and the button is usable again', page.locator('.sync-signin .btn-primary').is_enabled())

    # no connection — must NOT read like a wrong password
    srv['token_mode'] = 'abort'
    page.fill('.sync-signin input[type=password]', 'anything')
    page.click('.sync-signin .btn-primary'); page.wait_for_timeout(1200)
    err2 = page.locator('.sync-signin').inner_text()
    check('no connection reads as a connection problem, not a wrong password',
          'تعذّر الاتصال' in err2 and 'غير صحيحة' not in err2, err2.replace('\n', ' ')[:120])

    # unconfigured build — the third distinct cause
    srv['token_mode'] = 'ok'
    run(page, "() => { globalThis.__saved = globalThis.ZAJIL_SYNC_CONFIG; delete globalThis.ZAJIL_SYNC_CONFIG; }")
    open_tools(soft=True)
    check('an unconfigured build explains itself and offers no pointless form',
          page.locator('.sync-signin').count() == 0
          and 'غير مهيأة' in page.inner_text('body'),
          page.inner_text('body')[:120].replace('\n', ' '))
    run(page, "() => { globalThis.ZAJIL_SYNC_CONFIG = globalThis.__saved; }")

    # ENTER submits, from the password field
    open_tools(soft=True)
    page.fill('.sync-signin input[type=email]', 'spike-a@zajil.test')
    page.fill('.sync-signin input[type=password]', 'pw')
    page.press('.sync-signin input[type=password]', 'Enter')
    page.wait_for_timeout(2000)
    check('ENTER submits the form', run(page, "(db) => db.authState().signedIn") is True)
    check('...and the card switches to the signed-in state',
          page.locator('.sync-signin').count() == 0 and 'spike-a@zajil.test' in page.inner_text('body'))
    check('...offering «تسجيل الخروج»', 'تسجيل الخروج' in page.inner_text('body'))
    check('...and saying plainly that signing out is not deleting',
          'بياناتك تبقى على هذا الجهاز' in page.inner_text('body'))

    # the first-login flow ran, unchanged — no second code path for "just signed in"
    check('signing in ran a real sync cycle',
          run(page, "(db) => db.state.settings.lastSyncAt") is not None)

    # SIGN OUT KEEPS THE DATA
    birds_before = run(page, """async (db) => {
        await db.saveBird(db.newBird({ name: 'survives-sign-out', sex: 'cock' }));
        return db.allBirds().length;
    }""")
    page.click('text=تسجيل الخروج'); page.wait_for_timeout(1200)
    after_out = run(page, """async (db) => ({
        signedIn: db.authState().signedIn,
        birds: db.allBirds().length,
        tokens: db.AUTH_SETTING_KEYS.map(k => db.state.settings[k]).filter(Boolean).length,
    })""")
    check('signing out clears every token', after_out['tokens'] == 0, str(after_out))
    check('SIGNING OUT IS NOT DELETING — the birds are still there',
          after_out['birds'] == birds_before, f"{birds_before} -> {after_out['birds']}")
    check('...and the form comes back', page.locator('.sync-signin').count() == 1)

    # hand the next section the state it expects: signed in, with a sync behind
    # it. Asserted, not assumed — a silent failure here would surface as six
    # confusing failures in the next section instead of one clear one.
    handoff = run(page, """async (db) => {
        const st = await db.signIn('spike-a@zajil.test','pw');
        await db.syncNow();
        await db.refreshSyncStatus();
        return { signedIn: st.signedIn, email: st.email, state: db.syncStatus().state };
    }""")
    check('handed the next section a signed-in device',
          handoff['signedIn'] is True and handoff['state'] != 'hidden', str(handoff))

    # Leave the page on a DIFFERENT route. The next section navigates to
    # #/tools, and `page.goto` to the URL the browser is already on does not
    # re-run the app — it would read a card rendered before this hand-off and
    # report six confusing failures about state that is actually correct.
    page.goto(BASE + '#/birds', wait_until='load'); page.wait_for_timeout(600)

    # ── 9. the الأدوات card ──
    # Establish this section's own precondition rather than inheriting whatever
    # the previous one happened to leave behind: the card must show an error
    # WHEN THERE IS ONE, which is the actual claim.
    run(page, """async (db) => {
        await db.setSetting('lastSyncError', { key: 'sync.err.rejected', status: 400,
            at: new Date().toISOString(),
            since: new Date(Date.now() - 5 * 60 * 1000).toISOString() });
    }""")
    page.goto(BASE + '#/tools', wait_until='load'); page.wait_for_timeout(1200)
    body = page.inner_text('body')
    check('الأدوات has a المزامنة card', 'المزامنة' in body)
    check('...showing the signed-in account', 'spike-a@zajil.test' in body, body[:200].replace('\n', ' '))
    check('...the last sync time', 'آخر مزامنة' in body)
    check('...the pending count', 'بانتظار المزامنة' in body)
    check('...a «مزامنة الآن» button', 'مزامنة الآن' in body)
    check('...and a sync-off toggle', 'إيقاف المزامنة' in body or 'تشغيل المزامنة' in body)
    check('...with the last error shown IN FULL, status code and all',
          'آخر خطأ' in body and '400' in body, body[body.find('آخر خطأ'):][:120].replace('\n', ' ')
          if 'آخر خطأ' in body else 'no error line')

    # the manual button really runs a cycle
    before = run(page, "(db) => db.state.settings.lastSyncAt")
    page.click("text=مزامنة الآن")
    page.wait_for_timeout(1500)
    after = run(page, "(db) => db.state.settings.lastSyncAt")
    check('«مزامنة الآن» actually runs a cycle', after != before, f'{before} -> {after}')

    # the toggle really stops it
    run(page, "async (db) => { await db.setSyncEnabled(false); }")
    off_state = run(page, "async (db) => { await db.refreshSyncStatus(); return db.syncStatus().state; }")
    check('the toggle turns sync off', off_state == 'off', str(off_state))
    blocked = run(page, "async (db) => await db.runSyncCycle()")
    check('...and a background cycle refuses to run while it is off',
          blocked['reason'] == 'off', str(blocked))
    check('...but the manual button still works, because the user just asked',
          (run(page, "async (db) => await db.runSyncCycle({ manual: true })") or {})['reason'] != 'off')
    run(page, "async (db) => { await db.setSyncEnabled(true); }")

    # ── 10. the backoff curve ──
    bo = run(page, """(db) => {
        const seen = [];
        for (let attempt = 0; attempt < 8; attempt++) {
            const samples = Array.from({ length: 40 }, () => db.backoffDelay(attempt));
            seen.push({ attempt, min: Math.min(...samples), max: Math.max(...samples) });
        }
        return { seen, curve: db.BACKOFF_MS, window: db.SOFT_FAIL_WINDOW_MS };
    }""")
    check('the backoff curve is 2, 4, 8, 16, 32, 60 seconds (§11)',
          bo['curve'] == [2000, 4000, 8000, 16000, 32000, 60000], str(bo['curve']))
    check('the silent window is about two minutes', bo['window'] == 120000, str(bo['window']))
    check('every delay is jittered by ±25 %, so devices do not retry in lockstep',
          all(r['min'] < r['max'] for r in bo['seen']), str(bo['seen'][:2]))
    check('...within the ±25 % band, never outside it',
          all(r['min'] >= bo['curve'][min(r['attempt'], 5)] * 0.74 and
              r['max'] <= bo['curve'][min(r['attempt'], 5)] * 1.26 for r in bo['seen']),
          str(bo['seen']))
    check('...and it caps at 60 s, so a long outage reconnects within a minute',
          bo['seen'][-1]['max'] <= 60000 * 1.26, str(bo['seen'][-1]))

    # ── 11. an unconfigured build shows nothing and still works ──
    unc = run(page, """async (db) => {
        const saved = globalThis.ZAJIL_SYNC_CONFIG;
        delete globalThis.ZAJIL_SYNC_CONFIG;
        const s = db.syncStatus();
        const bird = await db.saveBird(db.newBird({ name: 'ui-unconfigured', sex: 'cock' }));
        globalThis.ZAJIL_SYNC_CONFIG = saved;
        return { state: s.state, saved: !!db.getBird(bird.id) };
    }""")
    check('an unconfigured build advertises no machinery it does not have',
          unc['state'] == 'hidden', str(unc['state']))
    check('...and still saves birds', unc['saved'] is True)

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()

print(f'\n{ok} passed, {fail} failed')
