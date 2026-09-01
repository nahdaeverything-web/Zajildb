import os
from playwright.sync_api import sync_playwright

# The shipped datasets carry real uuids (v1.9.1). Python's uuid5 derives exactly
# what tools/idmap.js derives from the same namespace and key, so these suites
# keep naming birds by the readable key that documents what they are.
import uuid as _uuid
_ID_NS = _uuid.UUID('7f3c9a54-2b18-4d6e-9c05-1a2b3c4d5e6f')
def bird_id(key):
    return str(_uuid.uuid5(_ID_NS, key))
ok=fail=0
def check(n,c,e=''):
    global ok,fail
    if c: ok+=1; print(f'  ✓ {n}')
    else: fail+=1; print(f'  ✗ {n} {e}')
with sync_playwright() as p:
    br=p.chromium.launch(); page=br.new_page(viewport={'width':1280,'height':900})
    errs=[]; page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto('http://127.0.0.1:8123/',wait_until='networkidle'); page.wait_for_timeout(800)
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');}""")
    page.reload(); page.wait_for_timeout(1000)
    check('import still lands the full payload verbatim',
          page.evaluate("async()=>(await import('./js/db.js')).allBirds().length")>=38)

    # saveBird called DIRECTLY, no view involved
    r=page.evaluate("""async(a)=>{
        const db=await import('./js/db.js');
        const out={};
        // 1. a chick whose sire is a hen
        try{ await db.saveBird(db.newBird({sex:'cock', sireId:a.lama})); out.henSire='SAVED (bad)'; }
        catch(e){ out.henSire = e.name + ':' + (e.errors||[]).map(x=>x.key).join(','); }
        // 2. a chick with a duplicate ring
        const dup = db.getBird(a.malik).rings[0].raw;
        try{ await db.saveBird(db.newBird({sex:'cock', rings:[{raw:dup,type:'national'}]})); out.dupRing='SAVED (bad)'; }
        catch(e){ out.dupRing = e.name + ':' + (e.warnings||[]).map(x=>x.key).join(','); }
        // 3. same duplicate, caller confirmed
        try{ const b=await db.saveBird(db.newBird({sex:'cock', rings:[{raw:dup,type:'national'}]}),{allowWarnings:true});
             out.dupConfirmed = b? 'saved':'no'; } catch(e){ out.dupConfirmed='REFUSED:'+e.name; }
        // 4. a pedigree cycle
        try{ const m=db.getBird(a.malik);
             await db.saveBird({...db.getBird(a.sheikh), sireId:a.malik}); out.cycle='SAVED (bad)'; }
        catch(e){ out.cycle = e.name + ':' + (e.errors||[]).map(x=>x.key).join(','); }
        return out;}""", {'lama': bird_id('g1-lama'), 'malik': bird_id('g4-malik'),
                           'sheikh': bird_id('g3-sheikh')})
    check('saveBird refuses a hen as sire', r['henSire'].startswith('ValidationError') and 'val.sireIsHen' in r['henSire'], r['henSire'])
    check('saveBird refuses an unconfirmed duplicate ring', r['dupRing'].startswith('ValidationError') and 'val.dupRing' in r['dupRing'], r['dupRing'])
    check('saveBird allows a duplicate ring once confirmed', r['dupConfirmed']=='saved', r['dupConfirmed'])
    check('saveBird refuses a pedigree cycle', r['cycle'].startswith('ValidationError') and 'val.cycle' in r['cycle'], r['cycle'])
    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
