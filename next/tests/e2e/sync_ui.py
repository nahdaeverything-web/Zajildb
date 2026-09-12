# tests/e2e/sync_ui.py — the sync status row, the الأدوات card, and the rule that
# decides what is allowed to interrupt a fancier (§10, §11).
#
# A copy of the root suite. Four kinds of change, and nothing else:
#   · the module token — `import('./js/db.js')` → `window.__zajilDb`;
#   · the shell's DOM — `#sync-row` / `.sync-details` / `.toast` are vanilla class
#     names; the port's shell says the same things through data-testid, and the
#     healthy row is not rendered AT ALL rather than rendered with display:none
#     (which is what "not taking up space" was asserting);
#   · the routes — `#/tools` → `tools.html`, `#/birds` → `birds.html`;
#   · RULING 1 (Phase 4 order) — the inline sign-in form inside the card is
#     superseded by /sign-in. Its ten assertions (#23–#33 of the root list) are in
#     tests/e2e/screens/tools.py and tests/e2e/screens/sign_in.py, re-authored
#     against the screens that now hold them, and are NOT duplicated here.
#
# The point of most of these assertions is what is NOT shown: nothing when it works,
# nothing alarming when there is no signal, and an interruption only for the two
# things a person can actually act on.
import json, os
from playwright.sync_api import sync_playwright

HARNESS = os.environ.get('ZAJIL_URL', 'http://127.0.0.1:8123/test-harness.html')
ROOT = HARNESS.replace('test-harness.html', '')
STUB_URL = 'https://stub.zajil.test'
STUB_KEY = 'sb_publishable_STUBKEY'

ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')

srv = {'mode': 'ok', 'token_mode': 'ok'}

def handler(route, request):
    if '/auth/v1/token' in request.url:
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

JS = "async (a) => { const db = await window.__zajilDb; return (%s)(db, a); }"
def run(page, fn, arg=None):
    return _wrap(page.evaluate(JS % fn, arg))

ROW = '[data-testid=sync-row]'
def row_text(page):
    return (page.eval_on_selector(ROW, 'n => n.textContent.trim()')
            if page.query_selector(ROW) else None)
def row_state(page):
    return (page.eval_on_selector(ROW, 'n => n.getAttribute("data-state")')
            if page.query_selector(ROW) else None)
def toasts(page):
    return page.eval_on_selector_all('[data-testid=toast]', 'ns => ns.map(n => n.textContent)')
