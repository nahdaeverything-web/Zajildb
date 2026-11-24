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

### RF-21 — BUILT 2026-11-16; first gate red, six rulings the same day, rebuilt (below)

**The caller.** `src/components/AutoBackup.tsx`, mounted once in `app/layout.tsx` beside the sync coordinator.
Vanilla's behaviour (`js/app.js:254-262`), unchanged: after the one shared boot a snapshot is taken if none was ever
taken or the last is older than the interval; then one every interval while the page stays open; never for an empty
register; a failure is swallowed. The interval and the number kept are now exported constants of the layer
(`AUTO_BACKUP_HOURS = 12`, `BACKUP_KEEP = 7`, `src/db/io.js`) and the restore screen prints THOSE, not literals.

**The suite.** `tests/e2e/screens/auto_backup.py`, 18 checks, harness build, the net armed. The interval is asserted
with the browser's clock driven: 11 h 59 min after the boot there is one snapshot, 12 h 01 min after it there are
two, stamped twelve hours apart.

**The mutants**, each on its own harness build (`~/zajil-gate-logs/autobackup-mutants.log`, `autobackup-M-boot-2.log`):

```
═══ MUTANT M-interval         (the setInterval line removed)
suite exit 1 · 16 passed, 2 failed
  ✗ [interval · M-interval fails here] 12 h 01 min after the boot, the page still open: a second snapshot EXISTS  {'n': 1, 'ids': ['2026-11-15T21:21:19.494Z'], 'kinds': ['auto-backup'], 'birds': [1], 'last': '2026-11-15T21:21:19.494Z', 'hours': 12, 'keep': 7}
  ✗ [interval] …stamped twelve hours after the first  ['2026-11-15T21:21:19.494Z']
═══ MUTANT M-boot             (the due-at-boot line removed)
suite exit 1 · 11 passed, 7 failed
  ✗ [boot · M-boot fails here] a register with birds and no snapshot yet: the boot takes ONE, an automatic one, holding both birds  {'n': 0, 'ids': [], 'kinds': [], 'birds': [], 'last': None, 'hours': 12, 'keep': 7}
  ✗ [boot · M-boot fails here] the last snapshot 13 hours old: the boot takes a new one  {'n': 0, 'ids': [], …, 'last': '2026-11-15T08:22:21.248Z', 'hours': 12, 'keep': 7}
  (and five that depend on a first snapshot existing)
═══ MUTANT M-empty            (the empty-register condition removed)
suite exit 1 · 15 passed, 3 failed
  ✗ [boot · empty] an empty register is not snapshotted  {'n': 1, …, 'birds': [0], …}
  ✗ [interval · empty] the register emptied, another interval passes: no snapshot of nothing
```

M-boot's first run died on an `IndexError` in the «kept» check — red for the wrong reason (TF-9's lesson again). The
check was made non-raising and the mutant run again; that second run is the one quoted.

**Does the restore screen's wording match what happens? Measured** (`~/zajil-work/followup/backup_wording_probe.py`,
log `~/zajil-gate-logs/autobackup-wording-probe.log`). The screen says «نسخ تلقائي داخلي كل 12 ساعة (آخر 7 نسخ)».

1. **«كل 12 ساعة» — true only while the app is open or is opened.** A snapshot is taken at a boot when twelve hours
   have passed, and every twelve hours on a page that stays open. A device that is not opened takes none; a device
   whose register was empty at boot and filled later (a first sync) takes its first at the next boot or after twelve
   hours open. This is vanilla's behaviour. Not changed.
2. **«آخر 7 نسخ» — FALSE once a replace-import or a restore has run.** The seven are counted over the whole store,
   and a `pre-import-…` snapshot sorts after every dated one, so it is never the one removed:
   ```
   P2. 3 replace-imports, then nine automatic snapshots:
       after the nine:  7 stored — automatic 4, pre-import 3
   P2. 7 replace-imports, then nine automatic snapshots:
       after the nine:  7 stored — automatic 0, pre-import 7
   ```
   After seven replaces or restores every automatic snapshot is deleted in the call that wrote it, while
   `lastAutoBackup` records that one was taken. Vanilla has the same code; it was unreachable in the port until now.
3. **«آخر نسخة تلقائية: {d}» shows the OLDEST, and the list is oldest-first.** The screen reads the store in key
   order and takes the first; vanilla sorts newest first (`js/views/tools.js:126`). A port defect, invisible while
   there was never more than one snapshot:
   ```
   P1. three automatic snapshots, oldest → newest: ['…T21:20:24.734Z', '…T21:20:25.837Z', '…T21:20:26.940Z']
       rows top → bottom (data-id): ['…T21:20:24.734Z', '…T21:20:25.837Z', '…T21:20:26.940Z']
   ```
   A `pre-import-…` snapshot always lists last, whatever its date.
4. **The الأدوات row's «{n} متاحة» is read once, at boot** — it can be one short of the snapshot the same boot takes,
   until the screen is opened again. Read from the code (`app/tools/view.tsx:37`), not measured.

**NOT fixed — 2, 3 and 4 are reported for a ruling.** Proposed: (2) the seven apply to the dated snapshots only,
and the pre-import ones get their own, separately ruled, limit; (3) newest first as vanilla, with a pre-import
snapshot placed by its date; (4) the row re-reads on a layer change.

**The full gate with the caller wired is NOT green — `gate-13-autobackup.log`: 2209 passed, 4 failed. NOT committed,
NOT deployed; STOPPED for rulings.** Snapshots now exist where no suite had ever seen one. The three suites:

```
[FAIL] screens/account_collision.py         47/48
  ✗ [CLOSED LIMIT] …C's edit stays local, and nothing on the device changed — not even an owner record  {"counts": [{"backups": 0, "birds": 3, …}, {"backups": 1, "birds": 3, …
[FAIL] screens/sync_auto.py                 50/51
  ✗ [typography] every new string, where it is drawn — … — is in a face that has Arabic, and unspaced  [('NO-ARABIC-COVERAGE ', '16 تشرين الثاني 2026، 01:10 ص (6 جمادى ا')]
[FAIL] screens/tools.py                    136/138
  ✗ [data_loss #5] PHOTOS SURVIVE the restore — a snapshot carries no media, so it must not wipe it  2 before, 0 after
  ✗ …and the records came back with it  28 -> 21
```

- **`account_collision`** — a device stopped at the account collision boots, and the boot takes a snapshot: the
  `backups` store goes 0 → 1 while the check says nothing on the device changed. Nothing else moved. Whether a
  snapshot counts as «a change on the device» there is a ruling, not mine to make by editing the count.
- **`sync_auto`** — a REAL defect in the restore list, exposed, not caused: a dated snapshot row prints its date in
  `plexMono` (`<strong className={s.data}>`, `app/tools/parts.tsx`), a face with no Arabic. Reproduced alone, with
  the face recorded. Until now the only row any suite saw was a `pre-import-…` one.
- **`tools`** — the test presses the FIRST «استرجاع» expecting the snapshot it has just taken; the list is
  oldest-first (wording gap 3 above) and the first is now a snapshot an earlier boot took, seven birds older. The
  photo it then looks for is on a bird that restore dropped. Not a loss of a photo on a surviving bird — measured
  separately (`~/zajil-gate-logs/autobackup-restore-media-probe.log`):
  ```
  before the restore: {"birds": ["جديد", "قديم"], "media": [["on-new.png", "جديد"], ["on-old.png", "قديم"]], "mediaTombstones": 0}
  after restoring the snapshot taken before both photos and before «جديد»: {"birds": ["قديم"], "media": [["on-new.png", "(bird gone)"], ["on-old.png", "قديم"]], "mediaTombstones": 0}
  ```
  The photo on the bird that stayed survives. **The photo on the bird the restore dropped is left in the store,
  pointing at a bird that is gone, with no tombstone** — an orphan. Against RF-15 («a replace and a restore
  tombstone every record they drop»): open, reported, not investigated further.

#### RF-21 — the six rulings of 2026-11-16, as built

**A correction to the record above first.** It says «a device stopped at the account collision boots, and the boot
takes a snapshot». The order was the other way round: the suite opens the sign-in screen, THAT boot took the snapshot,
and the collision was met afterwards, on submit. There is no stored «stopped at the collision» state for a caller to
read at boot. What a device stopped at a collision always is, is a configured build with no session — the sign-in
gate (`src/components/Gate.tsx`). So ruling 1 is built on the gate's own two conditions.

| ruling | built |
|---|---|
| 1. the caller skips a device stopped at the collision; the check keeps counting backups | `AutoBackup.tsx` takes nothing while the gate is shut (configured build, no session). The condition is read each time a snapshot is due. `account_collision.py` is untouched and passes 48/48. |
| 2. the snapshot row's face | `<strong className={s.data}>` → `<strong>` in the restore list (`app/tools/parts.tsx`); the row also shows a pre-import snapshot's moment, not its key. |
| 3. newest first, a pre-import snapshot by its date; «آخر نسخة تلقائية» the newest automatic | `listBackups()` sorts by the snapshot's moment, newest first (`backupMoment`); the line reads the first row that is not a pre-import one. `tools.py` is untouched and passes 138/138. |
| 4. seven automatic, separately three pre-import, neither evicting the other | `pruneBackups()` (`src/db/io.js`), called by both writers: the seven newest interval snapshots, the three newest pre-import ones (`PRE_IMPORT_KEEP = 3`). |
| 5. «{n} متاحة»: measure, then re-read on a layer change | measured below; the tools row and the restore list both re-read on every layer change; `autoBackup()` now raises one (`type: 'backup'`), which the sync coordinator ignores — a snapshot is not the fancier's work and starts no cycle. |
| 6. the screen says what is true | `backup.auto` overridden in `src/i18n.ext.js`, with three numbers read from the layer's constants. PROPOSED wording, shipped flagged in the report, awaiting Samir's correction with the fifteen. |

**The proposed string (the sixteenth), drawn under the restore list and under the «البيانات» section of الأدوات:**
«تُؤخذ نسخة تلقائية على هذا الجهاز عند فتح التطبيق، أو وهو مفتوح، كلما مضت {h} ساعة على آخر نسخة. يُحتفظ بآخر {n}
نسخ تلقائية، وبآخر {m} نسخ أُخذت قبل استيراد بالاستبدال أو قبل استرجاع.»

**Ruling 5, measured before the fix** (`~/zajil-work/b2/available_probe.py`, logs `b2-available-probe-before.log`,
`-after.log`):

```
before the boot: snapshots stored 0
الأدوات, +0.3s: row says «0 متاحة» · stored 1
الأدوات, +4.0s: row says «0 متاحة» · stored 1
after a reload: row says «1 متاحة» · stored 1
استرجاع opened 13 h after the last snapshot: rows listed 1 · stored 2
```
and after it: `«1 متاحة» · stored 1` at +0.3 s, `rows listed 2 · stored 2`. The restore LIST had the same one-short
read as the row; it was fixed with it, the same way.

**Ruling 1's question — does the collision CLEAR wipe the snapshots? YES, both kinds, measured.** `clearLocalData()`
clears the `backups` store and removes `lastAutoBackup` (it is not a device setting). Asserted in the suite on a
device holding two interval snapshots and one pre-import snapshot of account A:

```
  ✓ [CLEAR · setup] account A's device, signed out: two interval snapshots and one pre-import snapshot stored, «آخر نسخة» recorded
  ✓ [gate] STOPPED at the collision: the snapshots store is exactly as it was — nothing taken, nothing removed
  ✓ [CLEAR] account B chose CLEAR: NONE of A's snapshots is left on the device, of either kind, and «آخر نسخة» is gone with them
  ✓ [CLEAR] …so under account B the restore screen offers nothing to restore
```
Ownership changes only through `clearLocalData()`, so there is no other path by which one account's snapshot is on a
device under another account.

**The suite: `tests/e2e/screens/auto_backup.py`, 38 checks. Nine mutants, each on its own harness build, each failing
its named check** (`~/zajil-gate-logs/b2-mutants.log`; the suite is 38/0 again on the restored build):

```
═══ MUTANT M-gate      (the gate condition removed)                         36 passed, 2 failed
  ✗ [gate · M-gate fails here] a configured build with NO session and two birds — the sign-in gate, where a collision stops a device: the boot takes no snapshot  {'n': 1, …
  ✗ [gate · M-gate fails here] …nor does opening the sign-in screen itself  {'n': 1, …
═══ MUTANT M-kinds     (one shared limit of seven, as before)               34 passed, 4 failed
  ✗ [kinds · M-kinds fails here] seven replaces: the THREE newest pre-import snapshots are kept, and they are the last three taken  [seven pre-import ids]
  ✗ [kinds · M-kinds fails here] THE RULED PROOF — seven replaces, then nine interval snapshots: 7 interval and 3 pre-import remain  {'auto': 0, 'pre': 7}
═══ MUTANT M-order     (listBackups() unsorted)                             35 passed, 3 failed
  ✗ [order · M-order fails here] the layer lists the snapshots NEWEST FIRST, each pre-import one at its own moment among the interval ones  ['2026-03-10T08:00:00.000Z', '2026-03-12T07:00:00.000Z', 'pre-import-2026-03-11T09:00:00.000Z', 'pre-import-2026-03-13T06:00:00.000Z']
  ✗ [order · M-order fails here] …and the restore screen draws them in that order
═══ MUTANT M-last      («آخر نسخة تلقائية» reads the first row)             37 passed, 1 failed
  ✗ [last · M-last fails here] «آخر نسخة تلقائية» names the newest INTERVAL snapshot — the second row — though a pre-import one is newer  ('آخر نسخة تلقائية: pre-import-2026-03-13T06:00:00.000Z', …
═══ MUTANT M-face      (the mono face back on the row)                      36 passed, 2 failed
  ✗ [typography · M-face fails here] the four dated rows are drawn in a face that has Arabic  [('NO-ARABIC-COVERAGE ', 'plexMono', '13 آذار 2026، 09:00 ص (24 رمضان 1447 هـ)'), …
═══ MUTANT M-count     (row and list read once)                             36 passed, 2 failed
  ✗ [count · M-count fails here] الأدوات opened as the boot that takes the first snapshot: the row says «1 متاحة», as stored  ('0 متاحة', 1)
  ✗ [count · M-count fails here] استرجاع opened as the boot that takes a second one: the list shows both  (1, 2)
═══ MUTANT M-interval  (the setInterval line removed)                       36 passed, 2 failed
  ✗ [interval · M-interval fails here] 12 h 01 min after the boot, the page still open: a second snapshot EXISTS  {'n': 1, 'ids': ['2026-11-16T06:39:07.648Z'], …
═══ MUTANT M-boot      (the due-at-boot line removed)                       27 passed, 11 failed
═══ MUTANT M-empty     (the empty-register condition removed)               29 passed, 9 failed
```
M-last, unmutated, also shows what the line printed for a pre-import first row before ruling 3: the raw key.

**Left as it is, and said so.** (a) A device that signs in does not take a snapshot at that moment: its first is at
the next boot or the next interval tick, as before. (b) A device signed in as one account that opens the sign-in
screen still takes its due snapshot at that boot — it is that account's own data under that account's own session.
(c) An existing device holding more than three pre-import snapshots is brought down to three at its next snapshot of
either kind.

#### RF-21 — deployed 2026-11-16

| item | value |
|---|---|
| commit | `9039e8a`, full gate `gate-14-autobackup-ruled.log`: 2233 passed, 0 failed, control 548/548, no page-error record |
| live | `gh-pages 787a40c`, built from `9039e8a` |
| rollback target | `6a44f7a` |
| staged | 159 files, scan clean; rehearsal on the local stand-in 44 passed, 0 failed |
| live bytes | 158 files fetched and compared by sha256, 0 differ |
| live verification | `live_deployment.py` 44 passed, 0 failed; nothing reached the real project |
| logs | `~/zajil-gate-logs/deploy3-01..06-*.log` |

NOT yet accepted on Samir's two real devices. The live verification does not exercise the snapshot caller itself; what
it proves is that the bytes served are the bytes of the gated commit.

#### The dropped bird's photos — measured for RESTORE and for REPLACE-IMPORT (PROPOSAL ONLY, nothing built)

`~/zajil-work/b2/orphan_probe.py`, log `~/zajil-gate-logs/b2-orphan-probe.log`. Two birds, «قديم» with on-old.png and
«جديد» with on-new.png; the point in time put back holds «قديم» only.

```
═══ R. RESTORE of an automatic snapshot taken when only «قديم» existed
  what the question is given (replacePreview): {"removed": 1, "removedBirds": 1, "removedOthers": 0}
  after the restore: {"birds": ["قديم"], "media": [["on-new.png", "(bird gone)", "3 B"], ["on-old.png", "قديم", "2 B"]], "mediaTombstones": 0, "birdTombstones": 1, "mediaDeleteOps": 0, "birdDeleteOps": 1}
  a full export taken now carries media: ['on-new.png', 'on-old.png']
  ROLLBACK — restoring the pre-import snapshot that restore took: {"birds": ["جديد", "قديم"], "media": [["on-new.png", "جديد", "3 B"], ["on-old.png", "قديم", "2 B"]], …}
═══ I1. REPLACE-IMPORT of a full export (WITH media) taken when only «قديم» existed
  what the question is given (replacePreview): {"removed": 1, "removedBirds": 1, "removedOthers": 0}
  after the replace: {"birds": ["قديم"], "media": [["on-old.png", "قديم", "2 B"]], "mediaTombstones": 1, "birdTombstones": 1, "mediaDeleteOps": 1, "birdDeleteOps": 1}
  ROLLBACK — restoring the pre-import snapshot that replace took: {"birds": ["جديد", "قديم"], "media": [["on-old.png", "قديم", "2 B"]], …}
═══ I2. REPLACE-IMPORT of a file that holds BOTH birds and NO media (media: [])
  what the question is given (replacePreview): {"removed": 0, "removedBirds": 0, "removedOthers": 0}
  after the replace: {"birds": ["جديد", "قديم"], "media": [], "mediaTombstones": 2, "birdTombstones": 0, "mediaDeleteOps": 2, "birdDeleteOps": 0}
  ROLLBACK — restoring the pre-import snapshot that replace took: {"birds": ["جديد", "قديم"], "media": [], …}
═══ D. for comparison: deleting «جديد» by hand, then undoing it
  after the delete: {"birds": ["قديم"], "media": [["on-old.png", "قديم", "2 B"]], "mediaTombstones": 1, …}
  after the undo: {"birds": ["جديد", "قديم"], "media": [["on-new.png", "جديد", "3 B"], ["on-old.png", "قديم", "2 B"]], "mediaTombstones": 0, …}
```

1. **The two paths already differ.** A restore keeps every photo, orphaning those of a dropped bird; a replace-import
   deletes every photo that is not in the file, with a tombstone and a delete op — the cascade, in effect, already.
2. **The orphan is what makes a restore reversible today.** Rolling back with the pre-import snapshot returns «جديد»
   WITH its photo. After a replace-import the same rollback returns «جديد» without it: the photo is gone for good.
3. **Neither question counts photos.** `replacePreview()` counts the record stores only.
4. **I2 — a replace from a file with no media deletes every photo on the device, on birds that stay, while the
   question is given «0 removed» and says «لن يُحذف شيء».** The app's own export always carries media; whether an
   export from a second device (which holds the media rows and no blobs) produces such a file is NOT measured.
5. The orphan travels nowhere and is cleaned by nothing: no tombstone, no op; it is carried in every full export.

**Proposed for a ruling.** Photos have no server copy and a snapshot carries no media, so a photo deleted by a
restore cannot come back by any means the app has. Two shapes:
- **(A) the cascade, as Samir leans.** A restore tombstones and deletes a dropped bird's photos, like a bird delete;
  the question states how many photos will be lost; string 5 loses «الصور والوثائق تبقى كما هي». Cost: a restore
  stops being reversible for photos — the rollback returns the bird bare — and the question must say that too.
- **(B) keep, do not orphan forever.** A restore leaves a dropped bird's photos in place, as now; string 5 says they
  are kept on this device and return if the bird does; the orphans are removed only when their bird can no longer
  come back (no kept snapshot holds it). Cost: a rule to write and prove, and hidden storage until then.
