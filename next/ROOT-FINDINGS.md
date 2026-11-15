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

- **SUPPORT findings** (`SUP-n`) — things that make a CORRECT build look broken on a real
  device, from outside the app. No tree carries them and no assertion can fail on them;
  they are here so the next report with the same symptom is recognised rather than chased.

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

### Addendum 2026-11-13 — the pause was largely a CONSEQUENCE of the missing auto-sync

Supabase pauses a free project on low DATABASE activity. The port never started the background sync loop
(`startSyncLoop()` has no caller; RF-19), so even while Samir used the app daily it made almost no requests:
sync ran only at sign-in and on the button. No auto-sync → no requests → the project pauses → the one manual
press he makes fails → he stops using the app → fewer requests still. RF-3 and the loop gap are ONE causal
chain, not two findings. The October "three-week sync failure" was this chain, not the sync code: a real round
trip on the live project was confirmed on 2026-11-13 once the project was awake.

So the fix is the change set of RF-19 — automatic sync keeps the project awake while the app is in real use (the
suites do not: every one is stub-backed by rule). The chain describes October, when the app was in daily use; the FIRST pause, 2026-09-11 above, came with no
usage at all (last live traffic about 4 September), so it was not caused by the loop gap. A project nobody opens for a week can still pause; that case stops being the thing that silently kills a
loft. **Pro does NOT fix sync and must not be recorded as doing so**: it is justified by no pausing and by backups
(the free tier has none; Pro has daily backups with 7-day retention), both independent of anything in the
client and both mattering once another person's data is on the project — a pre-pilot item (DF-3), off the
critical path. The RF-3 handling text above ("production runs on Pro and does not pause") stands as a fact about Pro,
not as the reason for it.

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

### FIXED IN THE PORT, 2026-09-27 — and NOT in vanilla

**Ruled shape, and it is not a new mechanism:** when an import carries exactly one loft and
the current loft is pristine by the existing `isPristineLoft()` definition, adopt the imported
loft and drop the pristine one with `dropPristineLoft()`. That is precisely R4's rule, which
`sync.js:869-875` already applies when a first sync brings a real loft; it now also applies at
import. `src/db/io.js`, which is already recorded as port-divergent.

**Two refusals, both R4's.** Nothing is adopted and nothing dropped when the current loft is
NOT pristine — named, placed, or holding any record, in which case it is the fancier's and
which loft is current is not ours to decide — or when the import carries SEVERAL lofts, where
there is no basis for choosing and guessing would file their next bird somewhere arbitrary.

`tests/e2e/loft_adoption.py`, 14 assertions, reading the raw object stores rather than the
layer under test. Mutation-proved three ways, each breaking one rule and failing its own
assertion and no other:

| mutation | what failed |
|---|---|
| the `isPristineLoft()` guard removed | the NAMED-loft refusal, and the holds-a-bird refusal |
| `length === 1` widened to `>= 1` | the several-lofts refusal |
| an op and a tombstone written after the drop | `[R4] logged NO op`, `[R4] wrote NO tombstone` |

The third had to be mutated at the CALL SITE, not inside `dropPristineLoft()`: editing
`records.js` fails the `data-layer-identity` guard, which is the byte-identity contract doing
its job — the port cannot mutate a verbatim file even to test it.

### The same defect exists in vanilla and is NOT fixed there

`js/db/io.js` has the identical `importAll`, because that is what byte-identical means. A
fancier loading the teaching loft on the live app today gets the same split. It is **not
fixed**, deliberately: `main` is the deployed application, the defect is invisible until club
mode or sync attribution cares, and it is not worth a release on its own. Carry it into the
next vanilla release that ships for another reason.

---

## TF-2 — every suite serves at the ROOT, where a wrong URL and a right one are the same string

**A TOOLING finding, and the one that let a 404 reach a human.** It is not about a broken
tool this time; it is about a blind spot shared by an entire test tree, and the blind spot is
structural rather than accidental.

### The shape of it

`basePath` is the empty string at the root. So for any link the app renders:

```
at the root       href="/bird/new"   ->  /bird/new          CORRECT
under a prefix    href="/bird/new"   ->  /bird/new          WRONG — the app is at /zajilv2/
                  (what it should be)    /zajilv2/bird/new/
```

The wrong URL and the right one are **the same string** at the root, and every suite in this
tree serves the app at the root. A link that bypasses `next/link` is therefore not merely
untested — it is **unobservable**. No assertion anywhere could have distinguished the two,
because there was nothing to distinguish.

### What it cost

Two shipped controls rendered raw `<a href>` instead of `next/link`, which applies `basePath`
and `trailingSlash` where an anchor is emitted verbatim:

| component | control | rendered | should have been |
|---|---|---|---|
| `src/components/Empty.tsx` | `empty-cta` «أضف أول طائر» — **the only control an empty loft offers** | `/bird/new` | `/zajilv2/bird/new/` |
| `src/components/BackupBanner.tsx` | `backup-warn-act` «تصدير» | `/tools` | `/zajilv2/tools/` |

Both resolved to `github.io/bird/new` — not a route of this app — so both served GitHub's 404
page. **A human found the first one by clicking it**, on the live deployment, with 1876
assertions green and a deploy gate that had passed.

### Why the one suite that could have caught it did not

`tests/pwa/subpath_hosting.py` exists precisely because the app must work under a prefix, and
it builds its own export with `NEXT_PUBLIC_BASE_PATH=/zajil`. It was green throughout. It
exercised the ROUTES under the prefix — navigating to them, asserting assets resolved, the
worker scoped, offline working — and never asked **what the app puts in its links**. Testing
that a route works is a different question from testing that anything points at it.

### The rule adopted

**Anything that produces an internal URL goes through `next/link`.** A raw `<a href>` to an
in-app route is a defect even when it works, because it works only at the root.

And `subpath_hosting.py` now walks every rendered `href` across ten routes in BOTH loft states
— empty and seeded, because the empty state renders controls the seeded one does not, and the
broken control was one of them — asserting each stays under the prefix. Proven to fire by
restoring both raw anchors:

```
✓ links were found in BOTH loft states (else this proves nothing)
✗ every one of the 21 rendered links stays under /zajil/
      'empty-cta' (empty loft) -> /bird/new; 'backup-warn-act' (seeded loft) -> /tools
```

The live deploy gate asks the same question of the deployment (`[B1]`). This one asks it
before the deploy, which is the half that matters.

---

## TF-3 — a new build-output directory must be declared to four tools, with no shared source

**A TOOLING finding, recorded because the first half of it looked finished.**

`scripts/stage-release.mjs` (2026-09-27) writes a verified staging copy of `out/` into
`release/`, inside the project. Four separate tools walk this tree, each with its own ignore
mechanism, its own syntax, and no common source:

| tool | where | what it does with generated output otherwise |
|---|---|---|
| `guards/run.mjs` | `SKIP` set | `✗ no-hardcoded-version  release/sw.js:51` — a guard reporting the generator's own work as a source defect |
| ESLint | `globalIgnores` in `eslint.config.mjs` | **20 errors, 4725 warnings** from minified vendor chunks; fails the gate |
| TypeScript | `exclude` in `tsconfig.json` | `include` is `**/*.js`, so a staging directory is in scope by default |
| git | `.gitignore` | a 139-file build artefact committed to the source branch |

### The part worth keeping

**The guards passing did not mean the tree was clean.** `no-hardcoded-version` fired first,
was fixed, and `node guards/run.mjs` then reported `all guards pass` — which reads like the
end of the problem and was the end of one quarter of it. The ESLint failure surfaced only
because a FULL GATE ran afterwards; had the work been handed over on the strength of the
guards, lint would have failed for whoever ran it next, in generated files they did not write.

The generalisation is not "remember four lists". It is that **a tool reporting success speaks
only for what it inspects**, and four tools inspecting the same tree agree about that tree
only by coincidence. The defence is to run all of them — which is what the gate is — rather
than to trust the one that happens to be fastest.

The reason is recorded in `eslint.config.mjs` beside the pattern rather than only here,
because that is where the next person adding an output directory will be looking.

---

## SEC-1 — the dev test account's password is in a session transcript and must be rotated

**Not a defect in either tree. An operational fact with an expiry date, recorded here because
it is the kind of thing that is remembered for a week and then is not.**

On 2026-09-27 the DEV project's credentials were supplied in a working session so that
CUTOVER §0.3 could be closed, which needs a real sign-in from the live origin. That was a
deliberate choice, made knowingly, and it has consequences that outlive the session:

| value | exposure | action |
|---|---|---|
| `ZAJIL_SUPABASE_URL` | public by design — it is in the deployed `sync-config.js` | none |
| `ZAJIL_SUPABASE_PUBLISHABLE_KEY` | **public by design.** It grants nothing alone: the server denies `anon`, RLS scopes every row to its owner, and public signups are disabled | **none — it does not need rotating** |
| `ZAJIL_TEST_EMAIL` | a real address, in the transcript | judgement |
| `ZAJIL_TEST_PASSWORD` | **in the transcript in clear** | **ROTATE before this account is used for anything beyond this verification** |

The account is a manually-created test user on the DEV project (`thfxijqzxzdttsuqriwn`). While
it holds nothing but probe data on a project only its owner uses, the exposure costs nothing.
It stops being free the moment that account is reused — for a pilot, for a second person, or
on the production project. **Rotate it then, or before.**

`~/.zajil-deploy.env` is mode 600 and is covered by `.gitignore`'s `.env*`; it has never been
committed. Verify with `git log --all --full-history -- '*zajil-deploy.env'` returning nothing.

### A smaller thing, worth knowing before the next such file

The file is plain `KEY=VALUE` with no quoting, and **`source` cannot read it**: the password
contains `#`, which bash treats as a comment, and `)`, which is a syntax error. That format
was suggested in the same session that then failed to source it. Tools that read env files
parse them directly and are fine; shell scripts are not. Either quote the values or parse the
file rather than sourcing it — this session did the latter, so no credential ever reached a
shell command line, a history file, or a process listing.

---

## SF-3 — `add-edit-bird-v2.html` describes the external switch wrongly

**A SPEC finding. The spec is frozen, so it is not edited; the port says what it did instead.**

The approved spec's copy for the «سلف خارج اللوفت» switch reads:

> «سجل مرجعي للنسب فقط — لا يظهر في قائمة الطيور ولا في السباقات.»
> *A pedigree-only reference record — not listed among the birds and never in races.*

**Measured on the teaching loft: all 8 external birds DO appear in the register**, each tagged
«خارجي», with the count line reading «38 طائرًا» — the full loft, references included. The
«الخارجية فقط» filter exists precisely to isolate them.

RULED 2026-10-03: **the behaviour is right and the copy is wrong.** A fancier must be able to
find a bird he marked as a reference; hiding it would make the feature feel like deletion
under another name — which is exactly the confusion the three-way delete dialog exists to
resolve. `form.external.body` in `src/i18n.ext.js` now describes what the app does:

> «سجل مرجعي للنسب — يبقى في القائمة بوسم «خارجي» ويحافظ على شجرات نسله، ولا يُحتسب في السباقات.»

Recorded in `guards/strings.ruled.json` under `add-edit-bird-v2.html`, so the strings guard
accepts the divergence by name rather than by the port quietly matching a spec it disagrees
with. The guard caught this the moment the copy changed, which is the contract working: a
screen cannot drift from its approved spec without a ruling written down.

**The "never in races" half is NOT disputed** and is kept: an external bird is a pedigree
record and is not raced.

---

## SF-4 — the ownership model says external birds have no status; a dead ancestor needs one

**A ruling against a documented model, recorded because the model is in `HANDOFF.md` and that
file is root-owned and not edited during the port.**

`HANDOFF.md:160-166` defines ownership as `external: true` **plus** `status: 'reference'`, and
says explicitly that choosing external *"hides the status field and stores `REFERENCE_STATUS`"*.
The port implemented exactly that, and `tests/e2e/screens/bird_form.py` asserted it as
`[ownership#3] status hidden for an external bird`.

**What it cost:** a fancier who records a pedigree ancestor and later learns it died had no way
to say so. The field was not merely hidden — `app/bird/form.tsx` `collect()` carried an
unconditional `d.external ? REFERENCE_STATUS`, so a status set by any other route was silently
discarded on the next save of that bird through the form.

RULED 2026-10-03: show the field for external birds, with a **narrowed vocabulary**.

| offered | why |
|---|---|
| `reference` | the default, and what every imported ancestor carries |
| `dead` «نافق» | **a fact about the BIRD, not about who owned it** |

| withheld | why |
|---|---|
| `breeder`, `race team`, `young bird`, `stock` | jobs a bird does *in this loft*; a reference bird is by definition not in it |
| `sold`, `lost` | things that happen to a bird **you owned**; you cannot sell one you never had |

### The invariant is relaxed, and here is exactly how far

`src/db/records.js:28-29` still enforces it at CREATION — `newBird()` sets
`external ⇒ REFERENCE_STATUS`, and that file is byte-identical to vanilla's and untouched. Only
a deliberate edit of an existing bird can now produce `external: true, status: 'dead'`.

**Nothing depends on the invariant.** Measured before relying on it: setting an external bird to
`dead` changed neither the register nor the statistics.

```
BEFORE  stats 30 عدد الطيور … لا تشمل طيور المرجع   register 38 rows, ext tags present
set status=dead, external stays true
AFTER   stats 30 عدد الطيور … لا تشمل طيور المرجع   register 38 rows, ext tags present
```

Exclusion keys off `external`, never off `status === 'reference'` — the one place that reads
the status is `loftStatuses({includeReference})`, which only decides what the picker offers.

**ownership#3's intent survives:** `REFERENCE_STATUS` is still out of `DEFAULT_STATUSES` so it
cannot be picked for a real bird, external birds are still excluded from loft statistics, and
the only thing added is the one status that can be true of an ancestor.

The form now derives the displayed chips and the stored value from ONE function,
`effectiveStatus()`, so it cannot show one thing and save another — the first version offered
«احتياط» on a reference bird because it rendered the raw draft instead of what `collect()`
would store.

---

## TF-4 — no suite ever changed the language and then looked at anything but the page

**A TOOLING finding, and the second defect a person found on the live deployment with the
gate green** (1914 assertions, 23 on the deploy gate). Reported 2026-10-04 from a real
session with Arabic selected: the desktop rail read Birds / Breeding / Races / Health /
Statistics / Tools and the backup banner read «More than 30 days since your last export.»,
its full stop on the wrong side, beside an Arabic page.

> **Amended 2026-10-04.** The session behind the report was afterwards attributed to the
> browser's own page translation (SUP-1), which produces the SAME symptom on the SAME two
> surfaces. What follows stands regardless: it was reproduced on the live origin in a
> browser with no translator, and it is fixed. "Step 5 reproduces the report" is what was
> measured; that step 5 was that session is not.

### The mechanism — measured on the live origin before anything was changed

`t()` reads ONE module variable (`src/i18n.js:484`, set by `configure()`). It is not React
state, so a component shows a new language only when something ELSE makes it render again:

| surface | what re-rendered it | so it showed |
|---|---|---|
| a screen (the page body) | every data-layer change (`useZajilStore`) — and saving a setting raises one | the new language, at once |
| the nav — tab bar and rail (`components/Nav.tsx`) | a ROUTE change only (`usePathname`) | the language of its last navigation |
| the backup banner (`BackupBanner.tsx`) | its own boolean flipping — and setting `true` to `true` re-renders nothing | the language it first appeared in, until a reload |

The same seven steps at 1400px and at 430px, on `https://nahdaeverything-web.github.io/zajilv2/`:

| step | `<html>` | page h1 | nav | banner |
|---|---|---|---|---|
| 1 cold load, Arabic | ar/rtl | الأدوات والإعدادات | Arabic | Arabic |
| 2 «English» tapped | en/ltr | Tools & settings | **Arabic** | **Arabic** |
| 3 reloaded, English stored | en/ltr | Tools & settings | **Arabic** | English |
| 4 navigated birds → tools | en/ltr | Tools & settings | English | English |
| 5 «العربية» tapped | ar/rtl | الأدوات والإعدادات | **English** | **English** |
| 6 navigated to birds | ar/rtl | لوفت إربد التعليمي | Arabic | **English** |
| 7 reloaded | ar/rtl | لوفت إربد التعليمي | Arabic | Arabic |

