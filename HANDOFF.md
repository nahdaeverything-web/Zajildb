# Zajil — project handoff

**Status:** working app, all tests green

> Paste the block at the very bottom (“Seed prompt for a new chat”) into a fresh
> session to bring it up to speed in one message.

---

## 1. What this is

**زاجل / Zajil** — an Arabic-first, offline-first Progressive Web App for
racing-pigeon **pedigree and loft management**, aimed first at fanciers in
Jordan and the Gulf, usable by anyone. Built from a written product spec kept outside the repo, which remains the
authoritative scope document.

No framework, no build step, no dependencies. Vanilla ES modules + IndexedDB,
served as static files from any host.

### The three pillars (every scope decision defers to these)

1. **Arabic-first, true RTL** — layout *mirrors*, it is not a translation skin.
   In Arabic the pedigree subject sits on the **right**, ancestors extend
   **left**.
2. **Works offline** — IndexedDB is the source of truth; the app never blocks
   on the network. Rural lofts, weak data, no signal.
3. **Regional race structures** — Jordanian club/federation races, GCC
   one-loft races, FCI ring eligibility. Nothing else models this.

If a proposed feature doesn't serve one of those three, it is out of scope.

---

## 2. Status snapshot

| | |
|---|---|
| App version (service worker) | `zajil-v1.7.0` |
| `main` at | `eedb38d` — "Merge v1.7 invariant hardening pass" |
| **Live** | **https://nahdaeverything-web.github.io/Zajildb/** — serving `zajil-v1.7.0`, verified installable and offline-capable |
| Node tests | **75 passing, 0 failing** — `node tests/run.js` |
| Browser assertions | **148 passing, 0 failing** across **15 suites** — `python3 tests/e2e/run_all.py` |
| Opt-in suite | `live_deployment.py` — **11 passing**, not in the default run; printed as `[skip]` with its reason (needs the internet, tests the *deployed* build). Add `--live`. |
| Browser suites | committed under `tests/e2e/` with a runner and README, plus 6 diagnostic scripts |
| Source | `js/` 4,587 lines · `css/app.css` 372 · `sw.js` 89 |
| Tests | node 1,014 lines · browser 1,407 lines |
| Generators | `tools/` 448 lines |
| Example datasets | 20-bird loft + 38-bird / 6-generation teaching loft |
| Version control | git, pushed to **github.com/nahdaeverything-web/Zajildb** (public); `pre-v1.7-baseline` tagged, `hardening/v1.7` retained |
| Known issues | catalogued in [BACKLOG.md](BACKLOG.md) |

Line counts recounted from source, not carried forward:

```
$ find js -name "*.js" | xargs wc -l | tail -1
   4587 total
$ wc -l css/app.css sw.js
    372 css/app.css
     89 sw.js
$ find tests -name "*.js" -not -path "*/e2e/*" | xargs wc -l | tail -1
   1014 total
$ find tests/e2e -name "*.py" | xargs wc -l | tail -1
   1407 total
$ find tools -name "*.js" | xargs wc -l | tail -1
    448 total
```

---

## 3. Running, testing, serving

```bash
cd ~/zajil

# serve (static files; any host works)
python3 -m http.server 8123 --bind 0.0.0.0

# tests (node) — 33 tests incl. the mandatory COI fixtures
node tests/run.js

# regenerate the example datasets deterministically
node tools/gen-sample.js
node tools/gen-example-large.js
```

**URLs** (server must be running; it is *not* persistent across reboots):

- `http://localhost:8123` — full PWA: service worker, offline, installable
- `http://<your-lan-ip>:8123` — other devices on the LAN (find it with `hostname -I`)
- `http://<hostname>.local:8123` — same, survives DHCP IP changes (needs Avahi/mDNS)
- a hosted HTTPS deployment — the only way to get offline + install on a phone

⚠️ Over the **LAN URLs the app works but there is no service worker** — plain
HTTP is not a secure context, so no offline mode and no home-screen install.
Only `localhost` (or real HTTPS) gets those. See §11.

**In-app test panel:** الأدوات → لوحة المطوّر → «تشغيل الفحوصات» runs the same
engine suite inside the browser, plus an export/import round-trip check.

---

## 4. Architecture & file map

