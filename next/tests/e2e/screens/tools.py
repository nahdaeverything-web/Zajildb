#!/usr/bin/env python3
"""Tools & settings (/tools) — every state tools-v1 designs, the two rulings from the
Phase 4 order, and four intent lists re-authored against the real screen:

  · sync_ui           #23 #25 #26 #32 #34–#40 (the card's signed-out / unconfigured /
                      signed-in states, sign-out keeping the data)
  · version_display   #2 #3 #9 #10 (the About row renders, is never blank, and falls
                      back to «غير معروف» when no service worker answers)
  · picker_duplicates #8–10 (the finder lists a clone, says what each copy is linked
                      to, and the group disappears once the surplus copy is deleted)
  · convergence       the sync-complete duplicate notice is asserted in its own suite;
                      here the finder it points AT is what is proved.

RULING 1 rewrites sync_ui #23/#25: the inline email/password form inside this card is
superseded by /sign-in, so what the signed-out card must offer is the explanation line
plus a «تسجيل الدخول» button that navigates there. #24 (a masked password field) moved
with the form and is asserted in the sign-in suite.

Binds to data-testid only. Provisions its own server (R6)."""
import base64
import io
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
sys.path.insert(0, HERE)
from _serve import serve                      # noqa: E402
from _layout import check_clearance, check_toast_clear, wait_toasts_clear   # noqa: E402

FID = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'fidelity', 'tools')); os.makedirs(FID, exist_ok=True)
passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness.html', '')
TOOLS = f'{ROOT}tools.html'
STUB = 'https://stub.example.test'
# a 1×1 PNG — the smallest real image, so the logo path exercises a genuine Blob
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')


def shots(pg, name, widths=(430, 900, 1400)):
    for w in widths:
        pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(250)
        pg.screenshot(path=f'{FID}/{name}-{w}.png', full_page=True)
    pg.set_viewport_size({'width': 430, 'height': 900}); pg.wait_for_timeout(150)


def run(pg, fn, arg=None):
    return pg.evaluate("async (a) => { const db = await window.__zajilDb; return (%s)(db, a); }" % fn, arg)


# ── the stub project: enough for signIn() and a sync cycle to be answered ────────
srv_state = {'rows': {}, 'seq': 0, 'token_mode': 'ok'}


def handler(route, request):
    url = request.url
    if '/auth/v1/token' in url:
        if srv_state['token_mode'] == 'reject':
            route.fulfill(status=400, content_type='application/json',
                          body='{"error":"invalid_grant","error_description":"Invalid login credentials"}')
            return
        route.fulfill(status=200, content_type='application/json', body=json.dumps({
            'access_token': 'ACCESS-1', 'refresh_token': 'REFRESH-1', 'token_type': 'bearer',
            'expires_in': 3600, 'user': {'id': 'user-uuid-1', 'email': 'spike-a@zajil.test'}}))
        return
    if request.method == 'POST':
        body = json.loads(request.post_data or '[]')
        out = []
        for r in body:
            srv_state['seq'] += 1
            row = dict(r); row['server_seq'] = srv_state['seq']; row['owner'] = 'user-uuid-1'
            srv_state['rows'][(r['store'], r['record_id'])] = row
            out.append(row)
        route.fulfill(status=200, content_type='application/json', body=json.dumps(out))
        return
    route.fulfill(status=200, content_type='application/json', body='[]')