Step 5 reproduces the report. **Not a missing key** — both strings have Arabic and render it at steps
1 and 7. **Not a first-paint race** — a cold load with Arabic stored is correct. **Not a
hardcoded string.** A stale render. And the full stop is not a second defect: at step 5 the
banner is an English sentence in an `rtl` paragraph, so its trailing «.» resolves to the
paragraph's direction and lands on the left (measured: first character x=809, «.» x=806).

Step 3 is the same cause from the other side, and it had a second half: at BOOT
`applySettings()` raised no signal at all, so a device with English stored kept the
prerendered Arabic nav until the next navigation.

### Vanilla does not have it

`rerender()` is `applySettings(); renderShell(); route();` (`js/app.js:230-234`) — the nav is
rebuilt on every language change. The port replaced "redraw everything" with subscriptions
and gave the layout none. Port-only; nothing to record against the root tree.

### Why 1914 assertions did not see it

`screens/tools.py` did switch to English and back. It asserted `<html dir lang>`, one `h1`
and one `h3` — the page body, the one surface that was always right. Nothing asserted the
nav or the banner in any language but the default, the contrast and fidelity suites render
Arabic only, and the rail exists only at >=1100px while most suites run at 430.

### The fix, and the rule

`applySettings()` — the one function that changes the locale — now ANNOUNCES the change
through the layer's own change event, the signal the bridge already carries, at boot as on a
save. `useLocale()` (`src/components/settings.ts`) subscribes a component that reads no data;
the nav and the banner call it. **Anything in the layout that calls `t()` calls `useLocale()`.**

### What holds it

`tests/e2e/screens/language.py`, with a detector DERIVED FROM THE DICTIONARY
(`screens/_language.py`): a visible string "renders in English" when it is the `en` value of
a key whose `ar` differs, an instance of its template, or contains a multi-word phrase of it
— so it needs no list of surfaces and cannot go stale as strings are added. At 430px and
1400px: the reported round trip without a reload, then tab by tab; cold on every route the
export wrote (derived from `out/`); and the reverse direction. Proven to fire:

```
the deployed commit's build (8eeb2fe)        13 passed, 18 failed   nav + banner, both widths
M1  the nav unsubscribed                     17 passed, 14 failed   nav-link only
M2  the banner unsubscribed                  21 passed, 10 failed   backup-warn only
M3  applySettings applies but stays silent   25 passed,  6 failed   the boot path only
the fix                                      31 passed,  0 failed
```

The deploy gate asks the same of the deployment (`live_deployment.py [C]`), through the
language control itself — a production build has no harness globals. Against the live origin
before the fix shipped: `26 passed, 10 failed`, all ten `[C]`.

### Re-verification from the live origin

Deployed 2026-10-04 as `gh-pages ff5f603` from `5bb086a`: all 139 staged files served
byte-identical. `live_deployment.py` — **36 passed, 0 failed**, the twelve `[C]` among them —
and the seven-step measurement above, re-run: every step now shows the nav and the banner in
the language of the page, step 5 included (rail «الطيور … الأدوات», banner «مرّ أكثر من ٣٠
يومًا على آخر تصدير. صدّر نسخة الآن.»).

### Two things seen and deliberately left

- **Both navs carry `aria-label="التنقل"` as a literal** (`components/Nav.tsx`, both `<nav>` elements). It is
  the ruled label and it is not visible text, so nothing above measures it — but an English
  screen-reader user hears Arabic. Raised, not changed.
- **First paint is prerendered Arabic on every device.** The language lives in IndexedDB and
  the export is static, so a device with English stored paints the Arabic shell until the
  layer has booted and then switches. That is inherent to this architecture, not this defect;
  what is asserted is the state after boot.

---

## TF-5 — `tools.py` read an export-progress indicator in four round trips, and the indicator lives for ~320 ms

**A TOOLING finding: the gate's one intermittent failure, three times** — once on 2026-10-05
and twice in the gate runs of 2026-10-07, never when the suite ran alone:

```
  [FAIL] screens/tools.py                        ?  75s
         NO SUMMARY LINE — could not count | Traceback (most recent call last): |
         playwright._impl._errors.TimeoutError: Locator.inner_text: Timeout 30000ms exceeded.
```

A suite that dies without a summary line is a FAILED step (the gate refuses to count it), so
every such run had to be judged by re-running one suite by hand — a gate "green except for
the flake" is a weaker claim than a green gate, and the order of 2026-10-07 wanted the
stronger one.

### The mechanism — measured

The export-all check (`screens/tools.py`, "[pre-launch] while exporting, the button says so")
adds eight 2 MB photos, clicks «تصدير الكل», waits for `[data-testid=export-progress]`, and
then made THREE MORE round trips — the button's label, its disabled state, the progress text.
The indicator is rendered only while the export runs (`app/tools/parts.tsx`,
`busy && progress`); for eight photos that is ~320 ms. When the third read arrived after the
export had finished, `Locator.inner_text` waited its full 30 s for an element that would never
return. Not a product defect: the button DID say «جارٍ التصدير…», DID refuse a second click and
DID report progress — the suite was reading a sentence after the page had turned.

**Made deterministic before changing anything:** a 1 s pause inserted after the indicator
appears produced the identical traceback every time (line 419, the progress read).

### The fix

The three facts are read in the ONE `wait_for_function` evaluation that sees the indicator
appear — label, `disabled`, progress text, in the same frame. The assertions are unchanged.
Proof: the fixed suite passes as is (137/0) and with the same 1 s pause inserted after the
snapshot (137/0) — the pause that broke the old reads no longer matters.

### The rule it leaves

A read of something the page shows only WHILE it works (a busy label, a progress line, a
toast that clears itself) is one round trip, taken when the thing is first seen — never a
`wait_for_selector` followed by separate reads. `wait_for_function` returning the facts, or a
single `evaluate`, is the shape.

---

## TF-6 — the deploy gate read the backend from the deployed config with the wrong shape, routed no stub, and signed in against the real project

**A TOOLING finding, and a breach of the standing rule that live measurements never contact
the real project.** Found 2026-10-07 in the first rehearsal of the gate-aware deploy gate
(`tests/e2e/live_deployment.py`, 24c572e) on the local Pages stand-in.

### What happened — measured

The deploy gate reads the backend host from the DEPLOYED `sync-config.js` so that it can
answer it with a stub through request interception. It read it with the committed source's
shape, `url: '…'`. The injected line is JSON — `"url":"…"` (`scripts/inject-config.mjs:104`) —
so on a configured build the parse found nothing, `BACKEND` was `''`, `stubbed()` routed
nothing, and the gate's sign-in (`gate@zajil.test` / `pw`) went where the app sends it: the
dev project's `/auth/v1/token`. The project refused it, the gate stayed, and the suite died at
a 30 s wait with no summary line.

What reached the real project: password-grant requests with a made-up address, from the
rehearsal's first three contexts before the crash. Failed logins; nothing read, nothing written,
no row touched. The rule was still broken, and broken silently — a reader of the traceback saw
a timeout, not an escaped request.

### The fix, proved on the stand-in

- Both shapes are parsed (`"url":"…"` and `url: '…'`).
- **THE NET.** Every request to the backend host family that the stub does not answer is
  aborted on the device and counted; the gate asserts the count is zero («every request to the
  backend host was answered by the stub — nothing reached the real project»). Registered beneath
  the stub, so it is the fallback for any third shape, any new endpoint, any mistake of this
  kind. With the old parse put back on purpose, the sign-in now gets «لا يوجد اتصال» — the
  request aborted, never sent — and the gate reports it as a counted failure, not a crash.
- The COLD (no worker) walk signs in through the gate once, so "six nav links at each deep
  link" still proves the whole app at that route rather than the sign-in screen.

Stand-in rehearsal after the fix: 39 passed, 0 failed (91a0c17).

### The rule it leaves

A measurement that intercepts the backend proves it intercepts: a catch-all beneath the stub
that aborts and counts, asserted empty at the end. "No stub matched" must be a failure the
suite reports, never a request that leaves.

**RULED 2026-10-08: THE NET stays permanently, and it should apply to every stub-backed run,
not only the deploy gate.** Where it stands on that date, measured: eleven files route a stub;
the net is in ONE, `live_deployment.py` — the only run against a CONFIGURED build, where the
app itself knows the real host. The other ten run the harness build, which the postbuild guard
`no-sync-config-in-build` proves carries no endpoint, with a made-up host injected by init
script (`https://stub.zajil.test`, `https://stub.example.test`). Probed on that build with the
family catch-all beneath the stub, through sign-in, a sync, an edit, a second sync and
sign-out: the stub answered 4 requests, **0 escaped to the backend family**. They cannot address
the real project by construction; they did not yet assert it.

**RULED 2026-10-08 and BUILT the same day: the shared net, in all eleven.** `tests/e2e/_net.py`
— `NET.arm(check=check, ctx=…)` on every context BEFORE the suite's stub route (Playwright
matches routes newest-first, page routes before context routes, so the net is the fallback
beneath the stub); each escape is aborted on the device and FAILED AT ONCE through the suite's
own `check()`; `NET.assert_empty(check)` is the zero assertion before each summary line. At
once, because a suite whose sign-in was just aborted dies before its summary (measured on
`gate.py` and `sign_in.py`: the end-of-suite assertion never printed; the first version of the
helper only recorded). `service_worker.py` stubs files, not the backend — armed all the same.

Proven to fire, each suite's app config pointed at the host family with its stub left on the
fake host (verbatim):

```
=== MUTATED sign_in.py (app config → the host family; stubs on the fake host): exit 1
  ✗ [NET] a request to the backend host family was answered by NO stub — aborted on the device, never sent: POST https://mutation-never.supabase.co/auth/v1/token?grant_type=password
=== MUTATED gate.py (app config → the host family; stubs on the fake host): exit 1
  ✗ [NET] a request to the backend host family was answered by NO stub — aborted on the device, never sent: POST https://mutation-never.supabase.co/auth/v1/token?grant_type=password
=== RESTORED, clean runs:
sign_in.py: exit 0 → 31 passed, 0 failed · NET: 1 ✓ / 0 ✗
gate.py: exit 0 → 25 passed, 0 failed · NET: 1 ✓ / 0 ✗
```

The rule for a new suite: if it stubs the backend, it arms the net; if it runs against a
configured build, the net is what stands between a wrong stub and the real project.

**The lesson of the first proof (recorded at the ruling's request).** The first mutation
pointed `gate.py` at the host family and the suite died at its seed sign-in — a traceback,
no summary, the `[NET]` line never printed. The escape had happened and had been aborted, but
it READ as a crash, not as a failure, and a reader of that output could not tell the two
apart. Two things fixed that: the proof moved to a suite whose sign-ins are checks rather than
seeds, and `arm()` took the suite's own `check()` so that an escape fails the suite it
happened in, at the moment it happens, counted in that suite's tally — whatever the suite does
afterwards. A guard that only speaks at the end speaks only to suites that reach it.

The runner's own defect this uncovered is TF-8.

---

## TF-7 — the deploy pipeline's "verify" step ran the injector again, and the injector's own `--check` could not read what it writes

**A TOOLING finding in the deploy pipeline itself.** Found 2026-10-07 by the byte comparison
after the gate deployment: 157 of 158 served files identical to the staged release, and
`sync-config.js` not.

### What happened — measured

Two scripts have a verify mode and they are not the same flag: `scripts/stage-release.mjs
--verify-only <dir>` checks a staged directory (worker prefix, root-absolute references,
`.nojekyll`, source maps); `scripts/inject-config.mjs --check <dir>` checks an injected
config. The pipeline notes said "`--verify-only release`" after the injection, and on
2026-10-07 that was run against `inject-config.mjs`, which does not know the flag, ignores
it, and injects. So the release was injected twice and the deploy clone three times:

| copy | injection stamps | config line |
|---|---|---|
| the previous deployment (gh-pages 0e917e4) | 1 | correct |
| `release/` after stage → inject → "verify" | 2 | correct |
| the clone after copy → "verify" → push (gh-pages 5cfa9af) | 3 | correct |

The injector REPLACES the config line and APPENDS its comment stamp, so every copy carried
one correct config and the served app was right (the live deploy gate parsed and stubbed it,
39/0). The bytes were still not the artefact the pipeline claims to deploy.

Then the real check was run, and it failed on a correct file: `inject-config.mjs --check`
parsed `url: '…'` — the committed source's shape — while the line the same script writes is
JSON, `"url":"…"`. The injector's verifier had never been able to verify an injected file
(the same shape mistake as TF-6, in the other direction).

### The fix, proved

- `--check` parses both shapes (8b16942). Proved: the injected release and the served three-stamp copy pass
  with their values shown; the committed-empty source still reports EMPTY; a file with the
  config line removed still fails.
- The release's `sync-config.js` was rebuilt from the same build's empty copy and injected
  ONCE (one stamp, 40 lines, the other 157 files untouched), verified by BOTH verifiers —
  `stage-release.mjs --verify-only release` with `NEXT_PUBLIC_BASE_PATH=/zajilv2` set (without
  it the verifier assumes a root deployment and rightly refuses the worker), and
  `inject-config.mjs --check release` — scanned again (15/0), and redeployed.

### The rule it leaves

The deploy pipeline, in order, with each flag belonging to the script named:
`NEXT_PUBLIC_BASE_PATH=/zajilv2 node scripts/stage-release.mjs` → `node scripts/inject-config.mjs
release` (env loaded by the redacting wrapper) → `NEXT_PUBLIC_BASE_PATH=/zajilv2 node
scripts/stage-release.mjs --verify-only release` → `node scripts/inject-config.mjs --check
release` → the staged-bytes scan → the same two verifiers on the deploy clone → push. A flag
is read from the script's usage block, never from notes.

Seen and left: `--check` on a config whose values are EMPTY exits 0 with «EMPTY» printed —
true of the committed source, and a pipeline that forgot to inject would pass it. The
staged-bytes scan and the live deploy gate both catch that case; not changed here.

---

## TF-8 — `run_all.py` printed a suite `[ok  ]` on exit 0 with no summary line: the UNCOUNTABLE class, in the runner

**A TOOLING finding in the ported runner, found 2026-10-08** when `tests/e2e/_net.py` arrived
and `run_all.py` ran it as a suite:

```
  [ok  ] _net.py                    (no summary — suite errored)
  517 assertions passed, 0 failed, 0 suite(s) errored, 5 skipped
```

"ok" and "errored" on the same row, and the total unmoved. Two defects: `SUITES` was every
`*.py` in the directory but `run_all.py` and the opt-ins, so a helper was a suite; and the flag
was `ok` when `failed == 0 and returncode == 0`, so a suite that printed NO summary and exited
0 passed with nothing counted — the class `scripts/gate.mjs` refuses on principle ("a step
whose summary it cannot read is a FAILURE, not a zero") and the class TF-5 was about. The
runner was not honouring the gate's own rule. A suite that never reports read as a pass.

### Whether any past run_all green hid a suite on that path — measured

It would have taken a `*.py` in `tests/e2e/` that ends with exit 0 and no summary line.

- **Every root suite's summary print is its unconditional last statement** (all 28 files,
  `print(f'\n{ok} passed, {fail} failed')` or the `passed/failed` twin), and none has an early
  `sys.exit(0)`, `exit()` or `os._exit(0)`. A suite that dies by exception exits 1, which the
  runner already failed; a suite the runner times out raises in the runner itself.
- **No non-suite `*.py` ever lived directly in `tests/e2e/`** (`git log --all --diff-filter=A`
  over the branch's history): every file ever added there is a suite, or `run_all.py`. The only
  helpers ever, `screens/_language.py` and `screens/_layout.py`, live in `screens/`, which the
  runner never globbed.
- **Every row reports its own count.** The clean run after the fix lists 23 suites, each with
  its own `N passed, 0 failed`, totalling 517 — exactly 511 (every total recorded before the
  net) + 6 (one `[NET]` assertion in each of the six root suites that stub the backend).

So the path was unreachable before today, and `_net.py` on 2026-10-08 was the first and only
file to take it. Past run_all greens are not weakened by this; the runner was wrong all the
same, and the next helper or the next early-exiting suite would have passed silently.

### The fix, proved

`_name.py` is a helper, never a suite — the convention of `screens/` and `sync/`; and no
summary line is a FAILURE. Proved: a temporary suite that prints nothing and exits 0 →
`[FAIL] zz_nosummary.py (no summary — suite errored)`, exit 1, `_net.py` not listed; removed,
the clean run is `517 assertions passed, 0 failed, 0 suite(s) errored`, `_net.py` not listed.

### The rule it leaves

A runner counts what a suite REPORTS, never what it does not: a row with no summary is a
failure of the run, whatever the exit code. The same rule stands in `scripts/gate.mjs`,
`tests/e2e/run_all.py` and, since TF-5, in how a suite reads a thing that lives only while
the page works.

---

## TF-9 — two RF-18 proofs read as red for the wrong reason: a mutant that died on a timeout, and a page-error check over an empty list

**A TOOLING finding in `tests/e2e/screens/example_remove.py`, found 2026-10-30** on re-reading the RF-18
mutation output under the discipline *a mutation must reach and fail its ASSERTION*:

1. **The R1 mutant never reached an assertion — twice.** The first form (the `allowWarnings` literal
   deleted) stopped at the prebuild guard `allow-warnings-bounded` — build exit 1 in 1 s, the harness never
   built — and was reported red. The corrected form (the flag not passed at the call site, the literal left
   in place, so the guard passes) reached the suite and died in `ui_remove()` on a raw
   `wait_for_selector('[data-row=example-remove]', state='detached', timeout=120000)`: a Playwright
   timeout traceback after 200 s (`242 × locator resolved to visible <details …>`), no summary line, no
   assertion named. Red for the wrong reason, both times. Only R2 (the catch silenced) was a proof.
2. **The suite's last check could not fail.** `check('zero page errors', not any(getattr(x, 'errs', [])
   for x in []))` — every device page collected its errors (`pg.errs`), but no list of pages existed, so the
   check iterated over `[]` since the suite was written on 2026-10-14. The pre-fix RF-18 run, which raised
   `PAGEERROR: zajil/validation-failed` on the device, would have passed it.

### Fixed 2026-10-30

- `ui_remove()` waits, **bounded and non-raising**, for the row to detach OR a failure toast («لم تُزل …»)
  to appear, and returns a third value: whether the row is gone. `[one]` and `[shape]` gain a named
  completion check; a removal that never completes is now a `✗` with the toast as evidence, never a
  traceback. (`[both]` and `[own]` already asserted the row gone through `row_present()`.)
- `PAGES` holds every device page; the final check reads their lists and prints the first three errors.
- Suite 46 → 48 checks.

### The three proofs, verbatim (`scratchpad/mutate_rf18b.py`: each mutant is built, run, restored)

```