```
index.html  manifest.webmanifest  sw.js
sample-data.json  example-loft-large.json
css/app.css              — ALL styling: RTL logical properties, print CSS, high-contrast
js/engine/               — pure functions. No DOM, no IndexedDB. Unit-tested.
  pedigree.js            — traversal, cycle detection, pedigree grid, descendants
  coi.js                 — Wright path-method COI + breakdown, kinship cross-check, AVK
  relationship.js        — relationship naming + hypothetical pairing COI
  rings.js               — ring parsing/formatting/normalising
  fci.js                 — FCI eligibility rules
  velocity.js            — haversine distance, m/min velocity
  validate.js            — cycles, sex contradictions, ages, duplicate rings
js/db.js                 — IndexedDB layer, in-memory mirror, export/import, auto-backup
js/i18n.js               — ar/en dictionaries, numerals, Hijri/Gregorian dates, bidi helpers
js/ui.js                 — DOM kit: h(), modals, toasts, undo, bird picker, sex chips
js/app.js                — boot, hash router, shell, service-worker registration
js/views/                — birds, bird-form, bird-detail, pedigree, breeding, races,
                           health, stats, tools, cert
tests/                   — harness + engine suite + both dataset suites (node & in-app)
tools/gen-*.js           — deterministic dataset generators
README.md ENGINE.md HANDOFF.md
```

**Layering rule:** `engine/` never imports from `db.js`, `ui.js`, or `views/`.
Engine functions take a `getBird(id)` callback so they stay storage-agnostic
and testable. `db.js` keeps an in-memory `Map` of birds precisely because the
engine needs a *synchronous* `getBird`.

---

## 5. Data model

Stable UUIDs everywhere. **Never keyed on ring number** — birds carry
*multiple* rings and FCI eligibility depends on which one.

| Store | Notes |
|---|---|
| `birds` | `rings[]` `{country,union,year,serial,raw,type}` where type is `national\|FCI\|club\|private`; name, sex (`cock\|hen\|unknown`), hatchDate, colour, strain, eyeSign, status, `sireId`, `damId`, `external`, breeder, owner, acquiredFrom/Date, `notes[]` |
| `pairs` | sire, dam, season, nestBox, status, `rounds[] → eggs[]` (`laid → hatched → ringed → weaned`, each egg may link a `chickId`) |
| `raceResults` | birdId, raceName, date, `raceType` (`training\|club\|federation\|national\|one-loft\|international`), organisation, country, releasePoint/loftPoint (GPS), release/arrival times, distanceKm, velocity, position, `fanciersEntered`, `birdsEntered` |
| `healthEvents` | `vaccination\|treatment\|illness\|check`, per bird or whole loft |
| `lofts` | name, location, custom status list |
| `media` | photos (body/eye/wing) + scanned documents as Blobs, keyed to birds |
| `settings`, `backups` | prefs; automatic internal snapshots |