try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ══ A. THE SHIPPED BUILD — no project configured ══════════════════════
        ctx = b.new_context(viewport={'width': 430, 'height': 900})
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(TOOLS, wait_until='load'); pg.wait_for_selector('[data-testid=card-settings]', timeout=8000)

        # ── the spec's own shape: nine cards in three groups, with the index ──
        check('nine cards in the spec\'s three groups',
              pg.locator('[data-testid=group]').count() == 3
              and pg.locator('[data-testid^=card-]').count() == 9,
              f"{pg.locator('[data-testid=group]').count()} groups / {pg.locator('[data-testid^=card-]').count()} cards")
        idx = [' '.join(x.split()) for x in pg.locator('[data-testid=index-link]').all_inner_texts()]
        check('…each group in its designed order, each counting its own cards',
              idx == ['إعدادات 3', 'بيانات 3', 'متقدّم 3'], str(idx))
        check('…and the index jumps to each of them',
              [a.get_attribute('href') for a in pg.locator('[data-testid=index-link]').all()] ==
              ['#g-settings', '#g-data', '#g-adv'])

        # ── [sync_ui #32] the unconfigured state ──
        body = pg.inner_text('body')
        check('[sync_ui #32] an unconfigured build explains itself and offers no pointless form',
              pg.locator('[data-testid=sync-unconfigured]').count() == 1
              and 'غير مهيأة' in pg.locator('[data-testid=sync-unconfigured]').inner_text()
              and pg.locator('[data-testid=card-sync] input').count() == 0,
              pg.locator('[data-testid=sync-unconfigured]').inner_text())
        check('…and carries NO sign-in button — there is nothing on this device to sign into',
              pg.locator('[data-testid=go-signin]').count() == 0)
        check('[sync_ui #26] NO way to create an account anywhere on the screen — invite-only, permanently',
              not any(w in body for w in ['إنشاء حساب', 'Create account', 'Sign up', 'تسجيل جديد']),
              'a create-account control would be a dead end that looks like a feature')

        # ── [version_display #2 #3 #9 #10] the About row ──
        ver = pg.locator('[data-testid=about-version]').inner_text().strip()
        check('[version_display #2] the About card renders a version row', pg.locator('[data-testid=about-version]').count() == 1)
        check('[version_display #3 #9] …that is never blank, even with no service worker', ver != '', repr(ver))
        check('[version_display #10] …showing the «غير معروف» fallback rather than a made-up number',
              ver == 'غير معروف', repr(ver))
        check('[version_display #8] …and the crumb reads the same source, never a second constant',
              'غير معروف' in pg.locator('[data-testid=crumb]').inner_text(),
              pg.locator('[data-testid=crumb]').inner_text())
        shots(pg, 'unconfigured')

        # ── 1. display settings: every control writes through setSetting ──
        pg.locator('[data-testid=set-numerals] [data-testid=seg-btn][data-value=eastern]').click(); pg.wait_for_timeout(350)
        check('the numerals segment writes through setSetting',
              run(pg, "(db) => db.state.settings.numerals") == 'eastern')
        check('…and the WHOLE screen answers in eastern digits at once — the setting is applied, not just stored',
              '٣' in pg.locator('[data-testid=index-link]').first.inner_text(),
              ' '.join(pg.locator('[data-testid=index-link]').first.inner_text().split()))
        pg.locator('[data-testid=set-numerals] [data-testid=seg-btn][data-value=western]').click(); pg.wait_for_timeout(300)
        pg.locator('[data-testid=set-dates] [data-testid=seg-btn][data-value=hijri]').click(); pg.wait_for_timeout(300)
        check('the dates segment writes through setSetting', run(pg, "(db) => db.state.settings.dates") == 'hijri')
        pg.locator('[data-testid=set-dates] [data-testid=seg-btn][data-value=both]').click(); pg.wait_for_timeout(300)
        check('the language segment offers both languages and marks the current one',
              pg.locator('[data-testid=set-lang] [data-testid=seg-btn]').count() == 2
              and pg.locator('[data-testid=set-lang] [data-testid=seg-btn][data-value=ar]').get_attribute('aria-pressed') == 'true')

        for _ in range(9):
            pg.click('[data-testid=coi-more]'); pg.wait_for_timeout(60)
        pg.wait_for_timeout(300)
        check('the COI stepper stops at the engine\'s ceiling of 15 — a depth it cannot honour is not offered',
              run(pg, "(db) => +db.state.settings.coiDepth") == 15
              and pg.locator('[data-testid=coi-input]').input_value() == '15',
              pg.locator('[data-testid=coi-input]').input_value())
        for _ in range(14):
            pg.click('[data-testid=coi-less]'); pg.wait_for_timeout(50)
        pg.wait_for_timeout(300)
        check('…and at the floor of 3', run(pg, "(db) => +db.state.settings.coiDepth") == 3)
        pg.fill('[data-testid=coi-input]', '10'); pg.wait_for_timeout(350)
        check('…and a typed value is saved as typed', run(pg, "(db) => +db.state.settings.coiDepth") == 10)

        HC_BOX = '[data-testid=hc-input] + span'   # the drawn box, which is what a finger lands on
        pg.click(HC_BOX); pg.wait_for_timeout(400)
        check('high contrast is stored as a setting, not held in the view',
              run(pg, "(db) => db.state.settings.highContrast") is True)
        check('…and is APPLIED to the document, as vanilla applySettings() does',
              pg.evaluate("() => document.documentElement.classList.contains('high-contrast')") is True)
        pg.click(HC_BOX); pg.wait_for_timeout(400)
        check('…and turning it off takes it back off the document',
              run(pg, "(db) => db.state.settings.highContrast") is False
              and pg.evaluate("() => document.documentElement.classList.contains('high-contrast')") is False)

        # ── 3. [RULING 2] the loft card carries the certificate's branding fields ──
        pg.fill('[data-testid=ln]', 'لوفت الزاجل')
        pg.fill('[data-testid=lc]', 'عمّان')
        pg.click('[data-testid=lb]'); pg.type('[data-testid=lb]', 'سمير الهنداوي', delay=40)
        check('a text field keeps the caret while it is typed into (the card\'s fields are not remounted per keystroke)',
              pg.locator('[data-testid=lb]').input_value() == 'سمير الهنداوي'
              and pg.evaluate("() => document.activeElement?.getAttribute('data-testid')") == 'lb',
              pg.locator('[data-testid=lb]').input_value())
        pg.fill('[data-testid=lp]', '+962790000000')
        pg.fill('[data-testid=lw]', 'https://zajil.example')
        pg.set_input_files('[data-testid=logo-input]', files=[{'name': 'logo.png', 'mimeType': 'image/png', 'buffer': PNG}])
        pg.wait_for_timeout(600)
        check('[RULING 2] a chosen logo is stored and the card says so, without pretending it is anywhere else',
              pg.locator('[data-testid=logo-state]').inner_text().strip() == 'شعار محفوظ على هذا الجهاز',
              pg.locator('[data-testid=logo-state]').inner_text())
        pg.click('[data-testid=loft-save]'); pg.wait_for_timeout(700)
        saved = run(pg, """(db) => { const l = db.currentLoft();
            return { name: l.name, location: l.location, breederName: l.breederName, phone: l.phone,
                     website: l.website, logo: !!l.logoMediaId }; }""")
        check('[RULING 2] breeder name, phone, website and the logo id round-trip through Lofts.save',
              saved == {'name': 'لوفت الزاجل', 'location': 'عمّان', 'breederName': 'سمير الهنداوي',
                        'phone': '+962790000000', 'website': 'https://zajil.example', 'logo': True},
              str(saved))
        media = run(pg, """async (db) => { const l = db.currentLoft();
            const all = await db.mediaForBird(l.id);
            const m = all.find(x => x.id === l.logoMediaId);
            const ops = (await db.listOps()).filter(o => o.store === 'media' && o.recordId === l.logoMediaId);
            return { hasBlob: !!(m && m.blob && m.blob.size > 0), subtype: m && m.subtype,
                     ops: ops.length, opHasBlob: ops.some(o => o.record && 'blob' in o.record) }; }""")
        check('[RULING 2] the logo is device-local media: real bytes in the media store, and the op log carries only its metadata',
              media['hasBlob'] and media['subtype'] == 'logo' and media['ops'] >= 1 and media['opHasBlob'] is False,
              str(media))
        wait_toasts_clear(pg)

        # ── 5. the teaching data merges, never destroys ──
        before = run(pg, "(db) => db.allBirds().length")
        pg.click('[data-testid=load-sample]'); pg.wait_for_timeout(2500)
        after = run(pg, "(db) => db.allBirds().length")
        check('the small teaching loft loads', after > before, f'{before} -> {after}')
        check('…and says how many birds arrived',
              pg.locator('[data-testid=toast]').count() >= 1
              and str(after - before) in pg.locator('[data-testid=toast]').last.inner_text(),
              pg.locator('[data-testid=toast]').last.inner_text().replace('\n', ' ') if pg.locator('[data-testid=toast]').count() else '(no toast)')
        wait_toasts_clear(pg)
        pg.click('[data-testid=load-sample]'); pg.wait_for_timeout(2500)
        check('…and loading it twice MERGES rather than doubling the loft',
              run(pg, "(db) => db.allBirds().length") == after,
              f"{after} -> {run(pg, '(db) => db.allBirds().length')}")
        wait_toasts_clear(pg)

        # ── 4. [picker_duplicates #8–10] the duplicate-ring finder ──
        check('with a clean loft the finder says so, rather than showing an empty list',
              pg.locator('[data-testid=dup-clean]').count() == 1 and pg.locator('[data-testid=dup-group]').count() == 0,
              pg.locator('[data-testid=dup-clean]').inner_text() if pg.locator('[data-testid=dup-clean]').count() else '')
        clone = run(pg, """async (db) => {
            // a real duplicate: the same ring on a second record. saveBird refuses it
            // unless the warning is acknowledged, which is the write boundary working.
            const src = db.allBirds().find(b => (b.rings || []).length && db.allBirds().some(x => x.sireId === b.id || x.damId === b.id))
                     || db.allBirds().find(b => (b.rings || []).length);
            const copy = await db.saveBird(db.newBird({ name: src.name + ' (نسخة)', sex: src.sex,
                rings: JSON.parse(JSON.stringify(src.rings)) }), { allowWarnings: true });
            return { src: src.id, copy: copy.id, ring: src.rings[0].raw }; }""")
        pg.wait_for_timeout(800)
        check('[picker_duplicates #8] the finder lists the clone',
              pg.locator('[data-testid=dup-group]').count() == 1
              and pg.locator('[data-testid=dup-group] [data-testid=dup-copy]').count() == 2,
              f"{pg.locator('[data-testid=dup-group]').count()} group(s)")
        check('…labelled with the ring the two records share, and how many copies carry it',
              clone['ring'] in pg.locator('[data-testid=dup-group]').inner_text()
              and '2 نسخة' in pg.locator('[data-testid=dup-group]').inner_text(),
              pg.locator('[data-testid=dup-group]').inner_text().replace('\n', ' ')[:120])
        links = pg.locator('[data-testid=dup-links]').all_inner_texts()
        check('[picker_duplicates #9] every copy states what it is linked to — the fancier deletes the empty one, not the wired one',
              len(links) == 2 and any('بدون روابط معروفة' in x for x in links)
              and any('مرتبط' in x for x in links),
              str([x.replace('\n', ' ') for x in links]))
        expect_links = run(pg, """(db, a) => { const b = db.getBird(a.src);
            const kids = db.allBirds().filter(x => x.sireId === b.id || x.damId === b.id).length;
            const pairs = [...db.state.pairs.values()].filter(p => p.sireId === b.id || p.damId === b.id).length;
            const races = [...db.state.raceResults.values()].filter(r => r.birdId === b.id).length;
            const health = [...db.state.healthEvents.values()].filter(h => h.birdId === b.id).length;
            return kids + pairs + races + health; }""", clone)
        check('…with the count computed from the record, not guessed',
              expect_links > 0 and any(str(expect_links) in x for x in links),
              f'{expect_links} links expected in {[x for x in links]}')
        shots(pg, 'duplicates')
        pg.locator('[data-testid=dup-copy]', has=pg.locator('text=بدون روابط معروفة')).locator('[data-testid=dup-delete]').click()
        pg.wait_for_selector('[data-testid=dialog]', timeout=5000)
        check('…and deleting one asks first, naming the record',
              clone['ring'] in pg.locator('[data-testid=dialog]').inner_text()
              or 'نسخة' in pg.locator('[data-testid=dialog]').inner_text(),
              pg.locator('[data-testid=dialog]').inner_text().replace('\n', ' ')[:100])
        pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(1200)
        check('[picker_duplicates #10] the surplus copy deleted → no duplicates remain',
              pg.locator('[data-testid=dup-group]').count() == 0 and pg.locator('[data-testid=dup-clean]').count() == 1)
        check('…and the linked record is untouched', run(pg, "(db, a) => !!db.getBird(a.src)", clone) is True)
        wait_toasts_clear(pg)

        # ── 6. backup: export, import, and restoring a snapshot ──
        with pg.expect_download() as dl:
            pg.click('[data-testid=export-all]')
        name = dl.value.suggested_filename
        check('«تصدير الكل» downloads a dated JSON export', name.startswith('zajil-export-') and name.endswith('.json'), name)
        pg.wait_for_timeout(500)
        check('…and the card stops saying «لم يتم التصدير بعد»',
              pg.locator('[data-testid=last-export]').inner_text().strip() != 'لم يتم التصدير بعد',
              pg.locator('[data-testid=last-export]').inner_text())
        wait_toasts_clear(pg)
        check('the import button stays disabled until a file is chosen',
              pg.locator('[data-testid=import-file]').is_disabled()
              and pg.locator('[data-testid=file-name]').inner_text().strip() == 'لم يُختر ملف — .json',
              pg.locator('[data-testid=file-name]').inner_text())
        payload = json.loads(open(dl.value.path(), encoding='utf-8').read())

        def pick(obj, name='zajil-export.json'):
            pg.set_input_files('[data-testid=file-input]', files=[{'name': name, 'mimeType': 'application/json',
                                                                  'buffer': json.dumps(obj).encode('utf-8')}])
            pg.wait_for_timeout(400)

        pick(payload)
        check('…and names the chosen file once it is picked',
              pg.locator('[data-testid=file-name]').inner_text().strip() == 'zajil-export.json'
              and pg.locator('[data-testid=import-file]').is_enabled())
        n_before = run(pg, "(db) => db.allBirds().length")
        pg.click('[data-testid=import-file]'); pg.wait_for_timeout(2500)
        check('importing the app\'s own export in «دمج» mode changes nothing — the same records, not doubled',
              run(pg, "(db) => db.allBirds().length") == n_before,
              f"{n_before} -> {run(pg, '(db) => db.allBirds().length')}")
        check('…and reports the honest zero rather than the size of the file',
              pg.locator('[data-testid=toast]').count() >= 1
              and 'تم الاستيراد: 0' in pg.locator('[data-testid=toast]').last.inner_text(),
              pg.locator('[data-testid=toast]').last.inner_text().replace('\n', ' ') if pg.locator('[data-testid=toast]').count() else '(none)')
        wait_toasts_clear(pg)

        # a payload that really does carry something new — the count must follow the data
        newcomer = dict(payload['birds'][0]); newcomer['id'] = 'imported-newcomer'; newcomer['name'] = 'وافد'
        newcomer['rings'] = []; newcomer['sireId'] = None; newcomer['damId'] = None
        pick({**payload, 'birds': [newcomer]}, 'one-more.json')
        pg.click('[data-testid=import-file]'); pg.wait_for_timeout(2500)
        check('…while a payload with one new bird lands exactly one',
              run(pg, "(db) => db.allBirds().length") == n_before + 1
              and 'تم الاستيراد: 1' in pg.locator('[data-testid=toast]').last.inner_text(),
              pg.locator('[data-testid=toast]').last.inner_text().replace('\n', ' ') if pg.locator('[data-testid=toast]').count() else '(none)')
        wait_toasts_clear(pg)
        run(pg, "async (db) => { await db.deleteBird('imported-newcomer'); }")
        pg.wait_for_timeout(400)

        pick(payload)
        pg.select_option('[data-testid=import-mode]', 'replace'); pg.wait_for_timeout(200)
        pg.click('[data-testid=import-file]'); pg.wait_for_selector('[data-testid=dialog]', timeout=5000)
        check('«استبدال» asks before it destroys, in the danger voice',
              pg.locator('[data-testid=dialog-confirm]').count() == 1
              and 'استبدال' in pg.locator('[data-testid=dialog]').inner_text(),
              pg.locator('[data-testid=dialog]').inner_text().replace('\n', ' ')[:100])
        pg.click('[data-testid=dialog-cancel]'); pg.wait_for_timeout(400)
        check('…and cancelling leaves the loft alone', run(pg, "(db) => db.allBirds().length") == n_before)
        pg.select_option('[data-testid=import-mode]', 'merge'); pg.wait_for_timeout(150)

        # ── 7. the optional scanner ──
        check('the scanner is off by default and says the app is complete without it',
              pg.locator('[data-testid=scan-off]').count() == 1
              and 'يعمل دون اتصال' in pg.locator('[data-testid=scan-off]').inner_text(),
              pg.locator('[data-testid=scan-off]').inner_text())
        pg.fill('[data-testid=scan-url]', 'https://vision.example.org')
        pg.locator('[data-testid=scan-url]').blur(); pg.wait_for_timeout(400)
        check('…and a server address is saved through setSetting, not held in the view',
              run(pg, "(db) => db.state.settings.scanServerUrl") == 'https://vision.example.org')
        check('…after which the "not configured" note is gone', pg.locator('[data-testid=scan-off]').count() == 0)
        pg.fill('[data-testid=scan-url]', ''); pg.locator('[data-testid=scan-url]').blur(); pg.wait_for_timeout(400)

        # ── 9. the developer panel, collapsed, running the COPIED engine suite ──
        check('the developer panel is collapsed until a developer opens it',
              pg.locator('[data-testid=card-dev]').get_attribute('open') is None
              and pg.locator('[data-testid=dev-run]').is_visible() is False)
        pg.locator('[data-testid=card-dev] summary').click(); pg.wait_for_timeout(400)
        check('…and opens to three checks', pg.locator('[data-testid=dev-run]').is_visible()
              and pg.locator('[data-testid=dev-roundtrip]').is_visible()
              and pg.locator('[data-testid=dev-integrity]').is_visible())
        pg.click('[data-testid=dev-run]'); pg.wait_for_timeout(4000)
        out = pg.locator('[data-testid=dev-out]').inner_text()
        check('the panel runs the COPIED engine suite in the browser, and it passes',
              'PASS' in out and '✘' not in out and 'فشل' in out,
              out.strip().splitlines()[-1] if out.strip() else '(empty)')
        # the panel imports tests/engine.test.js and nothing else, exactly as vanilla does
        # (js/views/tools.js:447) — so the number it reports is that file's own, not the
        # 33 the node runner reaches across every test file.
        ENGINE_N = len(re.findall(r'^test\(', io.open('tests/engine.test.js', encoding='utf-8').read(), re.M))
        m = re.search(r'(\d+)\s+نجح', out)
        check('…reporting every test in the copied engine suite, not a subset',
              bool(m) and int(m.group(1)) == ENGINE_N and ENGINE_N > 0,
              f"{m.group(0) if m else out[-80:]} vs {ENGINE_N} in tests/engine.test.js")
        pg.click('[data-testid=dev-roundtrip]'); pg.wait_for_timeout(1500)
        check('the export round-trip check passes on real data',
              '✔' in pg.locator('[data-testid=dev-out]').inner_text(),
              pg.locator('[data-testid=dev-out]').inner_text().splitlines()[0])
        pg.click('[data-testid=dev-integrity]'); pg.wait_for_timeout(1500)
        check('the integrity check finds no dangling references in the teaching loft',
              'لا مراجع معلّقة' in pg.locator('[data-testid=dev-out]').inner_text(),
              pg.locator('[data-testid=dev-out]').inner_text().splitlines()[0])
        shots(pg, 'dev-open')
        pg.locator('[data-testid=card-dev] summary').click(); pg.wait_for_timeout(300)

        # ── [ruling C] fixed elements must not hide content ──
        check_clearance(pg, check, 'tools')
        pg.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)"); pg.wait_for_timeout(300)
        pg.click('[data-testid=loft-save]'); pg.wait_for_timeout(500)
        check_toast_clear(pg, check, 'tools')
        wait_toasts_clear(pg)
        shots(pg, 'full')
        check('zero page errors on the unconfigured build', not errs, '; '.join(errs[:2]))

        # ══ B. A CONFIGURED BUILD — the sync card's three remaining states ═════
        ctx2 = b.new_context(viewport={'width': 430, 'height': 900})
        ctx2.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};")
        ctx2.route(f'{STUB}/**', handler)
        sp = ctx2.new_page(); errs2 = []; sp.on('pageerror', lambda e: errs2.append(str(e)))
        sp.goto(TOOLS, wait_until='load'); sp.wait_for_selector('[data-testid=card-sync]', timeout=8000)

        # ── [sync_ui #23 #25, RULING 1] signed out ──
        check('[sync_ui #23 / RULING 1] signed out, the card explains what signing in is FOR',
              sp.locator('[data-testid=sync-signed-out]').count() == 1
              and 'لمزامنة بياناتك' in sp.locator('[data-testid=sync-signed-out]').inner_text(),
              sp.locator('[data-testid=sync-signed-out]').inner_text().replace('\n', ' ')[:100])
        check('[RULING 1] …and offers a button, not an inline form — the form lives at /sign-in now',
              sp.locator('[data-testid=card-sync] input').count() == 0
              and sp.locator('[data-testid=go-signin]').count() == 1)
        check('[sync_ui #25] …reading «تسجيل الدخول»',
              sp.locator('[data-testid=go-signin]').inner_text().strip() == 'تسجيل الدخول')
        check('[sync_ui #26] …with no way to create an account',
              not any(w in sp.inner_text('body') for w in ['إنشاء حساب', 'Create account', 'Sign up', 'تسجيل جديد']))
        shots(sp, 'signed-out')
        sp.click('[data-testid=go-signin]'); sp.wait_for_selector('[data-testid=signin-form]', timeout=8000)
        check('[RULING 1] …and it actually navigates there',
              '/sign-in' in sp.url, sp.url.split('/')[-1])
        sp.go_back(); sp.wait_for_selector('[data-testid=card-sync]', timeout=8000)

        # ── [sync_ui #34 #37] signed in ──
        run(sp, "async (db) => { await db.signIn('spike-a@zajil.test','pw'); await db.syncNow(); }")
        sp.wait_for_selector('[data-testid=sync-signed-in]', timeout=8000)
        check('[sync_ui #34] signing in switches the card to the signed-in state, naming the account',
              sp.locator('[data-testid=sync-account]').inner_text().strip() == 'spike-a@zajil.test')
        check('…showing the last sync time and the pending count the layer reports',
              sp.locator('[data-testid=sync-pending]').inner_text().strip() ==
              str(run(sp, "(db) => db.syncStatus().pending")),
              f"card {sp.locator('[data-testid=sync-pending]').inner_text()} vs layer {run(sp, '(db) => db.syncStatus().pending')}")
        check('[sync_ui #35] …offering «تسجيل الخروج»',
              sp.locator('[data-testid=sign-out]').inner_text().strip() == 'تسجيل الخروج')
        check('[sync_ui #36] …and saying plainly that signing out is not deleting',
              'بياناتك تبقى على هذا الجهاز' in sp.locator('[data-testid=sync-signed-in]').inner_text())
        check('[sync_ui #37] signing in ran a real sync cycle — no second code path for "just signed in"',
              run(sp, "(db) => db.state.settings.lastSyncAt") is not None)
        shots(sp, 'signed-in')

        before_seq = srv_state['seq']
        run(sp, "async (db) => { await db.saveBird(db.newBird({ name: 'survives-sign-out', sex: 'cock' })); }")
        sp.wait_for_timeout(400)
        sp.click('[data-testid=sync-now]'); sp.wait_for_timeout(2500)
        check('«مزامنة الآن» actually runs a cycle', srv_state['seq'] > before_seq, f"{before_seq} -> {srv_state['seq']}")
        wait_toasts_clear(sp)
        sp.click('[data-testid=sync-toggle]'); sp.wait_for_timeout(600)
        check('the toggle turns sync off, and says so',
              run(sp, "(db) => db.state.settings.syncEnabled") is False
              and 'تشغيل المزامنة' in sp.locator('[data-testid=sync-toggle]').inner_text(),
              sp.locator('[data-testid=sync-toggle]').inner_text())
        sp.click('[data-testid=sync-toggle]'); sp.wait_for_timeout(600)

        # ── [sync_ui #38 #39 #40] signing out keeps the data ──
        birds_before = run(sp, "(db) => db.allBirds().length")
        sp.click('[data-testid=sign-out]'); sp.wait_for_selector('[data-testid=dialog]', timeout=5000)
        check('…and sign-out asks first, repeating that the data stays',
              'بياناتك تبقى على هذا الجهاز' in sp.locator('[data-testid=dialog]').inner_text(),
              sp.locator('[data-testid=dialog]').inner_text().replace('\n', ' ')[:100])
        sp.click('[data-testid=dialog-confirm]'); sp.wait_for_selector('[data-testid=sync-signed-out]', timeout=8000)
        after_out = run(sp, """(db) => ({ signedIn: db.authState().signedIn, birds: db.allBirds().length,
            tokens: db.AUTH_SETTING_KEYS.map(k => db.state.settings[k]).filter(Boolean).length })""")
        check('[sync_ui #38] signing out clears every token', after_out['tokens'] == 0, str(after_out))
        check('[sync_ui #39] SIGNING OUT IS NOT DELETING — the birds are still there',
              after_out['birds'] == birds_before, f"{birds_before} -> {after_out['birds']}")
        check('[sync_ui #40] …and the signed-out state comes back, with the button that leads to /sign-in',
              sp.locator('[data-testid=sync-signed-out]').count() == 1
              and sp.locator('[data-testid=go-signin]').count() == 1)

        # a rejected sign-in never reaches THIS card: the message belongs to /sign-in
        srv_state['token_mode'] = 'reject'
        rejected = run(sp, "async (db) => { try { await db.signIn('x@y.test','wrong'); return 'signed-in'; } catch (e) { return e.kind || e.message; } }")
        sp.wait_for_timeout(500)
        check('a rejected sign-in leaves the card signed out and puts no status code on screen',
              rejected != 'signed-in' and sp.locator('[data-testid=sync-signed-out]').count() == 1
              and not any(c.isdigit() for c in sp.locator('[data-testid=card-sync]').inner_text()),
              str(rejected))
        srv_state['token_mode'] = 'ok'

        check_clearance(sp, check, 'tools (configured)')
        check('zero page errors on the configured build', not errs2, '; '.join(errs2[:2]))
        b.close()
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