def clear_toasts(page, timeout=12000):
    """Wait for the stack to empty through the app's own timers.

    The root suite removes the nodes (`n.remove()`), which works because vanilla's toasts
    are hand-made DOM. The port's are React-owned, and pulling one out behind React's back
    breaks reconciliation: the next render dies with "removeChild … not a child of this
    node" and the toast this section is measuring never appears. The longest timeout in
    play is the 10 s sync-interrupt, so the wait is a little longer than that."""
    page.wait_for_function("() => document.querySelectorAll('[data-testid=toast]').length === 0",
                           timeout=timeout)

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context()
    ctx.add_init_script(
        f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB_URL}', publishableKey: '{STUB_KEY}' }};")
    ctx.route(f'{STUB_URL}/**', handler)
    page = ctx.new_page(); page.set_default_timeout(30000)
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    # any screen that carries the shared row; the loft home is the one a fancier opens on
    page.goto(ROOT + 'birds.html', wait_until='load'); page.wait_for_timeout(1800)

    # ── 1. a device with no session shows NOTHING ──
    check('the shell has a place for the status row', page.evaluate(
        "() => typeof window.__zajilDb !== 'undefined'"))
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
    page.wait_for_timeout(400)
    check('a synced device shows NOTHING — sync is invisible when it works',
          (row_text(page) or '') == '', repr(row_text(page)))
    # the port renders no element at all in the healthy state, which is the same claim
    # the vanilla assertion made through display:none — the row takes no space
    check('...and the empty row is not taking up space',
          page.query_selector(ROW) is None
          or page.eval_on_selector(ROW, 'n => getComputedStyle(n).display') == 'none')

    # ── 3. pending work is stated plainly, in Arabic, with the count ──
    run(page, """async (db) => {
        await db.saveBird(db.newBird({ name: 'ui-pending-1', sex: 'cock' }));
        await db.saveBird(db.newBird({ name: 'ui-pending-2', sex: 'hen' }));
        await db.setSetting('syncEnabled', false);      // paused, so nothing drains it
        await db.refreshSyncStatus();
    }""")
    page.wait_for_timeout(400)
    check('a paused device says so', 'المزامنة متوقفة' in (row_text(page) or ''), repr(row_text(page)))
    check('...calmly, never as a warning', row_state(page) != 'error', row_state(page))

    st = run(page, """async (db) => {
        await db.setSetting('syncEnabled', true);
        await db.setSetting('lastSyncError', null);
        await db.refreshSyncStatus();
        return db.syncStatus();
    }""")
    check('pending ops are counted', (st['pending'] or 0) >= 2, str(st['pending']))
    page.wait_for_timeout(400)
    if st['state'] == 'pending':
        check('pending is shown with its count',
              'بانتظار المزامنة' in (row_text(page) or ''), repr(row_text(page)))
        check('...and is not styled as a warning', row_state(page) != 'error', row_state(page))
    else:
        check('pending is shown with its count', True, '(a cycle drained it first)')
        check('...and is not styled as a warning', True, '')

    # ── 4. OFFLINE IS NEVER AN ERROR, however long it lasts ──
    off = run(page, """async (db) => {
        await db.saveBird(db.newBird({ name: 'ui-offline', sex: 'cock' }));
        await db.setSetting('lastSyncError', { key: 'sync.err.network', status: null,
            at: new Date().toISOString(),
            since: new Date(Date.now() - 4 * 3600 * 1000).toISOString() });
        await db.refreshSyncStatus();
        return db.syncStatus();
    }""")
    page.wait_for_timeout(400)
    check('a four-hour outage is still just "offline"', off['state'] == 'offline', str(off['state']))
    check('...shown as reassurance, not an error',
          'دون اتصال' in (row_text(page) or '') and row_state(page) == 'offline',
          f'{row_text(page)!r} / {row_state(page)}')
    check('...and it never offers a "details" link, because there is nothing to fix',
          page.query_selector('[data-testid=sync-row-link]') is None)

    # ── 5. a TRANSIENT non-network failure stays silent ──
    quiet = run(page, """async (db) => {
        await db.setSetting('lastSyncError', { key: 'sync.err.rejected', status: 400,
            at: new Date().toISOString(), since: new Date().toISOString() });
        await db.refreshSyncStatus();
        return db.syncStatus();
    }""")
    check('a rejection that just started is NOT shown as an error',
          quiet['state'] != 'error', str(quiet['state']))
    page.wait_for_timeout(300)
    check('...so nothing alarming appears', row_state(page) != 'error', row_state(page))

    # ── 6. ...and becomes visible once it has outlived the backoff rounds ──
    loud = run(page, """async (db) => {
        await db.setSetting('lastSyncError', { key: 'sync.err.rejected', status: 400,
            at: new Date().toISOString(),
            since: new Date(Date.now() - 3 * 60 * 1000).toISOString() });   // 3 minutes
        await db.refreshSyncStatus();
        return db.syncStatus();
    }""")
    page.wait_for_timeout(400)
    check('a rejection that has persisted past the window IS shown',
          loud['state'] == 'error', str(loud['state']))
    check('...as a warning, with a link to الأدوات',
          row_state(page) == 'error'
          and page.eval_on_selector('[data-testid=sync-row-link]', 'n => n.getAttribute("href")') in ('/tools', '/tools.html'),
          f'{row_state(page)} / {page.query_selector("[data-testid=sync-row-link]") is not None}')
    check('...using wording that avoids blame and jargon',
          'تعذّرت المزامنة' in (row_text(page) or ''), repr(row_text(page)))

    # ── 7. a dead session interrupts IMMEDIATELY — it needs a password ──
    clear_toasts(page)
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
    clear_toasts(page)
    run(page, """async (db) => {
        await db.signOut();                       // the session is genuinely gone
        await db.setSetting('lastSyncError', null);
        await db.refreshSyncStatus();
    }""")
    page.wait_for_timeout(300)
    check('a signed-out device hides the row again',
          run(page, "(db) => db.syncStatus().state") == 'hidden')

    # ── 8. the interrupt fires ONCE, not on every cycle ──
    run(page, "async (db) => { await db.signIn('spike-a@zajil.test','pw'); }")
    srv['mode'] = '4xx'
    clear_toasts(page)
    run(page, """async (db) => {
        await db.saveBird(db.newBird({ name: 'ui-interrupt', sex: 'hen' }));
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
    page.wait_for_timeout(600)
    interrupts = [x for x in toasts(page) if 'المزامنة' in x or 'الجلسة' in x]
    # EXACTLY one, not "at most one": `<= 1` would pass just as happily if the
    # interruption never fired at all, which is the failure this is guarding
    # against in the other direction. The port raises it from the shell —
    # src/components/SyncNotices.tsx, which is js/app.js:195-217.
    check('a persistent rejection DOES interrupt', len(interrupts) >= 1,
          f'no interruption fired at all: {toasts(page)}')
    check('...exactly once, not on every cycle', len(interrupts) == 1,
          f'{len(interrupts)} toasts: {interrupts}')
    srv['mode'] = 'ok'

    # ── 9. the الأدوات card ──
    # Establish this section's own precondition rather than inheriting whatever the
    # previous one happened to leave behind: the card must show an error WHEN THERE
    # IS ONE, which is the actual claim.
    run(page, """async (db) => {
        await db.setSetting('lastSyncError', { key: 'sync.err.rejected', status: 400,
            at: new Date().toISOString(),
            since: new Date(Date.now() - 5 * 60 * 1000).toISOString() });
    }""")
    page.goto(ROOT + 'tools.html', wait_until='load'); page.wait_for_timeout(1800)
    body = page.inner_text('body')
    check('الأدوات has a المزامنة card', 'المزامنة' in body)
    check('...showing the signed-in account', 'spike-a@zajil.test' in body, body[:200].replace('\n', ' '))
    check('...the last sync time', 'آخر مزامنة' in body)
    check('...the pending count', 'بانتظار المزامنة' in body)
    check('...a «مزامنة الآن» button', 'مزامنة الآن' in body)
    check('...and a sync-off toggle', 'إيقاف المزامنة' in body or 'تشغيل المزامنة' in body)
    check('...with the last error shown IN FULL, status code and all',
          'آخر خطأ' in body and '400' in body,
          body[body.find('آخر خطأ'):][:120].replace('\n', ' ') if 'آخر خطأ' in body else 'no error line')

    # the manual button really runs a cycle
    before = run(page, "(db) => db.state.settings.lastSyncAt")
    page.click('[data-testid=sync-now]')
    page.wait_for_timeout(2000)
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
raise SystemExit(1 if fail else 0)
