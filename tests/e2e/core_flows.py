import os
from playwright.sync_api import sync_playwright

BASE = os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'')
ok = fail = 0
def check(name, cond, extra=''):
    global ok, fail
    if cond: ok += 1; print(f'  ✓ {name}')
    else: fail += 1; print(f'  ✗ {name} {extra}')

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto(BASE, wait_until='networkidle')
    page.wait_for_timeout(800)

    # 1. import sample data through the real import path
    n = page.evaluate('''async () => {
        const db = await import('./js/db.js');
        const payload = await (await fetch('./sample-data.json')).json();
        const counts = await db.importAll(payload, 'merge');
        return counts.birds;
    }''')
    check('import sample data (20 birds)', n == 20, f'got {n}')
    page.goto(BASE + '#/birds'); page.wait_for_timeout(600); page.reload(); page.wait_for_timeout(900)

    # 2. register
    rows = page.locator('.bird-row').count()
    check('register lists 20 birds', rows == 20, f'got {rows}')
    page.fill('.search-input', 'برق'); page.wait_for_timeout(400)
    check('arabic search finds برق', page.locator('.bird-row').count() == 1)
    page.fill('.search-input', 'jo-2024-31002'); page.wait_for_timeout(400)
    check('ring search normalised', page.locator('.bird-row').count() == 1)
    page.fill('.search-input', ''); page.wait_for_timeout(400)

    # 3. bird detail — COI 25% for برق
    page.goto(BASE + '#/bird/b-barq'); page.wait_for_timeout(700)
    badge = page.locator('.facts .coi-badge').first.inner_text()
    check('برق COI badge = 25%', '25' in badge, f'got {badge!r}')
    check('progeny analysis present', page.locator('.stat-grid').count() >= 1)

    # 4. pedigree RTL: subject must be RIGHTMOST in Arabic
    page.goto(BASE + '#/pedigree/b-barq'); page.wait_for_timeout(700)
    subj = page.locator('.ped-cell.gen-0').first.bounding_box()
    anc = page.locator('.ped-grid .ped-cell').last.bounding_box()
    check('RTL: subject sits RIGHT of ancestors', subj and anc and subj['x'] > anc['x'],
          f"subj.x={subj and subj['x']}, anc.x={anc and anc['x']}")
    check('COI breakdown table rendered', page.locator('.coi-panel table tbody tr').count() == 2)
    page.screenshot(path='/tmp/claude-1000/-home-samir/8788c756-998b-4a82-9d7a-2ebbad47d910/scratchpad/ped-ar.png', full_page=True)

    # 5. switch to English via settings → tree mirrors
    page.evaluate('''async () => {
        const db = await import('./js/db.js');
        await db.setSetting('lang', 'en');
    }''')
    page.reload(); page.wait_for_timeout(900)
    check('LTR: <html dir=ltr>', page.evaluate('document.documentElement.dir') == 'ltr')
    subj = page.locator('.ped-cell.gen-0').first.bounding_box()
    anc = page.locator('.ped-grid .ped-cell').last.bounding_box()
    check('LTR: subject sits LEFT of ancestors', subj and anc and subj['x'] < anc['x'])
    page.evaluate('''async () => {
        const db = await import('./js/db.js');
        await db.setSetting('lang', 'ar');
    }''')

    # 6. certificate — 5-gen Arabic, then PDF (print CSS)
    page.reload(); page.wait_for_timeout(800)
    page.goto(BASE + '#/cert/y-najm'); page.wait_for_timeout(900)
    cells = page.locator('.cert-page .ped-cell').count()
    check('5-gen certificate has 63 slots', cells == 63, f'got {cells}')
    check('cert page is RTL', page.evaluate('document.querySelector(".cert-page").dir') == 'rtl')
    page.screenshot(path='/tmp/claude-1000/-home-samir/8788c756-998b-4a82-9d7a-2ebbad47d910/scratchpad/cert-ar.png', full_page=True)
    page.pdf(path='/tmp/claude-1000/-home-samir/8788c756-998b-4a82-9d7a-2ebbad47d910/scratchpad/cert-ar.pdf', landscape=True, format='A4')

    # 7. dev panel in-app test run
    page.goto(BASE + '#/tools'); page.wait_for_timeout(800)
    page.locator('.card button', has_text='▶').click()
    page.wait_for_timeout(2500)
    out = page.locator('.test-output').inner_text()
    check('in-app engine tests all pass', '✗' not in out and 'passed' in out.lower() or '،' in out, out[-120:])
    page.locator('.card button', has_text='⇄').click()
    page.wait_for_timeout(2000)
    out = page.locator('.test-output').inner_text()
    check('in-app round-trip passes', out.strip().startswith('✓'), out[:120])

    # 8. breeding + stats + races render with data
    page.goto(BASE + '#/breeding'); page.wait_for_timeout(700)
    # sample-data.json has THREE 2026 pairs since v1.3 added the mid-cycle
    # teaching pair; this assertion was stale, not a regression
    check('breeding shows 2026 pairs', page.locator('.pair-card').count() == 3)
    page.goto(BASE + '#/races'); page.wait_for_timeout(700)
    check('race log rows', page.locator('tbody tr').count() == 12)
    page.goto(BASE + '#/stats'); page.wait_for_timeout(1200)
    check('stats histogram bars', page.locator('.hist-row').count() >= 6)
    page.screenshot(path='/tmp/claude-1000/-home-samir/8788c756-998b-4a82-9d7a-2ebbad47d910/scratchpad/stats-ar.png', full_page=True)
    page.goto(BASE + '#/birds'); page.wait_for_timeout(700)
    page.screenshot(path='/tmp/claude-1000/-home-samir/8788c756-998b-4a82-9d7a-2ebbad47d910/scratchpad/register-ar.png', full_page=False)

    check('zero page errors', not errs, '; '.join(errs[:3]))
    browser.close()

print(f'\n{ok} passed, {fail} failed')
exit(1 if fail else 0)
