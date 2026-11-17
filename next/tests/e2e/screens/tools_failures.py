#!/usr/bin/env python3
"""THE ELEVEN (RULED 2026-11-17): every mutating handler in الأدوات surfaces its failure.

ROOT-FINDINGS listed eleven handlers in the tools screens that could fail without a word: an unhandled rejection, and a
screen that looks as if the press did nothing — or, for «مزامنة الآن», «تم الحفظ» after a cycle that failed.
Each step here makes the handler's own write fail (IndexedDB refuses every write while the fault is armed; for the sync
button the stub project answers 500), presses the real control, and asserts: an error toast that names the control and
the reason, no success toast, no page error. Each handler has its own mutant (M-h01 … M-h11), which fails at its step.

Binds to data-testid only. Provisions its own server (R6). THE NET armed."""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr
import base64
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
sys.path.insert(0, HERE)
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _net import Net                          # noqa: E402
from _typography import SCAN                  # noqa: E402
NET = Net()

passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    if ok: passed += 1; print(f'  ✓ {n}')
    else: failed += 1; print(f'  ✗ {n}  {d}')

STUB = 'https://stub.example.test'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
SRV = {'rows': {}, 'seq': 0, 'down': False}
def handler(route, request):
    if '/auth/v1/token' in request.url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'access_token': 'ACCESS-A', 'refresh_token': 'REFRESH-A', 'token_type': 'bearer', 'expires_in': 3600, 'user': {'id': 'user-A', 'email': 'a@zajil.test'}})); return
    if SRV['down']: route.fulfill(status=500, content_type='application/json', body='{"message":"stub down"}'); return
    if request.method == 'POST':
        out = []
        for r in json.loads(request.post_data or '[]'):
            SRV['seq'] += 1; row = dict(r, server_seq=SRV['seq'], owner='user-A'); SRV['rows'][(r['store'], r['record_id'])] = row; out.append(row)
        route.fulfill(status=200, content_type='application/json', body=json.dumps(out)); return
    c = int(re.search(r'server_seq=gt\.(\d+)', request.url).group(1))
    route.fulfill(status=200, content_type='application/json', body=json.dumps(sorted((r for r in SRV['rows'].values() if r['server_seq'] > c), key=lambda r: r['server_seq'])[:int(re.search(r'limit=(\d+)', request.url).group(1))]))

def run(pg, js, *args): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(args))
# THE FAULT: while armed, IndexedDB refuses every write. Reads go on working, so the screen stays as it was.
ARM = """() => { const P = IDBObjectStore.prototype; if (window.__heal) return; const keep = {};
  for (const m of ['put', 'add', 'delete', 'clear']) { keep[m] = P[m]; P[m] = function () { throw new DOMException('injected-write-failure', 'QuotaExceededError'); }; }
  window.__heal = () => { for (const m in keep) P[m] = keep[m]; window.__heal = null; }; }"""
HEAL = "() => { if (window.__heal) window.__heal(); }"
# what is STORED — setSetting() writes memory first and storage second (src/db/storage.js), so after a failed write the two differ
STORED = "async (db, k) => { const r = (await db.idbGetAll('settings')).find(x => x.key === k); return r ? r.value : null; }"
def toasts(pg): return [(x.get_attribute('data-kind') or '', x.inner_text().replace('\n', ' ')) for x in pg.locator('[data-testid=toast]').all()]
def clear(pg):
    for _ in range(40):
        if pg.locator('[data-testid=toast]').count() == 0: return
        pg.wait_for_timeout(500)
def open_row(pg, row):
    r = pg.locator(f'[data-row={row}]')
    if r.get_attribute('open') is None: r.locator('summary').click(); pg.wait_for_timeout(300)
def goto(pg, url, sel):
    pg.goto(url, wait_until='load'); pg.wait_for_selector(sel, timeout=15000); pg.wait_for_timeout(800)

def verdict(pg, tag, mutant, label, what, reason='injected-write-failure', unchanged=None):
    """After the press: the failure was said, by name; nothing claimed success; nothing was thrown into the page."""
    pg.wait_for_timeout(1500); pg.evaluate(HEAL); got = toasts(pg); texts = ' | '.join(x[1] for x in got); errs = list(pg.errs); pg.errs.clear()
    typo = pg.evaluate(SCAN)
    ok = any('لم يكتمل' in x and f'«{what}»' in x and 'السبب' in x and reason in x for _, x in got) and not any('تم الحفظ' in x for _, x in got) and not errs
    check(f'[{tag} · {mutant} fails here] {label}: the failure is SAID — «لم يكتمل «{what}». السبب: …» — nothing claims success, and no error is thrown into the page', ok, (texts[:260], errs[:2]))
    if unchanged is not None: check(f'[{tag}] …and {unchanged[0]}', unchanged[1](), '')
    check(f'[{tag} · typography] the message is drawn in a face that has Arabic', bool(got) and not typo, [(x['why'], x['face'], x['text'][:30]) for x in typo][:3])
    clear(pg)

