import os
from playwright.sync_api import sync_playwright
ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={'width': 1280, 'height': 950})
    errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto(os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+''), wait_until='networkidle'); page.wait_for_timeout(800)

    # empty state offers BOTH examples
    btns = page.locator('.empty-state button')
    check('empty state offers two example buttons', btns.count() == 2, f'got {btns.count()}')
    # load the large one
    page.locator('.empty-state button').nth(1).click(); page.wait_for_timeout(2000)
    page.reload(); page.wait_for_timeout(1200)
    check('38 birds loaded', page.locator('.bird-row').count() == 38, str(page.locator('.bird-row').count()))

    # deepest pedigree renders 5 generations fully
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/pedigree/g5-faris26'); page.wait_for_timeout(900)
    page.locator('.seg-btn', has_text='5').click(); page.wait_for_timeout(800)
    known = page.locator('.ped-cell.ped-known').count()
    unknown = page.locator('.ped-cell.ped-unknown').count()
    check('5-gen tree fully populated (63 known, 0 unknown)', known == 63 and unknown == 0, f'known={known} unknown={unknown}')
    badge = page.locator('.coi-headline .coi-badge').inner_text()
    check('COI badge shows 12.5%', '12.5' in badge, badge)
    check('COI breakdown lists common ancestors', page.locator('.coi-panel tbody tr').count() >= 4)
    page.screenshot(path='/tmp/claude-1000/-home-samir/8788c756-998b-4a82-9d7a-2ebbad47d910/scratchpad/large-ped.png', full_page=True)

    # the severe-warning demo via relationship finder
    page.locator('.card .bird-picker input').last.fill('نجمة'); page.wait_for_timeout(500)
    page.locator('.picker-item').first.click(); page.wait_for_timeout(600)
    rel = page.locator('.rel-result').inner_text()
    check('full-sib pairing shows severe warning', 'أشقاء' in rel and page.locator('.warn-severe').count() == 1, rel[:90])

    # father × daughter bird
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/bird/g3-asif'); page.wait_for_timeout(800)
    check('عاصف detail shows 25% COI', '25' in page.locator('.facts .coi-badge').first.inner_text())

    # progeny analysis on a foundation bird
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/bird/x-remco'); page.wait_for_timeout(900)
    stats = page.locator('.stat-value').all_inner_texts()
    check('Remco progeny analysis populated', len(stats) >= 6 and stats[1] not in ('0', '٠'), str(stats[:4]))

    # other views
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/breeding'); page.wait_for_timeout(900)
    check('2026 breeding shows 3 pairs', page.locator('.pair-card').count() == 3)
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/races'); page.wait_for_timeout(900)
    check('17 race results', page.locator('tbody tr').count() == 17, str(page.locator('tbody tr').count()))
    page.locator('.seg-btn').nth(1).click(); page.wait_for_timeout(800)
    check('FCI tab lists birds', page.locator('tbody tr').count() >= 5)
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/stats'); page.wait_for_timeout(1500)
    check('stats render for 38 birds', page.locator('.hist-row').count() >= 6)
    page.screenshot(path='/tmp/claude-1000/-home-samir/8788c756-998b-4a82-9d7a-2ebbad47d910/scratchpad/large-stats.png', full_page=True)

    check('zero page errors', not errs, '; '.join(errs[:2]))
    b.close()
print(f'\n{ok} passed, {fail} failed')
exit(1 if fail else 0)
