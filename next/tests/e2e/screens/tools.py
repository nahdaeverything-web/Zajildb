#!/usr/bin/env python3
"""Tools & settings (/tools) — every state tools-v2 designs, the rulings of 2026-10-03 (the
hybrid shape, the dev panel retained, two strings retained, the teaching row kept), the two
rulings from the Phase 4 order, and the intent lists tools-v1's suite carried, re-authored
against the grouped list:

  · sync_ui           #23 #25 #26 #32 #34–#40 (the account row's signed-out / unconfigured /
                      signed-in states, sign-out keeping the data; the sync sub-screen)
  · version_display   #2 #3 #9 #10 (the version row renders, is never blank, falls back to
                      «غير معروف» when no service worker answers)
  · picker_duplicates #8–10 (the finder, now on /tools/duplicates/, lists a clone, says what
                      each copy is linked to, and the group disappears once the surplus copy
                      is deleted)
  · data_loss #5 #7 · core_flows #9-11 · the pre-launch export/import assertions

And THE PROOF the restructure lost nothing: every control tools-v1 shipped is reached from the
list in at most one tap (open a row, or go to a sub-screen) plus one tap on what opened.

RULING 1 (Phase 4) still rewrites sync_ui #23/#25: the inline email/password form is superseded
by /sign-in, so what the signed-out account row must offer is the explanation line plus a
«تسجيل الدخول» button that navigates there.

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
from _layout import check_clearance, check_toast_clear, wait_toasts_clear, shot   # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _net import Net                          # noqa: E402  THE NET (RULED 2026-10-08): armed beneath the stub, asserted at the end
NET = Net()

FID = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'fidelity', 'tools')); os.makedirs(FID, exist_ok=True)
passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness/', '')
TOOLS = f'{ROOT}tools/'
STUB = 'https://stub.example.test'
# a 1×1 PNG — the smallest real image, so the logo path exercises a genuine Blob
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')


def shots(pg, name, widths=(430, 900, 1400)):
    for w in widths:
        pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(250)
        shot(pg, path=f'{FID}/{name}-{w}.png', full_page=True)
    pg.set_viewport_size({'width': 430, 'height': 900}); pg.wait_for_timeout(150)


def run(pg, fn, arg=None):
    return pg.evaluate("async (a) => { const db = await window.__zajilDb; return (%s)(db, a); }" % fn, arg)


# ── the grouped list: rows open with one tap, sub-screens are one tap away ───────────
def is_open(pg, row):
    return pg.locator(f'[data-row={row}]').get_attribute('open') is not None


def open_row(pg, row):
    if not is_open(pg, row):
        pg.locator(f'[data-row={row}] summary').click(); pg.wait_for_timeout(250)


def close_row(pg, row):
    if is_open(pg, row):
        pg.locator(f'[data-row={row}] summary').click(); pg.wait_for_timeout(200)


def row_value(pg, row):
    return ' '.join(pg.locator(f'[data-row={row}] [data-testid=row-value]').inner_text().split())


def row_help(pg, row):
    return ' '.join(pg.locator(f'[data-row={row}] [data-testid=row-help]').inner_text().split())


def go_list(pg):
    pg.goto(TOOLS, wait_until='load'); pg.wait_for_selector('[data-testid=tools-list]', timeout=8000); pg.wait_for_timeout(300)


def go_sub(pg, row, testid):
    pg.click(f'[data-row={row}]'); pg.wait_for_selector(f'[data-testid={testid}]', timeout=8000); pg.wait_for_timeout(300)


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
        ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}))
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(TOOLS, wait_until='load'); pg.wait_for_selector('[data-testid=tools-list]', timeout=8000)

        # ── the spec's own shape: six sections, each a grouped list of rows ──
        secs = [x.get_attribute('data-section') for x in pg.locator('[data-testid=section]').all()]
        check('the spec\'s six sections, in its order',
              secs == ['account', 'loft', 'data', 'checks', 'settings', 'advanced'], str(secs))
        h2 = [' '.join(x.split()) for x in pg.locator('[data-testid=section] h2').all_inner_texts()]
        check('…titled as the spec titles them', h2 == ['حسابي', 'اللوفت', 'البيانات', 'الفحوصات', 'الإعدادات', 'متقدّم'], str(h2))
        rows = {sec: pg.locator(f'[data-section={sec}] [data-row]').count() for sec in secs}
        check('…each holding its rows — the teaching row kept in البيانات (deviation 4), the integrity check a row of its own',
              rows == {'account': 2, 'loft': 6, 'data': 4, 'checks': 2, 'settings': 5, 'advanced': 3}, str(rows))
        body = pg.inner_text('body')
        check('[item 3] the three NEW rows the order says not to build are NOT built',
              not any(w in body for w in ['الخطة الحالية', 'معرفة مزايا Pro', 'الإشعارات والتذكير']))
        check('[item 2] the breeder row carries the shadda — «المربّي», the existing key',
              'اسم المربّي' in body and 'اسم المربي' not in body)
        hrefs = {r: pg.locator(f'[data-row={r}]').get_attribute('href') for r in ('sync', 'import', 'restore', 'duplicates')}
        check('[hybrid] the four rows the list has no room for NAVIGATE — real routes under /tools/',
              all((hrefs[r] or '').endswith(f'/tools/{r}/') for r in hrefs), str(hrefs))
        check('…and no other row does', pg.locator('[data-row][href]').count() == 4,
              str(pg.locator('[data-row][href]').count()))
        check('the account row opens by default, as the spec draws it; nothing else is open',
              is_open(pg, 'account') and pg.locator('[data-testid=section] details[open]').count() == 1)
        open_row(pg, 'lang'); open_row(pg, 'numerals')
        check('only one row is open at a time inside a section (the spec\'s toggle handler)',
              not is_open(pg, 'lang') and is_open(pg, 'numerals') and is_open(pg, 'account'),
              'the account row stays open — it is in another section')
        close_row(pg, 'numerals')
        check('…and tapping the open row closes it', not is_open(pg, 'numerals'))

        # ── [sync_ui #32] the unconfigured state ──
        check('[sync_ui #32] an unconfigured build explains itself and offers no pointless form',
              pg.locator('[data-testid=sync-unconfigured]').count() == 1
              and 'غير مهيأة' in pg.locator('[data-testid=sync-unconfigured]').inner_text()
              and pg.locator('[data-row=account] input').count() == 0,
              pg.locator('[data-testid=sync-unconfigured]').inner_text().replace('\n', ' ')[:80])
        check('…the account row says so in its value and help',
              row_value(pg, 'account') == 'غير مهيأ' and 'إعداد الخادم غير موجود' in row_help(pg, 'account'),
              f"{row_value(pg, 'account')!r} / {row_help(pg, 'account')!r}")
        check('…and the sync row too', row_value(pg, 'sync') == 'غير مهيأة', row_value(pg, 'sync'))
        check('…and carries NO sign-in button — there is nothing on this device to sign into',
              pg.locator('[data-testid=go-signin]').count() == 0)
        check('[sync_ui #26] NO way to create an account anywhere on the screen — invite-only, permanently',
              not any(w in body for w in ['إنشاء حساب', 'Create account', 'Sign up', 'تسجيل جديد']),
              'a create-account control would be a dead end that looks like a feature')

        # ── [version_display #2 #3 #9 #10] the version row ──
        ver = pg.locator('[data-testid=about-version]').inner_text().strip()
        check('[version_display #2] the version row renders', pg.locator('[data-testid=about-version]').count() == 1)
        check('[version_display #3 #9] …never blank, even with no service worker', ver != '', repr(ver))
        check('[version_display #10] …showing the «غير معروف» fallback rather than a made-up number', ver == 'غير معروف', repr(ver))
        check('[version_display #8] …and the row value IS that reading, never a second constant', row_value(pg, 'version') == ver, row_value(pg, 'version'))
        shots(pg, 'unconfigured')

        # ── 1. display settings: every control writes through setSetting ──
        open_row(pg, 'numerals')
        pg.locator('[data-testid=set-numerals] [data-testid=seg-btn][data-value=eastern]').click(); pg.wait_for_timeout(350)
        check('the numerals segment writes through setSetting', run(pg, "(db) => db.state.settings.numerals") == 'eastern')
        check('…and the WHOLE screen answers in eastern digits at once — the setting is applied, not just stored',
              '١٠' in row_value(pg, 'coi') and '٠١٢٣٤٥٦٧٨٩' in row_value(pg, 'numerals'),
              f"coi={row_value(pg, 'coi')!r} numerals={row_value(pg, 'numerals')!r}")
        pg.locator('[data-testid=set-numerals] [data-testid=seg-btn][data-value=western]').click(); pg.wait_for_timeout(300)
        open_row(pg, 'dates')
        pg.locator('[data-testid=set-dates] [data-testid=seg-btn][data-value=hijri]').click(); pg.wait_for_timeout(300)
        check('the dates segment writes through setSetting, and the row value follows',
              run(pg, "(db) => db.state.settings.dates") == 'hijri' and row_value(pg, 'dates') == 'هجري', row_value(pg, 'dates'))
        pg.locator('[data-testid=set-dates] [data-testid=seg-btn][data-value=both]').click(); pg.wait_for_timeout(300)
        open_row(pg, 'lang')
        check('the language segment offers both languages and marks the current one',
              pg.locator('[data-testid=set-lang] [data-testid=seg-btn]').count() == 2
              and pg.locator('[data-testid=set-lang] [data-testid=seg-btn][data-value=ar]').get_attribute('aria-pressed') == 'true'
              and row_value(pg, 'lang') == 'العربية')

        open_row(pg, 'coi')
        for _ in range(9):
            pg.click('[data-testid=coi-more]'); pg.wait_for_timeout(60)
        pg.wait_for_timeout(300)
        check('the COI stepper stops at the engine\'s ceiling of 15 — a depth it cannot honour is not offered',
              run(pg, "(db) => +db.state.settings.coiDepth") == 15
              and pg.locator('[data-testid=coi-input]').input_value() == '15',
              pg.locator('[data-testid=coi-input]').input_value())
        check('…and the row counts in Arabic: eleven and up take the singular — «15 جيلًا»',
              row_value(pg, 'coi') == '15 جيلًا', row_value(pg, 'coi'))
        for _ in range(14):
            pg.click('[data-testid=coi-less]'); pg.wait_for_timeout(50)
        pg.wait_for_timeout(300)
        check('…and at the floor of 3, «3 أجيال»',
              run(pg, "(db) => +db.state.settings.coiDepth") == 3 and row_value(pg, 'coi') == '3 أجيال', row_value(pg, 'coi'))
        pg.fill('[data-testid=coi-input]', '10'); pg.wait_for_timeout(350)
        check('…and a typed value is saved as typed', run(pg, "(db) => +db.state.settings.coiDepth") == 10)

        open_row(pg, 'contrast')
        pg.click('[data-testid=hc-input]'); pg.wait_for_timeout(400)
        check('high contrast is stored as a setting, not held in the view',
              run(pg, "(db) => db.state.settings.highContrast") is True)
        check('…the switch says so, and the row value reads «مفعّل»',
              pg.locator('[data-testid=hc-input]').get_attribute('aria-pressed') == 'true' and row_value(pg, 'contrast') == 'مفعّل',
              row_value(pg, 'contrast'))
        check('…and is APPLIED to the document, as vanilla applySettings() does',
              pg.evaluate("() => document.documentElement.classList.contains('high-contrast')") is True)
        # [4D acceptance ruling 2] the palette is TOKEN-DERIVED, so what the mode changes is
        # measured on the tokens themselves rather than trusted to a class name.
        hc = pg.evaluate("""() => { const cs = getComputedStyle(document.documentElement);
            const g = (n) => cs.getPropertyValue(n).trim().toLowerCase();
            return { ink2: g('--ink-2'), ink3: g('--ink-3'), page: g('--page'), surface: g('--surface'),
                     line: g('--line'), brand: g('--brand'), brandTint: g('--brand-tint'),
                     goldTint: g('--gold-tint'), dangerTint: g('--danger-tint'),
                     weight: getComputedStyle(document.body).fontWeight }; }""")
        check('[ruling 2] high contrast collapses every muted ink step to full --ink',
              hc['ink2'] == '#101820' and hc['ink3'] == '#101820', str({k: hc[k] for k in ('ink2', 'ink3')}))
        check('[ruling 2] …drops every tint to white and both surfaces to pure white',
              all(hc[k] in ('#fff', '#ffffff') for k in ('page', 'surface', 'brandTint', 'goldTint', 'dangerTint')),
              str({k: hc[k] for k in ('page', 'surface', 'brandTint', 'goldTint', 'dangerTint')}))
        check('[ruling 2] …and turns the hairline into a line, at full weight',
              hc['line'] == '#8c97a2' and hc['weight'] == '500', str(hc))
        check('[P5 ruling 1] …and the brand fill goes to --brand-deep, so white text on it reaches AA',
              hc['brand'] == '#0e6f57', hc['brand'])
        check('[ruling 2] …with NOT ONE new colour: every value is already in the palette',
              {hc['ink2'], hc['line'], hc['brand']} <= {'#101820', '#8c97a2', '#0e6f57'})
        pg.click('[data-testid=hc-input]'); pg.wait_for_timeout(400)
        check('…and turning it off takes it back off the document, tokens and all',
              run(pg, "(db) => db.state.settings.highContrast") is False
              and pg.evaluate("() => document.documentElement.classList.contains('high-contrast')") is False
              and pg.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--ink-3').trim().toLowerCase()") == '#8c97a2'
              and pg.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--brand').trim().toLowerCase()") == '#128c6e'
              and row_value(pg, 'contrast') == 'موقوف')
        # the token that was read everywhere and declared nowhere (found at 4D acceptance)
        check('every token the stylesheets read actually resolves — --danger-tint and --gold-ink included',
              pg.evaluate("""() => { const cs = getComputedStyle(document.documentElement);
                  return ['--danger-tint', '--gold-ink', '--brand-tint', '--gold-tint', '--line', '--ink-3']
                    .every(n => cs.getPropertyValue(n).trim() !== ''); }"""),
              pg.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--danger-tint').trim()"))

        # ── 3. [RULING 2] the loft rows carry the certificate's branding fields ──
        open_row(pg, 'loft-name'); pg.fill('[data-testid=ln]', 'لوفت الزاجل')
        open_row(pg, 'loft-location'); pg.fill('[data-testid=lc]', 'عمّان')
        open_row(pg, 'breeder')
        pg.click('[data-testid=lb]'); pg.type('[data-testid=lb]', 'سمير الهنداوي', delay=40)
        check('a text field keeps the caret while it is typed into (the rows\' fields are not remounted per keystroke)',
              pg.locator('[data-testid=lb]').input_value() == 'سمير الهنداوي'
              and pg.evaluate("() => document.activeElement?.getAttribute('data-testid')") == 'lb',
              pg.locator('[data-testid=lb]').input_value())
        open_row(pg, 'phone'); pg.fill('[data-testid=lp]', '+962790000000')
        open_row(pg, 'website'); pg.fill('[data-testid=lw]', 'https://zajil.example')
        open_row(pg, 'logo')
        pg.set_input_files('[data-testid=logo-input]', files=[{'name': 'logo.png', 'mimeType': 'image/png', 'buffer': PNG}])
        pg.wait_for_timeout(600)
        check('[RULING 2] a chosen logo is stored, the row names the file, and its value reads «موجود»',
              'logo.png' in pg.locator('[data-testid=logo-state]').inner_text() and row_value(pg, 'logo') == 'موجود',
              f"{pg.locator('[data-testid=logo-state]').inner_text()!r} / {row_value(pg, 'logo')!r}")
        pg.click('[data-row=logo] [data-testid=loft-save]'); pg.wait_for_timeout(700)
        saved = run(pg, """(db) => { const l = db.currentLoft();
            return { name: l.name, location: l.location, breederName: l.breederName, phone: l.phone,
                     website: l.website, logo: !!l.logoMediaId }; }""")
        check('[RULING 2] breeder name, phone, website and the logo id round-trip through Lofts.save — ONE «حفظ» writes the whole draft, '
              'so what was typed into rows that have since closed is not lost',
              saved == {'name': 'لوفت الزاجل', 'location': 'عمّان', 'breederName': 'سمير الهنداوي',
                        'phone': '+962790000000', 'website': 'https://zajil.example', 'logo': True},
              str(saved))
        check('…and the rows show the saved values',
              row_value(pg, 'loft-name') == 'لوفت الزاجل' and row_value(pg, 'breeder') == 'سمير الهنداوي'
              and row_value(pg, 'website') == 'https://zajil.example',
              f"{row_value(pg, 'loft-name')!r} {row_value(pg, 'breeder')!r}")
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
        # NEW in tools-v2: «إزالة الشعار»
        open_row(pg, 'logo'); pg.click('[data-testid=logo-remove]'); pg.wait_for_timeout(800)
        gone = run(pg, """async (db) => { const l = db.currentLoft(); const all = await db.mediaForBird(l.id);
            return { logo: l.logoMediaId, media: all.filter(m => m.subtype === 'logo').length }; }""")
        check('[tools-v2] «إزالة الشعار» clears the pointer AND the bytes, and the row says «لا شعار»',
              gone == {'logo': None, 'media': 0} and pg.locator('[data-testid=logo-state]').inner_text().strip() == 'لا شعار'
              and row_value(pg, 'logo') == 'لا شعار' and pg.locator('[data-testid=logo-remove]').count() == 0,
              f"{gone} / {pg.locator('[data-testid=logo-state]').inner_text()!r}")
        wait_toasts_clear(pg)

        # ── 5. the teaching data merges, never destroys (deviation 4: the row tools-v2 dropped) ──
        open_row(pg, 'teaching')
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

        # ── 4. [picker_duplicates #8–10] the duplicate-ring finder — on its own route ──
        check('the duplicates row reports the finder\'s result on the list itself, under «آخر فحص» (RULING 3)',
              row_value(pg, 'duplicates') == 'نظيف' and row_help(pg, 'duplicates').startswith('آخر فحص'),
              f"{row_value(pg, 'duplicates')!r} / {row_help(pg, 'duplicates')!r}")
        clone = run(pg, """async (db) => {
            // a real duplicate: the same ring on a second record. saveBird refuses it
            // unless the warning is acknowledged, which is the write boundary working.
            const src = db.allBirds().find(b => (b.rings || []).length && db.allBirds().some(x => x.sireId === b.id || x.damId === b.id))
                     || db.allBirds().find(b => (b.rings || []).length);
            const copy = await db.saveBird(db.newBird({ name: src.name + ' (نسخة)', sex: src.sex,
                rings: JSON.parse(JSON.stringify(src.rings)) }), { allowWarnings: true });
            return { src: src.id, copy: copy.id, ring: src.rings[0].raw }; }""")
        pg.wait_for_timeout(800)
        check('…and turns gold the moment a duplicate exists, before the sub-screen is opened',
              row_value(pg, 'duplicates') == '1 مكرر' and 'تحتاج مراجعة' in row_help(pg, 'duplicates'),
              f"{row_value(pg, 'duplicates')!r} / {row_help(pg, 'duplicates')!r}")
        go_sub(pg, 'duplicates', 'card-duplicates')
        check('[hybrid] the duplicates row navigates to its own route', pg.url.endswith('/tools/duplicates/'), pg.url)
        check('[picker_duplicates #8] the finder lists the clone',
              pg.locator('[data-testid=dup-group]').count() == 1
              and pg.locator('[data-testid=dup-group] [data-testid=dup-copy]').count() == 2,
              f"{pg.locator('[data-testid=dup-group]').count()} group(s)")
        check('…labelled with the ring the two records share, and how many copies carry it',
              clone['ring'] in pg.locator('[data-testid=dup-group]').inner_text()
              and '2 نسخة' in pg.locator('[data-testid=dup-group]').inner_text(),
              pg.locator('[data-testid=dup-group]').inner_text().replace('\n', ' ')[:120])
        pg.reload(wait_until='load'); pg.wait_for_selector('[data-testid=card-duplicates]', timeout=8000); pg.wait_for_timeout(600)
        check('[hybrid] …and the sub-screen survives a reload, finder and all',
              pg.locator('[data-testid=dup-group]').count() == 1)
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
        pg.click('[data-testid=back-link]'); pg.wait_for_selector('[data-testid=tools-list]', timeout=8000); pg.wait_for_timeout(300)
        check('[hybrid] the back link returns to the list, which reads «نظيف» again',
              pg.url.endswith('/tools/') and row_value(pg, 'duplicates') == 'نظيف', row_value(pg, 'duplicates'))
        wait_toasts_clear(pg)

        # ── 6. backup: export (inline), import and restore (sub-screens) ──
        open_row(pg, 'export')
        with pg.expect_download() as dl:
            pg.click('[data-testid=export-all]')
        name = dl.value.suggested_filename
        check('«تصدير الكل» downloads a dated JSON export', name.startswith('zajil-export-') and name.endswith('.json'), name)
        # [pre-launch] the export is the migration path. Measured before the rewrite: at ~180
        # photos of 2 MB `JSON.stringify` threw `Invalid string length` and the fancier got NO
        # file, NO toast and an unchanged «آخر تصدير» — the button simply looked idle. The
        # button now carries a busy state and a failure now says so.
        run(pg, """async (db) => {
            const loft = db.currentLoft().id;
            for (let i = 0; i < 8; i++) {
                const bird = await db.saveBird(db.newBird({ name: 'ب-' + i, sex: 'cock', loftId: loft }));
                const buf = new Uint8Array(2 * 1024 * 1024);
                for (let o = 0; o < buf.length; o += 65536)
                    crypto.getRandomValues(buf.subarray(o, Math.min(o + 65536, buf.length)));
                await db.addMedia(bird.id, 'photo', 'bird', 'p' + i + '.png', new Blob([buf], { type: 'image/png' }));
            }
        }""")
        pg.reload(); pg.wait_for_selector('[data-testid=tools-list]', timeout=8000); pg.wait_for_timeout(1200)
        open_row(pg, 'export')
        pg.click('[data-testid=export-all]')
        # ONE round trip. The indicator lives ~320 ms for eight photos (measured 2026-10-05); four
        # separate reads raced it and, on 2026-10-05/07, lost — `inner_text` then waited 30 s for an
        # element that had already gone. The three facts are read in the frame that sees it appear.
        snap = pg.wait_for_function("""() => {
            const p = document.querySelector('[data-testid=export-progress]'); if (!p) return null;
            const b = document.querySelector('[data-testid=export-all]');
            return { label: b.innerText.trim(), disabled: b.disabled, prog: p.innerText.trim() }; }""", timeout=8000).json_value()
        busy_label, busy_disabled, prog = snap['label'], snap['disabled'], snap['prog']
        check('[pre-launch] while exporting, the button says so and refuses a second click',
              busy_disabled and busy_label == 'جارٍ التصدير…', f'{busy_label!r} disabled={busy_disabled}')
        check('[pre-launch] …and it reports progress through the photos rather than sitting blank',
              'من' in prog and any(ch.isdigit() or '٠' <= ch <= '٩' for ch in prog), prog)
        pg.wait_for_selector('[data-testid=export-progress]', state='detached', timeout=120000)
        check('[pre-launch] …and it hands the button back when it finishes',
              not pg.locator('[data-testid=export-all]').is_disabled())
        pg.wait_for_timeout(500)
        check('…and the row stops saying «لم يتم التصدير بعد», in its value as in its detail',
              pg.locator('[data-testid=last-export]').inner_text().strip() != 'لم يتم التصدير بعد'
              and row_value(pg, 'export') != 'لم يتم التصدير بعد',
              f"{pg.locator('[data-testid=last-export]').inner_text()!r} / {row_value(pg, 'export')!r}")

        # ── [pre-launch] backup.warn30: the 30-day export nudge ──
        check('[pre-launch] a fresh export means NO 30-day banner',
              pg.locator('[data-testid=backup-warn]').count() == 0)
        run(pg, "async (db) => { await db.setSetting('lastExport', '2020-01-01T00:00:00.000Z'); }")
        pg.reload(); pg.wait_for_selector('[data-testid=tools-list]', timeout=8000); pg.wait_for_timeout(1200)
        check('[pre-launch] an export older than 30 days banners «مرّ أكثر من ٣٠ يومًا»',
              pg.locator('[data-testid=backup-warn]').count() == 1
              and 'مرّ أكثر من ٣٠ يومًا' in pg.locator('[data-testid=backup-warn]').inner_text(),
              pg.locator('[data-testid=backup-warn]').inner_text()[:60])
        check('…and it offers the way to act on it', pg.locator('[data-testid=backup-warn-act]').count() == 1)
        wait_toasts_clear(pg)

        go_sub(pg, 'import', 'card-import')
        check('[hybrid] the import row navigates to its own route', pg.url.endswith('/tools/import/'), pg.url)
        check('the import button stays disabled until a file is chosen',
              pg.locator('[data-testid=import-file]').is_disabled()
              and pg.locator('[data-testid=file-name]').inner_text().strip() == 'لم يُختر ملف — .json',
              pg.locator('[data-testid=file-name]').inner_text())
        check('…and the mode is the spec\'s segmented control, «دمج» pressed by default',
              pg.locator('[data-testid=import-mode] [data-value=merge]').get_attribute('aria-pressed') == 'true'
              and pg.locator('[data-testid=import-mode] button').count() == 2)
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
        pg.locator('[data-testid=import-mode] [data-value=replace]').click(); pg.wait_for_timeout(200)
        pg.click('[data-testid=import-file]'); pg.wait_for_selector('[data-testid=dialog]', timeout=5000)
        check('«استبدال» asks before it destroys, in the danger voice',
              pg.locator('[data-testid=dialog-confirm]').count() == 1
              and 'استبدال' in pg.locator('[data-testid=dialog]').inner_text(),
              pg.locator('[data-testid=dialog]').inner_text().replace('\n', ' ')[:100])
        pg.click('[data-testid=dialog-cancel]'); pg.wait_for_timeout(400)
        check('…and cancelling leaves the loft alone', run(pg, "(db) => db.allBirds().length") == n_before)
        pg.reload(wait_until='load'); pg.wait_for_selector('[data-testid=card-import]', timeout=8000)
        check('[hybrid] the import screen survives a reload', pg.locator('[data-testid=import-file]').count() == 1
              and pg.locator('[data-testid=import-mode] [data-value=merge]').get_attribute('aria-pressed') == 'true')

        # ── [data_loss #5] restoring an automatic snapshot — the spec's list, on its own route ──
        # The claim that matters is not "a restore runs" but that PHOTOS SURVIVE one: a snapshot
        # deliberately carries no media (exportAll includeMedia:false, db/io.js), and importAll
        # keeps the media store for a payload marked auto-backup.
        run(pg, """async (db) => {
            const b = db.allBirds()[0];
            await db.addMedia(b.id, 'photo', 'body', 'keeps.png', new Blob(['x']));
            await db.autoBackup();
        }""")
        media_before = run(pg, "async (db) => (await db.mediaForBird(db.allBirds()[0].id)).length")
        birds_before = run(pg, "(db) => db.allBirds().length")
        pg.goto(f'{TOOLS}restore/', wait_until='load'); pg.wait_for_selector('[data-testid=card-restore]', timeout=8000)
        pg.wait_for_timeout(900)
        check('[hybrid] the restore screen answers its own deep link', pg.url.endswith('/tools/restore/'), pg.url)
        check('[data_loss #5] an automatic snapshot is offered for restore, by its own timestamp — the spec\'s list, one «استرجاع» per snapshot',
              pg.locator('[data-testid=snap-row]').count() >= 1
              and pg.locator('[data-testid=snap-restore]').count() == pg.locator('[data-testid=snap-row]').count()
              and any(ch.isdigit() for ch in pg.locator('[data-testid=snap-row]').first.inner_text()),
              pg.locator('[data-testid=snap-row]').first.inner_text().replace('\n', ' ')[:60])
        check('[RULING 3] …under «آخر نسخة تلقائية», which names the newest',
              'آخر نسخة تلقائية' in pg.locator('[data-testid=last-snapshot]').inner_text()
              and any(ch.isdigit() for ch in pg.locator('[data-testid=last-snapshot]').inner_text()),
              pg.locator('[data-testid=last-snapshot]').inner_text())
        pg.locator('[data-testid=snap-restore]').first.click(); pg.wait_for_selector('[data-testid=dialog]', timeout=5000)
        check('…and it asks first, naming the snapshot it would put back',
              any(ch.isdigit() for ch in pg.locator('[data-testid=dialog]').inner_text()),
              pg.locator('[data-testid=dialog]').inner_text().replace('\n', ' ')[:90])
        pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(3000)
        after = run(pg, """async (db) => ({ birds: db.allBirds().length,
            media: (await db.mediaForBird(db.allBirds()[0].id)).length })""")
        check('[data_loss #5] PHOTOS SURVIVE the restore — a snapshot carries no media, so it must not wipe it',
              after['media'] == media_before and media_before > 0,
              f"{media_before} before, {after['media']} after")
        check('…and the records came back with it', after['birds'] == birds_before,
              f"{birds_before} -> {after['birds']}")
        wait_toasts_clear(pg)
        go_list(pg)
        check('…and the list\'s restore row counts the snapshots',
              row_value(pg, 'restore').endswith('متاحة') and any(ch.isdigit() for ch in row_value(pg, 'restore')),
              row_value(pg, 'restore'))

        # ── [data_loss #7] the loft rows after a FOREIGN replace ──
        # An export from another device carries its own loft ids, so a replace-import can
        # leave currentLoftId pointing at a loft that no longer exists — which blanks the loft
        # rows and misfiles every new record. db/io.js repairs it; the layer half is covered
        # by import_atomicity.py, and this is the half a person would actually see.
        foreign = run(pg, """async (db) => {
            const p = await db.exportAll();
            const id = 'foreign-loft-uuid';
            p.lofts = [{ id, name: 'لوفت غريب', location: 'إربد', statuses: db.DEFAULT_STATUSES || [],
                         createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z' }];
            // parents dropped with the rest: this is a claim about the loft ROWS, and three
            // birds pointing at ancestors the payload does not carry would leave the loft
            // deliberately broken for the integrity check further down
            p.birds = (p.birds || []).slice(0, 3).map((b) => ({ ...b, loftId: id, sireId: null, damId: null }));
            p.pairs = []; p.raceResults = []; p.healthEvents = [];
            return p;
        }""")
        go_sub(pg, 'import', 'card-import')
        pick(foreign, 'foreign-loft.json')
        pg.locator('[data-testid=import-mode] [data-value=replace]').click(); pg.wait_for_timeout(200)
        pg.click('[data-testid=import-file]'); pg.wait_for_selector('[data-testid=dialog]', timeout=5000)
        pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(3500)
        check('[data_loss #7] after a replace-import of a FOREIGN loft, currentLoftId points at a loft that exists',
              run(pg, "(db) => !!db.currentLoft() && db.currentLoft().id === 'foreign-loft-uuid'"),
              str(run(pg, "(db) => db.state.currentLoftId")))
        go_list(pg)
        check('[data_loss #7] …and the loft rows name it, rather than «لوفت بلا اسم»',
              row_value(pg, 'loft-name') == 'لوفت غريب' and row_value(pg, 'loft-location') == 'إربد',
              f"{row_value(pg, 'loft-name')!r} / {row_value(pg, 'loft-location')!r}")
        open_row(pg, 'loft-name')
        check('…and are usable, not blank',
              pg.locator('[data-testid=ln]').input_value() == 'لوفت غريب'
              and pg.locator('[data-row=loft-name] [data-testid=loft-save]').is_enabled(),
              repr(pg.locator('[data-testid=ln]').input_value()))
        wait_toasts_clear(pg)

        # ── [core_flows #9-11] the ENGLISH app ──
        open_row(pg, 'lang')
        pg.locator('[data-testid=set-lang] [data-testid=seg-btn][data-value=en]').click()
        pg.wait_for_timeout(900)
        doc = pg.evaluate("() => ({ dir: document.documentElement.dir, lang: document.documentElement.lang })")
        check('[core_flows] choosing English turns the whole document LTR, lang=en',
              doc == {'dir': 'ltr', 'lang': 'en'}, str(doc))
        check('…and the screen is in English, not Arabic text in an LTR box',
              pg.locator('h1').first.inner_text().strip() == 'Tools'
              and pg.locator('[data-section=settings] h2').inner_text().strip() == 'Settings'
              and row_value(pg, 'lang') == 'English',
              f"{pg.locator('h1').first.inner_text()!r} / {pg.locator('[data-section=settings] h2').inner_text()!r}")
        check('…and it is a stored setting, so it survives a navigation',
              run(pg, "(db) => db.state.settings.lang") == 'en')
        pg.goto(f'{ROOT}stats/', wait_until='load'); pg.wait_for_timeout(2000)
        check('…on another screen too, which is what makes it the APP language and not a toggle',
              pg.evaluate("() => document.documentElement.dir") == 'ltr'
              and pg.evaluate("() => document.documentElement.lang") == 'en')
        go_list(pg); open_row(pg, 'lang')
        pg.locator('[data-testid=set-lang] [data-testid=seg-btn][data-value=ar]').click()
        pg.wait_for_timeout(900)
        back = pg.evaluate("() => ({ dir: document.documentElement.dir, lang: document.documentElement.lang })")
        check('…and Arabic comes back, RTL and all', back == {'dir': 'rtl', 'lang': 'ar'}, str(back))
        wait_toasts_clear(pg)

        # ── 7. the optional scanner ──
        open_row(pg, 'scanner')
        check('the scanner is off by default and says the app is complete without it',
              pg.locator('[data-testid=scan-off]').count() == 1
              and 'يعمل دون اتصال' in pg.locator('[data-testid=scan-off]').inner_text()
              and row_value(pg, 'scanner') == 'غير مفعّل',
              pg.locator('[data-testid=scan-off]').inner_text().replace('\n', ' '))
        pg.fill('[data-testid=scan-url]', 'https://vision.example.org')
        pg.locator('[data-testid=scan-url]').blur(); pg.wait_for_timeout(400)
        check('…and a server address is saved through setSetting, not held in the view',
              run(pg, "(db) => db.state.settings.scanServerUrl") == 'https://vision.example.org')
        check('…after which the "not configured" note is gone and the row shows the address',
              pg.locator('[data-testid=scan-off]').count() == 0 and row_value(pg, 'scanner') == 'https://vision.example.org',
              row_value(pg, 'scanner'))
        pg.fill('[data-testid=scan-url]', ''); pg.click('[data-testid=scan-save]'); pg.wait_for_timeout(400)
        check('…and the spec\'s «حفظ» saves too', run(pg, "(db) => db.state.settings.scanServerUrl") == ''
              and pg.locator('[data-testid=scan-off]').count() == 1)
        wait_toasts_clear(pg)

        # ── 9. the developer panel, collapsed, running the COPIED engine suite (RULED: kept exactly as tools-v1 had it) ──
        check('the developer panel is collapsed until a developer opens it, and says so',
              pg.locator('[data-testid=card-dev]').get_attribute('open') is None
              and pg.locator('[data-testid=dev-run]').is_visible() is False
              and row_value(pg, 'dev') == 'مطوي', row_value(pg, 'dev'))
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
        # (js/views/tools.js:447) — so the number it reports is that file's own.
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

        # ── the integrity check as a row of its own (tools-v2), with «آخر فحص» (RULING 3) ──
        open_row(pg, 'integrity')
        check('[tools-v2] the integrity check is a row of its own, honest about never having run',
              row_value(pg, 'integrity') == 'لم يُشغَّل بعد' and pg.locator('[data-testid=integrity-status]').count() == 0,
              row_value(pg, 'integrity'))
        pg.click('[data-testid=integrity-run]'); pg.wait_for_selector('[data-testid=integrity-status]', timeout=5000); pg.wait_for_timeout(400)
        st_txt = pg.locator('[data-testid=integrity-status]').inner_text().replace('\n', ' ')
        check('…running it reports the result under «آخر فحص» with the time',
              'لا مراجع معلّقة' in st_txt and 'آخر فحص' in st_txt and any(ch.isdigit() for ch in st_txt), st_txt[:90])
        check('…and the row value reads «سليم»', row_value(pg, 'integrity') == 'سليم', row_value(pg, 'integrity'))
        pg.reload(); pg.wait_for_selector('[data-testid=tools-list]', timeout=8000); pg.wait_for_timeout(800)
        check('…and «آخر فحص» survives a reload — the time and the count are settings, like lastExport',
              row_value(pg, 'integrity') == 'سليم'
              and run(pg, "(db) => typeof db.state.settings.integrityCheckedAt") == 'string',
              row_value(pg, 'integrity'))

        # ── THE PROOF: every control tools-v1 shipped, reached in at most two taps ──
        # (testid → route under /tools/, row to open). State-dependent controls are proved in
        # their flows above and in part B: sync-signed-out / go-signin / sync-signed-in /
        # sync-account / sign-out (account row), sync-pending / sync-now / sync-toggle (sync/),
        # dup-found / dup-group / dup-copy / dup-links / dup-delete (duplicates/, with a clone),
        # export-progress (export, while it runs). tools-v1's snap-select became the spec's
        # snapshot list: snap-row + snap-restore (restore/).
        V1_CONTROLS = {
            'set-lang': ('', 'lang'), 'set-numerals': ('', 'numerals'), 'set-dates': ('', 'dates'),
            'coi-less': ('', 'coi'), 'coi-input': ('', 'coi'), 'coi-more': ('', 'coi'), 'hc-input': ('', 'contrast'),
            'sync-unconfigured': ('', 'account'),
            'ln': ('', 'loft-name'), 'lc': ('', 'loft-location'), 'lb': ('', 'breeder'), 'lp': ('', 'phone'), 'lw': ('', 'website'),
            'logo-pick': ('', 'logo'), 'logo-state': ('', 'logo'), 'logo-input': ('', 'logo'), 'loft-save': ('', 'loft-name'),
            'load-sample': ('', 'teaching'), 'load-large': ('', 'teaching'),
            'last-export': ('', 'export'), 'export-all': ('', 'export'),
            'scan-url': ('', 'scanner'), 'scan-off': ('', 'scanner'),
            'about-version': ('', None), 'card-dev': ('', None),
            'dev-run': ('', 'dev'), 'dev-roundtrip': ('', 'dev'), 'dev-integrity': ('', 'dev'),
            'import-mode': ('import/', None), 'file-pick': ('import/', None), 'file-name': ('import/', None),
            'file-input': ('import/', None), 'import-file': ('import/', None),
            'snap-row': ('restore/', None), 'snap-restore': ('restore/', None),
            'dup-clean': ('duplicates/', None),
        }
        reach, cur = {}, None
        for tid, (route, row) in V1_CONTROLS.items():
            if route != cur:
                pg.goto(f'{TOOLS}{route}', wait_until='load')
                pg.wait_for_selector('[data-testid=tools-list], [data-testid^=card-]', timeout=8000); pg.wait_for_timeout(700)
                cur = route
            taps = 1 if route else 0
            if row:
                open_row(pg, row); taps += 1
            loc = pg.locator(f'[data-testid={tid}]')
            reach[tid] = (loc.count(), taps, loc.first.is_visible() if loc.count() else False)
        missing = [k for k, (n, _, _) in reach.items() if n == 0]
        hidden = [k for k, (n, _, vis) in reach.items() if n and not vis and k not in ('logo-input', 'file-input')]
        check('[tools-v1 → v2] EVERY control tools-v1 shipped is still on the screen', not missing, str(missing) if missing else f'{len(reach)} controls')
        check('…visible once its row is open or its screen is reached', not hidden, str(hidden))
        check('…and none further than one tap plus one tap', max(tp for _, tp, _ in reach.values()) <= 2,
              f"worst {max(tp for _, tp, _ in reach.values())} tap(s)")
        go_list(pg)

        # ── [ruling C] fixed elements must not hide content ──
        check_clearance(pg, check, 'tools')
        pg.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)"); pg.wait_for_timeout(300)
        open_row(pg, 'website'); pg.click('[data-row=website] [data-testid=loft-save]'); pg.wait_for_timeout(500)
        check_toast_clear(pg, check, 'tools')
        wait_toasts_clear(pg)
        close_row(pg, 'website')
        shots(pg, 'full')
        check('zero page errors on the unconfigured build', not errs, '; '.join(errs[:2]))

        # ══ B. A CONFIGURED BUILD — the account row and the sync screen's remaining states ═════
        ctx2 = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}))
        ctx2.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};")
        ctx2.route(f'{STUB}/**', handler)
        sp = ctx2.new_page(); errs2 = []; sp.on('pageerror', lambda e: errs2.append(str(e)))
        sp.goto(TOOLS, wait_until='load'); sp.wait_for_selector('[data-testid=signin-screen][data-gate]', timeout=8000); sp.wait_for_timeout(400)

        # ── THE GATE (RULED 2026-10-07) — with no session, الأدوات is the sign-in screen, like every route ──
        # The signed-out account-row states RULING 1 once drew here are unreachable now: a device with
        # no session never sees الأدوات. They are asserted on the gate itself in screens/gate.py.
        check('[GATE] a configured device with no session meets the sign-in gate at الأدوات, not the list',
              sp.locator('[data-testid=signin-form]').count() == 1 and sp.locator('[data-testid=tools-list]').count() == 0
              and sp.locator('[data-testid=nav-link]').count() == 0, sp.url)
        check('[sync_ui #26] …with no way to create an account',
              not any(w in sp.inner_text('body') for w in ['إنشاء حساب', 'Create account', 'Sign up', 'تسجيل جديد']))
        shots(sp, 'signed-out')

        # ── [sync_ui #34 #37] signed in ──
        run(sp, "async (db) => { await db.signIn('spike-a@zajil.test','pw'); await db.syncNow(); }")
        sp.wait_for_selector('[data-testid=sync-signed-in]', timeout=8000); sp.wait_for_timeout(300)
        check('[GATE] signing in lifts the gate in place: الأدوات, where the session is managed, with the account row open',
              sp.locator('[data-testid=tools-list]').count() == 1 and sp.url.endswith('/tools/'), sp.url)
        check('[sync_ui #34] signing in switches the account row to the signed-in state, naming the account',
              sp.locator('[data-testid=sync-account]').inner_text().strip() == 'spike-a@zajil.test'
              and row_value(sp, 'account') == 'spike-a@zajil.test', row_value(sp, 'account'))
        check('[sync_ui #35] …offering «تسجيل الخروج»',
              sp.locator('[data-testid=sign-out]').inner_text().strip() == 'تسجيل الخروج')
        check('[sync_ui #36] …and saying plainly that signing out is not deleting',
              'بياناتك تبقى على هذا الجهاز' in sp.locator('[data-testid=sync-signed-in]').inner_text())
        check('[sync_ui #37] signing in ran a real sync cycle — no second code path for "just signed in"',
              run(sp, "(db) => db.state.settings.lastSyncAt") is not None)
        check('…and the sync row reads «متزامن», with the last sync time as its help',
              row_value(sp, 'sync') == 'متزامن' and row_help(sp, 'sync').startswith('آخر مزامنة')
              and any(ch.isdigit() for ch in row_help(sp, 'sync')),
              f"{row_value(sp, 'sync')!r} / {row_help(sp, 'sync')!r}")
        go_sub(sp, 'sync', 'card-sync')
        check('[hybrid] the sync screen carries the status line, the last sync and the pending count the layer reports',
              sp.locator('[data-testid=sync-status]').get_attribute('data-state') == 'synced'
              and sp.locator('[data-testid=sync-pending]').inner_text().strip() == str(run(sp, "(db) => db.syncStatus().pending")),
              f"state={sp.locator('[data-testid=sync-status]').get_attribute('data-state')} pending={sp.locator('[data-testid=sync-pending]').inner_text()}")
        shots(sp, 'signed-in')

        before_seq = srv_state['seq']
        # MEASURED 2026-10-03: syncStatus().pending stays 0 after saveBird — the layer counts
        # unpushed ops on refreshSyncStatus() (db/sync.js:976-989), which the sync loop runs,
        # not on every write. The screen shows what the layer reports, so the refresh is
        # called here the way the loop would, and the PENDING state is what is asserted.
        run(sp, "async (db) => { await db.saveBird(db.newBird({ name: 'survives-sign-out', sex: 'cock' })); await db.refreshSyncStatus(); }")
        sp.wait_for_timeout(400)
        check('…a local change shows up as pending once the layer counts it — the clock line, and the number',
              sp.locator('[data-testid=sync-status]').get_attribute('data-state') == 'pending'
              and sp.locator('[data-testid=sync-pending]').inner_text().strip() == str(run(sp, "(db) => db.syncStatus().pending"))
              and run(sp, "(db) => db.syncStatus().pending") >= 1
              and 'بانتظار المزامنة' in sp.locator('[data-testid=sync-status]').inner_text(),
              f"state={sp.locator('[data-testid=sync-status]').get_attribute('data-state')} pending={sp.locator('[data-testid=sync-pending]').inner_text()}")
        sp.click('[data-testid=sync-now]'); sp.wait_for_timeout(2500)
        check('«مزامنة الآن» actually runs a cycle', srv_state['seq'] > before_seq, f"{before_seq} -> {srv_state['seq']}")
        wait_toasts_clear(sp)
        sp.click('[data-testid=sync-toggle]'); sp.wait_for_timeout(600)
        check('the toggle turns sync off, and says so',
              run(sp, "(db) => db.state.settings.syncEnabled") is False
              and 'تشغيل المزامنة' in sp.locator('[data-testid=sync-toggle]').inner_text(),
              sp.locator('[data-testid=sync-toggle]').inner_text())
        sp.click('[data-testid=back-link]'); sp.wait_for_selector('[data-testid=tools-list]', timeout=8000); sp.wait_for_timeout(300)
        check('…and the list\'s sync row reads «متوقفة» while it is off', row_value(sp, 'sync') == 'متوقفة', row_value(sp, 'sync'))
        go_sub(sp, 'sync', 'card-sync')
        sp.click('[data-testid=sync-toggle]'); sp.wait_for_timeout(600)
        check('…and back on', run(sp, "(db) => db.state.settings.syncEnabled") is not False)
        sp.click('[data-testid=back-link]'); sp.wait_for_selector('[data-testid=tools-list]', timeout=8000); sp.wait_for_timeout(300)

        # ── offline → pending → synced, on the real layer ──
        # The stub answers through ctx.route() BEFORE the network, so set_offline() cannot fail
        # a push here (measured: syncNow() completes offline). What it does flip is
        # navigator.onLine, which is what the layer reads for «دون اتصال» — so no sync is
        # attempted, and the unpushed op is what the count carries.
        ctx2.set_offline(True)
        run(sp, "async (db) => { await db.saveBird(db.newBird({ name: 'made-offline', sex: 'hen' })); await db.refreshSyncStatus(); }")
        sp.wait_for_timeout(900)
        off_state = run(sp, "(db) => db.syncStatus().state")
        check('offline with a local change, the sync row says so — by the layer\'s own state, not a guess',
              (off_state == 'offline' and row_value(sp, 'sync') == 'دون اتصال' and row_help(sp, 'sync') == 'يعمل محليًا')
              or (off_state == 'pending' and row_value(sp, 'sync').endswith('معلّقًا')),
              f"layer={off_state} row={row_value(sp, 'sync')!r} / {row_help(sp, 'sync')!r}")
        go_sub(sp, 'sync', 'card-sync')
        check('…and the sync screen\'s status line names the same state',
              sp.locator('[data-testid=sync-status]').get_attribute('data-state') == off_state
              and int(sp.locator('[data-testid=sync-pending]').inner_text().strip()) >= 1,
              f"{sp.locator('[data-testid=sync-status]').get_attribute('data-state')} / pending {sp.locator('[data-testid=sync-pending]').inner_text()}")
        ctx2.set_offline(False)
        sp.click('[data-testid=sync-now]'); sp.wait_for_timeout(2500); wait_toasts_clear(sp)
        check('…and once the connection is back, «مزامنة الآن» drains it to synced',
              sp.locator('[data-testid=sync-status]').get_attribute('data-state') == 'synced'
              and sp.locator('[data-testid=sync-pending]').inner_text().strip() == '0',
              f"{sp.locator('[data-testid=sync-status]').get_attribute('data-state')} / {sp.locator('[data-testid=sync-pending]').inner_text()}")
        sp.click('[data-testid=back-link]'); sp.wait_for_selector('[data-testid=tools-list]', timeout=8000); sp.wait_for_timeout(300)

        # ── [sync_ui #38 #39 #40] signing out keeps the data ──
        birds_before = run(sp, "(db) => db.allBirds().length")
        open_row(sp, 'account')
        sp.click('[data-testid=sign-out]'); sp.wait_for_selector('[data-testid=dialog]', timeout=5000)
        check('…and sign-out asks first, repeating that the data stays',
              'بياناتك تبقى على هذا الجهاز' in sp.locator('[data-testid=dialog]').inner_text(),
              sp.locator('[data-testid=dialog]').inner_text().replace('\n', ' ')[:100])
        sp.click('[data-testid=dialog-confirm]'); sp.wait_for_selector('[data-testid=signin-screen][data-gate]', timeout=8000); sp.wait_for_timeout(300)
        after_out = run(sp, """(db) => ({ signedIn: db.authState().signedIn, birds: db.allBirds().length,
            tokens: db.AUTH_SETTING_KEYS.map(k => db.state.settings[k]).filter(Boolean).length })""")
        check('[sync_ui #38] signing out clears every token', after_out['tokens'] == 0, str(after_out))
        check('[sync_ui #39] SIGNING OUT IS NOT DELETING — the birds are still there',
              after_out['birds'] == birds_before, f"{birds_before} -> {after_out['birds']}")
        check('[sync_ui #40 / GATE] …and the gate comes back at once, naming the loft the device holds',
              sp.locator('[data-testid=signin-screen]').get_attribute('data-gate') == 'records'
              and sp.locator('[data-testid=gate-loft]').count() == 1, sp.locator('[data-testid=gate-loft]').inner_text() if sp.locator('[data-testid=gate-loft]').count() else 'no loft line')

        # a rejected sign-in never reaches THIS row: the message belongs to /sign-in
        srv_state['token_mode'] = 'reject'
        rejected = run(sp, "async (db) => { try { await db.signIn('x@y.test','wrong'); return 'signed-in'; } catch (e) { return e.kind || e.message; } }")
        sp.wait_for_timeout(500)
        check('a rejected sign-in leaves the gate standing and puts no status code on screen',
              rejected != 'signed-in' and sp.locator('[data-testid=signin-screen][data-gate]').count() == 1
              and not any(c.isdigit() for c in sp.locator('[data-testid=gate]').inner_text()),
              str(rejected))
        srv_state['token_mode'] = 'ok'

        check_clearance(sp, check, 'tools (configured)')
        check('zero page errors on the configured build', not errs2, '; '.join(errs2[:2]))
        NET.assert_empty(check)
        b.close()
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