**Ownership (`external`) — read this before touching bird entry.** A bird you
never owned (an ancestor from a seller's pedigree) is still a full Bird record,
because relatedness maths depends on it. It is distinguished by
`external: true` **plus** `status: 'reference'`:

- The bird form asks ownership **up front** («في لوفتي» vs «خارجي — للنسب فقط»);
  choosing external hides the status field and stores `REFERENCE_STATUS`.
- External birds are excluded from loft statistics, filterable in the register
  («الملكية» filter), and shown with a chip.
- `REFERENCE_STATUS` is deliberately kept OUT of `DEFAULT_STATUSES` so it can't
  be picked for a real bird; `loftStatuses({includeReference:true})` appends it
  without rewriting an existing loft's stored list.
- Ownership is carried by "Save & add another", so back-filling a run of
  ancestors doesn't silently enrol them into the loft.

This matches the only mature convention found in the market (Pigeon Planner's
`show` flag — orthogonal to status, auto-set on parent entry, reversible).
**Known gap:** there is no way to *promote* an external bird into the loft when
you later buy it. Pigeon Planner has this; we don't.

**Club-mode hook (important):** every record carries `loftId` **and**
`updatedAt` from day one. Club features are *not* built, but the schema
already allows one admin over many member lofts, ring issuance tracking, and
club results propagating to member birds — without a migration.

**Sync:** does not exist and the app must stay correct with sync permanently
disabled. If ever added: **per-field last-write-wins** using `updatedAt`,
never whole-record overwrite.

---

## 6. The genetics engine

Full maths with hand-checkable worked examples lives in **`ENGINE.md`** — read
that before touching `coi.js`.

Summary: Wright's path formula with the `(1+F_A)` correction for inbred common
ancestors, on a depth-truncated pedigree (default 10 generations,
user-configurable), **cross-checked against an independent recursive-kinship
implementation** — the tests assert both agree to machine precision. The UI
shows a per-ancestor **contribution breakdown**, because a bare percentage
can't inform a breeding decision. AVK (ancestor loss) is shown alongside,
since COI can read low while the gene pool is already narrow.

### Acceptance fixtures — DO NOT WEAKEN

These are contractual from the original spec and are asserted exactly:

| Case | Required COI |
|---|---|
| full siblings mated | exactly `0.25` |
| parent × offspring | exactly `0.25` |
| grandparent × granddaughter | exactly `0.125` |
| unrelated | exactly `0` |
| inbred common ancestor (hand-verified, in sample data) | exactly `0.28125` |

Framing rules that must survive any rewrite: always label the figure
“**pedigree COI at N generations**”, always state that a shallow pedigree
understates it, and always state it is a pedigree statistic, **not a genetic
test**.

---

## 7. Feature status vs the spec

### Tier 1 — complete
1. ✅ Bird register — chunked rendering, Arabic + normalised-ring search, filters
2. ✅ Pedigree tree 3/4/5 generations, RTL-correct (verified geometrically)
3. ✅ COI + relationship finder, warnings surfaced **at pair creation**
4. ✅ Breeding season manager — pairs → nest boxes → rounds → eggs → hatch → ring → wean, chick auto-linked to parents. Also: pair provenance (acquired from/on), a settable pairing date, editable egg dates, clutch date inheritance, and **link an already-recorded bird to an egg** (validated; refuses cycles/sex contradictions) with unlink — for a pair bought with young already ringed.
5. ✅ Print-ready certificates, both languages, independent of UI language
6. ✅ Full JSON export/import with photos, round-trip tested

### Tier 2 — complete
7. ✅ Progeny analysis (descendant race records aggregated, best performers)
8. ✅ Race/training log with GPS velocity (m/min)
9. ✅ FCI eligibility checker (≥20 fanciers, ≥150 pigeons, FCI ring; names the failing reason)
10. ✅ Health & treatment log, per bird and whole loft
11. ✅ Loft statistics — COI distribution, breakdowns by strain/status/sex

### Tier 3 — partial (deliberately)
12. ⚠️ **Pedigree document scanner — hook only.** Settings field for a vision-server URL exists; no client implementation. Requires a server-side model that reads **Arabic handwriting**. Must stay strictly optional: the app must remain fully offline-capable without it.
13. ✅ Record sharing — export a bird + full ancestry as a file any Zajil user imports, no account either side
14. ❌ **Public loft page — not built.** Needs a publishing target; the share-a-bird file covers the buyer case meanwhile.

### Explicitly out of scope (spec)
Race weather routing, one-loft campaign management, finance modules, MCP
integrations. Competitors do these; they are not why anyone would switch.

---

## 8. Example datasets

Loadable from the empty bird list **or** الأدوات → تحميل بيانات تجريبية. Both
**merge** — they never delete the user's own records.

| File | Contents | Purpose |
|---|---|---|
| `sample-data.json` | 20 birds, 4 pairs, 12 results, 6 health · loft `loft-zarqa` | quick look; hand-verified 25% COI bird (**برق**) |
| `example-loft-large.json` | 38 birds, **6 generations**, 5 pairs, 17 results, 7 health · loft `loft-irbid-demo` | teaching/demo |

The large loft is built so every feature has something real to show:

- **فارس ٢٦** — a **100%-complete 5-generation pedigree** (63 slots, no gaps)
- **الشيخ**, **خيال** — COI 12.5% (double first cousins)
- **عاصف** — COI 25% (father × daughter), with an Arabic note explaining it
- **فارس ٢٦ × نجمة ٢٦** — full sibs → 32.2% hypothetical COI, triggers the severe warning
- **شهاب** — FCI ring with 2 qualifying results; training tosses correctly rejected
- one round of eggs **mid-incubation** + one chick **hatched but unringed**, so a learner can drive hatch → ring → wean themselves

Both datasets' pedigree depth, COI values, egg→chick links and stored
velocities are **asserted in the test suite**, so they cannot silently rot.
Regenerate with the `tools/gen-*.js` scripts — never hand-edit the JSON.

---

## 9. How this has been verified

- **33 node tests** — engine fixtures, cycle detection, AVK, relationships, ring parsing, FCI, velocity, validation, plus both datasets.
- **Same suite runs in-app** (الأدوات → لوحة المطوّر) + export/import round-trip check.
- **Browser suites** (`tests/e2e/`, committed, 148 assertions): RTL mirroring proven *geometrically* (the Arabic subject's bounding box is right of its ancestors; flips in English), Eastern-Arabic numerals apply everywhere **except** ring numbers, 5-gen certificate renders and prints to PDF, the dev panel passes in-browser, dialogs pin the page and restore scroll, and the service worker never wipes a sibling project's cache.
- **Offline test**: install service worker → set browser offline → reload → navigate → COI still computes. Passes with zero errors.
- **Engine audit against a real loft's records**: 0 structural errors.

---

## 10. Market position (researched, sourced)

A verified competitive study was run against ~20 pigeon products and several
general animal-pedigree suites. Claims were only kept if an agent fetched a
source supporting them, then survived an adversarial refutation pass (218 of
242 Benzing-related claims were refuted — the guard did real work, so treat
coverage as thinner than the raw count suggests). PigeonDB blocks crawlers, so
its entries come from structured metadata and forum reports, not its docs.

**Benzing is mostly hardware.** M1/M2/M3 clocks, SPEED antennas, chip rings,
ClubSystem — none of it replicable by a PWA. It *does* sell a pedigree product,
**Pedigree.Live** (~€51+/yr), but on the pedigree axis it is weaker than Zajil:
**3–4 generations** (more "promised for future releases"), no documented
inbreeding calculation, **cloud-only and account-gated** with no offline mode,
and no Arabic. Its sibling **MyPigeons.live** is race/club management (23
languages incl. Arabic) — a different category entirely.

**Conclusion: "Benzing replica" is the wrong north star.** Their pedigree app
is behind what already exists here; their moat is hardware. The useful framing
is *as trusted and professional-feeling as Benzing, in the category Benzing
serves badly.*

**Where Zajil already leads, per the sources:**

| Capability | Market reality |
|---|---|
| Computes COI at all | only 3 pigeon products (PigeonDB, Loft Manager Online, Brieftaubenscout) |
| **Per-ancestor COI breakdown** | **no product documents one** |
| AVK / ancestor loss | only ZooEasy and Brieftaubenscout — both desktop, paid, European |
| Arabic UI | only Benzing MyPigeons (race software, no pedigree genetics) and ELC Loft (Arabic-native, 4 generations, no COI) |
| Offline / no account | rare; the cloud products all require sign-in |

Arabic + 5 generations + real genetics + offline appears to be an unoccupied
corner. That is the thing to defend.

**Conventions worth copying (not yet built):**
- **Promote an external ancestor into the loft** when you buy it (Pigeon Planner).
- **Fostering / placed eggs** — an egg reared by a different pair, tracking
  biological vs rearing parents (AviRings, Hawkeye). Adjacent to the bought-eggs
  case and currently unmodelled.
- **Purchase provenance at bird level** — a "purchased" flag plus a breeder
  pick-list (PLO), a purchase/sale tab (Compustam). Zajil has this on pairs and
  loosely on birds (`acquiredFrom`/`acquiredDate`).
- **Import a seller's pedigree wholesale** rather than re-keying ancestors —
  either vendor-to-vendor (PLO), from a shared public pool (AviRings,
  pigeon.plus), or via OCR of the paper pedigree (PigeonDB, WingLoft,
  MyPigeon Records). Zajil's Tier-3 scanner is the same idea.

## 11. Known limitations & gotchas

1. **LAN = no offline/install.** Plain HTTP isn't a secure context. Needs real HTTPS (Cloudflare tunnel — `cloudflared` is installed; or free static hosting; or a trusted local cert).
2. **Static server isn't persistent** — dies on reboot/logout. No systemd unit yet.
3. **Service worker version must be bumped** (`sw.js` → `const VERSION`) whenever app files change, **and new files must be added to the `SHELL` precache list**, or offline users get stale/missing modules.
4. **Two reloads** are needed to see an update (first installs the new SW, second runs it).
5. `state.birds` mirrors IndexedDB in memory. Any new write path **must** update both (use the `saveBird` / `Pairs.save` / etc. helpers, never raw `idbPut`).
6. COI path enumeration is capped (`MAX_PATHS_PER_ANCESTOR`, `MAX_PAIRS_PER_ANCESTOR`). On pathological pedigrees the *breakdown* truncates and the UI says so; the *total* still comes from the exact kinship method.
7. Certificate rendering temporarily switches the i18n language and restores it — don't render certificates concurrently with other views.
8. `js/i18n.js` is large (473 lines) and holds every string. Adding a feature means adding keys there for **both** `ar` and `en`.

---

## 12. The five primitives (v1.7)

The medium backlog findings were symptoms of five missing shared primitives.
These are now installed, every caller routed through them, and **guard tests
fail the build if a future view goes around them** (`tests/guards.test.js`).

| Primitive | Where | Rule it enforces |
|---|---|---|
| **Local dates** | `js/dates.js` — `todayISO()`, `parseLocalDate()` | A calendar date is a label, not an instant. No UTC slicing anywhere else. |
| **Write boundary** | `db.js` `saveBird()` / `checkBird()`, `engine/validate.js` `classifySave()` | Validation happens at the write, not in each view. Strict by default: unconfirmed warnings block too. `{force:true}` is imports only. |
| **Change events** | `db.js` `emitChange`, `app.js` `wireAutoRefresh()` | Every write goes through db.js and emits. The router refreshes — deferred while a dialog is open, skipped on form routes, coalesced, scroll-preserving. |
| **Referential integrity** | `js/engine/integrity.js` `checkIntegrity()` | Dangling references are detectable. `deleteBird` cascades and snapshots everything for a complete undo. |
| **One record factory** | `db.js` `newBird()` | `external === (status === REFERENCE_STATUS)`, derived after the spread so no caller can contradict it. |

**Maintenance:** `CROSS_REFERENCES` in `integrity.js` must be extended whenever
a store or cross-record field is added. Nothing detects a reference it does not
know about. This is the one piece of upkeep the design does not eliminate.

See `docs/WRITEPATH-v1.7.md` for the full call-site map and
`docs/V1.7-NOTES.md` for known inconsistencies and where the structure will
fight a server-backed data layer.

## 13. Conventions a new session must not break

- **Never key records on ring number.** UUIDs only.
- **RTL is structural.** Use CSS **logical properties** (`inline-start/end`, `inline-size`, `border-inline-*`). The pedigree grid mirrors because grid tracks follow the document direction — **never** add `[dir="rtl"]` layout overrides to "fix" mirroring.
- **Ring numbers always render Western digits, LTR-isolated** — use `ringHTML()`. Eastern Arabic numerals are a user preference for everything else.
- **Dates: store ISO Gregorian, display per preference** (Gregorian / Hijri / both).
- **All user-facing text goes through `t()`** with `ar` + `en` entries. No hardcoded strings in views.
- **Engine stays pure** — no DOM, no IndexedDB, no i18n inside `js/engine/`. Return i18n *keys* + params, let the UI translate.
- **Every destructive action** confirms or offers undo (`confirmDialog` / `undoToast`).
- **Validation severity:** cycles, sex contradictions, parent-younger-than-child are **errors that block the save** and must name the offending link. Duplicate rings are **warnings** requiring confirmation.
- **Touch targets ≥44px**, one-handed phone layout, high-contrast mode must keep working.
- **No dependencies, no build step.** Anything that needs npm install or a bundler is a scope change to discuss first.
- **Never bypass a primitive.** All six rules below are enforced by
  `tests/guards.test.js`, which fails the build and names `file:line`:
  - **Dates** — `todayISO()` / `parseLocalDate()` from `js/dates.js`. Never
    `new Date().toISOString().slice(0,10)`: that is the UTC date, and east of
    Greenwich it names yesterday. Never `new Date('YYYY-MM-DD')` for display:
    that is UTC midnight, and west of Greenwich it renders a day early.
  - **Writes** — through `js/db.js` only. `idbPut`/`idbDelete`/`idbClear` are
    forbidden outside it; reads (`idbGet`/`idbGetAll`) are fine. Every write
    emits a change event and keeps the in-memory mirror in sync.
  - **Validation** — happens inside `saveBird()`, not in views. Views call
    `checkBird()` from db.js for pre-flight; `validateBird` must not be
    imported by a view.
  - **The save contract** — `saveBird` is strict by default: hard errors AND
    unconfirmed warnings both reject the write, throwing `ValidationError`
    with i18n keys. `{allowWarnings: true}` means *the user has confirmed
    them*; `{force: true}` skips validation entirely and belongs only to
    `importAll` and the dataset loaders.
  - **Bird records** — only ever from `newBird()`, which derives
    `external === (status === REFERENCE_STATUS)` after the spread so a caller
    cannot contradict it.
  - **Referential integrity** — `checkIntegrity()` in `js/engine/integrity.js`
    must report zero dangling references. Extend its `CROSS_REFERENCES` table
    whenever a store or cross-record field is added; nothing detects a
    reference it does not know about.
- **Every browser suite is either run or printed as skipped.** `run_all.py`
  derives its list from the difference between what exists on disk and what
  ran, and every exclusion carries its reason and the flag that lifts it. A
  suite must never be silently absent from the output.
- **`[hidden]` must always win** — `css/app.css` has a global `[hidden]{display:none!important}` because class-based `display` rules once resurrected hidden elements (this was a real bug: the parent-picker dropdown could never close).

---

## 14. Open items / awaiting the user's decision

### Open decisions
- **Local-network testing without HTTPS** has no service worker, so no offline
  or install. A hosted HTTPS deployment (GitHub Pages / Cloudflare Pages) is
  the way to exercise the offline promise on a phone in a loft.
- Whether to run the dev server as a persistent service on the workstation.

### Roadmap
1. **Design & typography pass** — the next planned piece of work. See §15.
2. **Work the [BACKLOG.md](BACKLOG.md)** — highest value first: the FCI column
   shows ✓ for birds with no FCI ring; Statistics freezes for seconds on a few
   hundred birds; the same bird can be linked as the chick of two eggs.
3. **Promote-to-loft** for external birds, and **fostering / placed eggs** — the
   two conventions the market research says we're missing (§10).
4. Tier 3 #14 **public loft page** — small, serves the “shareable to buyers” pillar.
5. Tier 3 #12 **scanner** — biggest effort; needs an Arabic-handwriting vision
   model server. Must stay strictly optional.
6. Club mode — the business case (a federation is the paying customer). Schema
   is ready; UI is not.

*(Switching on GitHub Pages and committing the browser suites were roadmap
items through v1.6; both are done — see the status snapshot.)*

## 15. Design & typography — the next piece of work

Not started. The brief: make it feel as professional as a paid product, and
unmistakably Arabic-first rather than a translated Latin UI.

Research partly completed before the run hit a limit; re-run it properly before
committing to choices. What surfaced, to be re-verified:

- **Candidate Arabic UI typefaces:** IBM Plex Sans Arabic, Cairo, Tajawal,
  Almarai, Noto Sans Arabic, and commercial options (29LT Bukra/Azel, GE SS,
  Dubai). Today the app ships **no webfont at all** — `css/app.css` uses a
  system stack (`system-ui … "Noto Sans Arabic", "Noto Naskh Arabic", Tahoma`),
  which is why it can look generic.
- **Reference material:** Apple's *Design for Arabic* (WWDC22), the W3C Arabic
  Layout Requirements (alreq), the UAE Design System, and Saudi DGA's design
  system.
- **Known Arabic-specific issues to address:** Arabic needs more line-height
  and usually a slightly larger optical size than Latin at the same nominal
  px; Latin/Arabic pairing must be deliberate (ring numbers are already
  monospace Western and LTR-isolated — keep that); numerals policy is already
  handled (Western/Eastern preference, rings always Western).
- **Constraint:** any webfont must be self-hosted, because the app must install
  and run fully offline — no Google Fonts CDN at runtime, and the files must be
  added to the `sw.js` SHELL precache list.

---

## 16. Change log

- **v1.0** — initial build: engine + tests first, then Tier 1, Tier 2, docs, sample data. Verified offline + RTL geometry.
- **v1.1** — data audit pass (0 structural errors). Fixed: `[hidden]` override bug (parent-picker dropdown could never close; same latent bug in the health dialog). Added readable **sex chips** (♂ ذكر / ♀ أنثى) in lists, pickers, detail, plus tree tinting and a legend. Added **add-sibling** flow (siblings derive from shared parents; creates placeholder parents when none exist). Added in-app example-data loader.
- **v1.2** — 8 code-verified UX fixes: inline creation of missing ancestors from the sire/dam pickers; **rings-first form** with a pre-seeded row; **save-&-add-another** carrying strain/colour/status/breeder/owner + ring prefix; **editable egg dates** that propagate a corrected hatch date to the chick's record; one-tap hatch date from the ring year; Enter no longer submits a half-entered bird; Latin keyboard hints on ring inputs; datalist autocomplete for strain/colour/breeder; save uses history-*replace* so the phone back gesture returns to the list.
- **v1.3** — added the 38-bird / 6-generation teaching loft (`example-loft-large.json`) + 5 asserting tests; both examples offered in the empty state and Tools; precached for offline.
- **v1.4** — pre-publish audit before going public (18 findings): removed a real name from the shipped sample data and real breeders' names from demo pedigrees, stripped private notes/paths from this file, moved commits to a noreply address, added the LICENSE, and fixed two service-worker bugs that only bite on GitHub Pages (per-origin cache deletion would have wiped sibling projects' offline caches; `addAll` read through the HTTP cache and could bake a stale deploy into a new version cache). Repo pushed public.
- **v1.5** — the ownership model (§5), register ownership filter, link-an-existing-bird to an egg, pair provenance and backdating. Plus a UI sweep across 11 routes × 3 viewports that found the real cause of the reported “page jumps to the top” bug: **the page scrolled behind open dialogs**. Dialogs now pin the page and restore position exactly; tall dialogs scroll themselves; Tab is trapped; race tabs remember scroll position.
- **v1.7** — invariant hardening. Five shared primitives installed and every
  caller routed through them: local dates (`js/dates.js`), validation at the
  write boundary (`saveBird`/`classifySave`), change events driving a deferred
  scroll-preserving refresh, referential integrity (`checkIntegrity` + a
  cascading delete with a complete undo snapshot), and one record factory.
  Structural guard tests make it permanent — one of them immediately caught two
  new modules missing from the service-worker precache, which would have broken
  offline. `importAll` made atomic: it decodes and validates the whole payload,
  and snapshots to `backups`, before touching anything — previously one
  malformed media entry destroyed the loft. Eleven backlog findings closed as
  side effects rather than patched individually. Browser suites moved out of
  scratch into `tests/e2e/` with a runner and README. Tests 33 → 75; browser
  assertions 148 across 15 suites. Merged as `eedb38d` and deployed.
- **v1.6** — deep bug hunt (39 confirmed, 32 refuted). Fixed the four data-loss defects: the parent picker silently detaching a link on an abandoned search; snapshot restore deleting every photo; a foreign replace-import bricking the loft; and object URLs pinning every photo Blob for the life of the tab. Also fixed ownership being dropped by “Save & add another”. The remaining 33 findings are in [BACKLOG.md](BACKLOG.md).

---

## 17. Seed prompt for a new chat

> I'm continuing work on **Zajil** — an Arabic-first, offline-first
> PWA for racing-pigeon pedigree and loft management, in Jordan/Gulf.
>
> **Read `HANDOFF.md` first** — it has the full state, architecture,
> conventions, and open items. `ENGINE.md` has the genetics maths;
> `README.md` the user-facing overview.
>
> Key context: vanilla ES modules + IndexedDB, no build step, no dependencies.
> 33 node tests pass (`node tests/run.js`) and must stay passing — the four
> COI fixtures are contractual. RTL is structural via CSS logical properties.
> Serve with `python3 -m http.server 8123` from the repo root.
>
> Current state: **v1.7.0**, `main` at `eedb38d`, live at
> https://nahdaeverything-web.github.io/Zajildb/ (public repo,
> all-rights-reserved licence). 75 node tests and 148 browser assertions pass.
> Known issues are catalogued in `BACKLOG.md` — all verified, none blocking.
> **Read §13 (Conventions) before writing code**: v1.7 installed five shared
> primitives and guard tests that fail the build if you go around them.
> The next planned piece of work is the **design & typography pass** (§15).
>
> What I want to work on next: **<describe your task here>**
