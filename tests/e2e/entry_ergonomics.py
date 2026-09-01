import os
from playwright.sync_api import sync_playwright

# The shipped datasets carry real uuids (v1.9.1). Python's uuid5 derives exactly
# what tools/idmap.js derives from the same namespace and key, so these suites
# keep naming records by the readable key that documents what they are.
import uuid as _uuid
_ID_NS = _uuid.UUID('7f3c9a54-2b18-4d6e-9c05-1a2b3c4d5e6f')
def bird_id(key):
    return str(_uuid.uuid5(_ID_NS, key))
ok = fail = 0
def check(name, cond, extra=''):
    global ok, fail
    if cond: ok += 1; print(f'  ✓ {name}')
    else: fail += 1; print(f'  ✗ {name} {extra}')

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={'width': 1280, 'height': 900})
    errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto(os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+''), wait_until='networkidle'); page.wait_for_timeout(700)
    page.evaluate('''async () => {
        const db = await import('./js/db.js');
        const payload = await (await fetch('./sample-data.json')).json();
        await db.importAll(payload, 'merge');
    }''')
    page.reload(); page.wait_for_timeout(900)

    # 1. new-bird form: rings section first, one seeded ring row
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/bird/new'); page.wait_for_timeout(700)
    first_section = page.locator('form > *').first
    check('rings section leads the form', 'form-section-first' in (first_section.get_attribute('class') or ''))
    check('one ring row pre-seeded', page.locator('.ring-row').count() == 1)

    # 2. Enter in a text input must NOT save
    page.locator('.ring-input').fill('JO-2026-77001')
    page.keyboard.press('Enter'); page.wait_for_timeout(400)
    check('Enter does not submit the form', '#/bird/new' in page.url)

    # 3. ring-year hint fills hatch date
    check('ring-year hint appears', page.locator('.hatch-hint button').count() == 1)
    page.locator('.hatch-hint button').click()
    check('hatch set from ring year', page.locator('input[type=date]').first.input_value() == '2026-01-01')

    # 4. inline ancestor creation from the sire picker
    sire_input = page.locator('.bird-picker input').first
    sire_input.fill('طير غير موجود'); page.wait_for_timeout(400)
    check('picker offers create row', page.locator('.picker-create').count() >= 1)
    page.locator('.picker-create').first.click(); page.wait_for_timeout(600)
    check('created stub selected as sire', 'طير غير موجود' in sire_input.input_value())

    # 5. save & add another: carries strain/status, ring prefix, stays on form
    page.locator('input[list=dl-strains]').fill('يانسن')
    page.locator('button[type=submit]', has_text='حفظ وإضافة آخر').click(); page.wait_for_timeout(900)
    check('save&new stays on a fresh form', '#/bird/new' in page.url)
    check('strain carried over', page.locator('input[list=dl-strains]').input_value() == 'يانسن')
    check('ring prefix carried', page.locator('.ring-input').input_value() == 'JO-2026-')
    check('datalist has strains', page.locator('#dl-strains option').count() >= 2)

    # 6. plain save uses replace: back returns to the LIST, not the form
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/birds'); page.wait_for_timeout(500)
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/bird/new'); page.wait_for_timeout(600)
    page.locator('.ring-input').fill('JO-2026-77002')
    page.locator('button.btn-primary[type=submit]').click(); page.wait_for_timeout(900)
    check('save lands on detail', '#/bird/' in page.url and 'new' not in page.url)
    page.go_back(); page.wait_for_timeout(500)
    check('back after save → birds list (not stale form)', page.url.endswith('#/birds'))

    # 7. egg dates editable; hatch-date edit propagates to the chick record
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/breeding'); page.wait_for_timeout(800)
    hatch_inputs = page.locator('.egg-row input[type=date]')
    check('egg rows expose date inputs', hatch_inputs.count() >= 4)
    changed = page.evaluate('''async (a) => {
        const db = await import('./js/db.js');
        const pair = db.state.pairs.get(a);
        const egg = pair.rounds[0].eggs[0];
        return { chickId: egg.chickId, before: db.getBird(egg.chickId).hatchDate };
    }''', bird_id('p-barq-malika-26'))
    # find the hatch input of that egg (second date input in first hatched row) and change it
    row = page.locator('.egg-row.egg-hatched').first
    row.locator('input[type=date]').nth(1).fill('2026-03-10'); page.wait_for_timeout(600)
    after = page.evaluate(f'''async () => {{
        const db = await import('./js/db.js');
        return db.getBird('{changed["chickId"]}').hatchDate;
    }}''')
    check('hatch-date edit propagates to chick record', after == '2026-03-10', f'got {after}')

    check('zero page errors', not errs, '; '.join(errs[:3]))
    b.close()
print(f'\n{ok} passed, {fail} failed')
exit(1 if fail else 0)
