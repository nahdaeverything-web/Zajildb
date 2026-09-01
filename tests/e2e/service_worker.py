import os
from playwright.sync_api import sync_playwright

# The shipped datasets carry real uuids (v1.9.1). Python's uuid5 derives exactly
# what tools/idmap.js derives from the same namespace and key, so these suites
# keep naming birds by the readable key that documents what they are.
import uuid as _uuid
_ID_NS = _uuid.UUID('7f3c9a54-2b18-4d6e-9c05-1a2b3c4d5e6f')
def bird_id(key):
    return str(_uuid.uuid5(_ID_NS, key))
ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(); page = ctx.new_page()
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    # seed a SIBLING project's cache on the same origin, as github.io would have
    page.goto(os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+''), wait_until='networkidle'); page.wait_for_timeout(500)
    page.evaluate("async () => { const c = await caches.open('other-project-v1'); await c.put('/sibling', new Response('x')); }")
    page.wait_for_timeout(2500)  # let our SW install/activate
    names = page.evaluate("async () => await caches.keys()")
    check("sibling project's cache survived our activate", 'other-project-v1' in names, str(names))
    check('our versioned cache exists', any(n.startswith('zajil-') for n in names), str(names))
    page.evaluate("""async () => {
        const db = await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(), 'merge');
    }"""); page.wait_for_timeout(1500)
    ctx.set_offline(True)
    page.reload(wait_until='load'); page.wait_for_timeout(1500)
    check('OFFLINE still works after SW changes', page.locator('.bird-row').count() == 38,
          str(page.locator('.bird-row').count()))
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/pedigree/'+bird_id('g5-faris26')); page.wait_for_timeout(1000)
    check('OFFLINE pedigree + COI', '12.5' in page.locator('.coi-headline .coi-badge').inner_text())
    check('zero page errors', not errs, '; '.join(errs[:2]))
    b.close()
print(f'\n{ok} passed, {fail} failed')
exit(1 if fail else 0)