- **Recommended: (A) for consistency with replace-import and bird delete, with the count and the irreversibility in
  the question** — and, whichever is ruled, the two defects that are independent of it: both questions count photos
  (3), and a replace never deletes the photo of a bird that STAYS merely because the file carries no media (4).

#### The dropped bird's photos — RULED 2026-11-16 (P1–P3), as built

The ruling differs from the proposal above: **a restore is an undo, and must not destroy the only copy.**

| | ruled | built |
|---|---|---|
| P1 | a restore keeps photos, as before; a returning bird gets its photos back; string 5 says what is true; no orphan cleanup now | `droppedMediaByReplace()` returns nothing for a snapshot payload; `restore.confirm.lead` reworded (proposed) |
| P2 | a replace-import deletes a photo ONLY when its bird is dropped | the media store is no longer cleared; the photos of the birds the replace drops (and that the file does not itself carry) are tombstoned and deleted with the other dropped records; every other photo is left alone |
| P3 | both questions count the photos that will be lost and say they cannot be recovered; «لن يُحذف شيء» only when that includes photos | `replaceMediaLoss()` feeds the replace question (`confirm.replace.photos`, proposed). A restore loses none by P1, so its question counts none and says they stay |

Read literally and to be confirmed: a photo ALREADY orphaned by an earlier restore is not deleted by a later
replace-import (its bird is not dropped by that replace; it was gone already). Under P2 a replace can no longer
produce "nothing removed, photos lost", so the guard on «لن يُحذف شيء» cannot be exercised by a constructed case.

**OPEN ITEM — hidden orphan storage.** A photo whose bird a restore dropped stays in the media store, drawn nowhere,
carried by nothing (a full export of such a device was measured to include it). Nothing removes it. Not built, by ruling.

**Measured first, as ordered — the second device** (`~/zajil-work/photos/second_device_probe.py`; harness build, stub
backend, the net armed). A second device holds the media ROWS and no bytes:

```
BEFORE (f27338f)
  ONE, after adding two birds with a photo each and syncing: {"birds": ["جديد", "قديم"], "media": [["on-new.png", "جديد", "NO BLOB"], ["on-old.png", "قديم", "NO BLOB"]], "mediaTombstones": 0, "mediaDeleteOps": 0}
  ONE, with the bytes put back by the probe (the sync cycle removed them: see the blob probe): {"birds": ["جديد", "قديم"], "media": [["on-new.png", "جديد", "3 B"], ["on-old.png", "قديم", "2 B"]], "mediaTombstones": 0, "mediaDeleteOps": 0}
  TWO, after its first pull: {"birds": ["جديد", "قديم"], "media": [["on-new.png", "جديد", "NO BLOB"], ["on-old.png", "قديم", "NO BLOB"]], "mediaTombstones": 0, "mediaDeleteOps": 0}

═══ 1. what does TWO export?
  layer exportAll():      {"ok": false, "error": "Failed to execute 'readAsDataURL' on 'FileReader': parameter 1 is not of type 'Blob'."}
  layer exportAllBlob():  {"ok": false, "error": "Failed to execute 'readAsDataURL' on 'FileReader': parameter 1 is not of type 'Blob'."}
  the screen «تصدير الكل» on TWO: NO FILE was downloaded · TimeoutError
  toasts on TWO: [] · console errors: ["export failed TypeError: Failed to execute 'readAsDataURL' on 'FileReader': parameter 1 is not of type 'Blob'.\n    at http://127.0.0.1:45761/_next/static/chunks/1iusteik7xahz.js:1:16820\n    at new Pro"] · page errors: []

═══ 2. the nearest file TWO could hand over: its records with NO media (media: []) — replace-imported on ONE
  the file: birds 2 · media rows 0 · kind None
  ONE, what the question is given (replacePreview): {"removedBirds": 0, "removedOthers": 0, "removed": 0}
  ONE, after the replace: {"birds": ["جديد", "قديم"], "media": [], "mediaTombstones": 2, "mediaDeleteOps": 2}

═══ 3. a hand-made file with media ROWS that carry no dataURL (what a blobless export would look like) — replace-imported on a fresh ONE
  a device holding both photos WITH blobs: {"birds": ["جديد", "قديم"], "media": [["on-new.png", "جديد", "2 B"], ["on-old.png", "قديم", "2 B"]], "mediaTombstones": 0, "mediaDeleteOps": 0}
  importAll(replace): {"ok": true, "counts": {"birds": 2, "pairs": 0, "raceResults": 0, "healthEvents": 0, "lofts": 1, "media": 2, "skipped": 0, "removed": 0}}
  after: {"birds": ["جديد", "قديم"], "media": [["on-new.png", "جديد", "335 B"], ["on-old.png", "قديم", "335 B"]], "mediaTombstones": 0, "mediaDeleteOps": 0}
  page errors: [] [] []
  ✓ [NET] every request to the backend host family was answered by a stub — nothing reached the real project  

UNDER P2
═══ 2. the nearest file TWO could hand over: its records with NO media (media: []) — replace-imported on ONE
  the file: birds 2 · media rows 0 · kind None
  ONE, what the question is given (replacePreview): {"removedBirds": 0, "removedOthers": 0, "removed": 0}
  ONE, after the replace: {"birds": ["جديد", "قديم"], "media": [["on-new.png", "جديد", "3 B"], ["on-old.png", "قديم", "2 B"]], "mediaTombstones": 0, "mediaDeleteOps": 0}
```

So: **a second device cannot export at all** — the layer throws on the first media row with no bytes and the screen
says «تعذّر التصدير. جرّب مرة أخرى.» (RF-4, here measured for the FULL export, not only a share). It therefore cannot
produce a media-less file by itself; the nearest thing, its records with `media: []`, deleted both photos on the first
device before P2 and deletes none under it.

**Suite** `tests/e2e/screens/photos_replace.py`, 19 checks. **Mutants** (one harness build each, `~/zajil-work/photos/mutants.sh`):

```
═══ MUTANT M-p2
  mutated: src/db/io.js
build exit 0
suite exit 1 · 14 passed, 5 failed
  ✗ [P2 · M-p2 fails here] a replace from a both-birds, no-media file: BOTH photos are still on the device, with their bytes  {'birds': ['جديد', 'قديم'], 'media': [], 'mediaTombstones': 2, 'mediaDeleteOps': 2}
  ✗ [P2 · M-p2 fails here] …no photo was tombstoned and no deletion of one is queued for the other devices  {'birds': ['جديد', 'قديم'], 'media': [], 'mediaTombstones': 2, 'mediaDeleteOps': 2}
  ✗ [P2 · M-cascade fails here] the dropped bird's two photos are deleted with it, each tombstoned and queued as a deletion  {'birds': ['قديم'], 'media': [], 'mediaTombstones': 3, 'mediaDeleteOps': 3}
  ✗ [P2 · M-p2 fails here] …and the photo of the bird that STAYS is kept, bytes and all, though the file carried no media  {'birds': ['قديم'], 'media': [], 'mediaTombstones': 3, 'mediaDeleteOps': 3}
  ✗ [P3] the question told the truth: restoring the pre-import snapshot returns «جديد» WITHOUT its photos  {'birds': ['جديد', 'قديم'], 'media': [], 'mediaTombstones': 3, 'mediaDeleteOps': 3}

═══ MUTANT M-p1
  mutated: src/db/io.js
build exit 0
suite exit 1 · 17 passed, 2 failed
  ✗ [P1 · M-p1 fails here] a restore to a point before «جديد»: the bird goes, and NO photo is deleted — its photo stays on the device, with its bytes  {'birds': ['قديم'], 'media': [['on-old.png', 'قديم', 2]], 'mediaTombstones': 1, 'mediaDeleteOps': 1}
  ✗ [P1 · M-p1 fails here] undoing the restore: «جديد» returns and its photo is ITS photo again, with its bytes  ({'birds': ['جديد', 'قديم'], 'media': [['on-old.png', 'قديم', 2]], 'mediaTombstones': 1, 'mediaDeleteOps': 1}, [])

═══ MUTANT M-cascade
  mutated: src/db/io.js
build exit 0
suite exit 1 · 14 passed, 5 failed
  ✗ [P3 · M-count fails here] the question counts the photos that go with the dropped bird — 2 — and says they cannot be recovered  استبدال السجلّ؟  سيُحذف من السجلّ 1 طيرًا و0 سجلًا آخر غير موجودة في الملف، ويحلّ محتوى الملف مكانها. متابعة؟  إلغاء استبدال
  ✗ [P2 · M-cascade fails here] the dropped bird's two photos are deleted with it, each tombstoned and queued as a deletion  {'birds': ['قديم'], 'media': [['on-new-2.png', '(bird gone)', 4], ['on-new.png', '(bird gone)', 3], ['on-old.png', 'قديم', 2]], 'mediaTombstones': 0, 'mediaDeleteOps': 0}
  ✗ [P2 · M-p2 fails here] …and the photo of the bird that STAYS is kept, bytes and all, though the file carried no media  {'birds': ['قديم'], 'media': [['on-new-2.png', '(bird gone)', 4], ['on-new.png', '(bird gone)', 3], ['on-old.png', 'قديم', 2]], 'mediaTombstones': 0, 'mediaDeleteOps': 0}
  ✗ [P3] the question told the truth: restoring the pre-import snapshot returns «جديد» WITHOUT its photos  {'birds': ['جديد', 'قديم'], 'media': [['on-new-2.png', 'جديد', 4], ['on-new.png', 'جديد', 3], ['on-old.png', 'قديم', 2]], 'mediaTombstones': 0, 'mediaDeleteOps': 0}
  ✗ [P2] a replace from a file WITH media: the dropped bird's photo goes (counted as 1 in the question), the file's photo is here with its bytes  ('استبدال السجلّ؟  سيُحذف من السجلّ 1 طيرًا و0 سجلًا آخر غير موجودة في الملف، ويحلّ محتوى الملف مكانها. متابعة؟  إلغاء استبدال', {'birds': ['قديم'], 'media': [['on-new.p

═══ MUTANT M-count
  mutated: app/tools/parts.tsx
build exit 0
suite exit 1 · 17 passed, 2 failed
  ✗ [P3 · M-count fails here] the question counts the photos that go with the dropped bird — 2 — and says they cannot be recovered  استبدال السجلّ؟  سيُحذف من السجلّ 1 طيرًا و0 سجلًا آخر غير موجودة في الملف، ويحلّ محتوى الملف مكانها. متابعة؟  إلغاء استبدال
  ✗ [P2] a replace from a file WITH media: the dropped bird's photo goes (counted as 1 in the question), the file's photo is here with its bytes  ('استبدال السجلّ؟  سيُحذف من السجلّ 1 طيرًا و0 سجلًا آخر غير موجودة في الملف، ويحلّ محتوى الملف مكانها. متابعة؟  إلغاء استبدال', {'birds': ['قديم'], 'media': [['on-old.p

═══ restored
 M app/tools/parts.tsx
 M src/db.js
 M src/db/io.js
 M src/i18n.ext.js
?? tests/e2e/screens/photos_replace.py
build exit 0
suite exit 0 · 19 passed, 0 failed
```

#### The photo set — deployed 2026-11-16

| item | value |
|---|---|
| commit | `b255cc4`, full gate `gate-16-photos.log`: 2252 passed, 0 failed, control 548/548, no page-error record |
| live | `gh-pages c77f6ed`, built from `b255cc4` |
| rollback target | `787a40c` |
| staged | 159 files, scan clean; rehearsal on the local stand-in 44 passed, 0 failed |
| live bytes | 158 files fetched and compared by sha256, 0 differ |
| live verification | `live_deployment.py` 44 passed, 0 failed; nothing reached the real project |
| logs | `~/zajil-gate-logs/deploy4-01..06-*.log` |

NOT yet accepted on Samir's two real devices. The live verification does not exercise a replace-import or a restore
with photos; it proves the bytes served are the bytes of the gated commit. The mirror's `main` was not updated (not ordered this time).

## RF-23 — a sync cycle removes the bytes of every photo from the device that took it (MEASURED 2026-11-16, NOT FIXED — awaiting a ruling)

**Found while measuring the second device for P2.** The "first device" in that probe had no bytes either.

```
  after adding the photo, before any sync: {"media": [["photo.png", "3 B"]], "cursor": 0}
  after «مزامنة الآن» #1: {"media": [["photo.png", "NO BLOB"]], "cursor": 3} · requests: [["POST", [["birds", 1], ["media", 2], ["lofts", 3]]], ["GET", 0, [["birds", 1], ["media", 2], ["lofts", 3]]]]
  after «مزامنة الآن» #2: {"media": [["photo.png", "NO BLOB"]], "cursor": 3} · requests: [["GET", 3, []]]
  after «مزامنة الآن» #3: {"media": [["photo.png", "NO BLOB"]], "cursor": 3} · requests: [["GET", 3, []]]
  page errors: []
  ✓ [NET] every request to the backend host family was answered by a stub — nothing reached the real project  
```

**Why.** A device's own pushed rows sit above its cursor (RF-15), so the pull in the same cycle returns the media row
it has just pushed — metadata only, as designed (§7). `applySyncPut()` writes a pulled record VERBATIM
(`src/db/records.js:394`, `await idbPut(store, body)`), so the stored record, blob included, is replaced by the row
without one. The same line is in vanilla (`js/db/records.js:393`).

**What it means.** With automatic sync (RF-19, deployed) a photo taken on a signed-in device loses its bytes
within seconds: a cycle runs 3 s after the change. The row remains, the profile draws a placeholder, the full export
then fails (RF-4). Photos have no server copy (DF-4), so the bytes are gone. P1–P3 protect a copy that the sync cycle
has, on a signed-in device, already removed. Measured against a stub that models the table; the real project was not
contacted. Not checked: whether Samir's devices hold any photo that still has its bytes.

**Proposed fix, not built:** in `applySyncPut`, for `media`, keep the bytes the device already holds —
`const have = await idbGet('media', id); if (have && have.blob && !body.blob) body = { ...body, blob: have.blob };` —
with a check that a photo survives three cycles with its bytes and a mutant that removes the line. It cannot bring back
bytes already lost.

### RF-23 fixed 2026-11-16 (RULED) — the first commit of the photo-safety set

**The invariant of the set: a media record that holds bytes is never replaced by one that does not.**
`withHeldBytes()` in `src/db/records.js`; `applySyncPut()` passes a pulled media row through it, so the record written
carries the bytes the device already holds. Port-only; vanilla keeps the defect. It cannot bring back bytes already lost.
`tests/e2e/screens/photo_safety.py`: the bytes survive «مزامنة الآن» (one cycle, and three), survive the coordinator's
own cycles with no press (the coordinator pulls before it pushes, so the row returns on the NEXT automatic cycle; the
suite brings one with a second change), and survive a newer row for the same photo pushed by a device with no bytes
(the name changes, the bytes stay). Mutant M-rf23 (the line removed): 5 passed, 4 failed, each at its named check.

## RF-24 — an import stores a media row that has no `dataURL` as a "photo" made of whatever the address `undefined` returns (MEASURED 2026-11-16, NOT FIXED)

