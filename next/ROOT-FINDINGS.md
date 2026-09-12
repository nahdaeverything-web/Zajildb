# Root and spec findings surfaced by the port

Two kinds of entry, both surfaced by the React port while copying the vanilla
tree and re-proving it against the approved designs:

- **ROOT findings** — inconsistencies in the **vanilla** tree (everything
  outside `next/`).
- **SPEC findings** — defects in an **approved design file** under
  `design/approved/`. Ruled in at 4D acceptance. The specs are frozen, so
  these are not edited either; the port states what it did instead, and why
  the intent was not in doubt.

Neither tree is written to during the port. Each entry names the file and
line, what is wrong, why it matters, and what the port did about it on its own
side. They land in the root `BACKLOG.md` as one docs commit at Phase 7.

Rule for adding to this file: an entry needs a `file:line`, a reproduction,
and the port-side handling. An observation without evidence does not go in.

---

## RF-1 — `tests/e2e/write_boundary.py` hardcodes the server port

**Where:** [`tests/e2e/write_boundary.py:19`](../tests/e2e/write_boundary.py#L19)
```python
page.goto('http://127.0.0.1:8123/',wait_until='networkidle'); page.wait_for_timeout(800)
```
**What:** every other local suite reads `ZAJIL_URL` (29 of 32 files under
`tests/e2e/`); this one does not, so `ZAJIL_URL` has no effect on it.

**Why it matters:** it is the R6 class of defect — a test that talks to a
server it did not start. Point the runner at any other port and this suite
still tests whatever is (or is not) on 8123: a stale server, another
checkout, or nothing. In the port it went to an empty port and failed with
`undefined.importAll`, which is how it was found; against a forgotten server
it would have passed about the wrong tree.

**Port handling:** the copy at `next/tests/e2e/write_boundary.py` reads
`ZAJIL_URL` — a URL-only change, permitted by the Phase 2 order. Root
untouched.

**Fix at source (Phase 7):** `page.goto(os.environ.get('ZAJIL_URL', 'http://127.0.0.1:8123/'), …)` — the idiom its siblings use.

---

## RF-2 — root browser suites exit 0 on assertion failure

**Where:** 28 of the 31 local suites in `tests/e2e/` end by printing a
summary and never call `sys.exit`. Two representatives:
- [`tests/e2e/resurrection.py:127`](../tests/e2e/resurrection.py#L127) — `print(f'\n{ok} passed, {fail} failed')`, last line
- [`tests/e2e/tombstones.py:121`](../tests/e2e/tombstones.py#L121) — same

Only `auth_live.py`, `pull_live.py` and `push_live.py` exit nonzero on
failure.

**What:** the process exit code is 0 whether `fail` is 0 or 20. The ONLY
thing that converts failures into a nonzero exit is the runner —
[`tests/e2e/run_all.py:63`](../tests/e2e/run_all.py#L63) parses the
`… failed` token out of the summary text,
[`:67`](../tests/e2e/run_all.py#L67) flags the suite, and
[`:81`](../tests/e2e/run_all.py#L81) exits 1.

**Why it matters:** anyone who runs a suite directly
(`python3 tests/e2e/tombstones.py`), chains one with `&&`, or wires one into
CI without the runner gets **green on red**. Reproduced during the Phase 2
mutation proof: with tombstones deliberately broken, `resurrection.py`
printed `12 passed, 4 failed` and exited **0**. A suite whose exit code
cannot say "failed" is green-that-proves-nothing outside the one script that
knows to read its stdout.

**Port handling:** `next/tests/e2e/*.py` are verbatim copies except the
module token, so they inherit this; `next/tests/e2e/run_all.py` mirrors the
root runner's parsing and is the gate. The port's own new test
(`next/tests/bridge/react_bridge.py`) exits 1 on failure.

**Fix at source (Phase 7):** append `sys.exit(1 if fail else 0)` after the
summary print in each suite (28 one-line changes), and keep the runner's
parse as belt-and-braces. Then a direct run means what it says.

---

## RF-3 — the free-tier dev project auto-pauses (ops, not code)

**What:** the dev Supabase project (`thfxijqzxzdttsuqriwn`) is on the free
tier, which **pauses a project after ~7 days idle**. A paused project's
hostname is withdrawn from DNS while the `supabase.co` apex keeps resolving.

**How it presented (2026-09-11):** every live suite failed at the first
network call with `AuthError('network')` — `js/db/sync.js:160`, the branch
for a fetch that rejects — from both the port *and* the vanilla tree (root
control). `getent hosts thfxijqzxzdttsuqriwn.supabase.co` returned nothing;
`curl` returned 000 "Could not resolve host". Last live traffic before that
was ~4 Sept. Restoring the project in the dashboard cleared it.

**Why it matters:** it blocks **every** live suite (`auth_live`, `push_live`,
`pull_live`, `live_deployment`) and looks, from the client, exactly like an
outage. Anyone running the live gates after a quiet week will see a red
network failure that no code change can fix.

**Port handling:** none needed — the classification is correct. Recorded so
the next person checks the dashboard before debugging DNS.

**At source (Phase 7 / release):** production runs on **Pro** (release
checklist) and does not pause. For the dev project: either keep it warm
(any authenticated request inside the window) or expect to unpause it before
a live run. Worth one line in the live suites' header comments.

---

## RF-4 — a bird share fails outright when an ancestor's photo is on another device

**Where:** [`js/db/io.js:237`](../js/db/io.js#L237), reached from
[`js/db/io.js:222`](../js/db/io.js#L222) `exportBirdWithAncestry(birdId, { includeMedia: true })`
```js
mediaOut.push({ ...m, blob: undefined, dataURL: await blobToDataURL(m.blob) });
```
and [`js/db/io.js:18`](../js/db/io.js#L18)
```js
function blobToDataURL(blob) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);          // blob is undefined here
  });
}
```

**What:** a media row whose bytes are on **another device** has metadata and no
`blob`. `readAsDataURL(undefined)` throws a `TypeError` inside the promise
executor, so the promise rejects and the **whole export** fails. Not the one
photo: the entire share, birds and pedigree and races included.

**Why it matters:** this is not an edge case, it is the designed steady state.
SYNC-DESIGN §7 is explicit that **metadata syncs and blobs do not**, so every
record pulled from another device arrives exactly this way. A fancier on a
second device therefore cannot share any bird whose ancestor carries a photo
taken on the first. The live app has this today: the profile's «مشاركة»
(`js/views/bird-detail.js:83`) calls the same function with the same options,
and vanilla attaches no rejection handler, so the button does nothing at all —
no file, no message.

**Reproduction** (the port's certificate suite does this, and asserts around it —
`next/tests/e2e/screens/certificate.py`):
```js
const m = await db.addMedia(sireId, 'photo', 'body', 'sire.png', new Blob(['x']));
const row = await db.idbGet('media', m.id);
delete row.blob;                       // what a pull leaves behind
await db.idbPut('media', row);
await db.exportBirdWithAncestry(birdId, { includeRaces: true, includeMedia: true });
// → TypeError: Failed to execute 'readAsDataURL' on 'FileReader'
```

**Port handling:** the root is read-only, so the copy at `next/src/db/io.js` is
**byte-identical to main** and was not touched. What the port changed is its own
side: both share paths now attach a rejection handler and say so —
`next/app/cert/view.tsx:216` and `next/app/bird/view.tsx:116`, raising
`err.exportFailed` («تعذّر تجهيز الملف للمشاركة.»). A share that cannot be made
must not silently do nothing. `next/tests/e2e/screens/certificate.py` asserts the
contract that holds either way: **a share always answers**, with the file or with
the reason.

**Fix at source (Phase 7):** skip the rows with no local bytes and export the rest,
rather than failing the export. The metadata is still worth carrying, so the
receiving device knows a photo exists:
```diff
   if (includeMedia) {
     for (const id of ids) {
       for (const m of await mediaForBird(id)) {
-        mediaOut.push({ ...m, blob: undefined, dataURL: await blobToDataURL(m.blob) });
+        // SYNC-DESIGN §7: metadata syncs, blobs do not. A row pulled from another
+        // device has no bytes HERE, which is normal — carry the metadata and say
+        // the file is elsewhere rather than failing the whole export.
+        mediaOut.push({ ...m, blob: undefined,
+                        dataURL: m.blob ? await blobToDataURL(m.blob) : null });
       }
     }
   }
```
`importAll` already validates every `dataURL` before touching the database
([`js/db/io.js:108-119`](../js/db/io.js#L108)), so the null case must be admitted
there in the same commit:
```diff
-    let blob;
-    try { blob = await dataURLToBlob(m.dataURL); }
-    catch (err) { throw new Error(`bad-media: ${m.name || m.id} could not be decoded`); }
-    if (!blob || typeof blob.size !== 'number') throw new Error(`bad-media: ${m.name || m.id}`);
+    let blob = null;
+    if (m.dataURL) {
+      try { blob = await dataURLToBlob(m.dataURL); }
+      catch (err) { throw new Error(`bad-media: ${m.name || m.id} could not be decoded`); }
+      if (!blob || typeof blob.size !== 'number') throw new Error(`bad-media: ${m.name || m.id}`);
+    }
```
with `media.elsewhereFile` («الملف على جهاز آخر») already in the dictionary for the
receiving end to render.

---

## SF-1 — `certificate-v1.html` puts its phone media query before the base rules it overrides

**Applies to:** `design/approved/certificate-v1.html` **only**. No other approved
spec has this ordering.

**Where:** [`design/approved/certificate-v1.html`](../design/approved/certificate-v1.html) —
the `@media (max-width:700px)` block declares
```css
.zoom-btn{ display:inline-flex; }
.cta{ position:fixed; bottom:0; inset-inline:0; z-index:15; padding:12px 16px calc(12px + env(safe-area-inset-bottom)); }
```
and the base rules that follow it declare
```css
.zoom-btn{ display:none; … }
.cta{ position:sticky; bottom:0; … }
```

**What:** both pairs are single-class selectors, so specificity ties and the
**later** rule wins at every width. The phone rules therefore never apply. In the
prototype as shipped, «تكبير» is `display:none` on every screen size, and the
action bar is `sticky` rather than `fixed` on the phone.

**Why it matters:** the button is the phone's only way to read a scaled-down A4
sheet, and the Phase 4 order names it («mobile scaled preview with «تكبير»»). The
intent is not in doubt from the file itself either: the spec's own
`.opts{ padding: 20px 20px 200px }` and its phone `.opts{ padding:18px 16px 140px }`
exist to clear a bar that is **fixed**, which a sticky bar does not need.

**Port handling:** both phone rules are restated at the end of
`next/app/cert/cert.module.css`, where they win, with the defect named in place.
Nothing else changed. `next/tests/e2e/screens/certificate.py` then measures the
result rather than trusting it: «تكبير» is visible at 430, the action bar reports
`position: fixed`, and ruling C's probe finds the bar and measures a real 299px
clearance above it instead of finding no bar at all.

**Fix at source (design):** move the `@media (max-width:700px)` block after the
base declarations for `.zoom-btn` and `.cta`, which is where every other approved
spec puts its phone block.

---

## SF-2 — the design kit's bird-status list disagreed with the data layer

**RULED at Phase 6 acceptance: the kit was wrong, the data is right, and stored status
lists are NOT migrated. Corrected on `main` in one docs-only commit — the single
authorised edit outside `next/` in the whole port.**

**Where:** [`design/ZAJIL-DESIGN-KIT.md:100-101`](../design/ZAJIL-DESIGN-KIT.md#L100) read
```
· status (نشط/تربية/فريق السباق/ميت/مباع/مفقود)
```
against [`js/db/storage.js:116`](../js/db/storage.js#L116)
```js
const DEFAULT_STATUSES = ['breeder', 'race team', 'young bird', 'stock', 'sold', 'lost', 'dead'];
```
which the dictionary ([`js/i18n.js`](../js/i18n.js), `status.*`) renders as
تربية / فريق السباق / فرخ / احتياط / مباع / مفقود / نافق.

**What:** four disagreements in one line. It invented **«نشط»**, a status the data layer has
never had; it wrote **«ميت»** where the dictionary says **«نافق»**; and it omitted **«فرخ»**
and **«احتياط»**. It also did not mention `REFERENCE_STATUS` («مرجع نسب»,
[`js/db/storage.js:121`](../js/db/storage.js#L121)), which is appended rather than seeded so
it cannot be picked for a real bird by accident.

**Why it matters:** the statuses are not a design list, they are the LOFT'S OWN stored
array — seeded at `initDB()` and carried per loft, so a status the kit names but the data
lacks cannot be rendered without a destructive migration of every existing loft. Four
approved specs draw the «نشط» chip on the strength of that line —
`add-edit-bird-v1.html:199`, `add-edit-bird-v2.html`, `bird-profile-v1.html:217` and
`zajil-prototype.html` — and it is MOCK CONTENT in all four: no build of Zajil, vanilla or
port, has ever rendered it, because there has never been anything to render.

**How it surfaced:** the port's Phase 6 fidelity pass audited all fourteen approved specs
state by state. «نشط» was the only gap that recurred across specs, and four auditors
independently called it a STOP with no authorising ruling. It is the one case in the port
where a spec state had no port state AND the port was right.

**Port handling:** none needed. The status segment and the profile's status chip render the
loft's own list (`next/app/bird/form.tsx`, `next/app/bird/view.tsx`), which is what vanilla
does. 4A acceptance item 4 had already accepted dropping the profile's hero «نشط» chip on
exactly this basis; this finding is the general case behind that one.

**Fixed at source:** yes, and uniquely so — `design/ZAJIL-DESIGN-KIT.md` now carries the
data layer's list verbatim plus a note that the line must match `DEFAULT_STATUSES` and
nothing else. The four specs are frozen and keep their mock chip; the kit now says so.

---

## RF-5 — two version strings that disagree, and a grep that can read a comment

**Where:**
- [`package.json:3`](../package.json#L3) — `"version": "1.4.1"`
- [`sw.js:4`](../sw.js#L4) — `const VERSION = 'zajil-v1.9.1';`
- [`HANDOFF.md:38`](../HANDOFF.md#L38) — `| App version (service worker) | zajil-v1.9.1 |`
- [`tests/e2e/version_display.py:11`](../tests/e2e/version_display.py#L11) —
  `re.search(r"const VERSION = '([^']+)'", open('sw.js').read())`

**What:** two separate problems in the same place.

1. The app's version lives in `sw.js` and is maintained by hand. `package.json` says
   `1.4.1`, five releases behind — so the Node package's version is not the app's, and
   nothing notices. [`BACKLOG.md:301`](../BACKLOG.md#L301) already records a
   HANDOFF-vs-`sw.js` agreement check as unbuilt; this is the same gap with a third
   party to it.
2. The suite reads `sw.js` **relative to the working directory**, so it only runs from the
   repo root. Every other local suite is CWD-independent. Run the root runner from anywhere
   else and this one suite errors on a file that is simply somewhere else — which is how the
   port's Phase 6 gate first reported it, having run the root control from `next/`.
   RF-1 is the same class of defect one level down.
3. The suite's grep is **unanchored** and takes the FIRST match in the file. `sw.js` has
   no comment spelling that assignment out today, so it happens to read the constant —
   but a comment that did would make the suite green about the wrong string. The port hit
   exactly this: `sw/sw.template.js` described the requirement in prose, and the first
   match became `'…'` from the comment. Found because the port's postbuild guard and the
   suite disagreed; a single unanchored reader would not have noticed.

**Why it matters:** #1 is the two-sources-of-truth problem the version machinery exists
to prevent, one level up. #2 is a test that can pass while reading a different value than
the one it is validating — the `version_display` #6 assertion ("the row shows what the
worker reports") would still hold against a string nobody ships.

**Port handling:** the port's version has ONE home, `next/package.json`, and
`scripts/build-sw.mjs` composes `'zajil-v' + version` into the generated worker — so the
package version and the app version cannot diverge. Its copy of the suite anchors the
grep (`re.M` with `^`), and `guards/postbuild.mjs` anchors it the same way, with the
template carrying a note that its own prose must never spell the assignment out.

**Fix at source (Phase 7):** resolve `sw.js` from the file's own location
(`os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'sw.js')`), as the
port's copy does; derive `sw.js`'s VERSION from `package.json` at release time
(or bump both in one commit and guard the agreement, which is BACKLOG.md:301's item), and
anchor the regex in `tests/e2e/version_display.py:11`:
```diff
-SW_VERSION = re.search(r"const VERSION = '([^']+)'", open('sw.js').read()).group(1)
+SW_VERSION = re.search(r"^const VERSION = '([^']+)'", open('sw.js').read(), re.M).group(1)
```