srvp, H = serve(); ROOT = H.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}))
        ctx.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};"); ctx.route(f'{STUB}/**', handler)
        pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e: pg.errs.append(perr(e, pg)))
        pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady'); run(pg, "async (db) => { await db.signIn('a@zajil.test', 'pw'); }")
        # the state the eleven need: a named loft, two birds wearing one ring, one snapshot
        run(pg, """async (db) => { await db.Lofts.save({ ...db.currentLoft(), name: 'لوفت الاختبار' });
            const ring = { raw: 'JOR 2024 0001', country: 'JOR', year: 2024, number: '0001' };
            await db.saveBird(db.newBird({ name: 'الأول', sex: 'cock', rings: [ring] })); await db.saveBird(db.newBird({ name: 'نسخته', sex: 'cock', rings: [ring] }), { allowWarnings: true }).catch(() => db.importAll({ format: 'zajil-export', version: 1, birds: [{ ...db.newBird({ name: 'نسخته', sex: 'cock', rings: [ring] }) }] }, 'merge'));
            await db.importAll(await db.exportAll({ includeMedia: false }), 'replace'); await db.syncNow(); }""")
        pg.wait_for_timeout(4500); pg.errs.clear()
        base = run(pg, "async (db) => ({ birds: db.state.birds.size, snaps: (await db.listBackups()).length })")
        check('[setup] two birds wearing one ring and one snapshot are on the device', base['birds'] == 2 and base['snaps'] >= 1, base)

        # ── 1 «مزامنة الآن»: the project answers 500 ──
        goto(pg, ROOT + 'tools/sync/', '[data-testid=sync-now]'); clear(pg)
        pg.click('[data-testid=sync-now]'); pg.wait_for_timeout(2500); ok_toast = toasts(pg)
        check('[1 · control] with the project answering, «مزامنة الآن» says «تم الحفظ»', any('تم الحفظ' in x for _, x in ok_toast) and not any('لم يكتمل' in x for _, x in ok_toast), ok_toast)
        clear(pg); run(pg, "async (db) => { await db.saveBird(db.newBird({ name: 'غير مرسل', sex: 'hen' })); }"); SRV['down'] = True
        pg.click('[data-testid=sync-now]'); pg.wait_for_timeout(2500)
        verdict(pg, '1', 'M-h01', '«مزامنة الآن» with the project answering 500', 'مزامنة الآن', reason='')
        SRV['down'] = False; pg.click('[data-testid=sync-now]'); pg.wait_for_timeout(2500); clear(pg); pg.errs.clear()

        # ── 2 the sync toggle ──
        was = run(pg, STORED, 'syncEnabled'); lab = pg.locator('[data-testid=sync-toggle]').inner_text().strip()
        pg.evaluate(ARM); pg.click('[data-testid=sync-toggle]')
        verdict(pg, '2', 'M-h02', 'the sync toggle', lab, unchanged=('the stored setting is as it was', lambda: run(pg, STORED, 'syncEnabled') == was))
        mem = run(pg, "(db) => db.state.settings.syncEnabled"); stored = run(pg, STORED, 'syncEnabled')
        check('[RF-25 · M-rf25 fails here] …and the setting IN MEMORY is what storage holds — sync is still on, and the button still offers to turn it off, with no reload', mem is not False and stored is not False and pg.locator('[data-testid=sync-toggle]').inner_text().strip() == lab, (mem, stored, pg.locator('[data-testid=sync-toggle]').inner_text().strip()))
        # RF-25 at the layer itself: a refused write rejects, and neither a setting that existed nor one that did not is left changed in memory
        pg.evaluate(ARM)
        direct = run(pg, """async (db) => { const before = db.state.settings.coiDepth; const out = {};
            try { await db.setSetting('coiDepth', 14); out.a = 'resolved'; } catch (e) { out.a = 'rejected'; }
            try { await db.setSetting('rf25-never-set', 'x'); out.b = 'resolved'; } catch (e) { out.b = 'rejected'; }
            return { ...out, same: db.state.settings.coiDepth === before, absent: !('rf25-never-set' in db.state.settings) }; }"""); pg.evaluate(HEAL)
        check('[RF-25 · M-rf25 fails here] setSetting() with storage refusing: it rejects, an existing setting keeps its value in memory, and a new one does not appear', direct == {'a': 'rejected', 'b': 'rejected', 'same': True, 'absent': True}, direct)
        run(pg, "async (db) => { await db.setSetting('rf25-probe', 7); }")
        check('[RF-25] …and with storage accepting, memory and storage both take the value', run(pg, "(db) => db.state.settings['rf25-probe']") == 7 and run(pg, STORED, 'rf25-probe') == 7, '')
        pg.errs.clear()

        # ── 3 deleting a duplicate copy ──
        goto(pg, ROOT + 'tools/duplicates/', '[data-testid=dup-delete]')
        pg.locator('[data-testid=dup-delete]').first.click(); pg.wait_for_selector('[data-testid=dialog]', timeout=8000); pg.evaluate(ARM); pg.click('[data-testid=dialog-confirm]')
        verdict(pg, '3', 'M-h03', 'deleting a duplicate copy', 'حذف', unchanged=('both copies are still stored', lambda: run(pg, "async (db) => (await db.idbGetAll('birds')).length") == 3))

        # ── 4 restoring a snapshot ──
        goto(pg, ROOT + 'tools/restore/', '[data-testid=snap-restore]')
        pg.locator('[data-testid=snap-restore]').first.click(); pg.wait_for_selector('[data-testid=dialog]', timeout=8000); pg.evaluate(ARM); pg.click('[data-testid=dialog-confirm]')
        verdict(pg, '4', 'M-h04', 'restoring a snapshot', 'استرجاع نسخة تلقائية', unchanged=('the three birds are still stored', lambda: run(pg, "async (db) => (await db.idbGetAll('birds')).length") == 3))

        # ── 5 loading the example data ──
        goto(pg, ROOT + 'tools/', '[data-testid=tools-list]'); open_row(pg, 'teaching'); pg.evaluate(ARM); pg.click('[data-testid=load-sample]'); pg.wait_for_timeout(1500)
        verdict(pg, '5', 'M-h05', 'loading the example data', 'تحميل بيانات تجريبية للتعلّم', unchanged=('no example bird was stored', lambda: run(pg, "async (db) => (await db.idbGetAll('birds')).length") == 3))

        # ── 6 the integrity check ──
        open_row(pg, 'integrity'); pg.evaluate(ARM); pg.click('[data-testid=integrity-run]')
        verdict(pg, '6', 'M-h06', 'the integrity check, whose result cannot be stored', 'فحص ترابط البيانات', unchanged=('no «آخر فحص» was stored', lambda: run(pg, STORED, 'integrityCheckedAt') is None))

        # ── 7 the scanner address: the button, then the blur ──
        open_row(pg, 'scanner'); pg.fill('[data-testid=scan-url]', 'https://vision.example.org'); pg.evaluate(ARM); pg.click('[data-testid=scan-save]')
        verdict(pg, '7', 'M-h07', 'saving the scanner address with «حفظ»', 'ماسح شهادات النسب الورقية', unchanged=('no address was stored', lambda: not run(pg, STORED, 'scanServerUrl')))
        pg.fill('[data-testid=scan-url]', 'https://vision2.example.org'); pg.evaluate(ARM); pg.locator('[data-testid=scan-url]').blur()
        verdict(pg, '7b', 'M-h07', 'saving the scanner address by leaving the field', 'ماسح شهادات النسب الورقية')

        # ── 9 saving the loft ──
        goto(pg, ROOT + 'tools/', '[data-testid=tools-list]'); open_row(pg, 'loft-name'); pg.fill('[data-testid=ln]', 'اسم لن يُحفظ'); pg.evaluate(ARM); pg.locator('[data-testid=loft-save][data-field=name]').click()
        verdict(pg, '9', 'M-h09', 'saving the loft', 'اللوفت', unchanged=('the loft keeps its name', lambda: run(pg, "(db) => db.currentLoft().name") == 'لوفت الاختبار'))

        # ── 10 choosing a logo ──
        goto(pg, ROOT + 'tools/', '[data-testid=tools-list]'); open_row(pg, 'logo'); pg.evaluate(ARM)
        pg.set_input_files('[data-testid=logo-input]', files=[{'name': 'logo.png', 'mimeType': 'image/png', 'buffer': PNG}]); pg.wait_for_timeout(1200)
        verdict(pg, '10', 'M-h10', 'choosing a logo', 'اختيار شعار', unchanged=('no logo was stored', lambda: run(pg, "async (db) => (await db.idbGetAll('media')).length") == 0))

        # ── 11 removing the logo ──
        pg.set_input_files('[data-testid=logo-input]', files=[{'name': 'logo.png', 'mimeType': 'image/png', 'buffer': PNG}]); pg.wait_for_timeout(1500)
        pg.locator('[data-testid=loft-save][data-field=logo]').click(); pg.wait_for_timeout(1200); clear(pg); pg.errs.clear()
        check('[11 · setup] a logo is stored and the loft points at it', run(pg, "async (db) => (await db.idbGetAll('media')).length === 1 && !!db.currentLoft().logoMediaId"), '')
        pg.evaluate(ARM); pg.click('[data-testid=logo-remove]')
        verdict(pg, '11', 'M-h11', 'removing the logo', 'إزالة الشعار', unchanged=('the logo is still stored, the loft still points at it, and the screen still offers «إزالة الشعار»',
                lambda: run(pg, "async (db) => (await db.idbGetAll('media')).length === 1 && !!db.currentLoft().logoMediaId") and pg.locator('[data-testid=logo-remove]').count() == 1))

        # ── 8 signing out (last: it ends the session when it works) ──
        open_row(pg, 'account'); pg.click('[data-testid=sign-out]'); pg.wait_for_selector('[data-testid=dialog]', timeout=8000); pg.evaluate(ARM); pg.click('[data-testid=dialog-confirm]')
        verdict(pg, '8', 'M-h08', 'signing out', 'تسجيل الخروج', unchanged=('the device is still signed in', lambda: run(pg, "(db) => db.authState().signedIn") is True))

        check('zero page errors left over', pg.errs == [], pg.errs[:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
