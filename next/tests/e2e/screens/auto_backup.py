"""RF-21 (RULED a defect 2026-11-01): THE INTERVAL SNAPSHOT HAS A CALLER.

The restore screen says «نسخ تلقائي داخلي كل 12 ساعة (آخر 7 نسخ)». Until this suite's change set nothing called
autoBackup(), so no snapshot was ever taken. Asserted here: one at boot when none exists or the last is older than the
interval; one after the interval with the page left open (the browser's clock is driven, not waited for); none for an
empty register; none before the interval; seven kept; and the screen's two numbers are the layer's two constants.

RULED 2026-11-16, asserted here too: seven INTERVAL snapshots and, separately, the last THREE taken before a replace or
a restore, neither kind ever evicting the other (seven replaces then nine interval snapshots leave 7 and 3); the list
newest first with a pre-import snapshot at its moment; «آخر نسخة تلقائية» the newest INTERVAL one; the snapshot row in
a face that has Arabic; «{n} متاحة» and the list re-read on a layer change; the note saying what is true; no snapshot
at the sign-in gate (where an account collision stops a device); and the collision CLEAR leaving no snapshot behind.
Harness build; no sync configured except on the two gate devices, which talk to a stub; the net armed. All shapes are
CONSTRUCTED.

    python3 tests/e2e/screens/auto_backup.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr   # TF-12: a page error is recorded with its stack, address, device and step
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _net import Net, no_bucket                          # noqa: E402  THE NET: armed, asserted at the end
from _typography import SCAN                  # noqa: E402
NET = Net()
PAGES = []

passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    if ok: passed += 1; print(f'  ✓ {n}')
    else: failed += 1; print(f'  ✗ {n}  {d}')

def run(pg, js, *args): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(args))
def digits(s): return re.sub(r'[٠-٩]', lambda m: str('٠١٢٣٤٥٦٧٨٩'.index(m.group())), s)
SNAPS = """async (db) => { const st = {}; for (const r of await db.idbGetAll('settings')) st[r.key] = r.value;
  const b = (await db.idbGetAll('backups')).sort((x, y) => (x.id < y.id ? -1 : 1));
  return { n: b.length, ids: b.map(x => x.id), kinds: b.map(x => x.payload && x.payload.kind), birds: b.map(x => ((x.payload && x.payload.birds) || []).length), last: st.lastAutoBackup || null,
    hours: db.AUTO_BACKUP_HOURS, keep: db.BACKUP_KEEP, keepPre: db.PRE_IMPORT_KEEP,
    auto: b.filter(x => !x.id.startsWith('pre-import-')).map(x => x.id), pre: b.filter(x => x.id.startsWith('pre-import-')).map(x => x.id),
    listed: (await db.listBackups()).map(x => x.id) }; }"""
def snaps(pg): return run(pg, SNAPS)
def settled(pg, want, seconds=6):
    """The snapshot is written after the boot, asynchronously: poll for the count, bounded, and return what is there.
    TF (APPROVED 2026-11-19): autoBackup() writes the snapshot and THEN its marker (io.js), and a read between the two
    saw the new count with the old marker — gate-38, once in 21 runs. So the wait is for both: the count, and the
    marker naming the newest interval snapshot. Still bounded; when no new snapshot is due it returns what is there."""
    end = time.time() + seconds; s = snaps(pg)
    def there(s): return s['n'] == want and s['last'] == (s['auto'][-1] if s['auto'] else None)
    while not there(s) and time.time() < end: time.sleep(0.25); s = snaps(pg)
    return s
def boot(pg, H): pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady')
STUB = 'https://stub.example.test'
def stub(route, request):
    """A backend with no rows: a session for whoever asks, every push echoed, every pull empty."""
    if no_bucket(route, request): return          # this suite's project has no photo bucket (tests/e2e/_net.py)
    if '/auth/v1/token' in request.url:
        body = json.loads(request.post_data or '{}'); who = (body.get('email') or '').split('@')[0].upper() or (body.get('refresh_token') or '').replace('REFRESH-', '')
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'access_token': 'ACCESS-' + who, 'refresh_token': 'REFRESH-' + who, 'token_type': 'bearer', 'expires_in': 3600, 'user': {'id': 'user-' + who, 'email': who.lower() + '@zajil.test'}}))
    if request.method == 'POST':
        stub.seq += 1; return route.fulfill(status=200, content_type='application/json', body=json.dumps([dict(r, server_seq=stub.seq + i) for i, r in enumerate(json.loads(request.post_data or '[]'))]))
    route.fulfill(status=200, content_type='application/json', body='[]')
stub.seq = 1000
def device(b, H, clock=False, configured=False):
    ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}))
    if configured:
        ctx.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};"); ctx.route(f'{STUB}/**', stub)
    pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e, _p=pg: pg.errs.append(perr(e, _p))); PAGES.append(pg)
    if clock: pg.clock.install()
    boot(pg, H); return ctx, pg
hours = lambda a, b: (time.mktime(time.strptime(b[:19], '%Y-%m-%dT%H:%M:%S')) - time.mktime(time.strptime(a[:19], '%Y-%m-%dT%H:%M:%S'))) / 3600

srvp, H = serve(); ROOT = H.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ═══ at boot ═══
        ca, A = device(b, H); time.sleep(1.5); s0 = snaps(A)
        check('[constants] the layer states the interval and the two numbers kept: 12 hours, 7 interval, 3 pre-import', s0['hours'] == 12 and s0['keep'] == 7 and s0['keepPre'] == 3, (s0['hours'], s0['keep'], s0['keepPre']))
        check('[boot · empty] an empty register is not snapshotted', s0['n'] == 0 and s0['last'] is None, s0)
        run(A, "async (db) => { await db.saveBird(db.newBird({ name: 'أول', sex: 'cock' })); await db.saveBird(db.newBird({ name: 'ثانٍ', sex: 'hen' })); }")
        boot(A, H); s1 = settled(A, 1)
        check('[boot · M-boot fails here] a register with birds and no snapshot yet: the boot takes ONE, an automatic one, holding both birds', s1['n'] == 1 and s1['kinds'] == ['auto-backup'] and s1['birds'] == [2], s1)
        check('[boot] …and «آخر نسخة تلقائية» is recorded as that snapshot', s1['n'] == 1 and s1['last'] == s1['ids'][0], s1)
        boot(A, H); time.sleep(2); s2 = snaps(A)
        check('[boot] a second boot straight afterwards takes none — the interval has not passed', s2['ids'] == s1['ids'], s2)
        run(A, "async (db, h) => { await db.setSetting('lastAutoBackup', new Date(Date.now() - h * 3600 * 1000).toISOString()); }", 11)
        boot(A, H); time.sleep(2); s3 = snaps(A)
        check('[boot] the last snapshot 11 hours old: still none', s3['ids'] == s1['ids'], s3)
        run(A, "async (db, h) => { await db.setSetting('lastAutoBackup', new Date(Date.now() - h * 3600 * 1000).toISOString()); }", 13)
        boot(A, H); s4 = settled(A, 2)
        check('[boot · M-boot fails here] the last snapshot 13 hours old: the boot takes a new one', s4['n'] == 2 and s4['last'] == s4['ids'][-1] and s4['ids'][0] == s1['ids'][0], s4)

        # ═══ the number kept ═══
        run(A, "async (db) => { for (let i = 0; i < 7; i++) { await new Promise(r => setTimeout(r, 15)); await db.autoBackup(); } }"); s5 = snaps(A)
        check('[kept] nine taken in all: SEVEN remain, and they are the seven newest', s5['n'] == 7 and len(s4['ids']) == 2 and not set(s4['ids']) & set(s5['ids']) and s5['last'] == s5['ids'][-1], s5)   # non-raising: under M-boot there are no earlier two

        # ═══ the screen's wording is the layer's constants, and its list is what is stored ═══
        A.goto(ROOT + 'tools/restore/', wait_until='load'); A.wait_for_selector('[data-testid=snap-list]', timeout=15000)
        note = digits(A.locator('[data-testid=snap-list] ~ p').last.inner_text()); rows = A.locator('[data-testid=snap-row]').count()
        check('[screen · wording] the note says what is true: on opening or while open once 12 hours have passed; 7 interval kept; 3 pre-import kept',
              'عند فتح التطبيق' in note and 'وهو مفتوح' in note and 'كلما مضت 12 ساعة' in note and 'آخر 7 نسخ تلقائية' in note and 'بآخر 3 نسخ' in note, note)
        typo = A.evaluate(SCAN)
        check('[screen] …and lists the seven that are stored', rows == 7, rows)
        A.goto(ROOT + 'tools/', wait_until='load'); A.wait_for_selector('[data-testid=tools-list]', timeout=15000); A.wait_for_timeout(800)
        val = digits(A.locator('[data-row=restore] [data-testid=row-value]').inner_text())
        check('[screen] the الأدوات row says «7 متاحة»', val.strip() == '7 متاحة', val)
        foot = digits(A.locator('[data-testid=tools-list]').inner_text())
        check('[screen · wording] the الأدوات list carries the same note, with the same three numbers', 'كلما مضت 12 ساعة' in foot and 'آخر 7 نسخ تلقائية' in foot and 'بآخر 3 نسخ' in foot, foot[-260:])
        typo += A.evaluate(SCAN)
        check('[typography · M-face fails here] the snapshot rows, «آخر نسخة تلقائية» and the note, where they are drawn, are in a face that has Arabic, and unspaced', not typo, [(x['why'], x['face'], x['text']) for x in typo][:3])
        ca.close()

        # ═══ RULED 2026-11-16 — two kinds, two limits, neither evicts the other ═══
        ck, K = device(b, H)
        run(K, "async (db) => { await db.saveBird(db.newBird({ name: 'ثابت', sex: 'cock' })); await db.setSetting('lastAutoBackup', new Date().toISOString()); }")
        REPLACE = "async (db) => { await new Promise(r => setTimeout(r, 15)); await db.importAll(await db.exportAll({ includeMedia: false }), 'replace'); return (await db.idbGetAll('backups')).map(x => x.id).filter(i => i.startsWith('pre-import-')).sort().pop(); }"
        taken_pre = [run(K, REPLACE) for _ in range(7)]; k1 = snaps(K)
        check('[kinds · M-kinds fails here] seven replaces: the THREE newest pre-import snapshots are kept, and they are the last three taken', k1['pre'] == taken_pre[-3:] and k1['auto'] == [], k1['ids'])
        taken_auto = [run(K, "async (db) => { await new Promise(r => setTimeout(r, 15)); return db.autoBackup(); }") for _ in range(9)]; k2 = snaps(K)
        check('[kinds · M-kinds fails here] THE RULED PROOF — seven replaces, then nine interval snapshots: 7 interval and 3 pre-import remain', len(k2['auto']) == 7 and len(k2['pre']) == 3, {'auto': len(k2['auto']), 'pre': len(k2['pre'])})
        check('[kinds] …the seven newest interval ones, and the same three pre-import ones — neither kind evicted the other', k2['auto'] == taken_auto[-7:] and k2['pre'] == taken_pre[-3:], k2['ids'])
        last_pre = run(K, REPLACE); k3 = snaps(K)
        check('[kinds] one more replace: still 7 interval, untouched; still 3 pre-import, the oldest of them gone', k3['auto'] == taken_auto[-7:] and k3['pre'] == taken_pre[-2:] + [last_pre], k3['ids'])
        ck.close()

        # ═══ RULED 2026-11-16 — the list is newest first, a pre-import snapshot at its moment ═══
        cs, S = device(b, H)
        run(S, """async (db) => { await db.saveBird(db.newBird({ name: 'مرتّب', sex: 'hen' })); await db.setSetting('lastAutoBackup', new Date().toISOString());
            const p = await db.exportAll({ includeMedia: false }); p.kind = 'auto-backup';
            for (const id of ['2026-03-10T08:00:00.000Z', 'pre-import-2026-03-11T09:00:00.000Z', '2026-03-12T07:00:00.000Z', 'pre-import-2026-03-13T06:00:00.000Z']) await db.idbPut('backups', { id, payload: p }); }""")
        WANT = ['pre-import-2026-03-13T06:00:00.000Z', '2026-03-12T07:00:00.000Z', 'pre-import-2026-03-11T09:00:00.000Z', '2026-03-10T08:00:00.000Z']
        o1 = snaps(S)
        check('[order · M-order fails here] the layer lists the snapshots NEWEST FIRST, each pre-import one at its own moment among the interval ones', o1['listed'] == WANT, o1['listed'])
        S.goto(ROOT + 'tools/restore/', wait_until='load'); S.wait_for_selector('[data-testid=snap-list]', timeout=15000); S.wait_for_timeout(600)
        shown = S.locator('[data-testid=snap-row]').evaluate_all('els => els.map(e => e.dataset.id)')
        dates = S.locator('[data-testid=snap-row] strong').evaluate_all('els => els.map(e => e.innerText.trim())')
        check('[order · M-order fails here] …and the restore screen draws them in that order', shown == WANT, shown)
        check('[order] …four different moments, drawn as four different dates — a pre-import row shows its moment, not its key', len(set(dates)) == 4 and not any('pre-import' in d or 'Invalid' in d for d in dates), dates)
        last = S.locator('[data-testid=last-snapshot]').inner_text()
        check('[last · M-last fails here] «آخر نسخة تلقائية» names the newest INTERVAL snapshot — the second row — though a pre-import one is newer', len(dates) == 4 and dates[1] in last and dates[0] not in last, (last, dates[:2]))
        typo = S.evaluate(SCAN)
        check('[typography · M-face fails here] the four dated rows are drawn in a face that has Arabic', not typo, [(x['why'], x['face'], x['text']) for x in typo][:3])
        cs.close()

        # ═══ RULED 2026-11-16 — «{n} متاحة» and the list are re-read on a layer change ═══
        cn, N = device(b, H)
        run(N, "async (db) => { await db.saveBird(db.newBird({ name: 'عدّ', sex: 'cock' })); }")
        N.goto(ROOT + 'tools/', wait_until='load'); N.wait_for_selector('[data-testid=tools-list]', timeout=15000); n1 = settled(N, 1); N.wait_for_timeout(800)
        val = digits(N.locator('[data-row=restore] [data-testid=row-value]').inner_text()).strip()
        check('[count · M-count fails here] الأدوات opened as the boot that takes the first snapshot: the row says «1 متاحة», as stored', n1['n'] == 1 and val == '1 متاحة', (val, n1['n']))
        run(N, "async (db) => { await db.setSetting('lastAutoBackup', new Date(Date.now() - 13 * 3600 * 1000).toISOString()); }")
        N.goto(ROOT + 'tools/restore/', wait_until='load'); N.wait_for_selector('[data-testid=last-snapshot]', timeout=15000); n2 = settled(N, 2); N.wait_for_timeout(800)
        rows = N.locator('[data-testid=snap-row]').count()
        check('[count · M-count fails here] استرجاع opened as the boot that takes a second one: the list shows both', n2['n'] == 2 and rows == 2, (rows, n2['n']))
        cn.close()

        # ═══ RULED 2026-11-16 — no snapshot at the sign-in gate; the collision CLEAR leaves none behind ═══
        cg, G = device(b, H, configured=True)
        run(G, "async (db) => { await db.saveBird(db.newBird({ name: 'أ-1', sex: 'cock' })); await db.saveBird(db.newBird({ name: 'أ-2', sex: 'hen' })); }")
        boot(G, H); time.sleep(2); g1 = snaps(G)
        check('[gate · M-gate fails here] a configured build with NO session and two birds — the sign-in gate, where a collision stops a device: the boot takes no snapshot', g1['n'] == 0 and g1['last'] is None, g1)
        G.goto(ROOT + 'sign-in/', wait_until='load'); G.wait_for_selector('[data-testid=signin-form]', timeout=15000); time.sleep(2); g2 = snaps(G)
        check('[gate · M-gate fails here] …nor does opening the sign-in screen itself', g2['n'] == 0, g2)
        boot(G, H); run(G, "async (db) => { await db.signIn('a@zajil.test', 'pw'); await db.syncNow(); }"); boot(G, H); g3 = settled(G, 1)
        check('[gate] signed in, the same device: the next boot takes one, holding both birds', g3['n'] == 1 and g3['birds'] == [2], g3)
        run(G, "async (db) => { await new Promise(r => setTimeout(r, 15)); await db.autoBackup(); await db.importAll(await db.exportAll({ includeMedia: false }), 'replace'); await db.syncNow(); await db.signOut(); }")
        g4 = snaps(G)
        check("[CLEAR · setup] account A's device, signed out: two interval snapshots and one pre-import snapshot stored, «آخر نسخة» recorded", len(g4['auto']) == 2 and len(g4['pre']) == 1 and g4['last'], g4)
        G.goto(ROOT + 'sign-in/', wait_until='load'); G.wait_for_selector('[data-testid=signin-form]', timeout=15000)
        G.fill('[data-testid=f-email]', 'b@zajil.test'); G.fill('[data-testid=f-password]', 'pw'); G.click('[data-testid=signin-submit]'); G.wait_for_selector('[data-testid=dialog]', timeout=15000); G.wait_for_timeout(1500)
        g5 = snaps(G)
        check('[gate] STOPPED at the collision: the snapshots store is exactly as it was — nothing taken, nothing removed', g5['ids'] == g4['ids'] and g5['last'] == g4['last'], g5)
        G.click('[data-testid=dialog-confirm]'); G.wait_for_timeout(500); G.click('[data-testid=dialog-confirm]'); G.wait_for_url(re.compile(r'/tools/$'), timeout=20000); G.wait_for_timeout(1500)
        g6 = snaps(G); who = run(G, "(db) => db.authState().email")
        check("[CLEAR] account B chose CLEAR: NONE of A's snapshots is left on the device, of either kind, and «آخر نسخة» is gone with them", who == 'b@zajil.test' and g6['n'] == 0 and g6['last'] is None, (who, g6))
        G.goto(ROOT + 'tools/restore/', wait_until='load'); G.wait_for_selector('[data-testid=last-snapshot]', timeout=15000); G.wait_for_timeout(800)
        check('[CLEAR] …so under account B the restore screen offers nothing to restore', G.locator('[data-testid=snap-row]').count() == 0 and 'لا نسخ تلقائية بعد' in G.locator('[data-testid=last-snapshot]').inner_text(), G.locator('[data-testid=last-snapshot]').inner_text())
        cg.close()

        # ═══ after the promised interval, the page left open — the browser's clock is driven ═══
        cc, C = device(b, H, clock=True)
        run(C, "async (db) => { await db.saveBird(db.newBird({ name: 'ساهر', sex: 'cock' })); }")
        boot(C, H); c1 = settled(C, 1)
        check('[interval · setup] booted with one bird: one snapshot', c1['n'] == 1, c1)
        C.clock.fast_forward('11:59:00'); time.sleep(1.5); c2 = snaps(C)
        check('[interval] 11 h 59 min later, the page still open: no second snapshot yet', c2['ids'] == c1['ids'], c2)
        C.clock.fast_forward('00:02:00'); c3 = settled(C, 2)
        check('[interval · M-interval fails here] 12 h 01 min after the boot, the page still open: a second snapshot EXISTS', c3['n'] == 2 and c3['kinds'] == ['auto-backup'] * 2 and c3['last'] == c3['ids'][-1], c3)
        check('[interval] …stamped twelve hours after the first', c3['n'] == 2 and 11.9 < hours(c3['ids'][0], c3['ids'][1]) < 12.1, c3['ids'])
        run(C, "async (db) => { for (const b of [...db.state.birds.values()]) await db.deleteBird(b.id); }")
        C.clock.fast_forward('12:00:30'); time.sleep(1.5); c4 = snaps(C)
        check('[interval · empty] the register emptied, another interval passes: no snapshot of nothing', c4['ids'] == c3['ids'], c4)
        cc.close()

        check(f'zero page errors across {len(PAGES)} devices', not any(p.errs for p in PAGES), [e[:160] for p in PAGES for e in p.errs][:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
