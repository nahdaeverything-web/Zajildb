import os
"""Isolate REAL scroll jumps: only click controls already visible in the
viewport at the scrolled position, so Playwright's scroll-into-view can't
manufacture a false positive."""
from playwright.sync_api import sync_playwright
BASE=os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'')
ROUTES=['#/breeding','#/races','#/health','#/bird/g5-faris26','#/pedigree/g5-faris26','#/birds','#/stats','#/tools']
real=[]; artifact=[]
with sync_playwright() as p:
    br=p.chromium.launch()
    ctx=br.new_context(viewport={'width':800,'height':1280},is_mobile=True,has_touch=True)
    page=ctx.new_page()
    page.goto(BASE,wait_until='networkidle'); page.wait_for_timeout(800)
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');}""")
    page.reload(); page.wait_for_timeout(1000)
    for route in ROUTES:
        page.goto(BASE+route,wait_until='load'); page.wait_for_timeout(700)
        h=page.evaluate('document.body.scrollHeight')
        if h < 1800: continue
        for i in range(12):
            btns=page.locator('main button:visible')
            if i>=btns.count(): break
            btn=btns.nth(i)
            try:
                label=(btn.inner_text() or '').strip()[:26] or f'#{i}'
                page.evaluate('window.scrollTo(0,600)'); page.wait_for_timeout(200)
                before=page.evaluate('window.scrollY')
                if before<300: continue
                box=btn.bounding_box()
                if not box: continue
                # is it ALREADY on screen? if not, skip — clicking would auto-scroll
                in_view = 0 <= box['y'] and box['y']+box['height'] <= 1280
                if not in_view:
                    artifact.append((route,label)); continue
                btn.click(timeout=2500); page.wait_for_timeout(450)
                after=page.evaluate('window.scrollY')
                if before-after>150: real.append((route,label,before,after))
                if page.locator('.modal-overlay').count():
                    page.keyboard.press('Escape'); page.wait_for_timeout(250)
                if page.url.split('#')[-1]!=route.lstrip('#'):
                    page.goto(BASE+route,wait_until='load'); page.wait_for_timeout(500)
            except Exception: pass
    br.close()
print(f'=== REAL scroll jumps (control was already on screen): {len(real)} ===')
for r in real: print(f'  {r[0]:28} "{r[1]}"  {r[2]}→{r[3]}')
print(f'\n=== skipped as off-screen (would be a test artifact): {len(artifact)} ===')
for a in artifact[:8]: print(f'  {a[0]:28} "{a[1]}"')