══ R1 the flag not passed to the removal's reference flips (the shipped defect; the INTERNAL literal stays, so the prebuild guard passes)  (build exit 0, suite exit 1, 80s)
   ✗ [shape] the removal RAN TO COMPLETION — the row detached, no failure toast (R1 fails here: the flag not passed)  لم تُزل البيانات التجريبية — لم يتغيّر شيء. السبب: سجلّ لم يجتز التحقق (رقم الحلقة JO-2026-13002 مستخدم لطير آخر (نجمة ٢٦).
   ✗ [shape] 47 deleted — 29 example birds remain, every one a reference bird  (76, False, 78)
   ✗ [shape] his record inside the teaching loft was re-filed to his loft, which is current  ([['حمّار-2', '8f268d1b-3dbe-57be-8d77-ede52297a2cd'], ['حمّار-1', 'b51a8c17-e73f-40dd-a22a-b4e9fdcab90d']], {'8f268d1b-3dbe-57be-8d77-ede52297a2cd': 'لوفت إربد التعليمي', 'b51a8c17-e73f-40dd-a22a-b4e9fdcab90d
   ✗ [shape] both teaching lofts gone, tombstoned, the toast reports 47 and 29  (0, 'لم تُزل البيانات التجريبية — لم يتغيّر شيء. السبب: سجلّ لم يجتز التحقق (رقم الحلقة JO-2026-13002 مستخدم لطير آخر (نجمة 2')
   44 passed, 4 failed
   verdict: PROOF — reached and failed its assertion(s)

══ R2 the catch no longer reports — destructive() rethrows without a toast  (build exit 0, suite exit 1, 82s)
   ✗ [shape · invariant] a removal that cannot proceed SAYS SO — a toast naming the reason, nothing changed  ('', 78, 0, ['zajil/validation-failed'])
   ✗ zero page errors across 10 devices  ['zajil/validation-failed']
   46 passed, 2 failed
   verdict: PROOF — reached and failed its assertion(s)

══ R3 a page error planted after a successful removal (proves the page-error check reads real lists, TF-9)  (build exit 0, suite exit 1, 82s)
   ✗ zero page errors across 10 devices  ['MUTATION: planted page error', 'MUTATION: planted page error', 'MUTATION: planted page error']
   47 passed, 1 failed
   verdict: PROOF — reached and failed its assertion(s)

══ RESTORED (build exit 0): 48 passed, 0 failed
```

Each mutant built (the guard is not what stopped it), reached the suite, failed named checks, and printed
its summary line. R2 now trips two checks: the invariant's, and — because an unhandled rejection is a page
error — the page-error check that was blind before. R3 exists only to prove the page-error check reads real
lists. After restore: 48 passed, 0 failed.

### The guard `allow-warnings-bounded` — its blind spots, declared (2026-10-30)

It is a regex over source text: per file under `src/` and `app/`, the count of `allowWarnings\s*:` minus
`allowWarnings\s*:\s*false`, pinned per ruled file; plus the literal `const INTERNAL = { allowWarnings:
true };` in `src/example-data.js`. A `!0` passed its first draft, which matched only `true`; it now counts any
non-`false` value. What it still cannot see:

1. **Shorthand and computed keys** — `{ allowWarnings }` (a true variable in scope), `{ ['allowWarnings']:
   true }`, `{ ['allow' + 'Warnings']: true }`: no `allowWarnings:` text, uncounted.
2. **Assignment and defaults** — `opts.allowWarnings = true`, `Object.assign(opts, …)`,
   `Object.defineProperty`, `function f({ allowWarnings = true } = {})`: uncounted.
3. **The option object travelling** — it pins the literal but counts no USE of `INTERNAL`: a third
   `saveBird(x, INTERNAL)` in the same file, `export { INTERNAL }`, `{ ...INTERNAL }` in another file, or
   `INTERNAL.force = true` (the object is not frozen) are all invisible to it.
4. **Counts, not sites** — a pinned file keeps its count if a use moves to a different save path in the same
   file, or if a pinned doc comment (`records.js`, `validate.js`, 1 each) is deleted and a real use added.
5. **Scope** — `src/` and `app/` only, `.js .mjs .ts .tsx` only: a `.jsx`/`.cjs` file or a new top-level
   directory is unscanned (tests set the flag freely, by design).
6. **Not its subject** — `{ force: true }` skips errors AND warnings in `classifySave`; it has no caller in
   `src/` or `app/` today (two doc comments) and the guard does not bound it. Nor does the guard see
   `idbPut()` and `importAll()`, which write without `classifySave` at all, by design.

What it sees conservatively: any non-`false` value counts (`true`, `!0`, a variable, `Boolean(x)`), so those
fail safe; text in comments and strings counts, so a commented-out use fails safe too. A guard with declared
gaps, as ruled, rather than one that reads as airtight. Not rewritten; an AST-based check is a later item.

---

## RF-13 — a second account signing in on a device inherits the first account's loft, and pushes it under its own name

**In the shared data layer — `js/db/sync.js:183` is the same `signIn()` — so it is present in
BOTH trees. FIXED IN THE PORT 2026-10-05; NOT in vanilla.** Found by the read-only audit of
2026-10-05, while measuring what the app does with and without a session.

### The defect

`signIn()` stored whatever session the server returned. It never compared the incoming user
with the owner of the data already on the device — and sign-out deliberately keeps all of it:
the records, the unpushed ops, `syncCursor`, `lastAckedSeq`, `lastSyncAt`. So the next account
to sign in was handed the previous one's loft, op log and cursor, and synced with them.

### Measured before the fix — two shapes, one defect

On a local build, with a stub modelling the real table (owner-only rows, ONE global sequence
— `docs/SYNC-DESIGN.md:84-152`). Account B has a loft on the server; account A used the device,
left two edits unpushed and signed out; then B signs in:

```
✗ BEFORE ANY SYNC: the only thing asked of the server was the token
      [('TOKEN', ''), ('GET', 'cursor>7: 0'), ('POST', ['أ-4 غير مرفوع', 'أ-5 غير مرفوع'])]
✗ sync_records for account B is UNCHANGED      3 rows 215febfd14ac  ->  5 rows 00f5cbc4afa2
✗ no session was stored                        signedIn=True tokens=2 account=b@zajil.test
```

A's two edits were uploaded into B's account; B's own rows, numbered below A's cursor, never
arrived; the device went on showing A's five birds under B's name.

On the DEPLOYED build (`gh-pages 7c50004`, backend stubbed by interception), where A's cursor
happened to be 0, the same defect took its other shape — a silent MERGE:

```
landed on            : /zajilv2/tools/
a decision is shown  : NO — nothing was asked
backend calls as B   : [('TOKEN', ''), ('GET', 'cursor>0 -> 68 row(s)'), ('POST', '1 row(s): lofts')]
the device now       : 58 birds · lofts ["لوفت إربد التعليمي", "لوفت أ — بعد التعديل"] · account b@zajil.test
server, B  before    : 68 rows · sha256 acb9fbd704a4e0b3
server, B  after     : 69 rows · sha256 9dc7eef350f7c25f   CHANGED
```

### RULED 2026-10-05, and what was built

- **The owner is recorded on the device**, as two settings: `dataOwnerId`, and
  `dataOwnerHint` — a masked address, `s•••@gmail.com`; the full address is not kept past
  sign-out and never was. **Why settings, and why outside `AUTH_SETTING_KEYS`:** sign-out
  nulls exactly those four keys, so anything else in the store survives it by construction —
  and the store already holds the things the record qualifies (`syncCursor`, `lastAckedSeq`,
  `lastSyncAt`), each of them bookkeeping about ONE account's server state. Settings are also
  never synced and never exported, so the record cannot ride a backup to another device.
- **`signIn()` compares, before it stores the session.** The same account proceeds exactly as
  before. A different one throws `AuthError('owner')` with the masked hint and stores nothing
  — an unstored session cannot sync, which is the whole guarantee: no merge, no push, no pull,
  nothing cleared. A recorded owner needs a positively matching id.
- **The sign-in screen puts the decision** (the shared three-way dialog): the previous
  account by its masked hint, and two ways forward — «تصدير البيانات», which returns to the
  decision, and «مسح والدخول», which asks a second time naming what goes. Cancelling leaves the
  device exactly as it was. There is no fourth path.
- **`clearLocalData()` is the only way ownership changes**, and is reached only through that
  choice: records, photos, op log, tombstones, snapshots and every setting about the data go;
  the device's identity and preferences stay; `initDB()` then runs as on a first launch, so
  the next cycle is a real first login. Nothing is logged and nothing is sent — the server
  hears of no delete, because none of it was the new account's to delete.
- **No recorded owner — every device today — adopts the first account that signs in.** For a
  device with a session older than the record, the session names the owner: it is written
  down by the next sync, and by sign-out before the session is cleared; and signing in OVER a
  live session of another account is stopped like any other collision. *(Narrowed 2026-10-07,
  below: the op log names the owner too, so only a device never signed in adopts.)*

### What holds it

`tests/e2e/screens/account_collision.py` — 39 assertions; "unchanged" is a digest of an
account's rows, not a count.

```
the pre-fix build                              11 passed, 28 failed
M1  THE COMPARISON removed from signIn()       17 passed, 22 failed   B's rows 3 -> 5; no decision
M2  clearLocalData() keeps the op log          35 passed,  4 failed   A's six rows pushed as B, then pulled back
M3  sign-out no longer writes a legacy owner   37 passed,  2 failed
M4  a live session no longer names the owner   37 passed,  2 failed
M5  a sync no longer establishes ownership     38 passed,  1 failed
the fix                                        39 passed,  0 failed
```

One existing assertion had to say what it meant: `sync/config_injection` pinned the WHOLE of
`sync.js` to vanilla's, when its claim is about one function — `syncConfig()` reads the
config at call time, as root does. It now compares that function, byte for byte, and was
proven to fire by changing one character inside it.

### Re-verification from the live origin

Deployed 2026-10-06 as `gh-pages cd732d5` from `b9423c8`: 160 of 160 staged files served
byte-identical; `live_deployment.py` 36 passed, 0 failed. The same two-account measurement
as the BEFORE above, on the deployed build:

```
landed on            : /zajilv2/sign-in/
a decision is shown  : هذا الجهاز يحمل بيانات حساب آخر / الحساب السابق: a•••@zajil.test / …
backend calls as B   : [('TOKEN', '')]
the device now       : 20 birds · lofts ["لوفت أ — بعد التعديل"] · unpushed 1 · signedIn false · owner user-A
server, B  before    : 68 rows · sha256 acb9fbd704a4e0b3
server, B  after     : 68 rows · sha256 acb9fbd704a4e0b3   UNCHANGED
CANCEL  -> signed in: False · birds 20 · unpushed 1 · B calls so far: [('TOKEN', '')]
EXPORT  -> 20 birds, loft ['لوفت أ — بعد التعديل'] · the decision is asked again: True
CLEAR   -> 38 birds · lofts ["لوفت إربد التعليمي"] · account b@zajil.test · owner user-B
        -> calls as B : [('TOKEN', ''), ('GET', 'cursor>0 -> 68 row(s)')]
        -> server, B  : UNCHANGED   · server, A: UNCHANGED
```

### The same defect exists in vanilla and is NOT fixed there

`js/db/sync.js` is no longer byte-identical to `src/db/sync.js`; the divergence is declared in
the `data-layer-identity` guard and recorded in `PORT-COMPLETE.md`. Vanilla signs in from its
tools card with the same `signIn()`, so two accounts on one device behave there as measured
above. Not fixed, deliberately: `main` is the deployed application. Carry it into the next
vanilla release.

### Follow-ups named by the sign-in-gate ruling (2026-10-07) — recorded, NOT built

- **The double loft after export → clear → import.** Measured 2026-10-07: a fancier who
  cannot recall his address can export from the gate, clear the device, sign in as another
  account and import the file — and the loft then lives twice on the server, once under
  each account, with nothing telling him so. A line of copy on the import or the clear,
  warning that the original stays under the old account, is wanted; to be ruled separately.
- **An admin route from a device's user id to an address.** The device keeps the previous
  account's id (the owner record, or the op log), never the address, so a person who has
  forgotten which address he used has no local way to learn it. Only the admin side can map
  the id it holds to an address. Not designed here.

### The sign-in gate — deployed and re-verified from the live origin (2026-10-07)

Built as `src/components/Gate.tsx` (24c572e; README «Since 2026-10-07: THE SIGN-IN GATE»),
deployed as `gh-pages 5cfa9af` and, after TF-7, `bf6cd00` — all 158 staged files served
byte-identical. Full gate on the committed tree: **2053 passed, 0 failed across 30 steps**
(`screens/gate.py` 24/24, `screens/tools.py` 137/137 after TF-5). Mutation-proved: the
session check removed → the five "through" assertions fail; the records check removed → the
loft-panel assertions fail.

The same probe script, backend answered by a stub through interception, run against the live
origin BEFORE (`0e917e4`) and AFTER (`bf6cd00`), verbatim:

```
BEFORE
1 no session, no records  : {"path": "/zajilv2/birds/", "gate": null, "navLinks": 12, "birdRows": 0, "account": false}
2 no session, records     : {"path": "/zajilv2/tools/", "gate": null, "loft": null, "exportBtn": false, "navLinks": 12}
  wrong password           : {"msgCred": "البريد الإلكتروني أو كلمة المرور غير صحيحة", "dialog": null} · device unchanged True
  another account (B)      : {"dialog": "هذا الجهاز يحمل بيانات حساب آخر", "msgCred": null} · device unchanged True · A/B unchanged True
3 session present, OFFLINE: {"path": "/zajilv2/birds/", "gate": null, "navLinks": 12, "birdRows": 20}

AFTER
1 no session, no records  : {"path": "/zajilv2/birds/", "gate": "empty", "loft": null, "exportBtn": false, "navLinks": 0, "birdRows": 0, "account": false}
  …and at /tools/         : {"path": "/zajilv2/tools/", "gate": "empty", "navLinks": 0}
2 no session, records     : {"path": "/zajilv2/tools/", "gate": "records", "loft": "هذا الجهاز يحمل لوفت أبو خالد", "breeder": "المربّي: خالد العمري", "exportBtn": true, "navLinks": 0, "account": false}
  export from the gate     : zajil-export-2026-10-07.json · 20 birds · any account in the file: False
  wrong password           : {"msgCred": "البريد الإلكتروني أو كلمة المرور غير صحيحة", "dialog": null, "gate": "records"} · calls [('TOKEN', '')] · device unchanged True
  another account (B)      : {"dialog": "هذا الجهاز يحمل بيانات حساب آخر", "msgCred": null, "gate": "records"} · calls [('TOKEN', '')] · device unchanged True · A/B unchanged True
  the owner signs in       : {"path": "/zajilv2/tools/", "gate": null, "navLinks": 12}
3 session present, OFFLINE: {"path": "/zajilv2/birds/", "gate": null, "navLinks": 12, "birdRows": 20}
```

Before, a device with no session opened every route (12 nav links, the two navs' pairs) and
the only thing the gate ruling asked for that already held was the RF-13 decision. After,
the two gate states stand on every route, the records gate names the loft and the breeder
and nothing matching `user-|@|•••`, export from the gate hands over the file without a
session and without an account in it, each wrong attempt costs one token request and
changes nothing on the device or on either account's rows, the owner's sign-in lifts the
gate in place, and a signed-in device goes straight through offline. `live_deployment.py`
against the live origin: **39 passed, 0 failed**, the three `[GATE]` checks among them,
nothing reaching the real project (TF-6's net, counted zero).

RULED 2026-10-08: a build with no sync configuration has nothing to sign into and does not
gate — correct, left as built: a build with nothing to sign into must not lock anyone out
(`screens/gate.py`, "[unconfigured]"); the test-harness route stands outside the gate. Also
ruled 2026-10-08: the records panel takes the form's 560-px cap from 1100 px up
(`signin.module.css`, `.auth .gate`) — accepted, matching the form.

### Three things seen and left as they are

- **THE RULED LIMIT — CLOSED 2026-10-07, reversing the 2026-10-05 ruling.** A device that was
  already signed OUT when the record arrived has no session and no record, and adopted
  whoever signed in first. Its op log carries the previous account's id (`actorId`,
  `oplog.js:90`) on every op made while signed in — and the first sync re-logs every record
  — so that inference was raised here and not used, because the ruling said adopt.
  **Reversed, and why:** a sign-in gate is the next piece of work, and a gate turns that
  adoption from an incidental risk (nobody has to sign in) into a compulsory one (everybody
  must, and the only thing between a person and the collision is typing the same address as
  last time). Now the most recent non-null `actorId` in the op log is the owner of record
  when no owner key and no session exist, compared exactly as the recorded owner is. Measured
  before the change on exactly that device: B signing in landed on /tools/ with calls
  `TOKEN, GET cursor>19: 0, POST ['ج-1-edit']` and account B's rows went 3 → 4. After: the
  decision, `TOKEN` only, the device unchanged byte for byte, both accounts' digests
  unchanged, and the previous account named only as «حساب آخر سبق استخدامه على هذا الجهاز»
  — the log carries no address. A long-synced device pruned to its 500-op tail still names
  its owner in every remaining op. **Adoption now applies only to a device that was never
  signed in** — every op `null` — which is the one case with nothing to protect.
  **Deployed 2026-10-07 as `gh-pages 0e917e4` from `29bd481`** — 160 of 160 staged files
  served byte-identical, `live_deployment.py` 36 passed, 0 failed — and re-measured on the
  live origin on a legacy device (owner record removed through IndexedDB, 44 ops stamped
  `user-C`, one edit unpushed). Before, on `cd732d5`: B landed on `/tools/`, calls
  `TOKEN, GET cursor>0 -> 68, POST 1 row`, the device went from 20 birds to 58 and account
  B's rows changed. After: `/sign-in/` with the decision, `TOKEN` only, the device unchanged,
  both accounts' digests unchanged.
- **A second tab.** A tab left open while another clears the device keeps its own mirror in
  memory. The same class as a replace-import in another tab; not new, not addressed.
- **A stopped attempt still obtains a token** from the server, which is discarded unstored.

---

## SF-5 — `tools-v2.html`, as uploaded, spells «المربي» without the shadda; everything else in both trees has «المربّي»

**A SPEC finding. CLOSED 2026-10-05, in favour of the shipped state** — the archive keeps
the shadda. Two rulings had pointed in opposite directions, the second resting on something
measurement contradicted; nothing was changed on the strength of it, and the third settled it.

### What is where — measured 2026-10-05

| | «المربي» | «المربّي» |
|---|---|---|
| the tools-v2 UPLOAD, lines 411–412 — «اسم المربي», the row label and the field label | **2** | 0 |
| `design/approved/tools-v2.html` as archived (`d8cee43`) | 0 | 2 |
| `design/approved/certificate-v1.html` — line 362 is the SAME label, «اسم المربّي» | 0 | 3 |
| `design/approved/races-v1.html` | 0 | 1 |
| `src/i18n.js`, and vanilla `js/i18n.js` — `bird.breeder`, `race.fanciers` | 0 | 2 |
| `src/i18n.ext.js` — `set.breederName`, `cert.breederLine`, `cert.showLoftHint` | 0 | 3 |

The upload is the only place in either tree without the shadda. And `set.breederName`
«اسم المربّي» (`src/i18n.ext.js:427`) is ONE key rendered in TWO places: the breeder row of
الأدوات (`app/tools/view.tsx:218`) and the certificate's options panel
(`app/cert/view.tsx:325`), where `certificate-v1.html:362` draws it with the shadda.

### The two rulings

- **2026-10-03** (the tools-v2 order, item 2; restated 2026-10-05 as ruling 4): archive with
  «المربّي», matching the existing key. Done — two lines, recorded in `design/README.md`;
  reversing them reproduces the upload byte for byte. This is what is archived and deployed.
- **2026-10-05, later:** keep «المربي», "as the spec and the app both have it", because a
  near-duplicate key would be worse than an inconsistent diacritic.

### Why the second was not applied

The app does not have «المربي» anywhere. Making the build say it would take exactly what the
ruling set out to avoid: a second key differing from `set.breederName` only by the shadda —
or changing that key, which also moves the certificate's label away from its own frozen
spec. Reported rather than forced, as the order's item 2 asked of a disagreement.

### What was put to a ruling — neither option changed a pixel of the deployed app

1. **Leave it as shipped.** The archive carries the shadda and the two-line difference from
   the upload stays recorded. Spec, app, vanilla and the other two specs agree; one key.
2. **Restore the archive to the upload's bytes.** The app keeps its key, and
   `guards/strings.ruled.json` gains one entry (the existing key wins). Spec and app then
   differ by one diacritic; still one key; no redeploy.

### RULED 2026-10-05 — option 1: leave it as shipped

The archive carries the shadda. The app, vanilla, `certificate-v1.html` and `races-v1.html`
all agree, and one key renders both surfaces. The two-line difference from the upload stays
recorded (`design/README.md`, tools-v2, deviation 4; reversing the two lines reproduces the
upload byte for byte). Nothing to change in either tree, the guards, or the deployment.

---

## RF-14 — a device whose current loft is removed remotely keeps pointing at it, and files new birds under the dead id

**In the shared data layer, so present in BOTH trees. Same class as RF-12: the integrity of
`currentLoftId`, a device setting that nothing re-checks.** Found 2026-10-11 by measurement on
a stub project while answering what a replace-import does to the server (see RF-15).

### Measured

A PC that had adopted the teaching loft at first login (it was the only remote loft). The
teaching loft was then removed by another device through the app's own `Lofts.remove()`,
which tombstones and pushes `deleted = true`; the PC pulled it:

```
A  PC after: lofts ["لوفت أبو خالد"], currentLoftId a52d53b8 (the removed loft), ui h1 «لوفت بلا اسم»
D  the first PC after reopening: lofts ["لوفت أبو خالد"], currentLoftId a52d53b8, current "(none)", h1 «لوفت بلا اسم»
E1 on that PC, a new bird would be filed under loftId: {"loftId": "2d7ccf0d…" (the dead id), "exists": false}
E2 its loft settings card (currentLoft): null
```

`currentLoft()` is `state.lofts.get(state.currentLoftId) || null` (storage.js:155); boot keeps
any stored id (`state.currentLoftId = state.settings.currentLoftId || first key`, storage.js:143),
so a reload changes nothing; and `record.loftId = state.currentLoftId` on save (storage.js:183)
files every new record under a loft that no longer exists — invisibly, since no screen filters
by loft. `applySyncDelete` on a loft does not touch `currentLoftId`.

### What a person sees

The loft card empty, the home heading «لوفت بلا اسم», everything else apparently fine. The
birds entered from then on belong to no loft; a later device adopting the real loft shows them
all the same (no filter), so the split surfaces only when loft identity starts to matter.

### FIXED 2026-10-14 (RULED, with the example-data removal)

`ensureCurrentLoft()` (`src/db/storage.js`, port-only — PORT-COMPLETE): at boot the stored
`currentLoftId` is validated instead of trusted, and `records.js` calls it after the generic
`remove()` of a loft and after `applySyncDelete()` of one. Dangling → exactly one loft left is
adopted, otherwise a fresh pristine loft is made current (a clear state the fancier can act on;
choosing among several would be the guess R4 refuses). Proven in
`tests/e2e/screens/example_remove.py`: the current loft removed locally → recovered at once; a
bird added afterwards is filed under a loft that exists; a reload keeps the recovery (the stored
id names a loft that exists); the current loft removed by a PULLED tombstone → recovered at once.
Mutation-proved: the call in `remove()` taken out → the recovery assertions fail.

### What it was before the fix — recorded on the ruling of 2026-10-11

The fix belongs with RF-12's: when the current loft is deleted (locally or by a pulled
tombstone), re-point `currentLoftId` — to the one remaining loft when there is exactly one,
otherwise to a fresh pristine loft — and never leave it dangling. The measured recovery today is
a replace-import of a good export (E3: lands on «لوفت أبو خالد» with the right current id) or
starting the device over.

---

## RF-15 — a replace-import does not reset the sync baseline: rows above the cursor come back, and the file's loft becomes a second loft on the server

**In the shared data layer, present in BOTH trees — but a SYNC behaviour, so it bites only
on a configured, signed-in device.** `importAll(payload, 'replace')` (io.js:218-233) clears the
five data stores and media and deliberately leaves the op log, the tombstones and the settings
— including `syncCursor` and `lastAckedSeq` — untouched. Its own A2 note says a replace
"RESETS THE SYNC BASELINE" and that "a future sync layer must treat a replace as a new starting
point rather than replaying history across it… That reconciliation is a v1.9 concern; nothing
here depends on it yet." The sync layer now exists and has no such handling (nothing in
sync.js reads an import origin or a baseline). Measured 2026-10-11, stub project, through the UI:

```
2 phone after REPLACE-import of an empty export: cursor 4, acked 8, birds [], lofts ["(unnamed)/f5285b88"], pending ["put:lofts:f5285b88(import)"], tombstones 0
  delete ops written: 0 · server unchanged: true
4 next sync, phone whose last cycle ended with a push:  GET >4 → ["تعليمي-4"]  → phone after: birds ["تعليمي-4/982ab0db", "حقيقي-1", "حقيقي-2"]
  next sync, settled phone:                               GET >4 → []           → phone after: birds ["حقيقي-1", "حقيقي-2"]
  server after (either): lofts ["لوفت أبو خالد", "لوفت إربد التعليمي"], birds [تعليمي-1..3(4), حقيقي-1, حقيقي-2]
```

Three consequences, each measured:

1. **The server keeps everything the replace removed** — no delete op, no tombstone, so the
   records a person wiped locally stay live for every other device and every future one.
2. **Rows above the cursor resurrect on the next pull.** A cycle pulls before it pushes, so
   a device's own last push sits above its cursor; after the replace those rows come back
   (تعليمي-4), filed under a loft the device no longer holds.
3. **The file's loft becomes the current loft**, with a new id. A fresh install's export
   carries its unnamed pristine loft; after the replace that loft is current, so everything
   entered afterwards is a SECOND loft beside the one still on the server — which is why a
   second device then meets two lofts and adopts neither (RF-16).

Not changed here. What a reset would have to do is the A2 reconciliation: on a replace, write
tombstones for every record the replace removed (so the server and other devices follow), and
decide whether the imported records are new puts (they are logged as such today). To be ruled.

---

### FIXED IN THE PORT 2026-11-13 (RULED) — a replace tombstones every record it drops; NOT in vanilla

Re-measured first on the deployed build (`823dd68`), two devices, one stub project, a pull fired DURING each
operation and again after (constructed shape):

```
REPLACE-IMPORT (payload: 1 bird): before {"birds": 39, "tombstones": 0} → after one more pull {"birds": 39} · tombstones written for the 38 dropped: 0
RESTORE of a snapshot older than a deletion made on the other device: the deleted bird is back on BOTH devices, the other device's tombstones 6 → 0
```

The whole pre-import set came back, not only what another device had touched: a device's own pushed rows sit
above its cursor until its next pull. **The rule now:** `importAll(payload, 'replace')` — and a restore is that —
writes a tombstone and logs a delete op for every record the payload does not carry, exactly as if the fancier
had deleted it, so the replacement TRAVELS and every device converges on the file. Tombstones are written first
(a pull in flight meets them), the delete ops last, after the payload is in (a failed import queues no deletion,
and takes its tombstones back); a record the payload carries clears its tombstone. An untouched default loft
is dropped without a trace, as `dropPristineLoft()` drops it. No lock around the operation, and no cursor
change (a landed push advancing the pull cursor was proposed and NOT approved: a row from another device could
sit between the old cursor and the pushed rows).

**The confirmations say what happens** (`replacePreview()`): the replace states the birds and other records it
removes and, on a signed-in device, that it applies on all the person's devices; the restore states what it
removes, names the birds it brings back (five by name, the rest counted) and that both happen on the other
devices. The file is now read BEFORE the question.

**Proof — `tests/e2e/screens/replace_sync.py`, 23 checks**, both operations with a pull during and after: nothing
dropped comes back, the second device converges to the import and then to the snapshot, the server agrees, a
replace that throws half way leaves no tombstone and no delete op. Mutants, each failing at a named check:

```
M1 the replace drops records without a trace (the shipped behaviour) — 12 passed, 11 failed, first:
   ✗ [replace] the device holds the file and nothing else, with a pull fired DURING the import  {'names': ['الملك', 'من-الملف'], 'birdsInStore': 4, …}
   ✗ [replace · M1 fails here] after ANOTHER pull NOTHING dropped comes back — the three the other device had edited included  ['الملك', 'من-الملف']
M2 tombstones written, the deletions never logged — 17 passed, 6 failed:
   ✗ [replace · M2 fails here] THE SECOND DEVICE CONVERGES TO THE IMPORT: the file's bird, the file's loft, nothing else  {'names': ['Anka', 'Julius', …
M3 a failed replace does not take its tombstones back — 22 passed, 1 failed:
   ✗ [failure · M3 fails here] a replace that throws mid-way leaves NO tombstone and NO delete op for records it did not finish replacing  ('DataCloneError', 0, 4, 0, 0)
```

**Declared, not fixed here:** a replace whose file carries NO loft still leaves the importing device with no
loft until its next boot (measured 2026-10-31; unchanged). A second device that received two lofts at its first
sync keeps its own untouched default loft beside them (R4 refuses to guess). The restore list still shows a
pre-import snapshot by its raw key. A replace that fails after the stores are cleared still leaves them
cleared, with the pre-import snapshot as the way back (unchanged). Photos of a dropped bird stay in the media
store when the snapshot carries no media (unchanged).

## RF-16 — no screen removes a loft: a fancier who loads the teaching loft has no way out

**In BOTH trees. Not one person's problem: the first thing a pilot fancier is invited to do is
load «لوفت تعليمي كامل», and the register then holds a loft they can never remove.** Found
2026-10-11.

`Lofts.remove(id)` exists in the data layer (records.js `makeGeneric`: logs a `delete` op,
writes a tombstone) and syncs correctly — measured: `POST [lofts لوفت إربد التعليمي deleted=true]`,
the other device and a brand-new one both drop it, and a brand-new device then adopts the one
remaining loft («لوفت أبو خالد», breeder shown). Nothing in `app/` calls it (grep: no
`Lofts.remove`, no loft delete control). Birds can be deleted one by one from the UI; the
loft row cannot.

Consequence on a synced account: the teaching loft row stays on the server for good. Every
new device signing in meets two remote lofts, `adoptRemoteLoftIfPristine()` refuses (≠1), and
the device lands on its own unnamed loft — h1 «لوفت بلا اسم», every bird of every loft listed:

```
a brand-new PC signing in: lofts ["(unnamed)", "لوفت أبو خالد", "لوفت إربد التعليمي"], currentLoftId = its own, h1 «لوفت بلا اسم»
```

Locally (no sync) the same person is left with two lofts and the RF-12 split. The only exits
today are the console (`Lofts.remove` through the app's own code) or a replace-import of an
export that does not carry the loft — which, on a synced device, is RF-15.

**ADDRESSED IN SCOPE 2026-10-14 (RULED as a pilot blocker):** one action in الأدوات → البيانات,
beside «تحميل سرب تعليمي», removes exactly what the dataset loaders put in — both generations of
both datasets, identified by derived ids — through the app's own code paths, with the real counts
confirmed, the fancier's own records re-filed, and example ancestors of his birds kept as
references (README «Since 2026-10-14»). General loft removal stays a separate later item, as ruled.
The tools-v2 deviation record for the row (deviation 5 of `design/README.md`) was committed on the port
branch on 2026-10-14 and tripped the gate's isolation step on 2026-10-30 (`main..HEAD` outside `next/` must be
empty — design records land on `main` on Samir's order, as the other four did). Taken off the branch
2026-10-30; the text is held on the local branch `design/tools-v2-deviation-5` (commit `5e404b9`, one commit on top of
`main`, fast-forwardable, NOT pushed — a scratchpad file is not a durable place). What lands it on `main`, on Samir's order:
`git checkout main && git merge --ff-only design/tools-v2-deviation-5 && git push origin main`.
Seen on the way (RULED 2026-10-16 as not acceptable — a silent no-op; measured below, proposal
pending Samir's ruling, NOT implemented): after the removal, loading the same dataset again on that device
imports nothing — the removal's tombstones are newer than the dataset's records, so the merge
skips every one (`[own · seen]` in the suite); a "load again" needs its own ruling.

**Measured 2026-10-16 (stub project modelling the trigger's LWW; `scratchpad/reload_probe.py`):** clearing
the tombstones for exactly the dataset's ids (68, none v4) and loading again imports 38/5/17/7 and logs 68
`put:import` ops stamped at load time; the push passes the server's LWW (0 rejected — the puts are newer
than the removal); a device that had pulled the removal gets the data back on its next pull with its
tombstones cleared (§2a's corollary); a device that removed locally BEFORE the reload and syncs after it
pulls first, its 128 pending ops are superseded by the newer rows, it pushes nothing and holds the data
again; a device that removes AFTER the reload wins instead (its deletes are newer) and everyone follows —
the latest intent wins either way; a brand-new device ends with whatever the latest intent was. On a
device whose current loft is the pristine recovery loft, the reloaded teaching loft is adopted as current
(RF-12's rule); on other devices it arrives beside their current loft. Clean. Proposed: the loader
clears the tombstones for exactly the ids in the file it is about to load — refusing any v4 id — then
merges as today; the canonical ids are kept, so the removal row's detection keeps working.

Also seen: a
device that joined while the teaching lofts stood keeps its own pristine loft beside the real one
after they go (RF-12's adoption runs only at first login) — the RF-12 class, left.

### Deployed and re-verified from the live origin (2026-10-14)

`gh-pages 029bd23` from `df6a42a`; all 158 staged files served byte-identical. Full gate on the
committed tree **1552 passed, 0 failed across 30 steps** plus the root control run by hand
(548/548 — the gate had skipped it because the `:8123` repo-root server was down; TF-1's
neighbour, now in memory). `screens/example_remove.py` 37/37, eight mutations each red.
`live_deployment.py` against the live origin **43 passed, 0 failed**, the four `[EXAMPLE]`
checks among them. Samir's exact case on the live build, stub-backed, verbatim:

```
  imported the PRE-v1.9.1 generation through the import screen: تم الاستيراد: 38 طير، 5 زوج، 17 نتيجة.
2 register rows with both generations: 76 · removal row present: 1 · value 76
  lofts line: الألوفت التجريبية: «لوفت إربد التعليمي»، «لوفت إربد التعليمي»
3 dialog: إزالة البيانات التجريبية؟  سيُحذف 76 طيرًا و10 زوجًا و34 نتيجة و14 سجلًا صحيًا من «لوفت إربد التعليمي»، «لوفت إربد التعليمي»، ثم اللوفت التجريبي نفسه. لا يُمسّ أي طير من طيورك.
4 register rows after: 0 · row present: 0
5 «مزامنة الآن»: synced · pushed [(119, 119), (17, 17)] · deleted rows pushed 136 · server {'birds†': 76, 'healthEvents†': 14, 'lofts†': 2, 'pairs†': 10, 'raceResults†': 34}
```

What was wanted before that ruling: a loft delete in the loft settings, through
`Lofts.remove`, with the three-way dialog's honesty about what goes with it, refusing while the
loft is current unless another loft exists to become current (RF-14).

---

## RF-17 — the teaching dataset changed every id at v1.9.1, so a loft loaded before and after exists TWICE on the server

**A data finding on the real dev project, measured by Samir 2026-10-12 with the read-only SELECT
(account 6092c513-…, 140 rows):**

```
  loft-irbid-demo                        «لوفت إربد التعليمي»  67 live
  8f268d1b-3dbe-57be-8d77-ede52297a2cd   «لوفت إربد التعليمي»  68 live
  2b466fd7-b14a-48bc-8e76-cff1871931ee   «Hummar»               3 live
  (no loftId field)                                             2 live
```

The pre-v1.9.1 datasets carried readable ids (`loft-irbid-demo`, `g5-faris26` — see the
SYNC-DESIGN amendment "client ids are opaque strings"). v1.9.1 rewrote every dataset id to
`uuid5(ID_NAMESPACE, key)` (`tools/idmap.js`, namespace `7f3c9a54-2b18-4d6e-9c05-1a2b3c4d5e6f`):
`uuid5(ns, 'loft-irbid-demo') = 8f268d1b-3dbe-57be-8d77-ede52297a2cd`, and likewise
`uuid5(ns, 'loft-zarqa') = b5ab67a5-483f-5a6c-997c-a5de423cb53f` for the small example. A device
that loaded the teaching loft before the change and again after it pushed both generations:
68 rows for the new (its loft record carries `loftId`), 67 + the loft record for the old (whose
loft record has no `loftId` field — one of the two "(no loftId)" rows). Same name, two ids,
two full copies, and nothing in the app can tell them apart or remove either (RF-16).

Consequences: every clean-up must name BOTH ids; a snippet that took one constant would have
cleaned one generation and left 67 rows of the other — the exact two-lofts state the clean-up
exists to end (RF-14/RF-16). The prepared console snippets take a list and refuse unless every
named id is held locally. Any device that still holds a pre-v1.9.1 export can re-create the old
generation by importing it.

Not changed here. To rule: whether the app should recognise the readable-key generation of
its own datasets (a fixed, small set of keys) and offer to retire it.

---

## DF-2 — the dev project holds two spike accounts' rows and must be cleared before production

Recorded 2026-10-12 from the same SELECT: `spike-a@zajil.test` (69 rows) and
`spike-b@zajil.test` (34 rows) from the September sync spike remain in `public.sync_records`
on the DEV project. Out of scope for the 2026-10-12 clean-up and NOT to be touched by it. The
dev project is to be cleared of spike rows before it is used for anything a person
relies on. Owner of that step: Samir, dashboard, on his ruling.

**Corrected 2026-11-13 (Route A, DF-3):** this entry used to say the production project is created
fresh at pre-pilot, so nothing would carry over. It is not: the existing project is upgraded in place and
IS production, so the spike accounts are deleted outright — the two auth users and their 103 rows — with
the SQL prepared on 2026-11-13 (before/after counts inside one transaction). A pre-pilot action, Samir's.

---

## RF-18 — the example-data removal was blocked by a duplicate-ring WARNING on every real device, and failed silently

**Found 2026-10-30 on the deployed build (`gh-pages 029bd23`), reproduced with a CONSTRUCTED shape — not his
data; see the correction of 2026-11-01 below — stub-backed, IndexedDB measured before and after.** WHAT SAMIR
REPORTED: the row with its badge 76, the panel «38 + 38» (per-loft example-bird counts), a press, the badge still
76, two errors in DevTools. Everything quoted in this entry, the dialog's «يبقى 29» included, is the constructed
shape's output.

```
3 after the press — dialog present: 1
  dialog: سيُحذف 47 طيرًا و10 زوجًا و34 نتيجة و14 سجلًا صحيًا … يبقى 29 طيرًا تجريبيًا كمراجع في النسب … لديك 1 من سجلاتك داخل اللوفت التجريبي
  console after confirm: ['PAGEERROR: zajil/validation-failed', …]
4 IndexedDB after: identical — deleted: 0 birds · tombstones + 0
5 row present after: 1 · badge: 76 · toast: (none)
6 removeExampleData() called directly: {"threw": "zajil/validation-failed", "errors": []}
```

### The mechanism — measured

The removal's first step flips the kept ancestors to reference birds through `saveBird()`, which refuses a save
on WARNINGS as well as errors unless `allowWarnings` is passed (validate.js:104). Duplicate rings are a warning
(`val.dupRing`), and with both dataset generations present (RF-17) every kept ancestor has a twin wearing its ring:

```
thrown: {"errors": [], "warnings": ["val.dupRing {ring: JO-2026-13002, otherId: g5-najma26 (the pre-v1.9.1 twin)}"]}
with { allowWarnings: true }: saved · keptWithWarnings: 29/29 · warningKinds: {val.dupRing: 31}
```

So the action threw before its first deletion; and `remove()` had no catch, so the fancier got no toast and no
dialog — a silent no-op of the class ruled out for the loader on 2026-10-20.

**Why the suite was blind:** the kept-ancestor case was proven on one generation (no twins, no warning); the
two-generation case had no linked birds (kept 0). The reported symptom needs the intersection — both generations
(every device that loaded the teaching loft before and after v1.9.1) AND a kept ancestor; the constructed shape
forced the second half by giving its own bird a teaching dam.

### Fixed 2026-10-30 (RULED)

1. **`allowWarnings` on the removal's own re-saves only** — the reference flips and the re-files inside
   `removeExampleData()`, as one `INTERNAL` option. The records already exist exactly as they are; the action
   flips two fields or a `loftId`; the warning concerns a twin the same action deletes. Errors block, unchanged.
   Bounded by the guard `allow-warnings-bounded`: every site that sets the flag is pinned with its count (the
   removal's one, the bird form's two after the fancier confirmed the warnings, «اجعله مرجعًا»'s one, the breeding
   screen's four, two doc comments); a new site, one more use, or `INTERNAL` rewritten fails the guard — proven
   both ways.
   **The warnings `saveBird` can raise, enumerated:** `val.dupRing` (a ring another bird wears), `val.dupRingSameBird`
   (the same ring twice on one bird), `val.parentSameDay` (parent and bird hatched the same day). In this shape the
   removal bypasses `val.dupRing` (31 across the 29 kept); in principle any of the three on a kept or re-filed record.
   None is load-bearing: each is an "are you sure" about data that already exists and which the removal does not
   alter (no ring, no date is touched). The nine errors (`val.cycle`, `val.selfParent`, `val.sireIsHen`, …) still block.
2. **THE INVARIANT, in code:** `destructive()` in `app/tools/parts.tsx` — no path through a destructive action in
   الأدوات returns having changed nothing without telling the user; a caught failure produces a toast naming the
   reason (the first validation issue in the fancier's language, or the message). The removal runs through it.
3. `screens/example_remove.py` gained the constructed intersection shape (step renamed 2026-11-01, TF-10): both
   generations, an own bird GIVEN a teaching dam (closure 29), an own record inside a teaching loft — 47 deleted, 29 kept with their rings intact, the own record re-filed, both lofts
   tombstoned; and the invariant: a forced ERROR (a kept ancestor's sire recorded as a hen → `val.sireIsHen`)
   produces the toast «لم تُزل البيانات التجريبية — لم يتغيّر شيء. السبب: …» with nothing changed and no page error.
   Mutations: `allowWarnings` removed → red; the catch removed → red.

### Deployed and re-verified from the live origin (2026-10-30)

`gh-pages 823dd68` from `e394cb0`; all 158 staged files served byte-identical. Full gate on the fix tree
**2108 passed, 1 failed across 31 steps** — the one failure was the isolation step over the branch-only
`design/README.md` record (taken off the branch in `8cc0177`; `main..HEAD` outside `next/` is empty again);
every suite step green, the root control 548/548 included, `example_remove.py` 46/46 with the constructed shape and the
invariant; mutations: the flag not passed → red (the removal never completes), the catch silenced → red.
`live_deployment.py` against the live origin **43 passed, 0 failed**. The same probe that caught it, on
the deployed build, the constructed shape, IndexedDB measured — before and after the fix:

```
BEFORE (029bd23): IndexedDB before {"birds": 78, "exampleIdBirds": 76, "lofts": ["Hummar", "لوفت إربد التعليمي", "لوفت إربد التعليمي"], "tombstones": 0}
                  console: ['PAGEERROR: zajil/validation-failed'] · IndexedDB after: identical · deleted: 0 · badge 76 · toast (none)
AFTER  (823dd68): IndexedDB before {"birds": 78, "exampleIdBirds": 76, "lofts": ["Hummar", "لوفت إربد التعليمي", "لوفت إربد التعليمي"], "tombstones": 0}
                  dialog: سيُحذف 47 … يبقى 29 … لديك 1 من سجلاتك داخل اللوفت التجريبي
                  IndexedDB after {"birds": 31, "exampleIdBirds": 29, "lofts": ["Hummar"], "tombstones": 107, "byLoft": {<Hummar>: 31}, "refs": 29}
                  deleted: 47 birds · tombstones + 107 (47 + 10 + 34 + 14 + 2) · row gone · no page error
```

### Correction 2026-11-01 — what he reported, what was constructed, and what his export then showed

**The attribution above was wrong, and it was ruled on.** The dialog quoted at the top («يبقى 29 طيرًا
تجريبيًا كمراجع») is the output of a shape the 30-Oct probe BUILT — its docstring says "one own bird whose
ancestry reaches deep into the teaching data": it gave its own bird the teaching dam نجمة ٢٦, the bird with the
largest ancestor closure (29). The suite step carried the label "SAMIR'S EXACT SHAPE" and this entry wrote
"reproduced with Samir's exact shape". He had never named a parent on any bird. What he actually reported, and
the only part of this entry that is his: badge 76, the panel «38 + 38», a press, the badge still 76, two errors
in DevTools. The 29, and the closure, were mine.

**His export, measured by him (2026-11-01):** PC 31 birds = 28 uuid5/external + 3 v4; one v4 bird, اشيق (ring
44234234, created 2026-10-01), carries `sireId` الملك and `damId` سديم, both external; exactly two external birds
have an inbound link from a non-external bird, both اشيق's; the PC also tombstones the teaching pair
`lp-malik-sadim-26`. So a keep set on his PC is real, and it comes from the mechanism measured on 2026-10-31
and then wrongly closed as "not his data": «تركيب الحلقة» on a teaching pair's egg mints a v4 chick carrying
`pair.sireId` and `pair.damId` (app/breeding/shared.tsx:209) — no parent typed by anyone. The dialog that keeps
them never names the bird that causes the keep; RULED 2026-11-01: it must («بسبب: اشيق»).

**Standing rule (Samir, 2026-11-01), recorded as TF-10:** no fixture, step or finding may carry a person's name
unless it was built from data they actually exported. The two steps in `screens/example_remove.py` are renamed
(THE PHONE + PC CASE; THE INTERSECTION SHAPE), both marked CONSTRUCTED; the wording of this entry is corrected in
place where it attributed the shape to him; the measured outputs stand, as the constructed shape's.

### Measured, NOT fixed in this change — for a ruling: the pattern

Mutating async handlers in `app/tools/*.tsx` that `await` a data-layer write **without a catch**.

**Re-measured 2026-10-30 (second pass, every `async` in the two files read): 11 of 14.** The first count,
"8 of 9", written the same morning, was an UNDERCOUNT — it listed the handlers behind a confirm dialog and
missed four plain ones. The full table, by file and line as of `b085441`:

| handler | where | awaits | catch? |
|---|---|---|---|
| `sync-now` | parts.tsx:172 | `db.syncNow()` | no (`try … finally` only) |
| sync toggle | parts.tsx:173 | `db.setSyncEnabled()`, `db.refreshSyncStatus()` | no (no `try` at all) — missed in the first count |
| `del` (a duplicate copy) | parts.tsx:192 | `db.deleteBird()` | no |
| `exportAll` | parts.tsx:226 | `saveSetting('lastExport')` | **yes** |
| `importFile` | parts.tsx:255 | `db.importAll()` | **yes** |
| `restore` (a snapshot) | parts.tsx:298 | `db.importAll(…, 'replace')` | no |
| `load` (the example loaders) | parts.tsx:326 | `db.importAll(…, 'merge')` | no (`try … finally` only) |
| `remove` (the example data) | parts.tsx:383 | `db.removeExampleData()` | **yes** — through `destructive()` |
| integrity `run` | parts.tsx:417 | `saveSetting()` ×2 | no (`try … finally` only) — missed |
| scanner save | parts.tsx:449/453 | `saveSetting('scanServerUrl')` | no; the `onBlur` form is not even awaited — missed |
| `signOut` | view.tsx:56 | `db.signOut()`, `db.refreshSyncStatus()` | no |
| loft `save` | view.tsx:192 | `Lofts.save()` | no — missed |
| `pickLogo` | view.tsx:197 | `db.addMedia()` | no |
| `removeLogo` | view.tsx:202 | `db.deleteMedia()`, `save()` | no |

Not counted: the dev panel's `runTests`, `roundtrip` and `integrity` (view-only; the first two catch, the
third reads only). A thrown failure in any of the eleven reaches the console and nothing else. The invariant
exists in code now; routing the eleven through it is one change, to be ruled — **measurement only, no fix.**

---

## SUP-1 — a browser's page translation makes the app look half-English, and nothing in the gate can see it

**A SUPPORT finding: a defect in neither tree.** The session behind the TF-4 report was
attributed to it on 2026-10-04 — Samir's screenshot shows Firefox's translation bar. That
attribution is his observation: the screenshot was not available here, and Firefox's
translator was not run. What IS measured below is the mechanism, with a stand-in.

### The symptom is TF-4's symptom, for the same structural reason

"Some strings English, most Arabic": the rail and the backup banner in English beside an
Arabic page. An in-page translator rewrites text nodes in place, from outside the app, after
the app has rendered. React does not rewrite a text node whose text it believes unchanged, so
the rewrite SURVIVES wherever the DOM persists — the layout's banner and nav
(`app/layout.tsx:45,47`), which outlive every navigation — and is LOST wherever a navigation
mounts fresh nodes. The same two surfaces as TF-4, because they are the two that persist.

Reproduced on the live origin, on the FIXED build (`gh-pages ff5f603`), at 1400px, with a
stand-in that prefixes every Arabic text node — **not Firefox's translator**, only the one
thing every in-page translator does:

```
                               still rewritten            untouched Arabic
                               nav   banner   page        strings on the page
before any rewrite              0      0        0                73
95 text nodes rewritten in place
immediately after               6      2       73                 0
after ONE tap on «الطيور»        6      2        1               170
after a tap on «الإحصائيات»      6      2        0                64
after a reload                  0      0        0                64
```

`<html>` is `ar/rtl` on every line. One tap is enough to produce the report's picture.

### Why no assertion can catch it

The app's own output is correct throughout — `screens/language.py` is 31/31 and the deploy
gate's `[C]` passes on this deployment. The rewrite happens after render, by an agent the
gate's browsers do not have. TF-4's fix does not prevent it and could not: the table above
is the fixed build.

### The two detection signals

1. **The browser is showing its translation UI** — Firefox's translation bar, as in the
   screenshot. If it is there, stop.
2. **English on a page that is still right-to-left.** The app's own English is never that.
   Measured on the live origin:

   | | `<html>` | rail | language control |
   |---|---|---|---|
   | the app in Arabic | `ar/rtl` | RIGHT edge | «العربية» pressed |
   | the app in English | `en/ltr` | LEFT edge | «English» pressed |

   and since TF-4 the nav and the banner cannot disagree with the page (asserted). A
   corollary that settles it alone: the app never translates the fancier's own text — in the
   app's English the loft is still «لوفت إربد التعليمي» and a bird still «غيمة ٢٦» — so a
   loft or bird NAME in English is the browser, whatever else is on screen.

### Port-side handling

None, RULED 2026-10-04: no app fix. Not done and not ruled: marking the document
`translate="no"`, the standard opt-out — whether Firefox's translator honours it was not
measured here.

## TF-10 — a constructed fixture carried a person's name, and its output was reported as what he saw

**Where:** `tests/e2e/screens/example_remove.py` (the step labelled "SAMIR'S EXACT SHAPE", and the earlier
"SAMIR'S CASE"); `ROOT-FINDINGS.md` RF-18 ("reproduced with Samir's exact shape", the dialog «يبقى 29» quoted as
his); the 30-Oct closure probe (docstring: "one own bird whose ancestry reaches deep into the teaching data").

**What:** the fixture GAVE its own bird the teaching dam نجمة ٢٦ to exercise the kept-ancestor path, then carried
his name, and its dialog was written up as what he had seen. He had never named a parent. The ruling of
2026-10-30 was made on that synthetic dialog; the amendment of 2026-10-31 then measured the real mechanism (a
chick ringed on a teaching pair inherits `pair.sireId`/`pair.damId`, app/breeding/shared.tsx:209) and closed it as
"false for his data" — on the fixture's output again. His own export answered it in a minute: اشيق, a v4 chick
with two external parents, created 2026-10-01 by exactly that path.

**Why it matters:** a fixture that wears a person's name is read as their data, by the person included. Four days
went to a "data question" the export settled at once, and a hypothesis that was TRUE on his device was reported
as false.

**THE STANDING RULE (Samir, 2026-11-01):** *no fixture, step or finding may carry a person's name unless it was
built from data they actually exported.* A constructed shape is labelled constructed, says what it assumed, and
its output is never quoted as what anyone saw. When a person's data cannot be measured here, hand them a
read-only measurement to run (the DevTools snippets) rather than infer.

**Port-side handling (2026-11-01):** the two steps renamed and marked CONSTRUCTED; RF-18 corrected in place with a
dated correction block; the rule here and in the working memory. PROPOSED, not built (for a ruling): a prebuild
guard that scans `tests/e2e/**/*.py` step headers and `check()` labels, and this file's entry heads, for a
person's name without a `[from-export: <file>]` tag.

## DF-3 — the dev project IS the production project (Route A, RULED 2026-11-13; a PRE-PILOT item, not a prerequisite)

**Recorded 2026-11-13, re-ordered the same day.** Sync works: a real round trip on the live project (a bird
pushed from one device appeared on the other; an updated pair travelled). The three-week "sync failure" of
October was RF-3's pause, and the pause was largely a consequence of the port's missing auto-sync (RF-3
addendum, RF-19) — so THE FIX IS THE CHANGE SET OF RF-19, which needs no plan change and no Pro; real use with
automatic sync keeps the free project awake. Leaving the free tier is a pre-pilot item beside the custom domain, the
password rotation and the spike clean-up, and it is justified by two things, NO PAUSING and BACKUPS: a paid
project is never paused, and the free tier has no backups where Pro has daily backups with 7-day retention.
Both matter once another person's data is on the project; neither is a repair of the client. "Pro fixes sync" is false and is not to enter this record. The question that remained was
HOW to leave the free tier when the time comes: upgrade this project in place (Route A) or create a fresh
production project (Route B).

### The measurement that decided it

A device that has synced with one project and is then re-pointed at another hits the account collision at
sign-in, because the same email gets a DIFFERENT user id on every project — and nothing in `settings` records
which project the owner, the cursor and the acks belong to. Measured on the deployed build (`823dd68`), two
stub projects, THE NET armed (`scratchpad/project_switch_probe.py`, constructed shape):

```
P1 on project ONE after sign-in: owner user-A · lastAckedSeq 7 · syncCursor 4 · oplog 7 · birds 3
P2 sign-in on project TWO with the same email → DIALOG: هذا الجهاز يحمل بيانات حساب آخر … لن تُدمج تلك البيانات مع حسابك ولن تُرفع إليه. صدّرها أولًا … أو امسحها من هذا الجهاز وادخل بحسابك
P3 if the refusal were bypassed: the first pull would ask TWO for server_seq > 4 (TWO numbers its rows from 1);
   the push would send only ops with seq > 7 — of 7 ops, 0 — the 3 birds already acked on ONE would never reach TWO
```

So a new project is a CLIENT-CODE problem, not a config problem. Route B needs a project-switch path first:
a recorded project host beside the cursors; on mismatch, cursor and ack reset, a re-enqueue as on a first
login, and a ONCE-ONLY adoption prompt whose owner rule — what the device does with the owner record of the
previous project — is NOT ruled. Building that to move onto an identical empty server buys hygiene at the price
of new risk.

### RULED: Route A — upgrade the existing project to Pro, in place, when the pre-pilot list is worked

Pro projects have daily backups and are never paused (supabase.com/pricing and the project-pausing guide,
read 2026-11-13) — those two are the reasons. Keys: none change. Rebuild: none.
Devices: untouched; the real data stays where it is. Nothing in the change set waits on this.

**What this leaves, accepted:** there is NO separate development environment. The one project is production.
Accepted while there are ZERO users other than Samir. **The project-switch path (owner rule, cursor reset, the
once-only adoption prompt) is the prerequisite for ever splitting development from production**, and the owner
rule stays unruled until that day. Route B is shelved, not cancelled.

**Three conditions, all before any fancier touches the project:**

| condition | status |
|---|---|
| SEC-1: rotate the test account's password — it was exposed in a transcript and the project is production now | prepared, not run: `scratchpad/rotate_test_password.py` (signs in as the account, changes its own password through the auth endpoint, rewrites the deploy env, prints nothing secret); or the dashboard. Samir's call which |
| DF-2: delete the spike accounts outright — `spike-a@zajil.test`, `spike-b@zajil.test`, the auth users and their rows (69 + 34 = 103 on 2026-10-12) | SQL with before/after counts in `scratchpad/delete_spike_accounts.sql`; Samir runs it in the dashboard and pastes the output here |
| this record | this entry |

### Route B, for the day it is taken — the estimate, measured against the tree 2026-11-13

| item | finding |
|---|---|
| schema, trigger, RLS, grants | exist only as prose in `docs/SYNC-DESIGN.md` §1 with two amendments (opaque `record_id`, the sequence grant); no `.sql` file in either tree. Extract one migration file, run the verification query, then the live push and pull suites — introspection cannot prove a write |
| auth | public signups off (SPIKE §4f); accounts through the admin endpoint with the secret key, server side only; a new test account |
| keys | `ZAJIL_SUPABASE_URL`, `ZAJIL_SUPABASE_PUBLISHABLE_KEY`, `ZAJIL_TEST_EMAIL`, `ZAJIL_TEST_PASSWORD` in the deploy env; the live suites read `ZAJIL_LIVE_*` names through a wrapper that must be rewritten |
| what rebuilds | nothing in source names the project; `public/sync-config.js` is empty in the tree and written at stage time; one release through the pipeline; `live_deployment.py` reads the host from the served config and follows |
| code assuming the ref | none — eight files mention the host family: prose, test examples, comments. THE NET's family regex and the postbuild guard's needle assume `*.supabase.co`; a custom domain (CUTOVER §e.2) widens both in the same commit |
| device state assuming the project | `dataOwnerId`, `authUserId`, `syncCursor`, `lastAckedSeq`, `lastSyncAt`, `syncAnomalies` — none labelled with a project: the project-switch path above |
| the data | re-pushed by the devices through that path, or copied by SQL with the owner remapped; deletions older than the op-log tail are not re-sent |
| rollout | returning devices keep the old host until the new worker installs — the old project stays up until every device has updated |

## RF-20 — the port never started the sync loop, and three things followed from it (the 2026-10-05 audit, unrecorded until now)

**Where:** `startSyncLoop()` (`src/db/sync.js:1262`) has no caller in `app/` or `src/`; its only caller is the
test harness under `?sync=1` (`harness/view.tsx:50`). Vanilla calls it at boot (`js/app.js:252`). Read from the
code 2026-10-05, measured on the deployed build 2026-11-01/02 (stub-backed, constructed shapes):

```
A makes a bird, nobody presses anything, 70 s → POSTs from A: 0 · after a reload, 70 s → 0
sync toggled off→on → a bird pushes within 70 s with no press; after a reload → 0 again
vanilla, same stub, signed in: a pull GET within 8 s of boot
13 records, push refused, pull empty: pending 26 → 39 → 52 → 65, one op per record per press
RELOAD: sync row absent · syncStatus() = synced, pending 0 · ops pending in the log: 52
```

1. **Sync runs only at sign-in, on «مزامنة الآن», and in a timer chain the toggle starts that dies on reload.**
2. **The pending count is right only after a cycle** — module state, 0 after every reload, so the app shows
   «متزامن» over unsent work.
3. **`enqueueFirstSyncOps()` re-logs every record on every cycle while `lastSyncAt` is unset** (push refused and
   an empty pull): the counter grows by one op per record per press.
4. **No destructive confirmation mentions unsent changes**, and "first sync done" is only `lastSyncAt` existing.

**Status:** RULED 2026-11-13 — fixed by the change set recorded as RF-19 (the re-enqueue law, automatic sync,
honest status), after RF-15.

**Items 2 and 4 FIXED 2026-11-13 — honest status (RF-19 § 3):** the count is taken at boot and on every change, the
status is `unknown` until it has been, and replace, restore, the example removal and the clear say so when changes
are unsent. "First sync done" is still `lastSyncAt` existing; the enqueue no longer depends on it (item 3).

**Item 1 FIXED 2026-11-13 — automatic sync (the design is RF-19).** One coordinator, started at boot by
`src/components/SyncCoordinator.tsx`, owns every trigger; `screens/sync_auto.py` § coordinator (19 checks) and the
rewritten `tests/sync/loop_flag.py`. Measured BEFORE the build, coordinator on in every suite and the test-only
switch used nowhere: three assertions in two suites changed, all three because their precondition was the defect —
`sync_ui.py` wrote an error into settings by hand and the app's opening cycle correctly cleared it (2), and
`account_collision.py` relied on two edits staying unsent across a page load (1). Both now build the condition for
real. `push.py`, `pull.py`, `convergence.py`, `auth.py`, `gate.py`, `sign_in.py`, `tools.py`, `example_remove.py`:
unchanged and green. Seven mutants, each failing at its named check:

```
O1 the app opening runs no cycle        ✗ [open · O1 fails here] the app opening runs a cycle with no press — a pull within 8 s of boot  []
C1 the debounce runs no cycle           ✗ [change · C1 fails here] the burst is ONE push of the three birds, with no press  ([], ['قبل'])
F1 no single flight                     ✗ [single flight · F1 fails here] four requests at once make TWO cycles — …  (4, [True, True, True, True])
B1 jitter allowed past the cap          ✗ [backoff · B1 fails here] THE CAP IS A CAP: 400 delays drawn at the top of the curve, none above 15 minutes  {'min': 675695, 'max': 1120037, 'cap': 900000}
B2 online does not reset the backoff    ✗ [backoff · B2 fails here] THE ONLINE EVENT RESETS IT: …  {'failures': 8, 'nextBaseMs': 900000, …}
G1 the heartbeat armed in background    ✗ [background · G1 fails here] AN HOUR IN THE BACKGROUND: no timer armed and not one request  ({'timerArmed': True, …}, [('GET', 'user-A', 1)])
S1 sign-out leaves the timer armed      ✗ [sign-out · S1 fails here] the loop stops with the session: a timer was armed, and none is after sign-out
```

**Item 3 FIXED 2026-11-13 — the re-enqueue law.** `syncOnce()` enqueues once and records `firstEnqueueSeq`; the
collision CLEAR removes it with the data. `screens/sync_auto.py` § law: 13 records, every push refused, nothing
to pull, five cycles — op counts `[26, 26, 26, 26, 26]`; when the server accepts, 13 rows land and nothing is
pending. The mutant that does not record the mark fails at its assertion:

```
✗ [law · L1 fails here] FOUR MORE FAILED CYCLES LEAVE THE OP COUNT FLAT  [26, 39, 52, 65, 78]
``` With RF-3: the missing loop is also why the free project went quiet in October.

## RF-21 — `autoBackup()` has no caller: the restore screen promises a snapshot every 12 hours and none is ever taken

**Where:** `src/db/io.js:362` defines it; nothing in `app/` or `src/` calls it. Vanilla calls it at boot when due
and every 12 hours (`js/app.js:254-262`). The port shows «نسخ تلقائي داخلي كل 12 ساعة (آخر 7 نسخ)»
(`app/tools/view.tsx:103`, `parts.tsx:318`). Read from the code 2026-10-30; on the real device the restore row
reads «0 متاحة». The only snapshot the port writes is the `pre-import-…` one a replace-import takes.

**Status:** RULED 2026-11-01 a DEFECT, ranked highest of its class — a data-safety feature that silently does
nothing. Not built. Ordered after the sync change set is accepted: wire it, assert a snapshot exists after the
interval, mutation-prove the assertion.

## RF-22 — the example-data removal decides membership by loft and id shape, so a teaching bird filed elsewhere survives and keeps its ancestors

**Where:** `src/example-data.js` `examplePresence()`: `example` = birds filed in a present dataset loft whose id
is not a v4 uuid; the keep walk starts from every bird NOT in that set. Measured 2026-10-31 on the deployed
build, stub-backed, constructed shape: two teaching birds pulled with a loftId outside the four dataset-loft ids
became walk starts, kept 9 ancestors, and survived the removal as ordinary birds; the dialog said «لأن طيورًا من
لوفتك تنحدر منها», which was false there.

**Status:** RULED 2026-11-01 a DEFECT. Membership must be the shipped datasets' own ids, a fixed known set —
not the loft a record sits in, and NOT "non-v4" (a pre-1.4.0 or hand-edited record of a fancier must never fall
into the example set). Mutation-prove both directions. The dialog must NAME the birds that cause a keep, up to
a sensible limit. Not built; ordered after acceptance, with the A-set.

## DF-4 — photos have no server copy (an open PRODUCT decision, Samir's)

Media metadata syncs; blobs do not (SYNC-DESIGN §7). Measured 2026-11-13, deployed build, stub-backed: a
4032×3024 photo is 792 KB on the device that took it after the app's downscale, 400 bytes on the server (no
blob), and a second device receives the row with no bytes and shows a placeholder. A lost or cleared device
loses its photos unless an export was taken. Not a defect against the design; a decision to make before a pilot.

## RF-19 — the sync change set: the design, as ruled and as built (2026-11-13)

**Why:** the port synced only when a button was pressed, and said «متزامن» while it had not (RF-20). Silent data
loss with a reassuring label. One change set, four commits, shipped together: RF-15 first, because automatic sync
fires a pull seconds after every replace and restore.

### 1. The re-enqueue law
The first-login enqueue runs once (`firstEnqueueSeq`); a cycle that cannot reach the server logs nothing.

### 2. Automatic sync — one coordinator
`src/db/sync.js` owns every reason a cycle runs; `src/components/SyncCoordinator.tsx` starts it once, after the
shared boot. Guard `sync-single-owner` pins every call site outside it.

| trigger | behaviour |
|---|---|
| the app opening | a cycle at boot |
| a change | a cycle 3 s after the LAST change — a burst is one push |
| the `online` event | a cycle now, and the failure backoff starts again from one minute |
| foreground | a cycle now; the heartbeat is re-armed |
| background, and the page being put away | one cycle now (the push with `keepalive`, bodies under 60 KB), then NOTHING is armed |
| the heartbeat | 60 s while something is unsent · while failing 1, 2, 4, 8, 15 minutes and it stays at 15 (jitter ±25 %, never past the cap) · 5 minutes idle, to receive the other device's work |
| «مزامنة الآن» | a cycle now; resets the backoff |
| sign-out, sync switched off | nothing armed |

**Single flight.** Never two cycles at once. A request mid-cycle marks it dirty: exactly one follow-up runs, and
everyone who asked is answered by it.

**NOT COVERED, by the platform: nothing syncs while the app is closed.** A change made on another device arrives
when this one is next opened or brought forward. A push larger than the keepalive limit made as the app is put
away waits for the next open.

### 3. Honest status
«متزامن» means: nothing unsent, no error, online. The count is in memory and starts at zero on every load, so the
status is `unknown` — and shows nothing — until the op log has been counted; a failure inside its two-minute
quiet window is `unknown` or unsent, never synced. Unsent work is said in a fancier's words with since-when
(`pendingSince`); **no count of operations appears anywhere in the app** — it read as a count of birds and misled
for three weeks.

| where | wording (RULED 2026-11-13) |
|---|---|
| the row above a list, unsent | «تغييراتك محفوظة على هذا الجهاز ولم تُرسل بعد · منذ {d}» |
| the row, offline | «دون اتصال — تغييراتك محفوظة وستُرسل عند عودة الاتصال» |
| the row, failure | «تعذّر الإرسال — راجع الأدوات» |
| the row, session | «انتهت الجلسة — سجّل الدخول لإرسال تغييراتك» |
| the tools row, unsent | «لم تُرسل بعد» |
| the tools row, synced | «متزامن» with «آخر مزامنة ناجحة {d}» beneath it (one row, two lines: the value column is too narrow for both) |
| the sync screen | the row's words; the number is gone |

**RULED 2026-11-14: these ship as written; corrections come as ONE follow-up** (they were written because the
behaviour was ruled and needed words). They are FIFTEEN: I reported "seventeen" and "RF-15's twelve" at the STOP, a
miscount — RF-15's strings are ten. The fifteen: the unsent warning on the
destructive questions («تنبيه: على هذا الجهاز تغييرات لم تُرسل بعد إلى أجهزتك الأخرى.» · for the clear «…لم تُرسل بعد، وستضيع
بالمسح.»); the form's question («تغيّر هذا السجل على جهاز آخر» · «عُدّل هذا السجل على جهاز آخر بعد أن فتحته هنا. إن حفظت الآن
حلّت بياناتك مكان ذلك التعديل.» · «أعد التحميل», beside the existing «حفظ رغم التحذير»); and RF-15's ten replace and
restore strings (`confirm.replace.*`, `restore.confirm.*` in `src/i18n.ext.js`).

**The form.** The bird form edits a copy taken when it opened. If the record's `updatedAt` is no longer what it was
— a pull landed underneath — saving asks first: save anyway, or reload what is there now. No merge UI. **Only the
bird form.** The health sheet, the race-result sheet, the pair sheets and the loft rows in الأدوات save without this
check; each is a short-lived sheet, but the class is the same and they are NOT covered (a known gap, below).

### 4. The three situations
- **Offline for days:** ops accumulate once each; the row says unsent since when; retries settle at four an hour. On
  reconnect: pull first, so the other device's newer edits win per record and the local losers are superseded,
  never pushed (they stay in the log); then push.
- **Back online mid-edit:** an open form holds a draft, not an op, so a cycle does not touch it; if the cycle
  replaced the record underneath, the save asks (above).
- **Two devices with unsent work:** each pushes its own; the server trigger decides per record by operation time,
  then by device id; the loser re-pulls the winner and its pending op is superseded. Two records for one physical
  bird go to the duplicate finder, as before.

### Known gaps — RULED 2026-11-14: recorded, NOT fixed in the first deploy of this change set
- **Only the bird form warns about a record changed underneath it.** The health sheet, the race-result sheet, the
  pair sheets and the loft rows save without the check. When it is extended, the pair sheets come first.
- **A replace-import whose file carries no loft leaves the device without one until the next boot** (RF-15).
  MEASURED and FIXED 2026-11-15 in the follow-up set — see «The no-loft replace» below.
- **The restore list shows a pre-import snapshot by its raw key** (`pre-import-…`); only the question strips it.
- **The failure row repeats a word:** «تعذّر الإرسال — راجع الأدوات» sits beside the existing «الأدوات» link. RULED: it
  becomes «تعذّر الإرسال»; that change goes in the same follow-up as the string corrections, not before.
  DONE 2026-11-15 in the follow-up set: `sync.error` is «تعذّر الإرسال» / "Could not send" (the English RULED the
  same day); the `sync_ui` check was changed deliberately and now also asserts «راجع» is absent. The corrections to
  the fifteen strings were not in when this shipped (RULED: do not wait) and remain one follow-up.
- RULED the same day: the tools synced row on two lines is approved; the three ledger entries are approved.

### The no-loft replace — measured, ruled and fixed (2026-11-15)
A restore is `importAll(snapshot, 'replace')`, so it shares this. The probe, on the unfixed build
(`~/zajil-work/tf12/noloft_probe.py`, log `~/zajil-gate-logs/followup-noloft-probe.log`):

```
after the replace: {"lofts": [], "current": null, "currentLoft": null, "storedCurrent": null, "birds": [], "loftTombstones": 0}
a bird saved now: {"saved": true, "loftId": null, …}
after a reload (boot): {"lofts": [["7d6f5216", "(unnamed)"]], "current": "7d6f5216-…", "currentLoft": "a loft", "storedCurrent": "7d6f5216-…", "birds": [["probe", null]], "loftTombstones": 0}
```

Worse than «until the next boot»: a bird saved in between is filed under no loft and STAYS so after the boot makes
a loft. **RULED 2026-11-15, built as ruled:** `importAll()` ends with `ensureCurrentLoft()` when no loft is left —
the loft the next boot would have made, made at once. Four checks in `tests/e2e/screens/replace_sync.py`; the
mutant (the line removed) on its own harness build:

```
  ✗ [no loft · M-noloft fails here] after a replace whose file has no loft the device HAS one, at once: one loft, current, stored  {'lofts': [], 'inStore': [], 'current': None, 'real': False, 'stored': None, 'birds': []}
  ✓ [no loft] …and it is not the loft the replace dropped
  ✗ [no loft · M-noloft fails here] a bird saved straight afterwards is filed under that loft, not under none  [['بعد-الاستبدال', None]]
  ✗ [no loft] the next boot makes no second loft: the same one, the bird still in it
24 passed, 3 failed
```

The second of those checks passed under the mutant on its first writing (`None == None`); it was tightened to
require a real loft id and the mutant was run again. That is the output above.

**OPEN against RF-14, for a later ruling — NOT touched:** the lines just above (`src/db/io.js`), when SEVERAL lofts
remain after an import and the current one is not among them, make the first loft current. RF-14's rule for that
case (`ensureCurrentLoft()`) is to refuse the guess and create a fresh loft. The two disagree.

### The upgrade path — measured 2026-11-14 before the deploy; (b) did NOT pass as stated, and the deploy was held
Nothing in the gate boots this build over data written by the build before it. Measured stub-backed, THE NET armed
(0): a device state built with the LIVE build (`gh-pages 823dd68`, a fresh clone), then the staged release of
`16f9474` served at the same origin and booted over the same IndexedDB, the service worker left to update as it does
on a device. IndexedDB read raw from a blank page outside the app's scope, before and after. Constructed shapes
(12 birds and a named loft). Script and output are outside the tree: `~/zajil-work/upgrade/upgrade_path.py`,
`~/zajil-gate-logs/upgrade-path-run3.log`.

| state built on the live build | op count before → after the first boot and first cycle | pushed | records changed | tools row, every distinct text from the first frame |
|---|---|---|---|---|
| a. synced (marker absent) | 26 → 26 | nothing; one pull | 0 | «» · «متزامن» · «جارٍ…» · «متزامن» |
| a2. inflated by three refused cycles, then synced | 78 → 78 | nothing; one pull | 0 | the same |
| b. inflated, never synced (26, 39, 52, 65) | **65 → 78**, pending 65 → 0 | 1 POST, 13 rows, 13 records | 0 | «» · «دون اتصال» · «جارٍ…» · «متزامن» |
| c1. never signed in | 13 → 13 | no request in 75 s | 0 | the sign-in gate; no status |
| c2. synced, then signed out | 26 → 26 | no request in 75 s | 0 | the sign-in gate; no status |

**(b) is the finding.** A device that never synced on the old build carries no `firstEnqueueSeq`, so the new build's
first cycle runs the first-login enqueue ONE more time — thirteen more ops, one per record — writes the marker, and
then drains everything in one push. It never happens again, no record changes, and the server ends with one row per
record exactly as the device holds it. But the stated pass was "drains without multiplying", the check written
before the measurement was "the count after equals the count before", and 65 → 78 fails it. Not patched: reported
for a ruling. The fix, if ordered, is small: on a device that has never synced, an op log that already holds pending
ops is the first enqueue — write the marker without enqueueing again.

Two of my own checks in that run were wrong, not the build: one demanded that the list-screen row never appear in
(a), and it shows «جارٍ المزامنة…» for the length of the boot cycle; one demanded «لم تُرسل بعد» before «متزامن» in (b),
and the device shows the approved «دون اتصال» wording instead, because the old build's refused cycles left a network
error on record. In neither does «متزامن» appear while anything is unsent.

### RULED 2026-11-14 (evening): (b) is ACCEPTED as it stands — a known ONE-TIME upgrade behaviour; no fifth commit
A device that never synced on the old build runs the first-login enqueue once more on its first cycle under the new
build, drains in one push, and never repeats; no record changes. No real device is in that state: both of Samir's are
in (a), which passed. The (b) output, verbatim:

```
  [b] live build: op count after sign-in and after each further refused cycle [26, 39, 52, 65] · server rows 0
  [b] LIVE build, worker: holds · BEFORE: {"by origin": {"user": 65}, "firstEnqueueSeq": "(absent)", "lastAckedSeq": "(absent)", "lastSyncAt": "(absent)", "opSeq": 65, "ops in the log": 65, "pending (seq > lastAckedSeq)": 65, "records": {"birds": 12, "healthEvents": 0, "lofts": 1, "media": 0, "pairs": 0, "raceResults": 0, "tombstones": 0}, "syncCursor": "(absent)"}
  ✓ [b] the service worker took the new build with no app page open  holds
  ✓ [b] the worker update alone touched nothing in IndexedDB
  ✓ [b] this boot runs the NEW build  NEW
  [b] AFTER the first boot and first cycle of the new build (3 s on the tools screen): {"by origin": {"user": 78}, "firstEnqueueSeq": 78, "lastAckedSeq": 78, "lastSyncAt": "2026-11-14T05:57:00.032Z", "opSeq": 78, "ops in the log": 78, "pending (seq > lastAckedSeq)": 0, "records": {"birds": 12, "healthEvents": 0, "lofts": 1, "media": 0, "pairs": 0, "raceResults": 0, "tombstones": 0}, "syncCursor": 13}
  [b] op count 65 → 78 · pending 65 → 0 · firstEnqueueSeq (absent) → 78
  [b] requests during it: [["POST", 13], ["GET", 0, 13]]
  [b] pushed: 1 POST(s), 13 row(s), 13 distinct record(s) · by store {"birds": 12, "lofts": 1}
  [b] records changed on the device (every store but the op log, settings, backups; byte comparison): 0 
  [b] status shown from the first frame — tools row value, every distinct text in order: ["", "دون اتصال", "جارٍ…", "متزامن"] · the row as it stands: "المزامنةآخر مزامنة ناجحة 14 تشرين الثاني 2026، 08:57 ص (4 جمادى الآخرة 1448 هـ)متزامن"
  [b] the list-screen status row over the same time: ["(no row)", "offline: ⚡دون اتصال — تغييراتك محفوظة وستُرسل عند عودة الاتصال", "syncing: ⟳جارٍ المزامنة…", "(no row)"] · sign-in gate shown: False
  [b] the layer says: {"everSynced": true, "loop": "not in a production build (test-only export, tree-shaken)", "status": {"email": "a@zajil.test", "error": null, "lastSyncAt": "2026-11-14T05:57:00.032Z", "pending": 0, "pendingSince": null, "state": "synced"}, "unsent": {}}
  ✓ [b] the state is the ordered one: never synced, every op pending, the log inflated  (65, 65)
  ✗ [b] WITHOUT MULTIPLYING: the op count after the first boot and first cycle equals the count before  (65, 78)
  ✓ [b] DRAINS: nothing is pending after the first cycle  0
  ✓ [b] the server holds the 13 records, one row each  (13, 13, 13)
  ✓ [b] every pushed row carries the record exactly as the device holds it  (13, 13)
  ✓ [b] NO RECORD CHANGED on the device  []
  ✓ [b] the status starts as not-synced and ends «متزامن»  ['', 'دون اتصال', 'جارٍ…', 'متزامن']
  ✗ [b] «لم تُرسل بعد» is shown before «متزامن» ever is  ['', 'دون اتصال', 'جارٍ…', 'متزامن']
  ✗ [b] WITHOUT MULTIPLYING: the op count after the first boot and first cycle equals the count before
  ✗ [b] «لم تُرسل بعد» is shown before «متزامن» ever is
```

**The check marked ✗ stays as written.** `WITHOUT MULTIPLYING: the op count after … equals the count before  (65, 78)`
was written before the measurement and is stricter than the ruling; it is not relaxed after the fact. It fails
because of the accepted one-time enqueue and for no other reason. The other ✗, `«لم تُرسل بعد» is shown before
«متزامن» ever is`, was my wrong expectation (above).

### Deployed 2026-11-15 and re-verified from the live origin
`gh-pages 84d838c` on the mirror, built from `16f9474` (the staged release the upgrade path was measured on).
**Rollback target: `823dd68`.** Staged bytes verified before and on the clone; 158 files fetched from the origin and
compared by sha256, 0 differ; `live_deployment.py` against the live origin: **44 passed, 0 failed**, THE NET 0.

**A seventh request-counting assertion, found by the rehearsal and changed deliberately.** `live_deployment.py` is not
in the gate (it needs an origin), so the suite-impact measurement never ran it. Its last step pressed «مزامنة الآن»
after the example removal and counted the rows THAT PRESS pushed; with the coordinator the removal is sent three
seconds after it happens, and the press found nothing (`0 rows pushed`, rehearsal log `deploy-04-rehearsal.log`).
It now asserts the stronger thing — the tombstones reach the stubbed project with NO press, and the press afterwards
pushes nothing twice. Not relaxed: the count (≥ 68) is the same, taken from before the removal.

`syncLoopState()` and `hasEverSynced()` do not exist in a production build (tree-shaken), so "starts no loop" in (c)
is proved by the absence of any request over 75 s with ops pending (the heartbeat would be 60 s), not by reading a
timer.

### Standing with it
Route A (DF-3): the one Supabase project is production and there is NO separate development environment; accepted
at zero users. Photos have no server copy (DF-4).

### Proof
`tests/e2e/screens/sync_auto.py`, 51 checks, real timers driven with the page clock, the typography scan run on
every new string where it is drawn; `tests/sync/loop_flag.py` (contract rewritten); `screens/replace_sync.py` (23).
Mutants: L1 (law), O1 C1 F1 B1 B2 G1 S1 (coordinator, in RF-20), and for this commit:

```
H1 the status does not wait for the count after a load
   ✗ [invariant · H1 fails here] IT SURVIVES A RELOAD: from the first frame after boot the tools row never displays «متزامن» while a change is unsent  (['متزامن', 'لم تُرسل بعد', 'جارٍ…', 'لم تُرسل بعد'], {'state': 'pending', 'pendingInLog': 1})
H2 the status is not recounted when a change is made
   ✗ [invariant · H2 fails here] THE MOMENT A CHANGE IS MADE the status is «unsent», never «synced»  {'state': 'synced', 'pendingInLog': 1}
H3 the destructive questions are told nothing is unsent
   ✗ [confirm · H3 fails here] REPLACE warns … · RESTORE warns · THE EXAMPLE REMOVAL warns · THE CLEAR warns that the unsent changes will be LOST   (47 passed, 4 failed)
W1 the form does not notice the record changed underneath it
   ✗ [form · W1 fails here] THE RECORD CHANGED ON ANOTHER DEVICE WHILE THE FORM WAS OPEN: saving asks first   (47 passed, 4 failed)
```

**Assertions changed deliberately, never relaxed:** `sync_ui.py` (the two card checks made real, the pending wording,
the failure wording, the backoff curve and cap, "no pending count"), `account_collision.py` (the two unsent edits are
made inside the debounce), `screens/tools.py` (five checks that read the number now assert the state and the absence
of the number). Three spec strings the port no longer renders are in `guards/strings.ruled.json` with this ruling.

**Acceptance is on two real devices** (airplane mode, add a bird, unsent before and after a reload; airplane mode
off, press nothing, the bird on the other device within two minutes; an edit back the other way). Until then this
entry describes what was built, not what is accepted.

### ACCEPTED 2026-11-15 on Samir's two real devices — `gh-pages 84d838c`
As reported by Samir, on the phone and the PC, the live build:
- **Phone → PC with no press:** a bird's status change arrived.
- **PC → phone with no press:** a pair's hatched eggs arrived.
- **Offline:** a bird added in airplane mode showed the offline wording, then pushed on reconnect with no press and
  appeared on the PC.

**NOT observed on a real device: a reload while offline** (the second half of acceptance step 1 — «Reload: still
unsent, never «متزامن»»). That step is covered only by the suites (`screens/sync_auto.py`, and the deploy
verification's offline boot), stub-backed. It stays named as a gap until it is seen on a device.

### The follow-up set — deployed 2026-11-16 and re-verified from the live origin
RULED 2026-11-15: three items as one deploy after acceptance — TF-12's fix (`a6c8a1c`), the failure row
(`eab265d`), the no-loft replace (`1cfb924`); each on its own green full gate (`gate-09`, `-10`, `-11`:
2191 / 2191 / 2195 passed, 0 failed, control 548/548, no page-error record). The corrections to the fifteen strings
were not in (RULED: do not wait).

| item | value |
|---|---|
| live | `gh-pages 6a44f7a`, built from `1cfb924` |
| rollback target | `84d838c` (before it: `823dd68`) |
| staged | 159 files, scan clean, `BUILT_FOR /zajilv2/`, `VERSION zajil-v2.0.0-dev.1` |
| rehearsal on the Pages stand-in | 44 passed, 0 failed (`deploy2-04-rehearsal.log`) |
| bytes | 158 files fetched from the origin and compared by sha256, 0 differ (`deploy2-05-live-bytes.log`) |
| live verification | 44 passed, 0 failed; nothing reached the real project (`deploy2-06-live-verify.log`) |

Not done, not ordered: the mirror's `main` (`01117e2`).

## TF-11 — a reload invariant that could not fail: mutant H1 survived its own check

**Where:** `tests/e2e/screens/sync_auto.py`, first version of «IT SURVIVES A RELOAD» (2026-11-13).

**What:** the check reloaded the page AFTER a refused cycle had run. A refused cycle leaves `lastSyncError` on
record, and `syncStatus()` answers from that branch before it ever reaches the "has the op log been counted" test —
so the mutant that removes that test (H1) changed nothing the check could see: `49 passed, 0 failed`. The assertion
read as proof of the invariant and exercised a different line.

**Found by** running the mutant, which is the only reason it was found. **Fixed:** the reload now happens with a
change that no cycle has yet attempted, so there is no failure on record and the first frame drawn after boot is
the test; an observer installed before the app's scripts records every text the tools row ever holds. H1 now fails
there, quoted in RF-19. Two mutants (C1, W1) also ended in a traceback after their failed checks on the first run;
the steps after them were made non-raising and both were re-run to a clean summary.

**The lesson is the standing one:** an invariant check is not written until its mutant has been seen to fail AT it.

## TF-12 — one page error in `screens/example_remove.py`, once, not reproduced, source unknown (2026-11-14)

A full gate on a documentation-only change (`~/zajil-gate-logs/gate-05c-docs-upgrade.log`) failed one check:

```
[FAIL] screens/example_remove.py            47/48    80s
         ✗ zero page errors across 10 devices  ["Cannot read properties of undefined (reading 'name')"]
```

The same suite passed in the gate run twenty-eight minutes earlier on the same `next/` bytes, in each of the four
change-set gates, and in eight consecutive isolated runs made straight afterwards with the stack and the page address
captured (`er-flake-run1..8.log`: 48 passed, 0 failed, no page error, every time). So: seen once, under the load of a
full gate, never alone. The suite records only the message, so there is no stack, no device and no screen for the
one occurrence.

**What is not known, and is not claimed:** whether it is the app or the suite, and whether the change set introduced
it. It did not appear before the coordinator existed, but four gates with the coordinator also passed; one sighting
decides nothing. A render reading `.name` on a record that a removal or a pull has just taken away is the obvious
candidate, and it is a guess.

**Not fixed, nothing relaxed.** Proposed, for a ruling: every stub-backed suite's `pageerror` hook records the stack
and the page address, not only the message, so the next sighting names its source.

### TF-12 — the hook, three full runs, and a second sighting with its stack (2026-11-15)

**The hook (test-only).** `tests/e2e/_pageerr.py` — every `pageerror` hook in the stub-backed suites (59 hooks, 45
files) now records the message, the page address, the device (context, page, viewport), the step (the last ✓/✗ line
printed before it), the seconds into the script and the stack; prints it the moment it happens; and appends it to
`$ZAJIL_PAGEERR_LOG` when that is set. No check was changed, added or relaxed: the suites still fail on any page error.

**Three full runs with it** (`~/zajil-gate-logs/gate-07-tf12-run{1,2,3}.log`):

```
run 1 exit 1 ·   2184 passed, 1 failed across 33 steps, 1 skipped  ·  27.4 min · page-error records: 1
run 2 exit 0 ·   2185 passed, 0 failed across 33 steps, 1 skipped  ·  27.4 min · page-error records: 0
run 3 exit 0 ·   2185 passed, 0 failed across 33 steps, 1 skipped  ·  27.4 min · page-error records: 0
```

**The sighting, verbatim** (`~/zajil-gate-logs/tf12-pageerrors-run1.log`):

```
2026-11-15T09:40:33 Cannot read properties of undefined (reading 'name') | at http://127.0.0.1:46499/tools/ | device: context 1, page 1 · viewport 430x900 | step: after «✓ [shape · invariant] …and the row is still there with its count» | 76.8 s into example_remove.py | stack: TypeError: Cannot read properties of undefined (reading 'name') ⏎     at http://127.0.0.1:46499/_next/static/chunks/3sl7h4ze97y3g.js:1:15334 ⏎     at Array.map (<anonymous>) ⏎     at Module.eo (http://127.0.0.1:46499/_next/static/chunks/3sl7h4ze97y3g.js:1:15301)
```

**The stack points into the app.** Offsets 15301 / 15334 of that chunk are, in the build the run used, the last
statement of `examplePresence()` — `src/example-data.js:81`:

```js
lofts: present.map((id) => ({ id, name: state.lofts.get(id).name || '',
```

`present` is filtered by `state.lofts.has(id)` at the top of the function (line 58); between that and line 81 the
function awaits `idbGetAll('media')` (line 77). A loft that was there at line 58 and is gone by line 81 gives exactly
this error. The caller is the removal row on الأدوات (`app/tools/parts.tsx:400`), which recomputes on every layer
change — so a recompute started while `removeExampleData()` is deleting the teaching lofts can straddle the deletion.
The step fits: the sighting is in the last scenario of the suite, on the removal that follows the «row is still there»
check. That the recompute and the removal interleaved in this run is READ from the code and the step, not observed —
the hook records the stack, not the interleaving.

**What it does to the fancier — not measured.** The rejected promise is not handled, so that one recompute sets
nothing; the next layer change recomputes again. In both sightings every other check of the suite passed, including
«the row detached». Whether a real device can be left showing the removal row for lofts that no longer exist has not
been tested.

**Whether the change set introduced it: UNKNOWN.** The two lines involved date from `df6a42a` and were not touched by
the change set. Against that, in the gate logs kept: 0 sightings in the 2 baseline runs and the 2 runs before the
coordinator (`gate-00`, `-00-b`, `-01`, `-02`); 2 sightings in the 9 runs since the coordinator (`gate-03` … `gate-07-run3`);
0 in 8 isolated runs. Four runs without it prove nothing about a fault seen 2 times in 9, and the coordinator does add
layer-change events around a removal. Neither reading is established.

**STOPPED — not fixed, nothing relaxed.** Reported for a ruling before any change to `src/`.

### TF-12 — measured, ruled and fixed (2026-11-15, the follow-up set)

**RULED: HOLD until `84d838c` was accepted; accepted the same day on Samir's two devices.**

**The probe, on the unfixed build** (`~/zajil-work/tf12/stale_row_probe.py`, log
`~/zajil-gate-logs/tf12-stale-row-probe.log`; stub-backed, the net armed). One recompute of the removal row is held
at `examplePresence()`'s media read — `IDBObjectStore.getAll` on `media` hands back a stand-in request whose success
is delivered on release — and something is removed while it waits.

*A. Held across the whole removal.* The question was whether a device can be left showing the row for lofts that
are gone. On the unfixed build: no.

```
before: {"value": "38", "lofts": "الألوفت التجريبية: «لوفت إربد التعليمي»"}
removal ran: {'birds': 38, 'kept': 0} · truth {"lofts": [""], "birds": 0, "presence": null}
row AFTER the removal, held recompute NOT yet released: null · page errors so far: 0
row AFTER the held recompute is released: null
page errors: 1
row after a reload: null
```

The page error is TF-12's, same message, same two stack offsets: the cause is reproduced on demand. The row stays
gone only BECAUSE the late recompute throws before it can set anything.

*A2. Held across the deletion of one example bird.* A late recompute overwrites a newer one:

```
held recompute released at 844 ms · row 400 ms later: {"value": "38", …} · truth {… "birds": 37 …}
row 6 s later, nothing pressed: {"value": "37", …}
every value shown [ms since the observer started, value]: [[0, "38"], [40, "37"], [845, "38"], [3037, "37"]]
```

The old count stood for about 2.2 s, until the after-change sync cycle caused another recompute.

**Why skip-only was not built.** Skipping the missing loft and returning the rest would make the late recompute
return a result — no lofts, counts taken before the await — and the row would set it: the page error traded for
the stale row. Read from the code, not measured.

**RULED 2026-11-15, built as ruled.**
- `examplePresence()` (`src/example-data.js`) re-checks the lofts after the await and returns null when none is left.
- The row (`app/tools/parts.tsx`) drops a recompute that finishes after a newer one started.

**Tests** (`tests/e2e/screens/example_remove.py`, six checks, the same hold), and the two mutants, each on its own
harness build (`~/zajil-gate-logs/followup-mutants.log`):

```
═══ THE FIX
suite[fix-example_remove] exit 0 · 54 passed, 0 failed
═══ MUTANT M-recheck          (the re-check and the null return removed)
suite[M-recheck] exit 1 · 52 passed, 2 failed
  ✗ [TF-12 · M-recheck fails here] released AFTER its loft was removed, the held recompute raises no page error  ["Cannot read properties of undefined (reading 'name') | at http://127.0.0.1:34087/tools/ | …
  ✗ zero page errors across 12 devices
═══ MUTANT M-order            (the row sets whatever finishes last)
suite[M-order] exit 1 · 53 passed, 1 failed
  ✗ [TF-12 · M-order fails here] the held recompute, released late with the OLD count, is dropped — the row never shows 38 again  ('38', ['38', '37', '38', '37'])
```

**Still unknown, and still not claimed:** whether the sync change set introduced the sightings. The fix removes the
fault; it does not answer that.