Section 3 of the probe above: a hand-made file whose media rows carry no `dataURL` was replace-imported onto a device
holding both photos with their bytes. `dataURLToBlob(undefined)` is `fetch(undefined)`, which fetches the relative
address «undefined»; the response (335 bytes of the server's not-found page here) passes the `blob.size` check and
OVERWRITES the real photo. No export the app makes today has this shape (a blobless export fails outright, RF-4), so
it is reachable only by a hand-made or future file. The RF-4 fix-at-source (admit a null `dataURL`, keep the bytes
already here) covers it. Not built.

### RF-24 fixed 2026-11-16 (RULED) — the second commit of the photo-safety set

`carriesBytes()` in `src/db/io.js`: only a `data:` URL is bytes. `importAll()` REJECTS any other media row — no
dataURL, the text «undefined», a file name, an address: it is never fetched and never written, so it can neither
replace a photo that has its bytes nor become a "photo" made of an error page. Rejected rows are counted
(`counts.mediaRejected`) and the import screen says how many (`backup.mediaRejected`, PROPOSED). A `data:` URL that
fails to decode still fails the WHOLE import before anything is touched, as before. A row a replace rejects is not
"carried" by the file: a dropped bird's photo listed that way goes with its bird and is counted in the question (P2/P3).
Read literally and to be confirmed: a rejected row is not stored as a bytes-less placeholder either.
Mutant M-rf24 (the rejection removed): 14 passed, 4 failed. Its first draft died on a traceback (the unguarded
`importAll` threw); the steps were made non-raising and it was rerun — first log kept as `ps-M-rf24-first-draft-TRACEBACK.log`.

**SEEN, not ruled:** a merge-import skips a media row the device already has, even when the device's row has no
bytes and the file's has them. So a second device cannot receive photos by importing the first device's export in
merge mode (a replace does bring them). Pinned as a `[seen · not ruled]` check in `photo_safety.py`.

### RF-4 fixed for the port 2026-11-16 (RULED) — the third commit of the photo-safety set

`exportable()` in `src/db/io.js`: `exportAll()`, `exportAllBlob()` and `exportBirdWithAncestry()` carry the media
whose bytes are on this device and leave out the rows that have none; `onMissing(n)` reports how many. The four
screens that export or share (الأدوات «تصدير الكل», the profile's and the certificate's «مشاركة», the pedigree's)
add `backup.mediaNotHere` (PROPOSED) to the success message when n > 0.
Decided, to be confirmed: the bytes-less rows are LEFT OUT of the file, not carried as metadata. RF-4's old
fix-at-source carried them with a null dataURL; but RF-24 now rejects such a row on import, and vanilla — which must
still read what the port writes — would fetch its address. Vanilla itself is unchanged and still cannot export there.
Mutant M-rf4 (the filter removed): 19 passed, 8 failed. Its first draft ended on a traceback from a step of mine that was timing-dependent (it assumed the first device never pulls the second one's row); the step was replaced and the mutant rerun.

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

### Built 2026-11-16 — NOT deployed (ordered: build, do not deploy)

**Membership.** `src/example-ids.js` lists the datasets' own ids as the generators' readable keys — 2 lofts, 58 birds,
9 pairs, 29 results, 13 health records — read from both datasets at `823db27^` (identical at `3190aa8` and `a932606`;
the two datasets share no id). `exampleIds()` holds each key and its uuid5: the pre-1.9.1 generation and the shipped
one. The suite checks the uuid half against the two shipped files, store by store, none missing and none extra.
`examplePresence()` and `removeExampleData()` ask that set and nothing else:

- a dataset record is example data WHEREVER it is filed (direction one);
- a record filed in a dataset loft whose id the datasets never shipped is the fancier's own, whatever its id looks like
  — re-filed, never deleted, and a walk start (direction two).

**What follows from it, decided in the build and to be confirmed:**
1. Presence no longer requires a dataset loft on the device: example records left behind without one bring the row
   back. With no loft the question cannot say «من {lofts}، ثم اللوفت التجريبي نفسه», so it has a second form
   (`example.remove.bodyNoLoft`, PROPOSED).
2. Kept references carry dataset ids, so they stay "example" for good. The row is absent while every example bird
   left is one a bird of the fancier's descends from; if that bird is later deleted, the row returns and offers to
   remove the references nobody descends from any more.
3. A kept reference that was filed outside the dataset lofts stays in its loft; only those filed inside one are re-filed.
4. When a dataset loft is present AND example birds are filed elsewhere, the question still says «من {lofts}»; the
   count is right, the place is not the whole truth. The row's button shows the outside count as one more term.

**The dialog names the cause.** `because` = every bird that is not example data and has an example bird as a parent,
sorted by name. The question adds «بسبب: {names}.» after the kept sentence — up to five (`BECAUSE_SHOWN`), then
«و{n} غيرها» (the existing `restore.confirm.more`). A bird with no name is named by its ring.

**The A-set.**
- *Re-saves may alter only the reference flag and loftId.* One function, `resave(id, patch)`, writes every bird the
  removal does not delete: the record as it stands now plus the patch, and it throws on any patch key outside
  `RESAVE_MAY_ALTER = ['external', 'status', 'loftId']` (`status` is the reference flag's second field). The generic
  re-files go through the same key check. Measured across 10 surviving birds: only those three fields differ, plus the
  two stamps every save writes (`updatedAt`, `deviceId` — a dataset record takes this device's id when re-saved).
- *INTERNAL frozen*: `Object.freeze({ allowWarnings: true })`; the guard pins that literal, pins the allowed-fields
  literal, and counts mentions of `INTERNAL` in code at exactly 2 (definition, `resave`).
- *`{ force: true }` guarded, not removed*: new guard `force-never-passed` — no `force:` with a non-false value under
  `src/` or `app/` (comments masked). Not removed because two suites pass it to build shapes validation refuses
  (`screens/bird_profile.py:138`, `screens/health.py:165`). Blind spots as declared for `allow-warnings-bounded`.

**Guard mutants** (`~/zajil-gate-logs/h3-guard-mutants.log`):

```
═══ G-freeze: INTERNAL not frozen
✗ allow-warnings-bounded  (1)
    src/example-data.js: the removal must set the flag exactly as `const INTERNAL = Object.freeze({ allowWarnings: true });`, for its own re-saves
✓ force-never-passed
✓ sync-single-owner
--
1 guard(s) FAILED
═══ G-use: INTERNAL used by a second save
✗ allow-warnings-bounded  (1)
    src/example-data.js: INTERNAL is mentioned 3× in code — 2 ruled (its definition, and resave())
✓ force-never-passed
✓ sync-single-owner
--
1 guard(s) FAILED
═══ G-alter: the allowed list widened
✗ allow-warnings-bounded  (1)
    src/example-data.js: a removal re-save may alter only the reference flag and loftId — `const RESAVE_MAY_ALTER = Object.freeze(['external', 'status', 'loftId']);`
✓ force-never-passed
✓ sync-single-owner
--
1 guard(s) FAILED
═══ G-force: a save in the app passes force
✗ force-never-passed  (1)
    app/bird/view.tsx passes force (1×) — no save in the app may skip validation
✓ sync-single-owner
✓ data-layer-identity
--
1 guard(s) FAILED
═══ restored
all guards pass
```

**Suite** `screens/example_remove.py`: 68 checks (was 53). **Mutants**, one harness build each (`~/zajil-work/h3/mutants.sh`):

```
═══ MUTANT M-loft
  mutated: src/example-data.js
build exit 0
suite exit 1 · 66 passed, 2 failed
  ✗ [H3 · M-loft fails here] a teaching bird filed in the fancier's own loft IS example data: 38 to delete, none kept, 1 counted outside the teaching loft, and it causes no keep  {'mine': '6e4bfd4b-7fe6-4b7c-be69-21f00b411911', 'moved': 'فارس ٢٦', 'movedId': 'f1d1a304-faff-503a-97e1-5c50246139a9', 'birds': 9, 'kept': 28
  ✗ [H3 · M-loft fails here] …the removal deletes it with the rest: no bird left, no reference bird made, the own loft untouched  (29, ['Anka', 'Julius', 'Kasper', 'Mieke', 'Remco', 'Witpen', 'الأمير', 'الشيخ', 'الفارس', 'الملك', 'برهان', 'خيال', 'دانة', 'ريما', 'زمرّدة', 'سدي

═══ MUTANT M-nonv4
  mutated: src/example-data.js
build exit 0
suite exit 1 · 63 passed, 5 failed
  ✗ [H3 · M-nonv4 fails here] a record with a non-uuid id that the datasets never shipped is the fancier's OWN, though it sits in the teaching loft: 7 own records, and it is among the causes of the keep, which are listed by name  {'own': 6, 'kept': 3, 'closure': 3, 'birds': 36, 'because': ['سليل-1', 'سليل-2', 'سلي�
  ✗ [H3 · M-names fails here] …and says «و2 غيرها» for the other two, without naming them  إزالة البيانات التجريبية؟  سيُحذف 36 طيرًا و5 زوجًا و17 نتيجة و7 سجلًا صحيًا من «لوفت إربد التعليمي»، ثم اللوفت التجريبي نفسه. �
  ✗ [H3 · M-nonv4 fails here] the fancier's old-id bird SURVIVES the removal, re-filed to the loft that is current, its teaching sire still linked and now a reference  None
  ✗ [H3] the seven own birds and the kept closure remain, nothing else  9
  ✗ [A-set · M-alter fails here] across the kept references and the re-filed birds, the removal altered ONLY external, status and loftId (and the two stamps every save writes, updatedAt and deviceId)  ['external', 'loftId', 'status']

═══ MUTANT M-names
  mutated: app/tools/parts.tsx
build exit 0
suite exit 1 · 66 passed, 2 failed
  ✗ [H3 · M-names fails here] the question NAMES the birds that cause the keep: «بسبب:» and the first five, by name  إزالة البيانات التجريبية؟  سيُحذف 35 طيرًا و5 زوجًا و17 نتيجة و7 سجلًا صحيًا من «لوفت إربد التعليمي»، ثم اللوفت الت
  ✗ [H3 · M-names fails here] …and says «و2 غيرها» for the other two, without naming them  إزالة البيانات التجريبية؟  سيُحذف 35 طيرًا و5 زوجًا و17 نتيجة و7 سجلًا صحيًا من «لوفت إربد التعليمي»، ثم اللوفت التجريبي نفسه. �

═══ MUTANT M-alter
  mutated: src/example-data.js
build exit 0
suite exit 1 ·     at async <anonymous>:316:30

═══ MUTANT M-patch
  mutated: src/example-data.js
build exit 0
suite exit 1 · 52 passed, 16 failed
  ✗ [own] the ruled outcome: the example sire and his ancestors stay, as reference birds, and the pedigree link is intact  {'mine': {'loft': '8f268d1b-3dbe-57be-8d77-ede52297a2cd', 'sireLinked': True}, 'up': [{'name': 'الفارس', 'external': False, 'status': 'breeder', 'loft': '8f268d1b-3dbe-57be-8d77-ede52297a2cd'}, {'nam
  ✗ [own] nothing else of the example data remains: the fancier’s own two birds and the whole ancestor closure of the sire (both sides), nothing more  {'birds': 40, 'pairs': 5, 'races': 17, 'health': 7, 'closure': 3}
  ✗ [own] the kept birds carry the external tag in the register  ['Anka', 'Julius', 'Kasper', 'Mieke', 'Remco', 'Witpen', 'طارق', 'نجلاء']
  ✗ [own] the row is gone  1
  ✗ [own · seen] loading the same teaching loft again on this device imports nothing — the tombstones win (follow-up, not ruled)  {'birds': 0, 'pairs': 0, 'raceResults': 0, 'healthEvents': 0, 'lofts': 0, 'media': 0, 'skipped': 68, 'removed': 0}
  ✗ [shape · invariant] a removal that cannot proceed SAYS SO — a toast naming the reason, nothing changed  ('لم تُزل البيانات التجريبية — لم يتغيّر شيء. السبب: خطأ غير متوقع (example-removal: a re-save may not alter «notes»)', 78, 0, [])
  ✗ [shape] the removal RAN TO COMPLETION — the row detached, no failure toast (R1 fails here: the flag not passed)  لم تُزل البيانات التجريبية — لم يتغيّر شيء. السبب: خطأ غير متوقع (example-removal: a re-save may not alter «notes»)
  ✗ [shape] 47 deleted — 29 example birds remain, every one a reference bird  (76, False, 78)
  ✗ [shape] the own record inside the teaching loft was re-filed to the own loft, which is current  ([['حمّار-2', '8f268d1b-3dbe-57be-8d77-ede52297a2cd'], ['حمّار-1', '123ab3c8-6505-44cd-a063-e31b6d31b50d']], {'123ab3c8-6505-44cd-a063-e31b6d31b50d': 'Hummar', '8f268d1b-3dbe-57be-8d77-ede52297a2cd': 'لوفت إربد
  ✗ [shape] both teaching lofts gone, tombstoned, the toast reports 47 and 29  (0, 'لم تُزل البيانات التجريبية — لم يتغيّر شيء. السبب: خطأ غير متوقع (example-removal: a re-save may not alter «notes»)')
  ✗ [H3 · A-set · M-patch fails here] the removal ran to completion  لم تُزل البيانات التجريبية — لم يتغيّر شيء. السبب: خطأ غير متوقع (example-removal: a re-save may not alter «notes»)
  ✗ [H3 · M-nonv4 fails here] the fancier's old-id bird SURVIVES the removal, re-filed to the loft that is current, its teaching sire still linked and now a reference  {'id': 'bird-0007', 'rings': [], 'name': 'قديم-العهد', 'sex': 'hen', 'hatchDate': '', 'colour': '', 'strain': '', 'eyeSign': '', 'status': 'stock', 's
  ✗ [H3] the seven own birds and the kept closure remain, nothing else  45
  ✗ [A-set · M-alter fails here] across the kept references and the re-filed birds, the removal altered ONLY external, status and loftId (and the two stamps every save writes, updatedAt and deviceId)  []
  ✗ [A-set] …the kept references are references in the current loft; the own birds changed their loft and nothing else  {'06ace477-3277-56a5-ae72-88ee440c2d02': None, '0b3cea81-446b-5207-8893-29310735fb20': None, '0c116294-faf4-52ae-a585-f18cac9d3f40': None}
  ✗ [H3] the row is gone though the kept references carry dataset ids: nothing of the example data is left to remove  

═══ restored
 M app/tools/parts.tsx
 M guards/run.mjs
 M src/db.js
 M src/example-data.js
 M src/i18n.ext.js
 M tests/e2e/screens/example_remove.py
?? src/example-ids.js
build exit 0
suite exit 0 · 68 passed, 0 failed
```

M-alter's first draft changed the bird's NAME, and an earlier step of the suite that finds a bird by name died on a
traceback before any A-set check — red for the wrong reason (kept as `h3-M-alter-first-draft-TRACEBACK.log`). Redrawn
to change `colour`, and rerun:

```
═══ MUTANT M-alter
  mutated: src/example-data.js
build exit 0
suite exit 1 · 66 passed, 2 failed
  ✗ [A-set · M-alter fails here] across the kept references and the re-filed birds, the removal altered ONLY external, status and loftId (and the two stamps every save writes, updatedAt and deviceId)  ['colour', 'external', 'loftId', 'status']
  ✗ [A-set] …the kept references are references in the current loft; the own birds changed their loft and nothing else  {'05211d34-65c4-4d66-bd48-895f861f8273': ['colour', 'loftId'], '0b3cea81-446b-5207-8893-29310735fb20': ['colour', 'loftId'], '20ab1172-8d79-4dc6-a610-f89d555b4a0f': ['colour', 'loftId']}

═══ restored
 M app/tools/parts.tsx
 M guards/run.mjs
 M src/db.js
 M src/example-data.js
 M src/i18n.ext.js
 M tests/e2e/screens/example_remove.py
?? src/example-ids.js
build exit 0
suite exit 0 · 68 passed, 0 failed
```

**Seen, not this item's subject:** on a build with no service worker الأدوات draws the version as «غير معروف»
(`about.unknown`) in the mono face, which has no Arabic. The route walk of the typography suite does not meet it. Not fixed.

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

---

## 2026-11-17 — the photo-safety set deployed; H3 decision 4 and the version row

**Photo-safety deploy.** `gh-pages f041810`, built from branch `photo-safety` at `677f968` (RF-23 `c709262`,
RF-24 `6c224d6`, RF-4 `551594b`, test correction `677f968`), without H3. Rollback target `c77f6ed`.
Live bytes: 158 files compared by sha256, 0 differ. Live verification: 44 passed, 0 failed, THE NET armed.
Logs `~/zajil-gate-logs/deploy5-01…06-*.log`. The mirror's `main` moved `0429668` → `1ecc09e` (fast-forward).

**Gates on the set** (`~/zajil-gate-logs/ps-gates.log`):

```
gate-19 on c709262 exit 0 ·   2261 passed, 0 failed across 36 steps, 1 skipped
gate-20 on 6c224d6 exit 0 ·   2270 passed, 0 failed across 36 steps, 1 skipped
gate-21 on 551594b exit 1 ·   2278 passed, 1 failed across 36 steps, 1 skipped
gate-22 on 677f968 exit 0 ·   2279 passed, 0 failed across 36 steps, 1 skipped
```

gate-21's one failure was the RF-24 check «NOTHING was fetched for them»: its listener counted Next's own route
prefetches (`…__PAGE__.txt?_rsc=…`), which depend on timing. `677f968` narrows the listener; the product code is
unchanged, and M-rf24, rerun against the narrowed check, still fails at it (`…/undefined`,
`https://example.invalid/ghost.png`). `551594b` stays in history with a red gate. The three commits were made
before their gates ran.

**H3 decision 4 (RULED 2026-11-17).** `examplePresence()` returns `outside`: example records of any kind filed
outside the dataset lofts it names. With one or more the question uses `example.remove.bodyNoLoft`. Mutant
M-outside: 68 passed, 1 failed, at its named check (`~/zajil-gate-logs/h3d-mutants.log`).
Seen, not ruled: in that case the question no longer says «ثم اللوفت التجريبي نفسه», though the dataset loft is
still removed; and the row's own note «الألوفت التجريبية: …» still names the loft.

**The version row (RULED 2026-11-17).** `valueKind` is `data` only when a version was reported. The typography
walk opens الأدوات with no service worker: before the fix 16 passed, 1 failed
(`h3d-typography-BEFORE-mono-fix.log`); after, 17 passed; M-mono fails at the named check.

**H3 + A-set deploy.** `gh-pages 9bcbc0b`, built from `feat/react-port 772dc65` (gate-23: 2296 passed, 0 failed,
control 548/548, 0 page-error records). Rollback target `f041810`. Live bytes: 158 files, 0 differ. Live
verification: 44 passed, 0 failed, THE NET armed. Logs `deploy6-01…06-*.log`. Mirror `main` `1ecc09e` → `d1ff92c`.

---

## 2026-11-17 — the eleven uncaught mutating handlers in الأدوات (built, NOT deployed)

Each of the eleven now runs through `destructive()` and names itself with one new string, `tools.failed.action`
«لم يكتمل «{what}». السبب: {reason}» (PROPOSED), `{what}` being a label the app already had.

| # | handler | `{what}` |
|---|---|---|
| 1 | `sync-now` | «مزامنة الآن» |
| 2 | sync toggle | «إيقاف المزامنة» / «تشغيل المزامنة» |
| 3 | duplicate copy `del` | «حذف» |
| 4 | snapshot `restore` | «استرجاع نسخة تلقائية» |
| 5 | example `load` | «تحميل بيانات تجريبية للتعلّم» |
| 6 | integrity `run` | «فحص ترابط البيانات» |
| 7 | scanner save, button and blur | «ماسح شهادات النسب الورقية» |
| 8 | `signOut` | «تسجيل الخروج» |
| 9 | loft `save` | «اللوفت» |
| 10 | `pickLogo` | «اختيار شعار» |
| 11 | `removeLogo` | «إزالة الشعار» |

**«مزامنة الآن» was not an exception.** A cycle never throws; it returns `{ ok: false }`, and the button said
«تم الحفظ» whatever came back. It now says the failure with the layer's own reason (`sync.err.*`).

**`removeLogo`** stops when the delete fails: the logo stays set. Before, a failed delete left the row as it was only
because the exception ended the handler.

**Tests.** `tests/e2e/screens/tools_failures.py`, 40 checks. IndexedDB refuses every write while the fault is armed
(the stub project answers 500 for the sync button); the real control is pressed; the check wants the error toast
naming the control, no «تم الحفظ», and no page error. Eleven mutants, one build each, the catch removed at one
handler (`~/zajil-gate-logs/h11-mutants.log`): every one fails at its named check, none on a traceback
(M-h01 39/1; M-h07 36/4; the other nine 38/2 — the second failure is the typography check finding no toast).

**RF-25 — seen, not ruled, not fixed.** `setSetting()` (`src/db/storage.js`) writes memory first and storage
second. When the write fails the setting is changed in memory and unchanged in storage: measured on the sync
toggle — the screen shows sync off, storage says on, and a reload puts it back. The toast now says the action did
not complete; the screen still shows the unsaved value until the reload. The suite records it
(`[seen · not ruled · RF-25]`).

**Seen, not ruled, not fixed.** `set()` in `app/tools/view.tsx` — language, numerals, dates, COI depth, contrast —
calls `saveSetting` without awaiting or catching it. It was not among the eleven listed.

---

## 2026-11-17 — RF-25 fixed: a setting storage refused is not kept in memory

**RULED 2026-11-17.** `setSetting()` (`src/db/storage.js`) writes storage first and memory second. Storage-first
was chosen over a rollback because every caller awaits it, and there is then no moment at which memory holds a
value storage has not taken.

**Correction to the first report of RF-25.** It said "the screen shows sync off". That was read from memory
(`state.settings.syncEnabled === false`), not from the screen: under the mutant the button still read
«إيقاف المزامنة». What was measured is that memory and storage disagreed until a reload.

**Tests** (`tests/e2e/screens/tools_failures.py`, now 42 checks) and the mutant, memory-first restored
(`~/zajil-gate-logs/rf25-mutant.log`):

```
═══ MUTANT M-rf25
suite exit 1 · 40 passed, 2 failed
  ✗ [RF-25 · M-rf25 fails here] …and the setting IN MEMORY is what storage holds — sync is still on, and the button still offers to turn it off, with no reload  (False, None, 'إيقاف المزامنة')
  ✗ [RF-25 · M-rf25 fails here] setSetting() with storage refusing: it rejects, an existing setting keeps its value in memory, and a new one does not appear  {'a': 'rejected', 'b': 'rejected', 'same': False, 'absent': False}
```

Vanilla has the same order and is not changed.

---

## 2026-11-17 — RF-25 corrected: memory is put back, not written second

**`9ac7e7a` (storage first) was wrong, and its green gate was luck.** gate-26, on the next change, failed 1 of
2353 in `screens/auto_backup.py`:

```
✗ [boot · M-boot fails here] the last snapshot 13 hours old: the boot takes a new one  {'n': 2, … 'last': '2026-11-17T01:26:30.944Z', …}
```

The snapshot was stored and «آخر نسخة تلقائية» was not yet in memory: storage-first opened a gap of one write in
which memory is behind. Rerun on that tree, the suite failed 1 run in 6 (a second check, same cause). The product
reads that setting from memory to decide whether a snapshot is due (`src/components/AutoBackup.tsx`), so the gap
is not only a test's concern.

**Now:** `setSetting()` writes memory first, as before RF-25, and puts the previous value back when storage refuses
the write — unless something newer was set meanwhile. Both forms were allowed by the ruling.
`auto_backup.py`: 14 runs, 0 failed. `tools_failures.py`: 42 passed. Mutant M-rf25b (the put-back removed)
fails at the same two named checks as M-rf25 (`~/zajil-gate-logs/rf25b-mutant.log`).

The change that was under gate-26 (the settings controls) was not committed; it is gated again after this.

---

## 2026-11-17 — the settings controls in الأدوات surface a failed save

**RULED 2026-11-17.** `set()` in `app/tools/view.tsx` — language, numerals, dates, COI depth, contrast — runs
through `destructive()` like the eleven, named by each control's existing label. No new string.
Suite `tools_failures.py`, now 57 checks. Mutant M-h12 (the bare call restored): 47 passed, 10 failed — the five
named checks and the five typography checks that find no toast (`~/zajil-gate-logs/set-mutant.log`).

---

## 2026-11-17 — the no-loft wording keeps the clause that the teaching loft goes

**RULED 2026-11-17.** With an example record filed outside the named lofts AND a dataset loft present, the question
uses a new string, `example.remove.bodyOutside` (PROPOSED): no loft is named, and «ثم اللوفت التجريبي نفسه» is kept
because that loft is removed. With no dataset loft on the device the wording is `example.remove.bodyNoLoft`, as
before, and a new check holds that branch. Suite `example_remove.py` 70 checks. Mutant M-clause (the clause
dropped): 69 passed, 1 failed, at the named check (`~/zajil-gate-logs/clause-mutant.log`).

---

## 2026-11-17 — a picked photo shows in the bird form before saving

**Reported from Samir's phone:** a photo picked on the bird form shows nothing until the form is saved and the bird
reopened.

**Measured before the change** (`~/zajil-gate-logs/photoform-probe-BEFORE.log`, 390×844, harness build):

```
after picking  : {"imgsInForm": [], "tileHtml": "<svg …plus…>", "tileBg": "none", "pendingText": "picked.jpg", "pendingFontPx": "12px"}
after save +300 ms: {"tiles": 0, "photos": []}
after save +1000 ms: {"tiles": 1, "photos": [[2048, 1365, true]]}
the EDIT form of that bird: {"imgsInForm": [], "tileHtml": "<svg …plus…>", "pendingText": null}
```

The form showed the file name in 12 px type and no picture. In this measurement the profile did show the photo
within a second of saving, without being reopened — the "reopened" half of the report was not reproduced here.

**Built (RULED 2026-11-17, "fix it here if small").** The 92 px photo tile draws the photo picked last, from an
object URL revoked when it is replaced and when the form goes away. Bytes are still stored only on save.
`screens/bird_form.py` 63 checks; mutant M-preview: 62 passed, 1 failed, at its named check.

**Seen, not changed:** the edit form shows nothing for the photos a bird already has; with several photos picked only
the last is drawn (all are listed by name).

---

## 2026-11-17 — the sign-in footer drew «غير معروف» in the mono face too

**Missed on 2026-11-17 when the version row on الأدوات was fixed.** The ruling was to fix «غير معروف» in the mono
face and extend the typography walk to that state; only الأدوات was fixed and walked. The sign-in footer wraps the
same fallback in `<code>`. Measured at 390×844, with and without a service worker
(`~/zajil-gate-logs/signin-mono-probe.log`):

```
service worker | url /sign-in/ | footer: الإصدار غير معروف | hits: [('NO-ARABIC-COVERAGE', 'plexMono', 'غير معروف')]
NO service worker | url /sign-in/ | footer: الإصدار غير معروف | hits: [('NO-ARABIC-COVERAGE', 'plexMono', 'غير معروف')]
```

**Fixed:** `<code>` wraps a reported version only. The walk now opens /sign-in with no service worker at phone
width: on the unfixed build 18 passed, 1 failed at the named check (`signin-mono-BEFORE.log`); fixed, 19 passed.
Not explained: why the walk's existing /sign-in visit (1400 wide) never caught it.

---

## 2026-11-17 — deploy record: the handlers set (`gh-pages bfe6ef5`)

Built from `feat/react-port 10d10ac`. Rollback target `9bcbc0b`. Live bytes: 158 files compared by sha256, 0 differ.
Live verification: 44 passed, 0 failed, THE NET armed. Logs `~/zajil-gate-logs/deploy7-01…06-*.log`.
Mirror `main` `d1ff92c` → `af64982` (fast-forward).

| commit | what | gate |
|---|---|---|
| `155ec2e` | the eleven handlers say their failures | gate-24 · 2336 / 0 |
| `9ac7e7a` | RF-25, storage first — superseded by the next | gate-25 · 2338 / 0 |
| `e1ca54c` | RF-25 corrected: memory put back on a refused write | gate-27 · 2338 / 0 |
| `2b2f799` | the five settings controls say a failed save | gate-28 · 2353 / 0 |
| `8a45d80` | the no-loft wording keeps «ثم اللوفت التجريبي نفسه» | gate-29 · 2354 / 0 |
| `db7e3e5` | a picked photo is drawn in the bird form before saving | gate-30 · 2358 / 0 |
| `10d10ac` | the sign-in footer's «غير معروف» in the Arabic face | gate-31 · 2360 / 0 |

gate-26 (the settings controls, first attempt) was red, 2352 / 1, in `screens/auto_backup.py`; the cause was
`9ac7e7a`, recorded above under «RF-25 corrected». Nothing was committed from it.

**RF-23 confirmed on a real device (reported by Samir, 2026-11-17).** A photo added on his phone survived automatic
sync and a reload; his PC shows the «photo on another device» placeholder for it. This is his observation on his
own devices, recorded here as reported — not a measurement made in this tree.

## 2026-11-18 — RF-16: the teaching data can be loaded again after it was removed

RULED 2026-11-18: forget tombstones by shipped-id membership on the three dataset loaders only; `importAll`
untouched; a guard on the call site; kept references stay references on a reload; general loft removal parked.

**Built.** `loadExampleDataset()` in `src/example-data.js`, called by the empty-register button
(`app/birds/view.tsx`) and the two buttons in الأدوات (`app/tools/parts.tsx`, one shared `load()`). A record is
eligible only when its id is BOTH in the file AND in the shipped-id membership set (`exampleIds()`).
Guard `example-loader-only`: who may clear a tombstone, exactly one clear in the example module, nothing under
`src/db/` mentions the example data, the three call sites pinned.

**The order is not the one first built, and the ruling does not state it — reported.** Built first as "forget the
tombstones, then merge" (the 16 October proposal). Measured with automatic sync running (load → remove → load,
`~/zajil-gate-logs/rf16-stress-3.log`): in 1 run of 8, **11 of 68 records were gone again** — device 57 records and
11 tombstones, server 57 live rows, a second device 57. A device's own pushed deletions sit above its cursor; an
automatic pull landed between the two steps, wrote 11 tombstones back, and the merge skipped those records. No
operation was logged for them, so nothing would ever have brought them back.
Now: (1) a shipped record that has a tombstone is handed to the merge stamped as made now (later than its deletion);
(2) `importAll` merges as it always has; (3) the tombstone of every such record that is on the device afterwards is
cleared. Nothing is forgotten before the data is in; a load that fails part-way clears only what came in. A record
with no tombstone is passed through untouched — a first load keeps the file's own `updatedAt` on all 38 birds
(checked). After the change: 24 runs of the same stress, 24 agree on 68 records (`rf16-stress-5.log`).
**The stamp is a decision inside the ruling's "forget", made here because the measurement required it.** If it is
not wanted, the alternative is a lock that keeps the coordinator out for the length of a load — sync design.

**The 16 October measurement, repeated under membership by id** (`tests/e2e/screens/example_reload.py`, a stub that
models the trigger's last-write-wins): the reload pushes 68 live rows, 0 rejected; a device that signs in afterwards
holds 38 birds; a device that removed locally BEFORE the reload and syncs after it pulls first, its 128 pending
operations are superseded, it POSTs nothing and holds the data again; a device that removes AFTER the reload wins
and the other follows; a brand-new device ends with the latest intent. Same as October in every line.

**Kept references.** After a removal that kept the sire's ancestor closure, a reload leaves each kept bird exactly
as it was (flag, status, loft, `updatedAt`), loads the other example birds around them, and the toast counts only
what was loaded.

**Not covered, as ruled or as found:** tombstones of the pre-1.9.1 generation's ids stay (the loaders load only the
current files). The empty-register loader has no failure message of its own — a refused load there is an unhandled
rejection, as before this change (seen, not changed). Navigating away while a load is running can leave a record
written without its operation — `importAll` writes the record and logs the op in two transactions (seen in a probe
that reloaded mid-load: the loft never reached the server; not changed).

## 2026-11-18 — RF-26 (FOUND; FIXED — see “RF-26 fixed” below): a pull can undo a local save made while it was applying

Found while building RF-16. **Pre-existing and live** (`gh-pages bfe6ef5`); not introduced by RF-16.

**Measured** (harness build, stub project, twice in two runs of the same sequence): load the teaching loft, add an
own bird with an example sire, call the removal at once — while the automatic cycle started by the save is still
pulling. Afterwards the sire «الفارس» is `external: false`, `status: breeder` — NOT a reference — and stays so.
Its operations, verbatim from the log:

```
seq  14  put  import  …47.881Z   external false  status breeder      (the load)
seq  70  put  user    …52.041Z   external true   status reference    changed: status+external+updatedAt+deviceId   (the removal's flip)
seq 173  put  user    …52.607Z   external false  status breeder      changed: updatedAt+loftId+deviceId            (the removal's re-file)
```

Between 70 and 173 the record went back to `external false / breeder` with NO operation. Operation 173 changed only
the loft, so it read a record that had already been reverted, and it is then pushed as the newest version: the
server and every device converge on the wrong record.

**Mechanism, read from `src/db/sync.js` and `src/db/records.js`:** a pull page decides last-write-wins against the
operations that were PENDING WHEN THE PAGE STARTED (`pending.get(...)`), then applies each row; `applySyncPut` and
`applySyncDelete` do not compare the row with the record on the device. A device's own pushed rows sit above its
cursor and come back on its next pull. So a save made after the page started and before its row is applied is not
seen: the older row (here the load's own row for the sire) is written over it. The removal is exposed because it is
many saves in a row; any save in that window is.

**Where it bites, in the fancier's terms:** an edit or a removal made in the seconds after a load or another burst of
changes, while the sync indicator is still working, can be silently taken back — and the taken-back version then
syncs as the truth. In the measured case a kept pedigree ancestor is left as an ordinary breeder in the fancier's
loft.

**Why the suites never saw it:** `example_remove.py` removes through the dialog, which takes long enough for the
pull to finish. `example_reload.py` settles sync before each removal and says so.

**Not fixed — it is sync design (§4).** Candidates, for a ruling: (a) re-read the pending operations for the row's
record immediately before applying it, and compare; (b) make the comparison and the write one IndexedDB transaction;
(c) keep the coordinator's pull and local multi-record actions (removal, import, replace) mutually exclusive.
(a) narrows the window, (b) and (c) close it. Probe logs: `~/zajil-gate-logs/rf16-stress-*.log`, and the op listing
above from `~/zajil-work/rf16/`.

## 2026-11-18 — deploy record: RF-16 (`gh-pages f6110c1`)

Live: `gh-pages f6110c1`, built from `feat/react-port fa08b40`. **Rollback target: `bfe6ef5`** (then `9bcbc0b`).
Rollback is `git push -f git@github.com:nahdaeverything-web/zajilv2.git bfe6ef5:gh-pages` from a clone that has it.
Mirror `main` = `bb492d2` (`git subtree split --prefix=next fa08b40`, fast-forward from `af64982`).

| step | result | log (`~/zajil-gate-logs/`) |
|---|---|---|
| gate-33 on the RF-16 tree | 2393 passed, 0 failed across 38 steps, control 548/548, 0 page-error records | `gate-33-rf16.log` |
| stage for `/zajilv2/`, inject, verify, scan | 159 files, CLEAN | `deploy8-01`, `deploy8-02` |
| rehearsal on the local Pages stand-in | 44 passed, 0 failed, NET armed | `deploy8-04` |
| live before | `gh-pages bfe6ef5`, `main af64982` | `deploy8-03` |
| live bytes | 158 files by sha256, 0 differ (new sw.js after 31 s) | `deploy8-05` |
| live verification | 44 passed, 0 failed, NET armed — nothing reached the real project | `deploy8-06` |

Two things about the run itself. The rehearsal used a stand-in server already listening on :8178 from the previous
deploy (it serves a symlink to `release/`, re-resolved per request, so it served this build); the second server
this run tried to start failed to bind and was not needed. The first push of the deploy commit failed — the clone
was made over https, which has no credentials here — and was repeated over ssh; nothing reached the remote from the
failed attempt.

Not yet accepted on Samir's two devices. RF-26 (above) is live in this build as it was in the last.

## 2026-11-18 — the live project was checked against `supabase/sync-schema.sql`, and matched

Samir ran `supabase/sync-schema-check.sql` (one read-only statement) in the SQL Editor of the real project and the
reviewer reported the output: **17 rows; `ok = true` on rows 1–16, each found value equal to its expected value.**
The header of `supabase/sync-schema.sql` now says so. PART 1 of that file has still never been executed from the
file on Supabase Postgres — the project was built earlier (Route A); what is established is that its catalog is
what the file describes.

**Row 17, information only:** `service_role` holds `REFERENCES, TRIGGER, TRUNCATE` on `sync_records` — it has **no
`SELECT`, `INSERT`, `UPDATE` or `DELETE`** on the table. Nothing in the app uses the service key, so nothing is
affected today. It matters only if an admin tool using the service key is ever built: that tool could not read or
write a row until the grants are added, and adding them is a change to the project that needs its own ruling.

## 2026-11-18 — photo storage exists on the live project: bucket `photos`, owner-only

Samir ran the storage SQL once, without error, after the reviewer read it. The verification returned the five
expected rows, verbatim from the reviewer's message:

```
bucket | photos public=false limit=5242880 types={image/jpeg,image/png,image/webp,application/pdf}
policy | photos owner delete DELETE {authenticated}
policy | photos owner insert INSERT {authenticated}
policy | photos owner select SELECT {authenticated}
policy | photos owner update UPDATE {authenticated}
```

The bucket exists and is **empty**; no deployed build uploads to it yet (stage 1 is not deployed). The text is kept
as `supabase/photo-storage.sql` — the text as PROPOSED; if what was run had been amended in review, the file must be
amended to match. Consequence of the four-type allow-list, as flagged when it was proposed: an image the app stores
as-is in another format (GIF, HEIC, BMP, AVIF, SVG) is refused by the bucket and stays on its device; stage 1 says so
to the fancier instead of sending it.

## 2026-11-18 — RF-26 fixed (RULED: candidate b): the comparison and the write are one transaction

**Ruling:** "the last-write-wins comparison against the record on the device and its pending operations, and the
write, happen in ONE IndexedDB transaction, for applySyncPut and applySyncDelete."

**What was built** (`src/db/records.js`, `storage.js`, `sync.js`): for each pulled row, one readwrite transaction
over the record's store, `oplog` and `tombstones` (`idbAtomic`) —

1. reads this record's unpushed operations: the page's index (built once, as before) plus every operation logged
   since it was built. The second part is read inside the transaction by key (`getAllKeys` on the `seq` index, then
   only the ops the index has not seen), so a page of 500 rows does not re-read the whole log 500 times;
2. reads the record on the device;
3. decides, supersedes the operations the row beat, and writes the record or the deletion and its tombstone.

It holds across a pull page: nothing is carried from one row to the next except the head-start index, and what that
index cannot know is read fresh for every row. Candidate (c) was not needed and was not built.

**The record half is a rule, and the rule is narrower than "newer stamp wins" — a choice made while building, for
confirmation.** A local save writes its record first and logs its operation after, so for a few milliseconds the
newer record is on the device with no operation to speak for it. The record on the device stands against a row only
when (i) THIS device stamped it (`deviceId`) and (ii) its `updatedAt` is strictly after the row's operation time.
Without (i), a record that arrived by pull with a stamp later than its operation time (a restored or imported
record, an author whose clock ran ahead) would block every later row for it, and this device would keep a version
the server had moved on from; mutant M-anydevice shows it.

**Where the rule can still be wrong, by reading, not measured:** a record this device stamped, whose operation is
gone or acknowledged, meeting a row dated before the stamp that is nevertheless the server's current row. With the
server's own last-write-wins guard that needs the operation's time to be EARLIER than the record's stamp, which no
writer in the port produces (a save's operation is logged after its stamp; first-login operations carry the stamp
itself; an undo restores an older stamp). Two fixtures in `tests/e2e/pull.py` did produce it artificially — they
clear the op log and then send a deletion dated in August for a bird saved on the device a moment ago — and those
two fixture dates were moved after the save, deliberately, with the reason written at the spot. No assertion in
that suite was changed.

**Windows that remain, by reading:** a local DELETE removes the record, logs its operation, then writes its
tombstone; a row for that record applied between the first and the last step puts the record back on the device
until the deletion's own echo removes it again. An undo (`restoreBird`) is covered once its operation is logged,
but not in the instant between its record write and that log, because a restored record carries its old stamp.
Both need the local writers themselves to become one transaction — a larger change, not ordered, not made.

**Proof** — `tests/e2e/pull_race.py`, 27 checks, deterministic: the local write is started from inside the change
event of the page's first row, so it always begins after the page's index was built; where the row under test sits
in the page decides which half is exercised.

| mutant | what it restores | result |
|---|---|---|
| M-old | both halves off — the behaviour before the fix | RED at 12 named checks |
| M-snapshot | operations logged since the page index are not read | RED at 5 |
| M-norecord | the record on the device is not compared | RED at 3 |
| M-anydevice | any newer stamp stands, not only this device's | RED at 1 |

Log: `~/zajil-gate-logs/rf26-mutants-1.log`. The plain case (save, save again, first echo arrives; then the second
echo) is checks `[plain]`. The 16 October agreement stress (`~/zajil-work/rf16/stress.py`, 8 delays; device, server and a second device)
was run three times on the fixed build: 0 runs disagreed (`rf26-stress-after-*.log`). The exact script that first
showed the reverted sire was not kept, so that measurement was not repeated as it was; `[page]` in the suite is
that shape made deterministic.

Vanilla has the same defect and is NOT changed.

## 2026-11-19 — deploy record: RF-26 (`gh-pages dccd8d7`)

Live: `gh-pages dccd8d7`, built from `feat/react-port d043eb4`. **Rollback target: `f6110c1`** (then `bfe6ef5`).
Rollback is `git -C ~/zajil-work/deploy/ghp-rf26-2026-11-19 push -f origin f6110c1:gh-pages`.
Mirror `main` = `65fe47c` (`git subtree split --prefix=next d043eb4`, run from `~/zajil`, fast-forward from `bb492d2`).

| step | result | log (`~/zajil-gate-logs/`) |
|---|---|---|
| gate-41 on the RF-26 tree | 2420 passed, 0 failed across 38 steps, 0 page-error records | `gate-41-rf26.log` |
| stage for `/zajilv2/`, inject, verify, scan | 159 files, CLEAN | `deploy9-01`, `deploy9-02` |
| live before | `gh-pages f6110c1`, `main bb492d2` | `deploy9-03` |
| rehearsal on the local Pages stand-in | 44 passed, 0 failed, NET armed | `deploy9-04` |
| live bytes | 158 files by sha256, 0 differ (new sw.js after 33 s) | `deploy9-05` |
| live verification | 44 passed, 0 failed, NET armed — nothing reached the real project | `deploy9-06` |

The steps were run by `~/zajil-work/deploy/deploy.sh`, which is the RF-16 deploy's commands in the same order with
a stop after any step that fails (`deploy9-00-run.log`). The deploy commit's author is read from the previous deploy
commit. Not yet accepted on Samir's two devices.

## 2026-11-18 — photo sync, stage 1 (BUILT, NOT DEPLOYED): bytes follow records, fetched on first view

Ruled 2026-11-18 (C, stages 1–3 in order). Stage 1 is on branch `feat/photo-stage-1`; it is **not deployed** and is
held for the size ruling from Samir's own photos.

**What it does.** `src/db/photos.js` (port-only). After a record cycle that SUCCEEDED the coordinator starts one
upload pass and does not wait for it. The pass sends every media record that holds bytes and has no `stored` marker
to `photos/<owner id>/<media id>` (upsert), then writes `stored: {at, size, type}` on the record as it stands then
and logs that as an ordinary change, so the marker reaches the other devices with the record. A device that has the
record, the marker and no bytes fetches them when the bird's profile first draws the tile, and keeps them (no
operation is logged for that). Until then the tile says where the photo is: on another device and not uploaded yet;
coming down; or the download failed and will be tried when opened again.

**What it refuses, and how it waits.** A file over 5 MiB or outside JPEG/PNG/WebP/PDF is never sent; a file the
server refuses for size or type is treated the same. Refusals are said ONCE, in one notice per pass (the shell shows
two notices at most — a notice per file lost all but the last two; found by the suite's first run), and the bytes
stay on the device. Anything else — no network, no bucket, a server fault — stops the pass at the first failure and
waits the coordinator's backoff (1-2-4-8-15 min); «مزامنة الآن» retries at once. A 2xx that is not storage's own
acknowledgement (`Key` = the object's path — a captive portal answers 200 too) marks nothing; a download whose length
is not the marker's length is not kept.

**The form (ruled with stage 1).** The edit form shows the bird's existing photos, and every picked photo shows
before saving: a strip of 56 px tiles under the photo block, saved first, then picked. The strip's layout is not from
a design spec — it is the builder's, and awaits a look.

**Guard** `photo-pass-owner`: one caller of `runPhotoPass` (the coordinator), never awaited; only `photos.js` names
the storage endpoint. Its three mutants each fail the build with the reason printed.

**Suite** `tests/e2e/screens/photo_sync.py` (45 checks, storage stub, THE NET armed) and six more checks in
`bird_form.py`. **Mutants** (`~/zajil-gate-logs/photo1-mutants-2.log`, `-3.log`), each red at named checks, no
traceback: M-await 1, M-nofetch 9, M-nokeep 7, M-drop 9, M-hot 2 (the bucket-missing case), M-each 1, M-bigsend 3,
M-anyok 1, M-anylen 1, M-nosaved 2, M-lastonly 1.

**The first mutant batch HUNG for seven hours and proved nothing.** M-await makes the cycle wait for the upload; the
suite holds that upload unanswered; the page call to `syncNow()` therefore never returned, and a page call has no
time limit of its own. Two faults, both the builder's: a check that could hang instead of fail, and a runner with no
limit. Fixed in both places: the held sync gives up after 10 s and fails its check; `~/zajil-work/ps/mut.sh` gives
the build and the suite 300 s each, kills the process group past that, reports `HUNG` (which is not a red mutant),
and restores sources on every exit. Four mutants in the rerun ended in tracebacks — not proof either — and were run
again after the suite's waits were made to answer instead of raise.

**Known limits of stage 1, not hidden:** the certificate view and the loft logo do not fetch (stage 3); deleting a
photo leaves its object in the bucket (stage 2); a refused file is named only in the notice — nothing on its tile
says it stays on this device; a page reload forgets the in-memory waits, so each app open may try once; the
`*File` variants of the tile strings and the single «نوع الملف…» notice are drawn by the same elements as their
checked siblings but are not themselves visited by a typography check; the 1600 px size is its own commit after this one.

**Strings, all PROPOSED (shipped as written in this build, corrections as one follow-up):** `media.notUploadedYet`,
`media.notUploadedYetFile`, `media.fetching`, `media.fetchingFile`, `media.fetchFailed`, `media.fetchFailedFile`,
`media.refused.size`, `media.refused.type`, `media.refused.many`.

**gate-37 was RED on this tree, and why.** Two suites died in a traceback — `photo_safety.py`
(`json.decoder.JSONDecodeError`) and `tools_failures.py` (`UnicodeDecodeError … byte 0x89`): their stubs model the
record API only and parse every POST as JSON rows, and a signed-in device with photo bytes now also POSTs those
bytes to storage. Nothing was committed. Answered deliberately, not by loosening anything: `tests/e2e/_net.py` gains
`no_bucket()`, and each of the fifteen record-only stubs (the two above, `sync_auto`, `tools`, `replace_sync`,
`example_remove`, `example_reload`, `auto_backup`, `gate`, `account_collision`, `pull`, `push`, `convergence`,
`sync_ui`, and the deploy gate `live_deployment.py`) calls it first: their project has no photo bucket — storage's
own 404 `NoSuchBucket` — which is the ruled case where bytes stay on the device and the pass waits. THE NET and its
expected counts are untouched. The thirteen that passed gate-37 had been answering storage requests by accident of
how their handlers were written; they now answer on purpose.

## 2026-11-18 — TF (FOUND; FIXED 2026-11-19, test-only, APPROVED): `auto_backup.py` can read between the snapshot and its marker

gate-38 on the stage-1 tree was RED on one check and committed nothing:

```
✗ [boot · M-boot fails here] the last snapshot 13 hours old: the boot takes a new one
  {'n': 2, 'ids': ['2026-11-18T09:10:13.907Z', '2026-11-18T09:10:18.226Z'], … 'last': '2026-11-17T20:10:18.129Z', …}
```

The new snapshot IS there (`n` 2, the second id); `last` still holds the 13-hours-ago value the test had planted
97 ms earlier. `src/db/io.js` writes the snapshot and THEN `setSetting('lastAutoBackup', id)`; the suite's
`settled()` polls only for the snapshot count and returned between the two writes. The product order is right (a
marker without its snapshot would be the worse failure); the observation is racy. The suite passed in gates 30–37,
and 12 of 12 times run alone afterwards on the same tree (`~/zajil-gate-logs/photo1-autobackup-run*.log`): one
failure in 21 observed runs. Nothing in stage 1 touches the snapshot path; the only change to this suite is the
no-bucket line in its stub.

**Not fixed — reported.** The gate was run again on the unchanged tree. Proposed, for a ruling: `settled()` also waits
for `last == ids[-1]`, bounded as it is now, so the check reads a finished boot.

## 2026-11-18 — new photos are stored at 1600 px (RULED), on the stage-1 branch

`MAX_EDGE` 2048 → 1600 in `src/components/media.ts`: one size, for NEW photos; a photo already stored at 2048 px is
not touched and uploads as it is. Ruled without the measurement from Samir's own photos — he sends them to the
reviewer, who revises the size only if a ring number is not legible at 1600 px. `tests/e2e/media_downscale.py` now
pins the exact edge (`== 1600`) where it used to accept anything `<= 2048`.

## 2026-11-19 — photo sync, stage 1: rebased onto RF-26, and the five things ordered before its gate

Rulings of 2026-11-19: the nine strings stand as proposals; the strip layout and the 📄 glyph are accepted for now;
the two hardening checks are accepted; RF-16's order (stamp, merge, clear) is confirmed; `no_bucket()` in the
record-only stubs is accepted.

**The rebase.** Four files conflicted, each because both sides had added text at the same place; both sides were
kept. `src/db/sync.js`: stage 1's `import { runPhotoPass }` kept, and `markOpsSuperseded` left out of the oplog
import as RF-26 left it. `guards/run.mjs` and `PORT-COMPLETE.md`: both reasons kept, stage 1's sentence then
RF-26's. This file: RF-26's sections, then stage 1's.

**(a) The allow-list** (`src/components/media.ts`). An image of a type outside JPEG, PNG and WebP that the browser
can decode is converted to JPEG at 1600 px on its longest edge, never enlarged, on a white ground (JPEG has no
transparency). One the browser cannot decode is stored as it is; the upload pass refuses its type and says so with
the existing notice, and its bytes stay. Choices made while building, for confirmation:
- the conversion runs where the downscale already ran — when the form is SAVED, not at the moment of picking. The
  picked file is what the strip shows until then;
- a converted file is stored under a `.jpg` name (`storedName()`, at all four pick sites: the bird form, the
  certificate's photo and logo, the loft logo in الأدوات). Its bytes are no longer what the old extension says;
- an animated GIF becomes its first frame;
- SVG is no longer passed through by name: it meets the same rule, and since neither browser here decodes one from
  a file, it is stored as it is and stays on the device.

Measured on this desktop (`~/zajil-gate-logs/photo1-type-probe.log`), files picked through a real file input:

| picked | Chromium 145 | WebKit 26 (Playwright, Linux) |
|---|---|---|
| GIF, AVIF, BMP | decoded → converted | decoded → converted |
| SVG | not decoded → stays | not decoded → stays |
| a file named `.heic` (NOT a real HEIC) | type reported `image/heif`, not decoded → stays | the same |

**HEIC is NOT measured.** No tool on this machine can write a real HEIC (ImageMagick reads it only; ffmpeg has no
HEIF muxer), and installing one was refused. What is known is only that a file the browser cannot decode takes the
"stays on the device, and the user is told" path. **Untested, and only a real iPhone can show it:** whether Safari
hands the picker a JPEG or a HEIC for a photo from the library or the camera; if a HEIC, whether
`createImageBitmap` decodes it there (then it is converted) or not (then it stays on the phone and the notice
appears after the next sync); and whether the orientation of a converted photo is right.

**(b) A refused file.** Current behaviour, unchanged: a refusal is written to this device's settings
(`photoRefused`, by media id), `photosAwaitingUpload()` leaves refused ids out, and the notice is raised only by the
pass that refused. So a refused file is sent zero more times and announced zero more times, including after the app
is opened again — new check `[refused · M-forget fails here]`. It did not repeat; nothing was fixed. Two limits by
reading: the refusal is permanent on that device (nothing clears it if the limit or the allow-list later changes),
and a second device holding the same bytes makes its own refusal and says it once too.

**(c)** `auto_backup.py`: `settled()` now waits for the count AND for the marker to name the newest interval
snapshot. Test-only. 38 passed.

**(d)** The three `…File` strings are now each drawn on a real document tile and put through the typography scan:
`[file · not uploaded]`, `[file · fetching]`, `[file · failed]` in `photo_sync.py`. All nine strings have now been
through it.

**(e) Mutants, all re-run on the final code** (`~/zajil-gate-logs/photo1-mutants-5.log`; the runner's limits on,
none HUNG, no traceback):

| mutant | red at | mutant | red at |
|---|---|---|---|
| M-await | 1 | M-anyok | 1 |
| M-nofetch | 11 | M-anylen | 1 |
| M-nokeep | 8 | M-nosaved | 2 |
| M-drop | 15 | M-lastonly | 1 |
| M-hot (bucket missing) | 2 | M-forget (new) | 1 |
| M-each | 2 | M-2048 | 2 |
| M-bigsend | 4 | M-noconvert (new) | 4 |

G-await, G-second and G-endpoint each fail the build at `photo-pass-owner` with the reason printed. Only this
section of this file was written after the batch; no code or test changed after it.

**Local bytes are never removed whatever storage answers** — the file's invariant; M-drop is the mutant that removes
them on a failure and on a refusal, and 15 checks catch it.

## 2026-11-19 — deploy record: photo sync, stage 1 (`gh-pages 7fd5c08`)

Live: `gh-pages 7fd5c08`, built from `feat/react-port eb776d0`. **Rollback target: `dccd8d7`** (the RF-26 build; then
`f6110c1`). Rollback is `git -C ~/zajil-work/deploy/ghp-photo1-2026-11-19 push -f origin dccd8d7:gh-pages`.
Mirror `main` = `3fe5548` (`git subtree split --prefix=next eb776d0`, run from `~/zajil`, fast-forward from `65fe47c`).

| step | result | log (`~/zajil-gate-logs/`) |
|---|---|---|
| gate-43 on the stage-1 tree, rebased onto RF-26 | 2484 passed, 0 failed across 39 steps, 0 page-error records | `gate-43-photo-stage-1-final.log` |
| stage for `/zajilv2/`, inject, verify, scan | 159 files, CLEAN | `deploy10-01`, `deploy10-02` |
| live before | `gh-pages dccd8d7`, `main 65fe47c` | `deploy10-03` |
| rehearsal on the local Pages stand-in | 44 passed, 0 failed, NET armed | `deploy10-04` |
| live bytes | 158 files by sha256, 0 differ (new sw.js after 31 s) | `deploy10-05` |
| live verification | 44 passed, 0 failed, NET armed — nothing reached the real project | `deploy10-06` |

**This is the first build that writes to the real `photos` bucket.** Nothing in the deploy or its verification wrote
there: the live verification runs with the backend stubbed. The first objects will be written by Samir's own
devices on their first sync after they take this build. A rollback to `dccd8d7` stops further uploads and leaves
whatever was uploaded in the bucket and every byte on the devices; a media record's `stored` marker is an ordinary
field the older build ignores.

The two stage-1 commits made before the rebase (`bc8b7f8`, `e1b25ba`) were gated as gate-39 and gate-40 on their
old base; after the rebase they were gated only together with `eb776d0`, by gate-43.

Not yet accepted on Samir's two devices. Acceptance: an existing phone photo appears on the PC when that bird is
opened; a photo added on the PC appears on the phone.

## 2026-11-19 — rulings recorded, and RF-27: a local delete and its undo are each one transaction

**Confirmed 2026-11-19:** the RF-26 record rule (the device's record stands against a pulled row only if this device
stamped it and its stamp is strictly later than the row's operation time); the two `pull.py` fixture dates; the
stage-1 choices (conversion at save, `.jpg` name, first frame of an animated GIF, white for transparency, SVG stays
local). **Known limit, recorded as ruled:** a refusal is remembered per device, and a refused file STAYS refused on
that device if the size limit or the allow-list later changes — nothing clears `photoRefused`.

**RF-27 — the two windows read under RF-26, now measured.** Both were real
(`~/zajil-gate-logs/windows-measure-before.log`, on the deployed code `eb776d0`). Made deterministic by issuing the
pulled row from inside the writer's own first store request, so its transaction is queued directly behind it:

| window | measured before | after |
|---|---|---|
| a row for a record applied behind a local delete's removal, before its operation and tombstone | the row was APPLIED: the record was back in the store and in memory, beside a tombstone and an owed delete operation | skipped (`local-op`); deleted in both |
| the echoed deletion applied behind an undo's put, before its operation | the deletion was APPLIED: the bird was gone from the store and from memory, with the restore operation still owed | skipped; the bird is there in both |

Both healed themselves once the device's own later row came back — unless something was saved on top of the wrong
state first, which is how RF-26 became permanent.

**Fix** (`src/db/records.js` `atomicWrite`, `src/db/oplog.js` `buildOp`/`tombstoneRecord`/`tombstoneKey`):
`deleteBird()` (its whole cascade), `restoreBird()`, the generic `remove()` and `restore()`, `deleteMedia()` and
`restoreMedia()` each write every record change, operation and tombstone in ONE transaction, and change the mirror
only after it commits. `oplog.js` is now divergent from vanilla for those three functions; `logOp()` is unchanged.

**Proof:** `[window]` checks in `tests/e2e/pull_race.py` (34 checks in all). M-split-delete and M-split-undo — the
bird's own write moved back in front of the transaction — are each red at their named check
(`rf27-mutants-1.log`). The checks and mutants exercise `deleteBird` and `restoreBird`; the generic and media
writers use the same helper and are covered only by the existing delete and undo suites, not by a window check of
their own.

**Not changed, by reading:** saves (`saveBird`, the generic `save`, `addMedia`) still write the record and then log
— the RF-26 record rule covers that instant for stamped records, and a new media record has an id no row can name
yet. `importAll` and the pruning of the op log are as they were. Vanilla has the same windows and is NOT changed.

## 2026-11-20 — deploy record: RF-27 (`gh-pages 73036f1`)

Live: `gh-pages 73036f1`, built from `feat/react-port 0181fe7`. **Rollback target: `7fd5c08`** (photo sync stage 1;
then `dccd8d7`). Rollback is `git -C ~/zajil-work/deploy/ghp-rf27-2026-11-20 push -f origin 7fd5c08:gh-pages`.
Mirror `main` = `a0ea16c` (`git subtree split --prefix=next 0181fe7`, run from `~/zajil`, fast-forward from
`3fe5548`); it carries the stage-1 deploy record `782abdd` (split as `ccd85ad`), as ruled.

| step | result | log (`~/zajil-gate-logs/`) |
|---|---|---|
| gate-45 on `0181fe7` | 2491 passed, 0 failed across 39 steps | `rf27-gate-45.out` |
| stage for `/zajilv2/`, inject, verify, scan | 159 files, CLEAN | `deploy11-01`, `deploy11-02` |
| live before | `gh-pages 7fd5c08`, `main 3fe5548` | `deploy11-03` |
| rehearsal on the local Pages stand-in | 44 passed, 0 failed, NET armed | `deploy11-04` |
| live bytes | 158 files by sha256, 0 differ (new sw.js after 31 s) | `deploy11-05` |
| live verification | 44 passed, 0 failed, NET armed — nothing reached the real project | `deploy11-06` |

RF-27 changes no stored shape: a rollback to `7fd5c08` returns the three-step delete and undo, and leaves every
record, operation and tombstone as it is. Photo sync stage 2 (`feat/photo-stage-2`) is NOT in this build.

### The photo diagnostic statement (ORDERED 2026-11-20: written, not run)

`supabase/photo-diagnostic.sql` — read-only, one statement for the SQL Editor: each object in the `photos` bucket
beside the media row in `sync_records` with the same owner and id (its `updated_at`, `deleted`, `device_id`, whether
its data carries the `stored` mark and the mark's value, and whether the mark's size equals the object's), plus every
media row with no object and every object with no row. The file states the expected row for a phone photo whose
upload and mark both reached the server, and how to read the other kinds. Checked on PGlite only (syntax, join, row
counts unchanged — `photo-diagnostic-pglite.log`); the real storage schema's column names are the docs', unmeasured.

## 2026-11-19 — photo sync, stage 2 (BUILT, NOT DEPLOYED)

Ordered: a photo tombstone removes the stored object, queued if offline; the sync status counts photos waiting to
upload; a full-storage refusal is said, with bytes kept locally; a refused file is marked on its own tile.

**Removing the object** (`src/db/records.js` `unstore`, `src/db/photos.js` `removeOne`). When `deleteMedia()` or
`deleteBird()`'s cascade deletes a media record that carries the `stored` marker, its id is queued in the same
transaction that deletes it (RF-27), in the device setting `photoRemovals`. The photo pass sends
`DELETE /storage/v1/object/photos/<owner>/<id>` for each queued id, BEFORE its uploads, and takes the id off the
queue when storage answers. A dropped connection, a missing bucket, a server fault or a 200 that is not storage's
own JSON leaves the id queued and stops the pass on the coordinator's backoff, as for uploads. Choices made while
building, for a ruling:

- **Only the device that made the deletion removes the object.** A device that receives the tombstone by pull
  sends nothing. One request, and no second device racing an undo it cannot see.
- **A grace of 60 seconds** (`PHOTO_REMOVE_GRACE_MS`) before a queued removal is sent. The «تراجع» notice lasts 6
  seconds; the other device drops its bytes as soon as it pulls the tombstone, so inside the undo the object can be
  the only copy the undoing device could fetch. After the grace nothing in the app can undo the deletion.
- **A record that exists again is never un-stored.** Before each DELETE the pass looks for the media record on the
  device; if it is there (an undo), nothing is sent and the id leaves the queue.
- **An object that is not there ends the matter** (`NoSuchKey`, or the older "Object not found"): the id leaves the
  queue. A missing BUCKET does not.
- A photo deleted while its own upload was in flight is queued when that upload finishes (`'gone'`).

**Known limits of the removal, by reading:** (1) a device that deletes a media record it holds WITHOUT the marker,
while another device has uploaded and its marker has not arrived yet, queues nothing — the object is orphaned; the
design leaves orphan reconciliation to stage 3. (2) Storage answers a DELETE the policy does not allow the same way
as a missing object, so a wrong policy would look like success here; the bucket's four owner policies were verified
on 2026-11-18. (3) The DELETE's answers are taken from Supabase's documentation and client code, not from the real
project: nothing is run against it. The usage query after a real deletion is the check.

**The status counts photos waiting** (`photos.js` `refreshPhotoWaiting`, `syncStatus().photosWaiting`). Files that
hold bytes on this device, are not marked stored and are not refused. Counted whenever the record status is
counted, and after every pass. Shown in two places: the sync screen in الأدوات (a line under the status), and the
status row above the lists — which until now was SILENT whenever records were in step, and would have gone on
saying "everything is sent" by saying nothing. The row now speaks, in its calm dress, when records are in step and
photos wait. A refused file is not counted: it is not waiting for anything.

**Storage that is full.** Supabase documents no error for it — the published list of storage error codes has
nothing for a quota. So what is recognised is a GUESS at what such an answer would look like: HTTP 402 or 507, or a
code or message naming a quota / insufficient storage / storage full or exceeded. **Unverified against the real
service, and it cannot be verified without filling a project.** What IS proven is what the app does if storage
answers that way: the pass stops at the first such answer and backs off; nothing is marked refused; every byte
stays; it is said once, when it begins («امتلأت مساحة التخزين…»), not on every retry; the sync screen shows the same
sentence while it lasts; and when an upload goes through again it clears. If the real answer is something else, it
is treated as any other failed upload: bytes kept, retried with backoff, the photos counted as waiting — and NOT
said as "full".

**A refused file is marked on its own tile** (`app/bird/view.tsx`): «لم يُرفع — على هذا الجهاز فقط» across the foot of
the tile, with the full sentence (size or type, with the file's name) as its title. The placement and dress are the
builder's — no spec draws it. On the bird's profile only; the edit form's strip is not marked.

**New strings — three, all PROPOSED, all through the typography scan:**

| key | Arabic | where |
|---|---|---|
| `sync.photosWaiting` | «صور وملفات بانتظار الرفع: {n}» | sync screen line; status row |
| `media.storageFull` | «امتلأت مساحة التخزين على الخادم — لم تُرفع الصور، وهي محفوظة على هذا الجهاز» | notice; sync screen line |
| `media.refusedMark` | «لم يُرفع — على هذا الجهاز فقط» | the refused file's tile |

**Proof** — `tests/e2e/screens/photo_sync.py`, 84 checks (29 new). Mutants on this code, the runner's limits on,
none HUNG, no traceback (`~/zajil-gate-logs/photo2-mutants-1.log`):

| stage-2 mutant | what it does | red at |
|---|---|---|
| M-nograce | a queued removal is sent at once | 5 |
| M-dropqueue | the id leaves the queue before storage has answered | 3 |
| M-anydel | any 200 counts as removed | 2 |
| M-noremove | nothing is ever removed | 8 |
| M-noundo | the record on the device is not looked for | 1 |
| M-nocascade | deleting a bird queues nothing | 1 |
| M-nocount | the status carries no count | 4 |
| M-rowsilent | the status row stays silent | 1 |
| M-nomark | the tile is not marked | 2 |
| M-fullsilent | full storage is not said | 2 |
| M-fullrefuse | full storage marks the file refused | 7 |

Every stage-1 mutant was run again on this code and is red at a named check: M-await 1, M-nofetch 11, M-nokeep 8,
M-drop 22 (re-anchored: the pass was restructured), M-hot 3, M-each 2, M-bigsend 6, M-anyok 1, M-anylen 1,
M-nosaved 2, M-lastonly 1, M-forget 1, M-2048 2, M-noconvert 4. G-await, G-second and G-endpoint each fail the build
at `photo-pass-owner`. Only this file, `PORT-COMPLETE.md` and the guard's reason text were written after the batch.

### 2026-11-20 — rulings on stage 2, and what was built before its gate

**Ruled:** (1) only the deleting device removes the object, after the 60-second grace — APPROVED. (2) Full storage:
the guessed answer is ACCEPTED because a wrong guess falls back to keep-and-retry; it stays **UNVERIFIED** against
the real service (nothing documents the answer, and it cannot be measured without filling a project). (3) The three
strings stand as proposals. (4) Known limits ACCEPTED: the object left behind when a device deletes a photo before
its stored mark arrived (stage 3's clean-up), and a DELETE the policy refuses looking like a missing object.

**The mark is said on a tap** (`app/bird/view.tsx`). Hover does not exist on a phone, where fanciers work. The mark is
now a button: a tap shows the full sentence (the refusal notice's own words, with the file's name: «الملف «…» أكبر
من الحد المسموح للرفع — بقي محفوظًا على هذا الجهاز فقط», or the type sentence) as a notice for 12 seconds, as long
as the refusal notice itself. The title stays for a pointer that can hover. No new string.

**The edit form's strip carries the same mark** (`app/bird/form.tsx`). The strip's tiles are 56 px; the mark does not
fit across one, so it sits UNDER the refused file's thumb, on one line, in the same dress, and the same tap says the
same sentence. The placement is the builder's — no spec draws it. Only saved files can be refused; a file picked
and not yet saved is never marked.

**Window checks for the other writers** (`tests/e2e/pull_race.py` §10). §9 drove `deleteBird`/`restoreBird` only. The
generic `remove`/`restore` (driven through health events) and `deleteMedia`/`restoreMedia` (a photo holding bytes)
are now driven the same way: the pulled row is issued from inside the writer's own first store request on that
record. Each writer's mutant MOVES its own record write out of the transaction, in front of it:

| mutant | what it does | red at |
|---|---|---|
| M-split-remove | the generic `remove` deletes the record before its transaction | 1 |
| M-split-restore | the generic `restore` puts the record back before its transaction | 1 |
| M-split-mdelete | `deleteMedia` deletes the record before its transaction | 1 |
| M-split-mrestore | `restoreMedia` puts the record back before its transaction | 1 |
| M-notap | the profile's mark says nothing on a tap | 1 |
| M-nostripmark | the strip carries no mark | 3 |
| M-nostriptap | the strip's mark says nothing on a tap | 1 |

**Proof.** `tests/e2e/pull_race.py` 50 checks (16 new); `tests/e2e/screens/photo_sync.py` 90 checks (6 new: the tap on
the profile's mark, the strip's mark — under the refused file only, on one line, inside a 430 px screen — the tap on
it, and the typography of each). The tap is a real touch tap (`has_touch`), not a click. All mutants above, the runner's
limits on, none HUNG, no traceback (`~/zajil-gate-logs/photo3-mutants-1.log`). On the same final tree, RF-27's own two
are red again (M-split-delete 1, M-split-undo 1 — these two DUPLICATE the bird's write in front of the transaction;
the four new ones MOVE it, which is the stricter form), and every stage-2 mutant is red again: M-nograce 5,
M-dropqueue 3, M-anydel 2, M-noremove 8, M-noundo 1, M-nocascade 1, M-nocount 4, M-rowsilent 1, M-nomark 3 (re-anchored
on the button; the tap check fails too, as there is nothing to tap), M-fullsilent 2, M-fullrefuse 7, M-drop 22.
Every stage-1 mutant is red again on this tree (`photo3-mutants-s1.log`): M-await 1, M-nofetch 11, M-nokeep 8, M-hot 3,
M-each 2, M-bigsend 10, M-anyok 1, M-anylen 1, M-nosaved 2 (re-anchored: the strip's map now returns the thumb or the
marked pair), M-lastonly 1, M-forget 1, M-2048 2, M-noconvert 4; G-await, G-second and G-endpoint each fail the build at
`photo-pass-owner`.

**Seen at 390 px (screenshots `~/zajil-gate-logs/s2b-shots/`, staged: the refusal written into the device setting):**
on the profile the photo grid has three columns, and the mark takes three lines and covers most of the refused photo,
its file name included (a tap says the name). In the strip the mark is wider than the thumb, so the refused file's
place is as wide as its mark and the strip's even spacing is broken around it. Both are the builder's placement.

The stage-2 commit `c749dea` (gate-46) was rebased onto the RF-27 deploy record `33ddf79` as `88adce4` — a docs-only
change of base, so that stage 2 merges fast-forward. After the rebase it was gated only together with this commit.

### 2026-11-20 (later) — Samir's stage-1 acceptance PASSED; two items before stage 2's gate

**Accepted on Samir's devices:** the phone photo uploaded 2026-11-19 18:51:35 UTC (1 object, 251267 bytes) shows on the
PC's profile and in its edit form; a photo added on the PC appears on the phone; orientation is right on both. Earlier
that day the PC had still shown «الصورة على جهاز آخر ولم تُرفع بعد» after two reloads.

**1. Mark timing — MEASURED, nothing changed on the sending side** (`~/zajil-work/photo3/mark_timing.py`, harness
build with the coordinator RUNNING, table and storage stubbed, the net armed; `~/zajil-gate-logs/mark-timing-3.log`).
On the device that takes the photo, seconds after the photo is added:

| s | request |
|---|---|
| 3.06 | the record cycle (change trigger, 3 s debounce) pushes the media row, no mark |
| 3.10 | the photo pass, started after that cycle, uploads the bytes |
| 6.13–6.15 | the upload's own change event starts the next cycle 3 s later: it pushes the row WITH the mark |

The mark is pushed in the SAME session, with nothing pressed, 3.05 s after the upload — by the change trigger the
upload itself fires. It does not wait for another session or a press, so the extra cycle the order allowed for that
case was NOT added: it would move the push by three seconds. If the app is put away inside those three seconds, going
to the background is itself a trigger and pushes it at once — as far as the phone lets the page run.

**What WAS late is the receiving side** (same probe, the PC's profile of the bird open):
- an idle PC pulls only when it is opened, brought forward, after its own change, or every 5 minutes (RULED idle
  heartbeat), so the photo and its mark reach an idle PC up to 5 minutes later;
- when a pull does bring the row and its mark, an OPEN profile does not change: the media list re-reads only on a
  local `media` event, and a pulled row emits `sync`. Measured: after a cycle pulled the row and its mark, the open
  profile still showed 0 tiles; after a reload the photo was fetched and shown;
- a RELOAD whose own opening cycle brings the mark shows the OLD tile throughout (measured every 0.5 s for 5 s), because
  the profile is read before that pull lands; the NEXT reload shows the photo. That is the shape Samir saw: the first
  reload after the mark reached the server cannot show it.
Not fixed here (not ordered). Stage 3's background download refreshes the profile when the bytes land; the open
profile and form re-reading on a pulled media row is proposed with it.

**2. The refused mark is a small corner badge** (RULED 2026-11-20: it must not cover the photo or its name). One short
word, «لم يُرفع» (`media.refusedMark`, PROPOSED — it replaces the proposed «لم يُرفع — على هذا الجهاز فقط», which never
shipped), in the tile's top corner opposite the delete button; the full sentence on a tap, as built. Measured at 390 px:
the tile is 96 × 96, the badge 52 × 18 (10% of the photo), 4 px from the delete button, 49 px above the file's name. In
the edit form's strip the badge sits ON the refused thumbnail's top corner; every thumbnail keeps 56 × 56 and the strip
its 8 px spacing. Screenshots: `~/zajil-gate-logs/s2c-shots/`. The suite's refusal device now runs at 390 px with touch.

| mutant | what it does | red at |
|---|---|---|
| M-bigmark | the badge back across the tile's foot | 1 |
| M-stripout | the strip's badge loses its thumbnail (positioned outside it) | 1 |
| M-nomark | no badge | 4 |
| M-notap | no tap | 1 |
| M-nostripmark | no badge in the strip | 4 |
| M-nostriptap | no tap in the strip | 1 |
| M-nosaved, M-lastonly (`bird_form.py`, the strip re-shaped again) | | 2, 1 |

`photo_sync.py` 92 checks. Log: `~/zajil-gate-logs/photo3-mutants-badge.log`; none HUNG, no traceback.

## 2026-11-20 — deploy record: photo sync, stage 2 (`gh-pages 6ca309e`) — LIVE VERIFICATION NOT CLEAN

Live: `gh-pages 6ca309e`, built from `feat/react-port 2323fc2` (fast-forwarded from the gated stage-2 branch).
**Rollback target: `73036f1`** (RF-27; then `7fd5c08`). Rollback is
`git -C ~/zajil-work/deploy/ghp-photo2-2026-11-20 push -f origin 73036f1:gh-pages`.

| step | result | log (`~/zajil-gate-logs/`) |
|---|---|---|
| gate-49 on `2323fc2` | 2544 passed, 0 failed across 39 steps, 0 page-error records | `gate-49-photo-stage-2c.log` |
| stage for `/zajilv2/`, inject, verify, scan | 159 files, CLEAN | `deploy12-01`, `deploy12-02` |
| live before | `gh-pages 73036f1`, `main a0ea16c` | `deploy12-03` |
| rehearsal on the local Pages stand-in | 44 passed, 0 failed, NET armed | `deploy12-04` |
| live bytes | 158 files by sha256, 0 differ (new sw.js after 31 s) | `deploy12-05` |
| **live verification** | **43 passed, 1 failed**, NET armed — nothing reached the real project | `deploy12-06` |

The failed check, verbatim: `✗ no failed requests  503 https://nahdaeverything-web.github.io/zajilv2/health/__next._tree.txt?_rsc=5CB68i4pnAekjehf`.
The deploy script stopped there, as built: **the mirror's `main` was NOT pushed (still `a0ea16c`) and
`origin/feat/photo-stage-2` was NOT deleted** — the order made both follow the live verification.

Measured after the stop, nothing patched:
- that file, fetched three times: `200`, 832 bytes each; its sha256 equals the release's (`f6742ea48a0e45bc…`);
- ONE re-run of the live verification (`deploy12-06b-live-verify-rerun.log`): 43 passed, 1 failed — a DIFFERENT check:
  `✗ service worker registered at the scope this origin implies  none does not end with /zajilv2/` (the 503 check passed);
- a read-only probe, three fresh browsers on the live origin (`deploy12-live-sw-probe.log`): the service worker
  registered at `/zajilv2/` 0.8 s after load in all three; no response was 4xx or 5xx; four page requests ended
  `net::ERR_ABORTED` (`/breeding/`, `/races/`, `/health/`, `/birds/`) — not HTTP errors, and the suite's check does not
  count them; not examined further.
Reading, not proven: the two failures are the live origin's (a 503 from Pages, then a registration slower than the
suite's fixed 3-second wait), not the build's — the bytes are the release's, and the rehearsal of the same bytes passed
44 of 44. The build stays live; the mirror and the branch deletion wait for a word.

## 2026-11-20 — photo sync, stage 3; the photo viewer; the pair offer (BUILT, NOT DEPLOYED)

### Stage 3 — every stored photo comes down in the background (`src/db/photos.js`)

Ordered: background download of every photo whose bytes are not on the device, so exports, shares and certificates
from either device are complete; bounded — one at a time, only while online and in the foreground, never blocking
record sync, the same backoff; and the merge-import photo gap closed with it.

- **The download leg** of the photo pass runs after the removals and the uploads: every media record marked `stored`
  whose bytes are not here (`photosAwaitingDownload()`), the ones that failed least first, then oldest first.
- **One at a time — everywhere.** The pass downloads in sequence, and `fetchPhotoBytes()` itself now runs in a single
  lane, so the pass, a profile drawing its tiles and the viewer never have two downloads out at once.
- **Online and in front only.** Checked before the leg starts and again before each file (`navigator.onLine`,
  `document.visibilityState`). Offline, nothing is even tried: no request, no failure counted, no backoff.
- **Never in the way.** The pass is still started after a record cycle and not awaited (the `photo-pass-owner` guard).
- **The same backoff.** A failed download stops the pass on the photo backoff, as a failed upload does; a file whose
  own last try failed is passed over until its own wait is out, so one bad object cannot hold the others back.
- **The merge-import gap, closed** (`src/db/io.js`): a merge gives a media row this device holds WITHOUT bytes the
  file's bytes — bytes only, the row otherwise as it was (its stored mark included), no operation. A row that has
  bytes is never touched. Recorded as a divergence (guard, PORT-COMPLETE).
- **An open profile follows a pull** (`src/db/react.ts`) — added from the mark-timing measurement, NOT ordered: a
  pulled media row re-reads the bird's media list, so a photo pulled while its profile is open appears on it.

### The photo viewer (`src/components/PhotoViewer.tsx`; ORDERED 2026-11-20)

A tap on a photo's tile (the profile) or a thumbnail (the edit form's strip, saved or just picked) opens it full
screen. Choices made while building, for a ruling:
- **Swipe direction:** right-to-left, as the tiles run — a swipe to the right brings the next photo.
- **Close:** a tap (even when zoomed in), a swipe down, the back button, Escape, or the ✕ in the corner.
- **Pinch:** 1× to 4×; while zoomed a drag pans and a swipe does not change photo; let go under 1.05× and it resets.
- **A pointer and a keyboard:** two arrow buttons on the sides (labels `viewer.prev` / `viewer.next`, PROPOSED), the
  arrow keys, and a counter «٢ / ٣».
- **The back button:** one history entry is pushed when the viewer opens; going back closes it and the page underneath
  is never navigated; a close from inside the viewer takes the entry back off.
- **Not on this device:** the viewer says what the tile says — «جارٍ تنزيل الصورة…» — and becomes the photo when the
  bytes land; «الصورة على جهاز آخر ولم تُرفع بعد» for one not uploaded. No new string.
- **The delete button** stays the delete control, a sibling in its own corner: a tap on the photo cannot reach it.
- **Documents** open in the browser's own viewer: the tile is a link to the file (`target="_blank"`), no longer a
  download. **Found while building, measured, fixed:** that link was `display:inline` — a 22 × 21 px target inside a
  96 × 96 tile, only the 📄 itself tappable (since stage 1). It now fills its tile, the glyph centred. Measured in Chromium (its new headless mode, which has the PDF viewer): a new page showing the PDF, nothing
  downloaded. **NOT measured on a real iPhone**, where a link to a blob from an app added to the home screen may not
  open; Samir's acceptance covers it.

### The pair offer (`app/bird/form.tsx`; ORDERED 2026-11-20)

Found on Samir's data: a father and a mother set on two youngsters, no breeding pair ever made. Built:
- asked when a bird is saved with both parents and **this save set or changed them** — editing a bird whose parents
  did not change asks nothing, so an unrelated edit never nags (a choice, for a ruling);
- not asked when a pair of that cock and that hen exists **in any season, active or not** (a choice);
- never for an external or reference parent, nor when the father is a hen or the mother a cock;
- «إنشاء الزوج» saves the bird first, then opens «زوج جديد» on the breeding screen with both parents filled; the nest
  box and season are still the fancier's; «ليس الآن» goes on as before and makes nothing. It is asked again for the
  next youngster of the same two while no pair exists.
- «حفظ وإضافة آخر» asks too; «إنشاء الزوج» there leaves the entry rhythm for the breeding screen (by reading — the
  suite drives «حفظ» only).

### New strings — six, all PROPOSED, all through the typography scan

| key | Arabic | where |
|---|---|---|
| `viewer.prev` | «الصورة السابقة» | the viewer's arrow (read by a screen reader) |
| `viewer.next` | «الصورة التالية» | the viewer's arrow (read by a screen reader) |
| `pairOffer.title` | «لا يوجد زوج تربية لهذين الأبوين» | the offer's title |
| `pairOffer.body` | «اخترت {sire} أبًا و{dam} أمًّا، ولا يوجد في السجل زوج تربية يجمعهما. هل تريد إنشاء هذا الزوج الآن؟» | the offer |
| `pairOffer.create` | «إنشاء الزوج» | the offer's answer |
| `pairOffer.later` | «ليس الآن» | the offer's other answer |

### Proof

New suites: `tests/e2e/screens/photo_viewer.py` (19 checks — real touch sequences at 390 px: tap, swipe, pinch, swipe
down, the back button; full Chromium for the PDF) and `tests/e2e/screens/pair_offer.py` (15). `photo_sync.py` 104
checks (12 new). `photo_safety.py` 29: its `[seen · not ruled]` merge check is replaced, deliberately, by three checks
of the closed gap.

Test changes made deliberately because the behaviour changed: the stage-1 «down» sections prove the fetch ON VIEW, and
a background pass now fetches first — so their receiving device is put "in the pocket" (a per-tab test switch that
makes the page report itself hidden), which keeps the background pass out of them; the document section leaves the
profile before its pull, because an open profile now follows the pull and would fetch at once.

| mutant | what it does | red at |
|---|---|---|
| M-nodown | no download leg | 6 |
| M-parallel | the lane removed, the leg in parallel | 3 |
| M-hiddendown | downloads in the background | 4 |
| M-offlinedown | downloads tried offline | 1 (first run SURVIVED — the check was strengthened; see below) |
| M-downnoback | a failed download does not stop the pass | 1 |
| M-nosyncload | an open profile ignores a pulled row | 1 |
| M-mergeskip | the merge fill removed | 2 |
| M-noopen | a tap on a photo opens nothing | 6 |
| M-delcover | the delete button covers the tile | 6 (its named check: the centre tap asked to delete) |
| M-noswipe | no swipe | 1 |
| M-nopinch | no pinch | 1 |
| M-noback | no history entry: back leaves the profile | 1 |
| M-nodoc | the document downloads again | 1 |
| M-nostripopen | a strip thumbnail opens nothing | 1 |
| M-doctiny | the document's link back to an inline 22 × 21 px target | 1 |
| M-nostriptap2 | the strip badge's tap says nothing (re-anchored: the badge now stops its tap opening the viewer) | 1 |
| M-nooffer | no offer | 7 |
| M-noprefill | the sheet opens with no father | 4 |
| M-offerref | a reference parent is offered | 1 |
| M-offerevery | every save with parents asks | 1 |

M-offlinedown survived its first run: offline, the test's stub still ANSWERS a routed request (the browser's offline
switch does not stop a request the test intercepts), so the mutant's download hung on a held request and the check —
which read only the failure count — passed. The check now also asserts `navigator.onLine` is false, that no request
was made and that no pass is left hanging; the mutant is red at it. Logs: `stage3-mutants-1.log`, `stage3-mutants-2.log`.

Every earlier photo mutant was run again on this tree (`stage3-mutants-rerun.log`, `stage3-mutants-3.log`) and is red:
stage 2 — M-nograce 5, M-dropqueue 3, M-anydel 2, M-noremove 8, M-noundo 1, M-nocascade 1, M-nocount 4, M-rowsilent 1,
M-fullsilent 2, M-fullrefuse 7, M-drop 23; the badge — M-nomark 4, M-notap 1, M-nostripmark 4, M-bigmark 1, M-stripout 1
(re-anchored as M-stripout2: the thumbnail's rule gained `cursor:zoom-in`); stage 1 — M-await 3, M-nofetch 12,
M-nokeep 14, M-hot 4, M-each 2, M-bigsend 12, M-anyok 2, M-anylen 1, M-forget 1, M-nosaved 2, M-lastonly 1. None HUNG,
no traceback. Screenshots at 390 px: `~/zajil-gate-logs/s3-shots/`.

**Gate-51 FAILED (2590 passed, 1 failed), not committed.** `photo_viewer.py`'s «a tap on the photo never deletes» check:
every tap opened nothing. Measured, not guessed: my first reading (a banner moving the page) was wrong — a probe showed
the tile never moves; the same check failed once in three runs alone; a diagnostic copy printed what each tap hit, and in
the failing run tile 0 was the DOCUMENT's tile (the tiles follow the media ids, which are random), whose link did not
fill its tile — the second finding above. The suite now picks a photo's tile; five runs in a row green; the document's
link fills its tile, pinned by its own check and M-doctiny. Logs: `s3-viewer-diag-*.log`, `stage3-mutants-4.log`
(the eight viewer mutants re-run on the changed suite, all red).

## TF-13 — the live checks asked the origin to be fast (2026-11-20, ORDERED: robust without relaxing)

deploy12's live verification failed on a `503` that GitHub Pages served as `200` a moment later; run again, it failed on
the service worker not yet registered after a fixed 3 s; a third run (2026-11-20, ordered) was clean, 44 of 44.
`tests/e2e/live_deployment.py`, test-only:
- **the worker** is waited for until it is ACTIVE (`navigator.serviceWorker.ready`), up to 30 s, before its scope and its
  cache are judged — the cache is written by the worker's install, so it is judged once that has finished. The time it
  took is printed. On the real origin after this change: active 2.9 s after the first page settled.
- **a 5xx from the origin under test** is asked for ONCE more: served then, it is a WARNING printed with the URL and both
  statuses (and listed again above the summary); still 5xx, the check fails as before. A 4xx is never re-asked.
- two reads that RAISED when the origin served no worker (the precache manifest read, the offline reload and deep route)
  now fail their checks instead, so such a run ends with a summary line, not a traceback.

Proved against a local Pages stand-in that injects faults (`~/zajil-work/deploy/serve_faults.py`, runner
`prove_live.sh`; logs `~/zajil-gate-logs/live-proof-*.log`), on the staged stage-2 release:

| condition | the suite before | the suite after |
|---|---|---|
| clean | 44 / 0 | 44 / 0 |
| one 503 on `health/__next._tree.txt` | 43 / 1 at «no failed requests» | 44 / 0, `! WARNING 503 … — asked again: 200` |
| that file 503 every time | — | 43 / 1 at «no failed requests» (`asked again: 503`) |
| `sw.js` held 12 s | 43 / 1 at «the cache is EXACTLY …» | 44 / 0 (active 6.4 s after) |
| `sw.js` 404 every time | — | 37 / 7, first at «service worker registered …», no traceback |
| the real origin | — | 44 / 0 |

### 2026-11-20 (later) — rulings on stage 3, and the amendments built before its deploy

**Ruled:** (1) the profile follows synced photos — APPROVED; (2) the swipe direction — APPROVED (Samir checks it feels
natural); (4) the arrows and the counter — APPROVED, the counter «2 / 5» in Western digits, on phones too; (5) the offer
only when the save changed the parents, any season counting — APPROVED; (6) the document filling its tile — APPROVED.
The six strings stand as proposals. Stage 3 deploys only after Samir's stage-2 acceptance passes.

**(3) CHANGED — a tap closes only at 1×.** Zoomed in, a tap does nothing; a double tap (two taps within 350 ms) returns to
1×. The close button in the top corner is there on every screen size (it already was; now pinned at 390 and 1280 px, 44 px).

**The counter** reads «2 / 5» in Western digits, left to right, whatever the numerals setting (it used the device's
numerals, and in a right-to-left line «2 / 3» was drawn «3 / 2»). Shown whenever the bird has more than one photo, on
every screen size, as before.

**A stuck download no longer holds the queue.** Each download is given `PHOTO_DOWNLOAD_TIMEOUT_MS` — PROPOSED 60 s (a
1600 px photo, 0.3–0.5 MB, comes in seconds on a slow phone line; a 5 MiB document needs about 40 s at 1 Mbit/s). Then
it is abandoned: that file fails, waits out its own backoff, and the pass goes on to the next file — a timeout does
not stop the pass (`timedOut` counts it); any other failure still does, as ruled. A tile or the viewer waiting on it
says «تعذّر تنزيل الصورة…» as for any failed download. Measured in the suite: given up at about 60 s, the next photo
came down in the same pass. Found while testing it: a photo that arrives while a pass is already running waits for the
next pass (the pass works from the list it started with) — unchanged, recorded.

Also, test-only: the suite now ANSWERS every request it was holding before it forgets it (`drop_held()`): with the
timeout, a held request the page abandoned surfaced as a `CancelledError` traceback from the driver.

| mutant | what it does | red at |
|---|---|---|
| M-zoomtapclose | a tap closes even when zoomed in | 2 |
| M-nodoubletap | a double tap does not return to 1× | 3 |
| M-countnumerals | the counter in the device's numerals, right to left | 1 |
| M-noclosebtn | no close button | 1 |
| M-notimeout | a download is never given up | 2 |

`photo_viewer.py` 23 checks, `photo_sync.py` 106. On the amended suites every stage-3 mutant was run again and is red
(`stage3-mutants-amend.log`): M-nopinch 3, M-noswipe 1, M-noback 2, M-noopen 10, M-nodoc 1, M-delcover 11, M-doctiny 1,
M-nostripopen 1, M-nodown 8, M-parallel 4, M-hiddendown 6, M-offlinedown 1, M-downnoback 1, M-nosyncload 1,
M-nostriptap2 1, M-stripout2 1. None HUNG, no traceback.

## 2026-11-20 — deploy record: photo sync, stage 3; the photo viewer; the pair offer (`gh-pages 4acbf2a`)

**Stage 2 closed first.** Samir's stage-2 acceptance PASSED on his phone and PC (relayed 2026-11-20): a test photo
added on the phone raised the bucket count by one and showed on the PC; after its deletion and a sync it was gone from
the PC and the bucket count was back at its starting value. Before that, the stage-2 live verification was run once
more, clean (`deploy12-06c-live-verify-rerun2.log`, 44 passed, 0 failed); then **the mirror's `main` was pushed as
`3fbbc26`** (`git subtree split --prefix=next 2323fc2`, fast-forward from `a0ea16c`) and **`origin/feat/photo-stage-2`
and `origin/feat/photo-stage-2b` were deleted**: the two things the stage-2 record above says wait are done.

**Ruled with the deploy order:** the download timeout of 60 s APPROVED (the comment above `PHOTO_DOWNLOAD_TIMEOUT_MS`
in `src/db/photos.js` still says PROPOSED; it is corrected with the next code change, not in this record); TF-13 and the
stage-3 amendments accepted. The six stage-3 strings ship as written, as proposals; corrections come as one follow-up.

Live: `gh-pages 4acbf2a`, built from `feat/react-port 591622c`, fast-forwarded from `feat/photo-stage-3`
(`697e145` stage 3, viewer, pair offer; `b16ad55` TF-13; `591622c` the amendments). **Rollback target: `6ca309e`**
(stage 2; then `73036f1`). Rollback is `git -C ~/zajil-work/deploy/ghp-photo-stage-3-2026-11-20 push -f origin 6ca309e:gh-pages`.
Mirror `main` = `c7cfe95` (`git subtree split --prefix=next 591622c`, run from `~/zajil`, fast-forward from `3fbbc26`).

| step | result | log (`~/zajil-gate-logs/`) |
|---|---|---|
| gate-54 on `591622c` | 2598 passed, 0 failed across 41 steps, 0 page-error records | `gate-54-stage3-amend.log` |
| stage for `/zajilv2/`, inject, verify, scan | 159 files, CLEAN | `deploy13-01`, `deploy13-02` |
| live before | `gh-pages 6ca309e`, `main 3fbbc26` | `deploy13-03` |
| rehearsal on the local Pages stand-in (TF-13 suite) | 44 passed, 0 failed, no WARNING | `deploy13-04` |
| live bytes | 158 files by sha256, 0 differ (new sw.js after 31 s) | `deploy13-05` |
| live verification (TF-13 suite) | 44 passed, 0 failed, no WARNING, NET armed — nothing reached the real project; service worker active 2.8 s after the first page settled | `deploy13-06` |

Stage 3 adds no stored shape: a downloaded photo's bytes go into the media row that was already there, as stage 1's
fetch-on-view did, and the merge-import fill writes the same row. The download backoff (`failedAt`) is held in memory
only. A rollback to `6ca309e` stops the background download, the viewer and the pair offer, and leaves every record,
photo and tombstone as it is; photos already downloaded stay on the device.

Not deleted (not ordered): `origin/feat/photo-stage-3` (now equal to `feat/react-port`'s deployed commit) and
`origin/feat/photo-stage-1`.

## 2026-11-23 — placeholder parents (BUILT, NOT DEPLOYED; branch `feat/siblings-clutch`, commit 1 of 2)

Samir ruled a new feature on 23 Nov — on the bird form, «sibling of» and «from the same clutch» for birds whose
parents are unknown — and, before it, eight rulings on the records the app already makes for unknown parents. This
commit is those eight. The feature itself is the next commit.

**What was there.** «إضافة شقيق/شقيقة» on a bird with no recorded parents makes two records, a father and a mother,
and writes them to both birds (`app/bird/form.tsx`). Kinship is derived from shared `sireId` / `damId` and from nothing
else, so the two records are what makes the birds siblings. They were ordinary reference birds: a row each in the bird
list, counted, offered by every picker — typing «أب غير معروف» in any parent picker selected the placeholder of
ANOTHER family, making the two families full siblings without a word (`src/components/picker.ts`, the exact-name
match) — and printed everywhere under the name they were given in whatever language the app was in that day.

**What is built (items 1–7).**

1. `placeholder: true` on the bird, always with `external: true` (`newBird()` derives it); missing means false. Set
   where the two records are made. Port-only: `src/family.js` (`isPlaceholder`, `listedBirds`), re-exported by the facade.
2. Not in the bird list or anything fed by its rows (count line, year groups, filters, search) — `selectListedBirds`;
   not in the three bird counts: the sign-in gate's «does this device hold records» (`Gate.tsx`), the CLEAR question
   (`sign-in/view.tsx`), the restore list's «{n} طيرًا» (`tools/parts.tsx`). Statistics: a bird whose parents are BOTH
   placeholders has no recorded pedigree (`stats/view.tsx`); one placeholder beside a recorded parent still has.
3. No picker offers, matches or returns one. The rule lives once, in `pickerModel()` and `createFromQuery()`
   (`pickable()`), which five of the six pickers go through; the relationship finder has its own filter.
4. The pedigree tree, the profile's mini pedigree, the certificate's sheet and its parent photo boxes read «غير معروف»
   / "Unknown" from the flag, in the language of the screen. In the tree and the mini pedigree the box is a link to the
   record's edit form. The common-ancestor dot is drawn as for any bird.
5. The flag clears when the form saves the record with at least one ring, or under a name other than the stored one.
   The key is removed, not set to false.
6. `deleteBird()` deletes, in its one transaction, every placeholder parent left with no other child, each with its own
   operation and tombstone; the snapshot carries them and `restoreBird()` puts them back.
7. NOT hidden from the duplicate-ring search or the integrity check. `src/example-data.js` is not changed.

**Chosen without a ruling — each a PROPOSAL.**

- The flag also clears when the form saves the record as a bird of the loft (external switched off): it never stays
  without `external`.
- A placeholder box in the tree takes the unknown slot's dashed look and its «+», and carries `data-known="0"`
  `data-placeholder="1"`; on the certificate `data-recorded="no"`. The certificate's sheet has no links today and none
  was added. As the SUBJECT of its own pedigree page or profile a placeholder still shows its stored name.
- Item 6 is transitive (a placeholder's own placeholder parents go too) and runs the whole cascade for each record that
  goes (its results, health events, pairs, photos). The undo restores the placeholders before the bird that names them.
- `Gate.tsx:44` is not a number anyone reads: it answers yes or no, and only when no loft on the device answers first —
  a loft any record is filed under is not pristine, and placeholders are filed under the current loft like every
  record. Built as ruled; it decides only on a device whose records are filed under a loft that is not on it
  (`screens/gate.py` builds that device). My own description of this line on 23 Nov, «the record count on the sign-in
  screen», was wrong.

**Not ruled, NOT built — found while building.**

- **A placeholder whose last child is re-pointed stays, hidden and unreachable.** Item 6 covers deletion. Changing or
  clearing a parent in the form leaves the placeholder with no child; nothing lists it and nothing points to it.
- **Where the stored name still shows:** the bird form's parent slot, the profile's «الأب» / «الأم» rows, the
  placeholder's own profile and pedigree page, the COI breakdown table under the tree, the names in the form's
  validation messages, the duplicate-ring list.
- **What still counts a placeholder as a known ancestor** (the engine, unchanged): the tree's «أسلاف» and «أجيال
  مكتملة» tiles, the profile's pedigree completeness, AVK.
- **Counts not in the ruling, unchanged:** the import and replace toasts and the replace question («{birds} طيرًا»),
  the teaching-data loader's toast.

**Item 7, measured (`~/zajil-gate-logs/sib-c1-measure7*.log`; teaching loft of 38, harness build, no backend).**
The removal deletes through `deleteBird()`, so item 6 applies inside it.

| | before | after the removal |
|---|---|---|
| placeholder father and mother whose two children are both teaching birds | 2 records | **both deleted**, each tombstoned — with their last teaching child |
| placeholder father and mother with one teaching child and one bird of the user's | 2 records | **both kept**, still placeholders; the user's bird still names both; the teaching child deleted |
| the removal's own count | question: «38 طيرًا» | returned `birds: 38` — it deleted 40 bird records |
| integrity | — | 0 dangling |

On a first-run device, where the teaching loft is the current loft and the placeholders are therefore filed under it,
the question also says «لديك 5 من سجلاتك داخل اللوفت التجريبي؛ لا تُحذف، بل تُنقل إلى لوفتك.» — the 5 are the four
placeholders and the user's one bird — and the removal then moved 3 and **deleted the 2** whose only children were
teaching birds. The sentence's «لا تُحذف» is not true of those two. Not changed, by order; for a ruling.

**Item 8, measured (`sib-c1-measure8.log`) — legacy placeholders, on a CONSTRUCTED register.** No record made before
this change set carries the flag, and none is guessed. On a register of 35 bird records built to hold every case, the
predicate «external, no rings, no hatchDate, name equals `bird.unknownSire` / `bird.unknownDam` in ar or en, parent of
at least one bird» matches **12**: 10 without the flag (8 under the Arabic names, 2 under the English) and the 2 made
after this change set. Of the 10, one was typed by hand into a parent picker and is no placeholder by origin. It
misses 5 records the old menu made: one renamed since, one given a ring, one given a hatch date, and the two parents
of a family whose children were since deleted.

PROPOSED, not built — a one-time marking step that asks instead of guessing: a row in الأدوات → البيانات, shown only
while a record matches the predicate and has no `placeholder` key, that lists each match with the birds that name it
and lets the fancier say which are unknown parents. Yes writes `placeholder: true`; no writes `placeholder: false`, so
the record is never asked about again and the answer travels with it to his other devices.

**Proof.** New suite `tests/e2e/screens/placeholders.py`, 39 checks at 390 px; `screens/gate.py` 25 → 28 (the gate and
the CLEAR question need its stub backend). Nineteen mutants, one harness build and one suite each, 300 s limits; every
one red at the check that names it. M-greedy and M-noundo first ended in a traceback AFTER their named check had
failed — a later step wrote to a record the mutant had removed; the suite's later steps now read before they write,
and both were run again (`sib-c1-mutants.log`, `sib-c1-mutants-b.log`).

| item | mutant | what it does | red at |
|---|---|---|---|
| 1 | M-noflag | the father is made without the flag | 23 |
| 2 | M-list | the bird list reads every bird | 4 |
| 2 | M-backup | the restore list counts every record | 1 |
| 2 | M-stats | two placeholder parents count as a recorded pedigree | 2 |
| 2 | M-gate | the gate counts every bird record | 1 |
| 2 | M-signin | the CLEAR question counts every bird record | 1 |
| 3 | M-pick | `pickable()` lets everything through | 6 |
| 3 | M-create | «إنشاء» returns the existing placeholder | 1 |
| 3 | M-finder | the relationship finder offers placeholders | 1 |
| 4 | M-ped | the tree prints the stored name | 4 |
| 4 | M-mini | the mini pedigree prints the stored name | 2 |
| 4 | M-cert | the certificate prints the stored name | 1 |
| 4 | M-certbox | the photo box label prints the stored name | 2 |
| 5 | M-noclear | a ring does not clear the flag | 2 |
| 5 | M-noclearname | another name does not clear the flag | 2 |
| 6 | M-noorphan | the orphaned placeholder is left | 2 |
| 6 | M-greedy | a placeholder goes although another child names it | 7 |
| 6 | M-noundo | the undo does not restore the placeholders | 6 |
| 7 | M-dupblind | the duplicate-ring list is blind to placeholders | 1 |

## 2026-11-23 — sibling of / same clutch, for new and existing birds (BUILT, NOT DEPLOYED; branch `feat/siblings-clutch`, commit 2 of 2)

Ruled items 9–15. Until now the only way to record two birds as siblings without knowing their parents was the
profile's «إضافة شقيق/شقيقة», which makes a NEW bird; two birds already in the register could not be linked, and
nothing could say that two birds hatched from the same clutch unless a pair record with a round held them both.

**What is built.**

- **Item 9 — `clutchId`** on the bird: a group id (a uuid). It points at no record, so there is nothing for the
  integrity check to follow and nothing for a delete to cascade over.
- **Item 10 — `clutchMates(bird)`**, one implementation (`src/engine/clutch.js`, pure and port-only; bound to the
  register by `src/family.js`): the birds sharing its `clutchId`, plus the birds whose ids are `chickId` in the same
  round of a pair. Nothing writes `clutchId` when a chick is ringed — the round is that record.
- **Item 11 — «أخ/أخت لطير مسجَّل…»** on the bird form, new and existing birds alike. A panel under the two parent
  slots: pick a bird (never this one, never a placeholder), then «الأبوان معًا» / «الأب فقط» / «الأم فقط», and the
  checkbox «من نفس البطن», which presses «الأبوان معًا» and locks the three. «تأكيد» settles the choice and holds it:
  the slots show the parents taken from the other bird, a notice says what the save will do, and NOTHING IS WRITTEN.
  The save plans it (`planSiblingLink()`, which writes nothing) and writes the placeholders it makes, the other bird
  and this one in ONE transaction (`saveBirds()` in `src/db/records.js`), judged first as one set (`checkBirds()`).
  - the other bird has the parent → its id is copied;
  - neither has it → a placeholder is made and written to both;
  - this bird has a DIFFERENT parent → the form stops and asks, naming both and the other bird, «استبدال» / «إلغاء»;
    asked when the choice is made, and again at the save if either record changed in between;
  - same clutch → the other bird's `clutchId` is copied, or a new one written to both; an empty hatch date takes the
    other bird's; two different hatch dates warn; a clutch of more than two warns; neither blocks;
  - the other bird is this bird's ancestor or descendant → refused, with the reason, and no choice is held.
- **Item 12 — `src/engine/validate.js`:** `val.clutchParents`, a warning, when a clutch-mate does not share this bird's
  sire and dam. For the round's mates it needs the pairs, so `validateBird()` and `classifySave()` take them, and
  `records.js` hands them over at every validation — the form's check, the save, and the diagnosis of a pulled row.
  **`validate.js` is now declared DIVERGENT — the first engine file the port owns** (guard `data-layer-identity`,
  PORT-COMPLETE). Called with three arguments, as the vanilla suite calls it, it behaves as before.
- **Item 13 — the profile**, النسب tab: a card «الإخوة» with up to three plain lists of links — full siblings, half
  siblings, clutch-mates — under the mini pedigree; absent when there is nothing to list. **Placement and styling are
  PROPOSED**, as is the panel's place and its checkbox row; both are drawn with classes the two screens already have.
- **Item 14 —** the menu's «إضافة شقيق/شقيقة» is the same link, arriving as `?siblingOf=`; it sets the flag and is now
  written in one transaction too.

**Chosen without a ruling — each a PROPOSAL.**

1. **The other bird lacks the parent and THIS bird has it → the other bird is given this bird's.** The ruling says a
   placeholder is made and written to both; doing that here would replace a recorded parent of this bird with an
   unknown one. Nothing of either bird is replaced this way, and no placeholder is made.
2. The choice is held by the form and written with the save — that is what makes «nothing written on cancel» true for
   a bird that does not exist yet, and one rule for both.
3. The conflict question has two answers, «استبدال» and «إلغاء»; declining leaves the form as it was.
4. Clutch ids: the other bird's wins; if it has none and this bird has one, the other bird joins this bird's; if both
   have one and they differ, this bird moves to the other's and its former mates keep theirs.
5. Only this bird's empty hatch date is filled; the other bird's is never written.
6. The clutch warnings and the validation warnings are asked in the form's existing warnings dialog, at the save. The
   other bird's warnings are shown only where this link brings them (under its name); an error it would have stops the
   whole save. Its own older warnings are not this save's to judge (`allowWarnings`, pinned: `allow-warnings-bounded`
   2 → 3 for `app/bird/form.tsx`).
7. Item 12 covers both kinds of clutch-mate (item 10's definition), not only the `clutchId` group.
8. Siblings are listed as the engine derives them: a missing mother is not a shared mother, so two birds with the same
   father and no recorded mother are half siblings. A placeholder is never listed. The lists reuse two existing
   strings for their headings (`rel.fullSiblings`, `rel.halfSiblings`).
9. The menu's intent keeps its own sentence only where it is true — both parents unknown on both birds; if the new
   bird was given a parent in the form, the intent is now honoured (it used to be dropped without a word) and the
   notice says the general thing.
10. Notes and picked photos are written after the transaction, as before.

**Not built, for rulings.** A link whose other bird was deleted before the save is dropped without a word (the notice
disappears with it). Offline, two devices that put the same bird in different clutches each keep their own write
until last-write-wins picks one per record, which can leave a clutch of one.

**New strings — twenty-one, all PROPOSED, all through the typography scan** («أخ/أخت لطير مسجَّل…» and «من نفس
البطن» are the order's own words):

| key | Arabic | English |
|---|---|---|
| `sib.action` | «أخ/أخت لطير مسجَّل…» | Sibling of a recorded bird… |
| `sib.both` | «الأبوان معًا» | Both parents |
| `sib.sireOnly` | «الأب فقط» | Father only |
| `sib.damOnly` | «الأم فقط» | Mother only |
| `sib.sameClutch` | «من نفس البطن» | From the same clutch |
| `sib.notice.title` | «أخ/أخت لـ «{name}»» | Sibling of “{name}” |
| `sib.notice.both` | «عند الحفظ يُسجَّل للطيرين الأب نفسه والأم نفسها. لن يُكتب شيء إن ألغيت.» | On save, both birds are recorded with the same father and the same mother. Nothing is written if you cancel. |
| `sib.notice.sire` | «عند الحفظ يُسجَّل للطيرين الأب نفسه. لن يُكتب شيء إن ألغيت.» | On save, both birds are recorded with the same father. Nothing is written if you cancel. |
| `sib.notice.dam` | «عند الحفظ تُسجَّل للطيرين الأم نفسها. لن يُكتب شيء إن ألغيت.» | On save, both birds are recorded with the same mother. Nothing is written if you cancel. |
| `sib.notice.clutch` | «عند الحفظ يُسجَّل الطيران من البطن نفسه، بالأب نفسه والأم نفسها. لن يُكتب شيء إن ألغيت.» | On save, both birds are recorded as hatched from the same clutch, with the same father and the same mother. Nothing is written if you cancel. |
| `sib.notice.unknown` | «الأب أو الأم غير المسجَّل يُنشأ له سجلّ «غير معروف» ويُربط بالطيرين معًا.» | A father or mother that is not recorded gets an “unknown” record, linked to both birds. |
| `sib.remove` | «إلغاء الربط» | Remove the link |
| `sib.conflict.title` | «اختلاف في الأبوين» | The parents differ |
| `sib.conflict.sire` | «أب هذا الطير المسجَّل هو «{mine}»، وأب «{name}» هو «{theirs}». هل تريد استبدال «{mine}» بـ «{theirs}» أبًا لهذا الطير؟» | This bird’s recorded father is “{mine}”, and the father of “{name}” is “{theirs}”. Replace “{mine}” with “{theirs}” as this bird’s father? |
| `sib.conflict.dam` | «أم هذا الطير المسجَّلة هي «{mine}»، وأم «{name}» هي «{theirs}». هل تريد استبدال «{mine}» بـ «{theirs}» أمًّا لهذا الطير؟» | This bird’s recorded mother is “{mine}”, and the mother of “{name}” is “{theirs}”. Replace “{mine}” with “{theirs}” as this bird’s mother? |
| `sib.conflict.replace` | «استبدال» | Replace |
| `sib.reject.lineage` | «لا يمكن تسجيل «{name}» أخًا أو أختًا لهذا الطير: أحدهما من أسلاف الآخر.» | “{name}” cannot be recorded as this bird’s sibling: one of them is an ancestor of the other. |
| `sib.warn.clutchSize` | «سيصير في هذا البطن {n} طيور، والبطن في العادة بيضتان.» | This clutch would hold {n} birds; a clutch is normally two eggs. |
| `sib.warn.hatchDiffers` | «تاريخ فقس هذا الطير ({mine}) يختلف عن تاريخ فقس «{otherName}» ({theirs})، وهما من البطن نفسه.» | This bird’s hatch date ({mine}) differs from that of “{otherName}” ({theirs}), and they are from the same clutch. |
| `val.clutchParents` | «هذا الطير و«{otherName}» من البطن نفسه، لكن أبويهما المسجَّلين مختلفان.» | This bird and “{otherName}” are from the same clutch, but their recorded parents differ. |
| `profile.siblings.title` | «الإخوة» | Siblings |

**Proof.** New suite `tests/e2e/screens/siblings_clutch.py`, 48 checks at 390 px through the form itself; two engine
tests in the port-only `tests/clutch.test.js` (the node suite 33 → 35). «One transaction» is proven by failure: a
`saveBirds()` whose second record storage cannot take leaves the first out of memory, out of storage and out of the op
log. Seventeen mutants, one harness build and one suite each, 300 s limits (`sib-c2-mutants.log`):

| item | mutant | what it does | red at |
|---|---|---|---|
| 11 | M-clutchboth | «من نفس البطن» alone no longer asks for both parents in the plan | 1 |
| 11 | M-planhatch | the plan does not take the other bird's hatch date | 1 |
| 9 | M-noclutchid | this bird is not given the clutchId | 11 |
| 11 | M-eager | «تأكيد» writes to the other bird at once | 15 |
| 11 | M-noother | the placeholder is not written to the other bird | 16 |
| 10 | M-nogroup | clutchMates() ignores the clutchId group | 8 |
| 10, 12 | M-noround | clutchMates() ignores the rounds | 3 |
| 12 | M-noclutchwarn | no warning when clutch-mates' parents differ | 6 |
| 11 | M-nocopy | the other bird's parents are not taken into the form | 4 |
| 11 | M-noask | a different parent is replaced without asking | 4 |
| 11 (proposed) | M-give | the other bird is not given this bird's parent (a placeholder replaces it) | 3 |
| 11 | M-nowarnsize | no warning for a clutch of more than two | 1 |
| 11 | M-nowarnhatch | no warning for two hatch dates | 1 |
| 11 | M-nolineage | an ancestor or descendant is accepted | 1 |
| 11 | M-notx | saveBirds() writes each bird in its own transaction | 1 |
| 11 | M-partial | saveBirds() writes a record that failed validation | 1 |
| 13 | M-nolists | the profile draws no sibling lists | 3 |

---

## 2026-11-24 — placeholder parents: the rulings on the report, B1–B8 (BUILT, NOT DEPLOYED; branch `feat/siblings-clutch`, commit 3)

**Rulings on the report of 2026-11-23.** Both commits accepted. Commit 2's first proposal — where the other bird lacks a
parent this bird has, the other bird is given this bird's — is accepted and replaces the wording of item 11.
`src/engine/validate.js` as a declared divergent file is accepted. Every other listed proposal is accepted except where
B1–B8 change it. The one-time marking of legacy placeholders is deferred and is not in this commit.

**B1 — the teaching-data removal counts real birds, and «لا تُحذف» is true of what it counts** (`src/example-data.js`).
`own` and `ownBirds` leave out placeholder parents; `moved` counts real birds only (a placeholder that is still here is
re-filed and not counted). On the first-run device measured on 2026-11-23 — the teaching loft current, one bird of the
fancier's and four placeholder parents filed in it — the question said 5 and the removal moved 3 and deleted 2; it now
says 1, moves 1, and the record it counts is the one that stays.

**B2 — one name** (`src/components/BirdBits.tsx`: `placeholderName()`, with `birdName()`, `birdLabelText()`,
`BirdLabel` and `problemParams()` going through it). A box of the tree, the mini pedigree or the certificate reads
«غير معروف»; everywhere else that prints a bird's name reads «أب غير معروف» / «أم غير معروفة» by sex, in the language
of the screen, whatever the record's stored name is: the form's parent slots, the profile's «الأب» / «الأم» rows, the
record's own profile, pedigree page and certificate, the COI breakdown table, validation messages, the duplicate-ring
list and its delete question, the sibling link's questions.

**B3 — a placeholder is not a known ancestor** (`src/family.js`: `knownAncestors()`). The pedigree's «{n} سلف من 30» and
«أجيال مكتملة» tiles and the profile's «اكتمال الشجرة» count without placeholders. The coefficient of inbreeding and AVK
are not changed, and no engine file was touched.

**B4 — a save that leaves a placeholder with no child** (`src/db/records.js`: `parentsDropped()`,
`placeholdersLeft()`, `settlePlaceholders()`, `writeBirds()`). When `saveBird()` or `saveBirds()` changes or clears a
parent and a placeholder is left with no child, it is deleted in that save's own transaction, with its operation and
tombstone, and so is a placeholder parent of its own left childless in turn. A save that drops no placeholder is
written exactly as before. `deleteBird()` now uses the same rule (it was item 6's own loop).

**B5 — one that holds anything of its own is never deleted that way** (`holdsOwn()`). Not by item 6 and not by B4: its
flag is cleared in the same transaction and it stays, a reference bird the register lists. The undo of a deletion puts
the flag back. This replaces commit 1's seventh proposal (a placeholder that goes took its own results, health events,
pairs and photos with it): one that goes now holds none.

**B6 — a held sibling link whose other bird is gone** (`app/bird/form.tsx`). The save stops, names the bird, and writes
nothing; the notice on the form says the same as soon as the bird goes, and offers «إلغاء الربط».

**B7 — the other counts** (`src/db/io.js`, `app/tools/parts.tsx`, `app/birds/view.tsx`). The import toast, the restore
toast and the two teaching loaders' toast count real birds (`counts.placeholders`, `birdsImported()`); the replace
question counts a dropped placeholder among the other records, never among the birds; the restore question neither
counts nor names a placeholder among the birds that come back.

**B8.** The comment in `app/bird/form.tsx` names the button it is («تأكيد»). The introduction of `PORT-COMPLETE.md`
states seven declared exceptions and ten identical files of seventeen, measured with `cmp` over the guard's own list.

**Chosen without a ruling — PROPOSED:**

1. **B1, beyond placeholders.** `own` also leaves out a result, a health event or a pair of the fancier's that names a
   teaching bird the removal deletes: `deleteBird()` removes it with that bird, so «لا تُحذف» was false of it. Measured
   by M-b1-cascade: of five such records in the teaching loft the question counted 5 and 3 were deleted; it now counts
   the 2 that stay. **Not built:** those three are still not among the question's deleted counts, which are the
   datasets' own records.
2. **B1.** A placeholder that B5 frees during the removal is a real bird by the time it is re-filed, and is counted in
   `moved`. [read from code]
3. **B2.** A placeholder whose sex is not recorded reads «غير معروف». The certificate's parent photo rows are boxes;
   the row and the heading of the certificate's own subject read by sex.
4. **B2.** The same helper now also names a bird on the races, health, statistics, breeding and pair screens, in the
   delete questions, and in the removal's «بسبب» list. No picker offers a placeholder, so none is reachable there by
   the form; a record arriving by import or sync is. [read from code; not in a suite]
5. **B3.** Also applied to the completeness figure beside AVK on the pedigree page, and to the certificate's
   «{f} من {tot} سلفًا» — neither is named in the ruling. An ancestor recorded BEHIND a placeholder counts as known.
6. **B4.** Applies to every save through the boundary — the breeding screen's «ربط طير مسجَّل» included — and not to an
   import or a pulled row, which apply records as they are.
7. **B5, what "its own" compares.** Every field of the record except its identity and bookkeeping (`id`, `loftId`,
   `createdAt`, `updatedAt`, `deviceId`, `provenance`), `name` and `sex`: any that is not empty, or not what a
   placeholder is made with (a status other than `reference`, for one). `name` and `sex` are not compared — the record
   does not keep what it was made with, and a rename through the form already clears the flag. A parent that is itself
   a placeholder is not something it holds (so item 6's chain still goes together); a recorded parent is. An egg that
   names it as its chick counts as a pair.
8. **B5.** The record that stays keeps the name stored on it, which is now shown: «أب غير معروف», or "Unknown sire"
   if it was made in English.
9. **B6.** The notice changes while the form is open and carries «إلغاء الربط» for the menu's link too (it had none);
   a link whose other bird has become a placeholder is treated as gone; the check is made again just before the write.
10. **B7.** `counts.birds` is unchanged and `counts.placeholders` is added. The restore's «يُحذف {n} سجلًا» counts
    records, placeholders included.

**AVK — what it does with placeholders (not changed, as ruled).** [read from code, measured] `ancestorLoss()` counts a
place as filled when the child names an id there, and counts the different ids; a placeholder is an id like any other.
Measured: a bird with two placeholder parents and nothing else has 2 filled places of 62 and 2 different ancestors, AVK
100.0%; a youngster of two full siblings who share two placeholder parents has 6 filled and 4 different, AVK 66.7%.
Without the placeholders that youngster would read 100.0% beside a coefficient of 25.0%. **Proposed: leave it.** AVK
measures repeats among the ancestors recorded, and "the same unknown father, twice" is exactly what a shared placeholder
records — the reason the coefficient was left alone. The one oddity is 100.0% on a bird with no known ancestor, which is
what any bird with no parents reads today.

**Found while building — not built, for rulings:**

- **Across devices, B4 and item 6 can leave a link to nothing.** Measured with two devices of one account: device 2,
  offline, recorded a second child for a placeholder father; device 1 cleared the first child's father, which deleted
  the placeholder there; after both synced, the second child names a father no device holds
  (`integrity.birdParent` on both). Sync is per record, and a pulled deletion does not look at who names the record.
  The same was already possible through item 6 (delete the last child on one device). Proposal: the device that pulls
  the deletion of a placeholder while a bird of its own names it puts the placeholder back.
- **The name field of a placeholder's own edit form** still holds the stored name — it is the value being edited, and
  item 5 compares against it. Typing the label the app shows («أب غير معروف» over a stored "Unknown sire") counts as a
  new name and clears the flag. Proposal: show the field empty for a placeholder, the label as its hint, and clear the
  flag when anything is typed.
- **Not covered by B4:** a parent changed by an import or by a pulled row leaves the placeholder where it is.

**New string — one, PROPOSED, through the typography scan:**

| key | Arabic | English |
|---|---|---|
| `sib.gone` | «لم يعد «{name}» مسجَّلًا، فلا يمكن حفظ هذا الطير أخًا أو أختًا له. ألغِ الربط أو اختر طيرًا آخر.» | “{name}” is no longer recorded, so this bird cannot be saved as its sibling. Remove the link or choose another bird. |

No existing string was changed. `bird.unknownSire`, `bird.unknownDam` and `common.unknown` are now printed in more
places (B2); their texts are as they were.

**Proof.** Two new suites at 390 px: `tests/e2e/screens/placeholder_rulings.py` (B2–B6, 48 checks) and
`tests/e2e/screens/placeholder_counts.py` (B1 and B7, 17 checks). «One transaction» is measured directly: every put and
delete is tagged with the IndexedDB transaction it ran in, and the bird's record, the placeholder's deletion and its
tombstone carry the same one. Thirty-nine mutants, one harness build and one suite each, 300 s limits, every one red at
the check that names it, none with a traceback (`sib-c3-mutants.log`, `sib-c3-mutants-b.log`):

| ruling | mutant | what it does | red at |
|---|---|---|---|
| B1 | M-b1-own | the removal counts placeholder parents among the fancier's records | 2 |
| B1 | M-b1-moved | `moved` counts the placeholders it re-files | 1 |
| B1 | M-b1-cascade | `own` counts records the removal deletes with a teaching bird | 1 |
| B2 | M-b2-name | `birdName()` ignores the flag | 8 |
| B2 | M-b2-slot | the form's parent slot prints the stored name | 2 |
| B2 | M-b2-row | the profile's parent rows print the stored name | 1 |
| B2 | M-b2-title | the profile's heading prints the stored name | 2 |
| B2 | M-b2-pedpage | the pedigree page's bar prints the stored name | 1 |
| B2 | M-b2-box | a box reads by sex instead of «غير معروف» | 4 |
| B2 | M-b2-label | `birdLabelText()` ignores the flag (the certificate's heading, the questions) | 2 |
| B2 | M-b2-biglabel | `BirdLabel` ignores the flag (the COI breakdown table) | 1 |
| B2 | M-b2-val | a validation message keeps the stored name | 1 |
| B2 | M-b2-dup | the duplicate-ring list prints the stored name | 1 |
| B3 | M-b3-known | `knownAncestors()` counts placeholders | 6 |
| B3 | M-b3-tiles | the pedigree's tile reads the engine's count | 3 |
| B3 | M-b3-profile | the profile's completeness reads the engine's count | 2 |
| B3 (proposed) | M-b3-cert | the certificate reads the engine's count | 1 |
| B4 | M-b4-off | a save never looks for a placeholder it drops | 8 |
| B4 | M-b4-greedy | a placeholder another bird still names is taken as childless | 2 |
| B4 | M-b4-chain | its own placeholder parents are not followed | 1 |
| B4 | M-b4-split | the placeholder is deleted in a second transaction | 3 |
| B4 | M-b4-link | `saveBirds()` (the sibling link) does not apply the rule | 1 |
| B5 | M-b5-off | nothing counts as its own | 10 |
| B5 | M-b5-fields | its fields are not looked at | 7 |
| B5 | M-b5-media | its photos and documents are not looked at | 2 |
| B5 | M-b5-records | its results, health events and pairs are not looked at | 2 |
| B5 | M-b5-parent | a recorded parent of its own is not looked at | 2 |
| B5 | M-b5-keepflag | it stays, but keeps the flag | 8 |
| B5 | M-b5-undo | the undo does not put the flag back | 1 |
| B6 | M-b6-drop | the link is dropped and the bird saved without it | 3 |
| B6 | M-b6-notice | the notice does not change when the bird goes | 2 |
| B7 | M-b7-toast | `birdsImported()` returns every bird record | 4 |
| B7 | M-b7-count | the import does not count placeholders apart | 4 |
| B7 | M-b7-replace | the replace question counts placeholders as birds | 1 |
| B7 | M-b7-returning | the restore question lists placeholders as birds that come back | 1 |
| B7 | M-b7-site-import | the import toast prints every bird record | 1 |
| B7 | M-b7-site-restore | the restore toast prints every bird record | 1 |
| B7 | M-b7-site-loader | the loader's toast in الأدوات prints every bird record | 1 |
| B7 | M-b7-site-empty | the loader's toast on the empty register prints every bird record | 1 |

Two reversals. M-b2-label was first red at one check, not two: the fixture for the sibling question held an Arabic
stored name, so that check could not tell the helper from the record. The fixture was given an English one. My first
edit of it commented out the rest of its line, and the re-run ended in a traceback, which is not proof; the line was
repaired and the mutant run again — red at two named checks. No other mutant's checks read that fixture's name.
