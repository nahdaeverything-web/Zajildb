import os
"""Test the shrink-clamp hypothesis: does a re-render that shortens the page
throw the user back to the top? Uses JS dispatch (no auto-scroll) so the
result reflects the APP, not the test harness."""
from playwright.sync_api import sync_playwright
BASE=os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'')
with sync_playwright() as p:
    br=p.chromium.launch()
    ctx=br.new_context(viewport={'width':800,'height':1280},is_mobile=True,has_touch=True)
    page=ctx.new_page()
    page.goto(BASE,wait_until='networkidle'); page.wait_for_timeout(800)
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');}""")
    page.reload(); page.wait_for_timeout(1000)

    def probe(route, desc, js):
        page.goto(BASE+route, wait_until='load'); page.wait_for_timeout(800)
        h0=page.evaluate('document.body.scrollHeight')
        page.evaluate('window.scrollTo(0, document.body.scrollHeight*0.7)'); page.wait_for_timeout(300)
        before=page.evaluate('window.scrollY')
        page.evaluate(js); page.wait_for_timeout(600)
        after=page.evaluate('window.scrollY'); h1=page.evaluate('document.body.scrollHeight')
        verdict='JUMP' if before-after>150 else 'ok'
        print(f'  [{verdict:4}] {desc:44} scrollY {before}→{after}   height {h0}→{h1}')
        return before-after>150

    print('=== re-render / shrink probes (clicked via JS, no auto-scroll) ===')
    # races: switch from the 17-row log to the shorter FCI tab
    probe('#/races','races: switch to FCI tab',
          "document.querySelectorAll('.seg-btn')[1].click()")
    probe('#/races','races: switch back to log tab',
          "document.querySelectorAll('.seg-btn')[1].click(); setTimeout(()=>document.querySelectorAll('.seg-btn')[0].click(),50)")
    # pedigree: generation buttons call navigate() with the SAME hash
    probe('#/pedigree/g5-faris26','pedigree: 5→3 generations (navigate same hash)',
          "[...document.querySelectorAll('.seg-btn')].find(b=>b.textContent.trim()==='3').click()")
    # breeding: delete a pair (list shrinks)
    probe('#/breeding','breeding: toggle pair status (re-render)',
          "[...document.querySelectorAll('.pair-card button')].find(b=>/مفصول|نشط/.test(b.textContent)).click()")
    # birds: apply a filter that shortens the list a lot
    probe('#/birds','birds: filter to external only (list shrinks)',
          "const s=document.querySelectorAll('.filter-bar select')[0]; s.value='external'; s.dispatchEvent(new Event('change'))")
    # tools: settings change triggers a full rerender()
    probe('#/tools','tools: change numerals (full rerender)',
          "const s=[...document.querySelectorAll('select')].find(x=>x.value==='western'); if(s){s.value='eastern'; s.dispatchEvent(new Event('change'));}")
    br.close()
