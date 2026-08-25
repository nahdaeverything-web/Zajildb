import os
"""Exhaustive UI sweep: visit every route, click every control, record defects."""
from playwright.sync_api import sync_playwright
import sys, json

BASE = os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'')
ROUTES = ['#/birds', '#/breeding', '#/races', '#/health', '#/stats', '#/tools',
          '#/bird/new', '#/bird/g5-faris26', '#/bird/g5-faris26/edit',
          '#/pedigree/g5-faris26', '#/cert/g5-faris26']
VIEWPORTS = [('tablet', 800, 1280), ('phone', 390, 844), ('desktop', 1280, 900)]
defects = []

def log(kind, where, detail):
    defects.append({'kind': kind, 'where': where, 'detail': detail})

with sync_playwright() as p:
    br = p.chromium.launch()
    for vname, vw, vh in VIEWPORTS:
        ctx = br.new_context(viewport={'width': vw, 'height': vh},
                             is_mobile=(vname != 'desktop'), has_touch=(vname != 'desktop'))
        page = ctx.new_page()
        page.on('pageerror', lambda e, v=vname: log('pageerror', v, str(e)))
        page.on('console', lambda m, v=vname: log('console-error', v, m.text) if m.type == 'error' else None)
        page.goto(BASE, wait_until='networkidle'); page.wait_for_timeout(800)
        page.evaluate("""async()=>{const db=await import('./js/db.js');
            await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');}""")
        page.reload(); page.wait_for_timeout(1000)

        for route in ROUTES:
            page.goto(BASE + route, wait_until='load'); page.wait_for_timeout(700)
            where = f'{vname} {route}'

            # --- layout defects ---
            overflow = page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 1')
            if overflow:
                w = page.evaluate('document.documentElement.scrollWidth'), vw
                log('h-overflow', where, f'scrollWidth {w[0]} > viewport {w[1]}')
            # elements sticking out horizontally
            spill = page.evaluate("""() => {
                const bad = [];
                for (const el of document.querySelectorAll('main *')) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && (r.right > window.innerWidth + 2 || r.left < -2)) {
                        const c = (el.className||'').toString().slice(0,40);
                        bad.push(el.tagName.toLowerCase() + '.' + c);
                    }
                }
                return [...new Set(bad)].slice(0, 5);
            }""")
            if spill: log('element-spill', where, ', '.join(spill))
            # touch targets too small on touch devices
            if vname != 'desktop':
                small = page.evaluate("""() => {
                    const bad = [];
                    for (const el of document.querySelectorAll('main button, main a.btn, main select, main input')) {
                        const r = el.getBoundingClientRect();
                        if (r.height > 0 && r.height < 32) bad.push((el.textContent||el.tagName).trim().slice(0,25));
                    }
                    return [...new Set(bad)].slice(0, 6);
                }""")
                if small: log('small-touch-target', where, ', '.join(small))

            # --- THE SCROLL-JUMP HUNT: click each control, check scroll position ---
            n = page.locator('main button:visible, main .seg-btn:visible').count()
            for i in range(min(n, 14)):
                btns = page.locator('main button:visible, main .seg-btn:visible')
                if i >= btns.count(): break
                btn = btns.nth(i)
                try:
                    label = (btn.inner_text() or '').strip()[:28] or f'button#{i}'
                    # scroll down first so a jump-to-top is detectable
                    page.evaluate('window.scrollTo(0, Math.min(400, document.body.scrollHeight))')
                    page.wait_for_timeout(150)
                    before = page.evaluate('window.scrollY')
                    if before < 50: continue   # page too short to test
                    btn.click(timeout=2500)
                    page.wait_for_timeout(400)
                    after = page.evaluate('window.scrollY')
                    if before - after > 150:
                        log('scroll-jump', where, f'"{label}" scrolled {before}→{after}')
                    # close anything the click opened
                    if page.locator('.modal-overlay').count():
                        page.keyboard.press('Escape'); page.wait_for_timeout(250)
                    if page.url.split('#')[-1] != route.lstrip('#'):
                        page.goto(BASE + route, wait_until='load'); page.wait_for_timeout(500)
                except Exception as ex:
                    msg = str(ex).split('\n')[0][:90]
                    if 'Timeout' not in msg: log('click-error', where, f'{label}: {msg}')
        ctx.close()
    br.close()

by_kind = {}
for d in defects: by_kind.setdefault(d['kind'], []).append(d)
print(f'=== SWEEP: {len(defects)} defects across {len(VIEWPORTS)} viewports × {len(ROUTES)} routes ===\n')
for kind, items in sorted(by_kind.items(), key=lambda x: -len(x[1])):
    print(f'--- {kind} ({len(items)}) ---')
    seen = set()
    for d in items:
        key = (d['where'], d['detail'][:60])
        if key in seen: continue
        seen.add(key)
        print(f"  [{d['where']}] {d['detail'][:130]}")
    print()
json.dump(defects, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
