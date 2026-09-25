# Root and spec findings surfaced by the port

Three kinds of entry, the first two surfaced by the React port while copying
the vanilla tree and re-proving it against the approved designs:

- **ROOT findings** — inconsistencies in the **vanilla** tree (everything
  outside `next/`).
- **SPEC findings** — defects in an **approved design file** under
  `design/approved/`. Ruled in at 4D acceptance. The specs are frozen, so
  these are not edited either; the port states what it did instead, and why
  the intent was not in doubt.
- **TOOLING findings** (`TF-n`) — defects in the machinery used to VERIFY the
  other two. They belong here because a broken tool does not announce itself:
  it reports a clean result and ends the investigation. TF-1 is one that
  invalidated a verification already reported as fact.
- **DEPLOYMENT findings** (`DF-n`) — things true of the two builds only once a
  host is serving them. No file in either tree can show these, because they are
  not properties of a tree. DF-1 was found by deploying and it invalidated the
  phrase "side by side".

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

---

## RF-6 — twelve document-relative URLs, and the blank page they produced

**Numbered RF-6, not RF-5: the Phase 7 acceptance asked for "RF-5", but that number is
already the two-disagreeing-version-strings finding above.**

**FIXED at source on `main` (`a98b228`) — not by changing these twelve, but by removing the
only condition under which they are wrong.**

**Where:** every one of these resolves against the DOCUMENT's url:

| | file:line | value | resolves to, at `/bird/edit` | consequence |
|---|---|---|---|---|
| 1 | [`index.html:18`](../index.html#L18) | `src="./js/app.js"` | `/bird/js/app.js` | **blank page** — the whole app |
| 2 | [`index.html:12`](../index.html#L12) | `href="./css/app.css"` | `/bird/css/app.css` | unstyled |
| 3 | [`index.html:9`](../index.html#L9) | `href="./manifest.webmanifest"` | `/bird/manifest.webmanifest` | no install |
| 4-5 | [`index.html:10-11`](../index.html#L10) | `href="./icons/icon-192.png"` ×2 | `/bird/icons/…` | no icon |
| 6 | [`js/app.js:267`](../js/app.js#L267) | `register('./sw.js')` | `/bird/sw.js` | **the worker can never re-register or update** |
| 7-9 | [`js/views/birds.js:16,121,122`](../js/views/birds.js#L16) | `'./sample-data.json'`, `'./example-loft-large.json'` | `/bird/…` | the teaching loft dies |
| 10-12 | [`js/views/tools.js:374-375`](../js/views/tools.js#L374) | the same two datasets | `/bird/…` | the Tools buttons die |

`import` is **not** affected — a static or dynamic import resolves against the MODULE's url,
measured across all 99 specifiers under `js/**`, every one served correctly from `/js/…`
while the document sat at `/bird/edit`.

**Why they were harmless until now.** Vanilla routes entirely on `location.hash`, so its
document is only ever AT the scope root — where `./` is right. The single code path that
could serve it anywhere else was [`sw.js`](../sw.js)'s navigation fallback, which answered a
cache-missing navigation with the shell at the requested address. That is now a redirect to
the scope root, so the document is never at the wrong url and all twelve are correct again.

**Why it mattered.** The React port creates path documents (`/bird/edit`, `/bird/new`). A
vanilla redeploy over an origin the port has served puts anyone parked on a two-level path
straight into the blank page, and reloading repeats it.

**Fixed at source:** yes — `a98b228`, `sw.js` only, with four assertions in
`tests/e2e/subpath_hosting.py` each proven to fire.

**Two couplings the redirect creates, both currently safe, both measured:**

1. **`tests/e2e/schema_upgrade.py:17` navigates to a deep path on purpose** —
   `page.goto(BASE + '__seed__')`, chosen because it is a same-origin page that does NOT
   boot the app, so `initDB()` cannot create a v2 database before the suite opens v1. Under
   the redirect that path would go to the scope root, which DOES boot the app, and opening
   v1 would block forever. It is safe **only because it is the FIRST navigation in a fresh
   context**, before any worker exists to intercept it, and line 65 boots the app afterwards
   without ever returning. Measured 11/0 with the fix, twice, independently. **Anyone
   reordering that suite so a worker is active first will get a hang with no obvious cause.**
   A comment in place would be cheap insurance; not added here, because it is a second
   change to `main` and only one was authorised.
2. **The tree ships 19 tracked HTML documents under the worker's scope**
   (`design/approved/*.html` and the drafts), so they deploy to `…/Zajildb/design/…`. They
   were **already unreachable** with a worker installed: the baseline answers a navigation
   to one of them with the cached shell, measured by title. The redirect changes the symptom
   from "the app at a lying URL" to "the app at an honest URL"; it does not take anything
   away that was there. If those files ever need to be reachable, the fix is a network-first
   attempt for navigations, which costs offline latency and is a separate decision.

---

## The refuted ruling — recorded because the refutation came from the tree itself

Phase 7 acceptance ruling 6 directed that vanilla's `./js/app.js` be made **root-absolute**
on `main`, so the rollback path would be safe before it was needed. The intent was right and
**the mechanism was refuted by this repository's own assertions**, which is the reason it is
worth writing down.

`tests/e2e/subpath_hosting.py` — eight assertions that predate the ruling — run against a
root-absolute copy of the tree:

```
  ✗ app boots under /zajil/
  ✗ no 4xx/5xx responses   404 …/css/app.css; 404 …/js/app.js
  ✗ service worker scoped to the subdirectory   none
  ✗ manifest resolves
  ✗ 38 birds under subpath
Traceback … line 66, in <module>   Locator.inner_text: Timeout 30000ms exceeded
```

Five failures then a hard crash. The cause: vanilla is served at
`nahdaeverything-web.github.io/**Zajildb**/`, a subpath, so `/js/app.js` leaves the
deployment entirely. Measured at a simulated subpath: blank white page, 0 nav links,
**zero service-worker registrations** — and the same ruling's companion decision (ruling 1)
requires that origin to keep serving as the **export bridge**, the only route from an
existing fancier's records to the new origin. The fix would have taken down the thing the
plan depends on.

Two further facts the ruling could not have known, both measured: there are **twelve**
document-relative URLs and not one (RF-6 above), so `index.html` alone was never enough;
and no static variant works at both prefixes — `<base href="/">` is root-absoluteness
respelled, `<base href="/Zajildb/">` mirrors the break to the apex root.

**Verified in two engines.** Chromium and **WebKit 26.0** — Safari's engine, which is where
these fanciers actually are — agree in all eight cells: patched redirects to the scope root
with six nav links at the subpath and at the origin root, online and offline; baseline stays
on the deep path with zero. One methodological finding came out of it, worth keeping:
**playwright's `set_offline` is unusable with WebKit's service worker.** It breaks navigation
outright — even a plain offline reload at the scope root throws — and it reported the
UNPATCHED tree as passing, which is impossible. Offline was therefore measured by **shutting
the HTTP server down**, a real transport failure that needs no emulation. Any future
WebKit-side offline assertion has to do the same.

**The lesson is about where the knowledge of "where the app lives" belongs.** Root-absolute
paths hardcode an origin layout into the shipped shell, so one `index.html` cannot serve two
deployments. The worker derives it at runtime from `self.location`, so it is correct at any
prefix without being told. That is why the accepted fix is three lines in `sw.js` and not
eight edits across four files.

---

## RF-7 — the register's sort is not total: same-year birds are ordered by uuid

**Not a defect. A design question, recorded so it is a decision rather than an accident.**

**Where:** [`next/app/birds/view.tsx:90-94`](app/birds/view.tsx#L90) — the desktop table's
default sort is `sortK = 'year'`, `desc = true`, comparing the year and nothing else:

```js
return [...filtered].sort((a, b) => { const x = k(a), y = k(b); return (x > y ? 1 : x < y ? -1 : 0) * (desc ? -1 : 1); });
```

**What:** a loft's birds are mostly hatched across a handful of seasons, so most comparisons
are ties. `Array.prototype.sort` is stable, so ties keep source order — and source order is
`db.state.birds`, populated from IndexedDB, which returns rows in **key order: the uuid**.

**Measured.** Eight birds in two years, three trials, ids left to `uuid()`:

```
trial 1 TABLE order: 7,5,1,3,4,6,2,0     map order: 4,7,5,6,1,3,2,0   (by uuid)
trial 2 TABLE order: 5,3,7,1,6,4,0,2     map order: 6,5,4,3,7,1,0,2
trial 3 TABLE order: 5,3,1,7,0,4,2,6     map order: 0,5,3,4,2,1,7,6
```

Years sort correctly every time (2025 group, then 2024). Inside each year the table order
matches the uuid order exactly, in all three.

**Why it is NOT a bug.** A bird's uuid never changes, so for a given loft the order is
**stable** — it does not reshuffle between page loads. It is arbitrary, not unstable.

**Why it is worth a decision.** The order a fancier sees inside a season is meaningless to
them: not by ring, not by name, not by age, not by when it was added. The phone grouping
already has an answer for this — it orders by `createdAt` descending
([`view.tsx:95`](app/birds/view.tsx#L95)) — so the two surfaces disagree about what "no sort
chosen" means. A secondary key on the table (ring, or `createdAt`, to match the phone) would
make them agree. **Vanilla's table should be checked for the same shape before ruling.**

**It is not one comparator, it is a pattern.** An independent audit found the same
tie-falls-through-to-store-order shape at:
[`app/races/view.tsx:77`](app/races/view.tsx#L77) and `:87` (date desc — ties on equal or
empty dates), [`app/breeding/view.tsx:26`](app/breeding/view.tsx#L26) (nest box),
[`app/health/view.tsx:66`](app/health/view.tsx#L66) and
[`app/bird/view.tsx:107`](app/bird/view.tsx#L107) (date desc),
[`app/bird/view.tsx:176`](app/bird/view.tsx#L176) (progeny top five) and `:288` (notes by
`at`). They are latent rather than visible today because imported fixture data keeps the ids
it was created with ([`src/db/io.js:104-106`](../js/db/io.js#L104)), so only records made
with a fresh `uuid()` expose it. **The fix, if ruled, is one clause — a final
`|| a.id.localeCompare(b.id)` — applied consistently rather than per screen.**

**How it surfaced:** `fidelity/loft-home/small-1400.png` was a different picture on every
run. The first hypothesis — colliding `createdAt` in a fast fixture — was wrong, and seeding
`createdAt` changed nothing. Seeding the **ids** made it pixel-identical.

---

## RF-8 — the committed fidelity captures encode the timezone of the machine that made them

**Not a product defect. An artefact defect, and the reason the PNGs cannot be diffed across
machines.**

**Where:** `fmtDate` → `fmtGregorian` ([`src/i18n.js:534-546`](src/i18n.js#L534)) calls
`parseLocalDate`. A **date-only** string is parsed as local midnight and is therefore safe by
design ([`src/dates.js:44-52`](src/dates.js#L44)) — that is what the module exists for. A
value **with a time component** keeps instant semantics, and `toLocaleDateString` then
renders it in the machine's own zone.

**Measured.** `sample-data.json` stores `createdAt: "2026-08-01T09:00:00.000Z"`. At UTC+03
the bird profile renders «في زاجل منذ **1 آب 2026** (18 صفر 1448 هـ)». The same capture taken
under `TZ=Pacific/Midway` (UTC−11) renders «**31 تموز 2026** (17 صفر 1448 هـ)». The
certificate's «سجل موثق … منذ» line shifts identically.

**So the committed baseline is Samir's `+03`.** Anyone running the gate west of roughly
UTC−9 regenerates a different `bird-profile/overview-*`, `certificate/*` and `tools/*`, and
will see them as modified files with no change of their own.

**A frozen clock does not fix it** — `page.clock` sets the instant, not the zone.
`browser.new_context(timezone_id='Asia/Amman')` does, it is one argument, and it is
side-effect-free. It would also produce byte-identical output on this machine, since that is
already the zone here. **Not applied**: it touches the context creation in every suite, and
the Phase 7 close authorised the capture change only. Recorded so it is a decision.

**Related, from the same audit and worth ruling with it:** a `Locator.screenshot()` taken
before a `full_page` screenshot makes the fixed tab bar's inclusion in the full-page image a
coin flip — measured **1 of 6** with element shots first against **6 of 6** without, and
`animations='disabled'` does not change it. `shared_states.py` takes nine element shots
before its full-page shot, which is why `shared-states/full-*` carries a band nobody had
attributed.

---

## RF-9 — `File.text()` returns an EMPTY STRING past 512 MB, and the import trusts it

**Vanilla is exposed and is NOT being fixed here — `main` is the live deployment. Recorded for
the release checklist.** The port has the same bug and it is a RELEASE BLOCKER there, being
ruled separately.

**Where:**

| tree | line | catch? |
|---|---|---|
| vanilla | [`js/views/tools.js:113`](../js/views/tools.js#L113) — `const payload = JSON.parse(await f.text());` | **yes**, `:116-118` toasts `⚠ <message>` |
| port | `next/app/tools/view.tsx:333` — `JSON.parse(await file.text())` | **no** — nothing is surfaced at all |

`importAll()` itself is byte-identical between the trees; the difference is only the handler.

**What.** V8 caps a string at `2**29 - 24` = **536,870,888** bytes. `File.text()` does not throw
past it — **it resolves successfully with `""`**. Measured:

```
bytes=   536869864  File.text() ok=True  len=536869864  truncated=False
bytes=   536870888  File.text() ok=True  len=536870888  truncated=False   <- exactly the cap
bytes=   536871912  File.text() ok=True  len=0          truncated=True
bytes=   559396374  File.text() ok=True  len=0          truncated=True
```

So `JSON.parse("")` throws **`Unexpected end of JSON input`** — a message that describes an
empty file, not a file that was too large. Anyone reading that error would look for a
truncated download.

`new Response(file).json()` fails **identically**, measured on a 587 MB file whose largest
single value was only 2.8 MB — so the cap is on the total decoded text, not on any one value,
and there is no cheap substitution.

**Why it matters.** This is the read half of the migration path. A fancier's whole loft is on
the far side of it. The measured ceiling is **403 MB of photo bytes** (the export runs
1.3337× source), which is:

| typical photo | photos before the wall |
|---|---|
| 8 MP JPEG (~1.5 MB) | 255 |
| 12 MP JPEG (~3 MB) | 127 |
| 48 MP JPEG (~9 MB) | 42 |
| scanned A4 pedigree PNG (~20 MB) | 19 |

Photos are stored **raw** — [`app/bird/form.tsx:240`](app/bird/form.tsx#L240) hands the picker's
`File` straight to `addMedia` with no resize — so a modern phone reaches this with a few dozen
birds. This is not an edge case.

**Vanilla's exposure specifically.** Vanilla can *export* far less than the port (its own
`JSON.stringify` throws around the same size), so a vanilla user is more likely to hit the
write wall first. But vanilla can be handed a file exported by the port, and then this is the
failure — mitigated only by the `catch`, which at least says *something*.

**Not fixed here.** Recorded for the release checklist alongside the vanilla export defect.

---

## RF-10 — the four options for reading past the boundary, and why three were not taken

**Recorded so the rejected ones stay rejected for a reason, and the held ones can be picked up
with their costs already measured.** All figures are from prototypes built and run during the
analysis, not estimates.

### REJECTED — multi-file export

The obvious shape (a manifest plus typed parts) is **dead on arrival**: measured, deployed
vanilla throws `bad-format` on both the manifest and a part. A non-obvious shape *does* work —
every part is itself a complete `zajil-export` payload — and deployed vanilla imports a
three-part set correctly in **merge** mode. That is genuinely the only way to get an 839 MB
loft into the app that is live today.

It is rejected anyway, because of what it does in **replace** mode. `mode === 'replace'` clears
`birds, pairs, raceResults, healthEvents, lofts` and `media` before writing, so **part 2 wipes
everything part 1 imported**. Measured end state of a three-part replace-import: **zero birds
and one orphaned photo, with three «تم الاستيراد» success toasts.** Losing one part of three is
equally silent — two parts import, photos are missing, nothing says so.

**This cannot be closed from the port**: the behaviour is in deployed vanilla. It converts a
loud all-or-nothing failure into a silent partial one, which is the exact failure class this
project spent the whole port hunting. Rejected on those grounds, not on cost.

### HELD — a streaming JSON parser

Feasible, and it is the only option that changes nothing about the file, so both format
directions keep working untouched. Measured costs:

- **No native incremental JSON parse exists.** `Object.getOwnPropertyNames(JSON)` is
  `["parse","stringify","rawJSON","isRawJSON"]`. The transport half is native
  (`file.stream()`, `TextDecoderStream`, `Blob.slice`); the parse half is not.
- A library would be **the project's first runtime dependency** — `next/package.json`
  is exactly next, react, react-dom — and would contradict the reasoning already recorded in
  `README.md` for writing the service worker by hand rather than taking Serwist.
- Hand-rolled: **80 lines as a prototype, 120–150 in production** with escapes and surrogate
  pairs across chunk boundaries. A prototype written during the analysis had a chunk-boundary
  bug, which is the honest measure of the risk.
- It does **not** lower peak memory much: the parsed object still holds every data URL, so the
  ceiling moves but still scales with file size.

One correction worth keeping, because it nearly became a recorded fact: an analysis claimed
603 MB was "reachable" by summing the lengths of 64 MiB slices. **Summing lengths is not
producing a string** — `chunks.join('')` throws `RangeError: Invalid string length`, measured.
Every built-in read path fails past the cap: `blob.text()`, `Response.text()`,
`FileReader.readAsText`, `fetch().json()`, and slice-and-concatenate.

### HELD — a zip container, manifest plus raw blobs

Also feasible, and it has the cleanest ceiling: **154 lines, no dependency**, prototyped and
run in two engines. There is no native zip in any browser (`CompressionStream` supports
deflate/gzip only), but STORE-mode is simple enough to write. It takes the media ceiling from
**403 MB to 4 GB** (~2,000 photos) — the 32-bit fields and uint16 entry count cap it there
without ZIP64. Compression buys nothing, since photos are already compressed; the win is
dodging base64's 1.333× and the string cap entirely.

**Held because it breaks the direction the cutover depends on.** Vanilla cannot read a
container, and cannot be taught to — it is deployed.

### Why both are held rather than built

Neither is justified while **vanilla's export caps lower than the port's import** (RF-11). A
fancier whose loft is past that cannot produce a file from the live app by any means, so a
port-side read improvement does not reach them.

---

## RF-11 — vanilla's export is the binding constraint on migration, at ~384 MB of photos

**Not a code problem. A people problem, and the answer is likely a conversation rather than a
change. Recorded so the cutover plans for it.**

`js/views/tools.js:96` → `downloadJSON` → `JSON.stringify`, which throws
`Invalid string length` past V8's ~512 MB cap. Working back through the measured 1.3337×
inflation, the live app **cannot write an export at all** beyond roughly **384 MB of photo
bytes** — and it fails the way the port's used to: no file, no message.

The cutover direction is **vanilla → port**. So for a loft past that size:

- the fancier cannot produce a migratable file from the app they are using today;
- nothing the port does to its *import* reaches them;
- the port's own export ceiling (403 MB) is irrelevant, because they never get a file to import.

**Not fixed here — `main` is the live deployment.** For a real loft near the line the answer is
operational: export in two passes with some photos temporarily removed, or a one-off assisted
migration. Carried into `CUTOVER.md` as a pre-pilot question, not a work item.

Note that the downscale-on-add work makes this recede for *new* photos on either app, since
`main` shares no code with it — but it does nothing for photos already stored, which is
precisely the population that would be migrating.

---

## TF-1 — `grep` on this machine silently reports nothing for matches that exist

**A tooling finding, not a code one, and recorded here because it invalidated a verification
I had already reported as fact.** Every "I checked and there are none" in this tree is only
as good as the tool that checked, and for a while this one was not good at all.

### The measurement

Three tools, one file, one needle, at the same moment:

```
$ grep -c "data-testid" app/stats/view.tsx
                      ← printed NOTHING, exit status lost in the pipeline
$ /bin/grep -c "data-testid" app/stats/view.tsx
27
$ python3 -c "print(open('app/stats/view.tsx').read().count('data-testid'))"
29
```

Three different answers, and the one on `PATH` gave the answer that ends an investigation.
(`/bin/grep` counts matching LINES and Python counts OCCURRENCES, which is why 27 and 29
disagree and both are right. Nothing explains the first.)

The `grep` on `PATH` is not GNU grep. Earlier in the same session it had emitted
`ugrep: warning: --include=*.css: No such file or directory` for a flag GNU grep accepts, so
it also does not support the same options — a search that looks like it ran, runs, and
reports a confident zero.

### What it actually cost

While porting to `trailingSlash: true`, four `fetch('./example-loft-large.json')` call sites
had to move to a basePath-aware URL. A scan for the remaining ones reported **one** — the
comment inside `src/components/asset.ts` describing the very bug — and that was reported
upward as "app-wide relative fetches remaining: 1, only asset.ts".

It was wrong. `app/stats/view.tsx:123` was a real, unfixed fourth call site. It surfaced
only because the gate failed on it, and it failed with

```
Unexpected token '<', "<!DOCTYPE "... is not valid JSON
```

which is a JSON parser being handed a 404 page and says nothing whatever about the cause.
Had the deploy gone out on that scan, the stats screen's teaching-loft button would have been
dead on the live site with an error naming nothing.

### The rule adopted

**Anything load-bearing — a claim that something does not exist, a count that gates a
decision, a sweep that is about to be reported as complete — uses Python or `/bin/grep`,
never bare `grep`.** Bare `grep` is fine for looking around; it is not evidence.

A zero from a search is a claim about the whole tree, which makes it exactly the kind of
statement that deserves the most suspicion, not the least. The cheap defence is a control: a
search whose expected answer is non-zero, run with the same tool in the same breath. Had the
scan above been paired with "and here is the count of a string I know is there", it would
have caught itself.

### Re-verification

Every grep-derived claim from that session was re-run under Python. All four held —
white-on-gold rules remaining **0**, hard-coded `132px` outside the token **0**, relative
fetches in app code **0**, flat `.html` routes in tests **0**. The conclusions were right; the
basis was unsound, which is a different thing and worth separating.

---

## DF-1 — two apps at different paths on ONE ORIGIN share everything

**A DEPLOYMENT finding: it is not visible in either tree, because it is a property of what
happens when two builds meet on a host. It was found by deploying, and it invalidates the
phrase "side by side".**

Since 2026-09-25 the port is live at `…github.io/zajilv2/` and vanilla at `…github.io/Zajildb/`.
Different paths, **the same origin**. IndexedDB and CacheStorage are partitioned by ORIGIN,
not by path, so the two apps are not neighbours — they are the same tenant.

### The data is shared, completely

Measured in one ephemeral browser profile, against both live deployments:

```
VANILLA  /Zajildb/   dbs ['zajil@v2']
PORT     /zajilv2/   dbs ['zajil@v2']          SAME ORIGIN: True

38 birds loaded through the PORT's own UI   ->   VANILLA sees 38
VANILLA first rows: ['JO-2022-09011 · نسمة', 'BE-2016-6012345 · Remco', 'JO-2022-09021 · ريما']
shared zajil DB: {birds: 38, healthEvents: 7, pairs: 5, raceResults: 17, oplog: 68, lofts: 2}
```

and it is bidirectional — a bird created through vanilla's data layer appeared in the port's
register on the next load, 39 rows.

**The port is therefore not a sandbox.** Anyone who opens `/zajilv2/` in the browser they use
for the real app is running a `2.0.0-dev.1` build against their actual loft, and every write
lands in the one database. "Side by side" describes the URLs, not the storage.

The compensation is real and worth stating: **no migration is needed between these two paths.**
CUTOVER §d's export/import applies to a move to a *different* origin — a custom domain — which
is also the thing that would end this sharing.

### The service workers evict each other, asymmetrically

Each sweeps on ACTIVATE with `keys.filter(k => k.startsWith('zajil-') && k !== VERSION)`, and
activation happens once per install. So whichever worker installs or updates LAST wipes the
other's cache, and the other does not retaliate until it next updates:

```
after VANILLA       ['zajil-v1.9.1']
after PORT          ['zajil-v2.0.0-dev.1']                     <- the port deleted vanilla's
back to VANILLA     ['zajil-v1.9.1', 'zajil-v2.0.0-dev.1']     <- vanilla rebuilt its own, kept the port's
VANILLA reload      ['zajil-v1.9.1', 'zajil-v2.0.0-dev.1']
```

No records are lost: the sweep touches CacheStorage and never IndexedDB. What is lost is
**vanilla's offline capability**, from the moment a user first opens the port until their next
ONLINE visit to vanilla rebuilds it. For an app whose promise is «يعمل دون اتصال», a user who
tries the port on the aeroplane and then wants the real app is the case this describes.

Note this is the mirror image of CUTOVER §0.1 rather than a contradiction of it: identical
version strings meant neither could evict the other, distinct ones mean each can.

### What actually isolates a trial — measured, not assumed

A separate browser profile, or a private window. Nothing about the URL does it. Each Playwright
CONTEXT is a separate storage partition by the same mechanism a profile is, so:

```
A. one partition, port alone
   first boot                      lofts [e27b1afa (unnamed)]      birds 0
   after the teaching loft         lofts [8f268d1b, e27b1afa]      birds 38
B. a FRESH partition, port         lofts [bf00d4c7 (unnamed)]      birds 0   <- sees none of A
   same fresh partition, vanilla   lofts [bf00d4c7 (unnamed)]      birds 0   <- and shares with the port
```

So the honest instruction for trying the port against a real loft is: **use a separate browser
profile or a private window, and expect that inside it the port and vanilla still share.** The
separation is between profiles, never between the two apps.

---

## RF-12 — after loading the teaching loft, new birds are filed under a DIFFERENT loft

**In the shared data layer, so it is present in BOTH trees — `src/db/` is byte-identical to
`js/db/`. Not caused by the deployment; found while investigating DF-1.** This is the R4
pristine-loft class, by a different mechanism than expected.

`initDB()` creates an unnamed default loft on first run and points `currentLoftId` at it
(`storage.js:136-143`). Importing the teaching dataset ADDS the loft the file carries — it does
not adopt it — so `currentLoftId` still names the pristine one, while every imported record
carries the imported loft's id. Measured in the port alone, in a clean partition:

```
1. first boot            lofts [e27b1afa (unnamed)]                    currentLoftId e27b1afa   birds {}
2. teaching loft loaded  lofts [8f268d1b «لوفت إربد التعليمي», e27b1afa] currentLoftId e27b1afa   birds {8f268d1b: 38}
3. one bird added        (same two lofts)                              currentLoftId e27b1afa   birds {8f268d1b: 38, e27b1afa: 1}
```

**So a bird the fancier adds is filed under a loft that holds none of the birds on screen,**
and the loft settings card is editing that same empty loft — name it «لوفت سمير» and the name
lands on the loft containing one bird, while the 38 in the register stay under «لوفت إربد
التعليمي». Nothing warns, because no screen filters by `loftId`: the register shows all 39
rows regardless, so the split is invisible until something cares about lofts, and the things
that will care are club mode and sync attribution.

`dropPristineLoft()` exists for exactly this and is guarded properly (`records.js:442-470`),
but it is reachable **only from sync.js:875**, during first-sync loft adoption. `importAll`
never calls it — see `io.js:264-276`, which repairs a `currentLoftId` pointing at a loft that
no longer EXISTS, and has no case for one pointing at a loft that exists and is empty.

**Not fixed.** Ruled: investigate, report, do not change. Two shapes are available and they are
not equivalent — adopt the imported loft as current (changes what the fancier's own loft is
called), or drop the pristine one when an import brings a named loft (the sync path's choice,
`isPristineLoft` already makes it safe). That is a product decision about whose loft this is.
