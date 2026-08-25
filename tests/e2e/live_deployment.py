import os
"""Verify the REAL deployment: secure context, SW install, PWA installability, offline."""
from playwright.sync_api import sync_playwright
URL='https://nahdaeverything-web.github.io/Zajildb/'
ok=fail=0
def check(n,c,e=''):
    global ok,fail
    if c: ok+=1; print(f'  ✓ {n}')
    else: fail+=1; print(f'  ✗ {n} {e}')
with sync_playwright() as p:
    br=p.chromium.launch()
    ctx=br.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,
        user_agent='Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Mobile Safari/537.36')
    page=ctx.new_page()
    errs=[]; bad=[]
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('response', lambda r: bad.append(f'{r.status} {r.url}') if r.status>=400 else None)
    page.goto(URL, wait_until='networkidle'); page.wait_for_timeout(3000)

    check('secure context (HTTPS)', page.evaluate('window.isSecureContext'))
    check('app rendered', page.locator('.nav-link').count()==6)
    check('no failed requests', not bad, '; '.join(bad[:3]))
    sw=page.evaluate("async()=>{const r=await navigator.serviceWorker.getRegistration();return r?r.scope:'none';}")
    check('service worker registered at the right scope', sw.endswith('/Zajildb/'), sw)
    cached=page.evaluate("async()=>{const k=await caches.keys();return k;}")
    check('versioned cache created', any('zajil-' in c for c in cached), str(cached))
    man=page.evaluate("""async()=>{const l=document.querySelector('link[rel=manifest]');
        const r=await fetch(l.href); const j=await r.json();
        return {ok:r.ok,name:j.name,start:j.start_url,display:j.display,icons:(j.icons||[]).length};}""")
    check('manifest valid & installable', man['ok'] and man['display']=='standalone' and man['icons']>=3, str(man))

    # load the teaching loft over the real network, then go offline
    page.locator('.empty-state button').nth(1).click(); page.wait_for_timeout(4000)
    page.reload(wait_until='networkidle'); page.wait_for_timeout(1500)
    check('38-bird example loaded from the live site', page.locator('.bird-row').count()==38,
          str(page.locator('.bird-row').count()))

    ctx.set_offline(True)
    page.reload(wait_until='load'); page.wait_for_timeout(2500)
    check('OFFLINE: app boots with no connection', page.locator('.nav-link').count()==6)
    check('OFFLINE: data intact', page.locator('.bird-row').count()==38,
          str(page.locator('.bird-row').count()))
    page.goto(URL+'#/pedigree/g5-faris26'); page.wait_for_timeout(1500)
    badge=page.locator('.coi-headline .coi-badge').inner_text() if page.locator('.coi-headline .coi-badge').count() else 'none'
    check('OFFLINE: pedigree + COI compute', '12.5' in badge, badge)
    page.screenshot(path='/tmp/claude-1000/-home-samir/8788c756-998b-4a82-9d7a-2ebbad47d910/scratchpad/live-offline.png')
    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
