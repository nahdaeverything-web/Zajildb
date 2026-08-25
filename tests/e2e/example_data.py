import os
from playwright.sync_api import sync_playwright
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
    page.goto(os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+''), wait_until='networkidle'); page.wait_for_timeout(800)

    # 1. empty state now offers the example loader; click it
    check('empty state has example buttons', page.locator('.empty-state button').count() == 2)
    page.locator('.empty-state button').first.click(); page.wait_for_timeout(1500)
    page.reload(); page.wait_for_timeout(900)
    check('example data loaded via UI', page.locator('.bird-row').count() == 20)

    # 2. sex chips readable in register
    chip = page.locator('.bird-row .sex-chip').first.inner_text()
    check('register rows show sex word chip', 'ذكر' in chip or 'أنثى' in chip or '?' in chip, chip)

    # 3. picker dropdown actually hides now ([hidden] fix)
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/bird/new'); page.wait_for_timeout(700)
    inp = page.locator('.bird-picker input').first
    inp.click(); page.wait_for_timeout(400)
    check('picker opens', page.locator('.picker-list').first.is_visible())
    page.locator('.picker-item').first.click(); page.wait_for_timeout(300)
    check('picker CLOSES after pick (was the stuck bug)', not page.locator('.picker-list').first.is_visible())
    inp.click(); page.wait_for_timeout(300)
    page.locator('h1').first.click(); page.wait_for_timeout(300)
    check('picker closes on outside click', not page.locator('.picker-list').first.is_visible())

    # 4. add-sibling: prefilled parents for سهم (has parents)
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/bird/c-sahm'); page.wait_for_timeout(700)
    page.locator('button', has_text='👥').click(); page.wait_for_timeout(700)
    check('add-sibling routes to prefilled form', '#/bird/new?sire=b-barq&dam=u-malika' in page.url)
    vals = page.locator('.bird-picker input').evaluate_all('els => els.map(e => e.value)')
    check('sire+dam prefilled', any('برق' in v for v in vals) and any('الملكة' in v for v in vals), str(vals))

    # 5. add-sibling on a bird WITHOUT parents → placeholder dialog, creates parents
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/bird/o-asifa'); page.wait_for_timeout(700)
    page.locator('button', has_text='👥').click(); page.wait_for_timeout(500)
    check('placeholder dialog shown', page.locator('.modal').count() == 1)
    page.locator('.modal-actions .btn-primary').click(); page.wait_for_timeout(900)
    check('placeholder flow lands on prefilled form', '#/bird/new?sire=' in page.url)
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/bird/o-asifa'); page.wait_for_timeout(700)
    facts = page.locator('.facts').inner_text()
    check('عاصفة now has placeholder parents', 'أب غير معروف' in facts and 'أم غير معروفة' in facts)

    # 6. health dialog: bird field hides when whole-loft ([hidden] fix there too)
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/health'); page.wait_for_timeout(700)
    page.locator('button', has_text='+').click(); page.wait_for_timeout(400)
    page.locator('.modal select').nth(1).select_option('loft'); page.wait_for_timeout(200)
    check('health: bird field hides for whole-loft', not page.locator('.modal .bird-picker').is_visible())
    page.keyboard.press('Escape')

    # 7. breeding shows 3 pairs in 2026 (incl. the new mid-cycle learning pair)
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/breeding'); page.wait_for_timeout(700)
    check('breeding 2026 has 3 pairs', page.locator('.pair-card').count() == 3)
    check('mid-cycle pair shows hatch buttons', page.locator('.egg-row button').count() >= 4)

    # 8. legend under pedigree
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/pedigree/y-najm'); page.wait_for_timeout(700)
    check('sex legend under tree', page.locator('.sex-legend .sex-chip').count() == 3)
    page.screenshot(path='/tmp/claude-1000/-home-samir/8788c756-998b-4a82-9d7a-2ebbad47d910/scratchpad/ped-v11.png', full_page=True)

    check('zero page errors', not errs, '; '.join(errs[:3]))
    b.close()
print(f'\n{ok} passed, {fail} failed')
exit(1 if fail else 0)
