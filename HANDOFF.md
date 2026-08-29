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
| App version (service worker) | `zajil-v1.9.0` |
| Branch | `sync/v1.9` — **not merged**; merge and deploy are a separate explicit go |
| `main` at | `4185578` — v1.8.0, tagged · **`main` still serves v1.8.1** |
| **Live** | **https://nahdaeverything-web.github.io/Zajildb/** — serving `zajil-v1.8.1` until v1.9 is deployed |
| Node tests | **138 passing, 0 failing** — `node tests/run.js` |
| Browser assertions | **508 passing, 0 failing** across **27 suites** — `python3 tests/e2e/run_all.py` |
| Opt-in suites | 4, never silently absent — each printed as `[skip]` with its reason and the flag that lifts it: `live_deployment.py` (`--live`), `auth_live.py` (`--live-auth`, 13 passing), `push_live.py` (`--live-push`, 24 passing), `pull_live.py` (`--live-pull`, 12 passing). The three sync suites take every credential from the environment and commit none. |
| Browser suites | committed under `tests/e2e/` with a runner and README, plus 6 diagnostic scripts |
| Source | `js/` 6,688 lines · the db layer is **2,312** across a facade and five modules (§15.1) · `css/app.css` 399 · `sw.js` 107 |
| Tests | node 1,801 lines · browser 4,172 lines |
| Server | Supabase, schema in [docs/SYNC-DESIGN.md](docs/SYNC-DESIGN.md) §1 — **that block is the complete current schema**, guard-asserted, and is what a fresh project is created from |
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

**Browser-test gotchas** (also in `tests/e2e/README.md`):
`wait_until='networkidle'` **hangs** — the service worker holds the connection
open; use `'load'` plus an explicit wait. And to seed a database without
booting the app, navigate to a same-origin URL that isn't the app (e.g.
`BASE + '__seed__'`, which 404s) — loading `BASE` runs `initDB()` first, which
creates a current-version database and makes opening an older version block
forever.

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

## 13. Sync shape (v1.8) — local only, no server

v1.8 captured the things a future sync layer **cannot reconstruct after the
fact**: who wrote, what changed, that a delete happened, and ownership as
history. Everything is local; there is no network code anywhere in the app.

### Two new stores (schema v2)

| Store | Key | Holds |
|---|---|---|
| `oplog` | `opId` (index on `seq`) | `{ opId, seq, deviceId, actorId, at, origin, store, op, recordId, changed, record }` — what THIS DEVICE did |
| `tombstones` | `store:recordId` | `{ id, store, recordId, at, deviceId, seq }` — that a deletion happened |

The upgrade is additive: `mk()` is idempotent, so a v1 database gains the two
stores and **no existing record changes** (asserted against a real v1.7 fixture
in `tests/e2e/schema_upgrade.py`).

### Device identity
`settings` gains `deviceId` (uuid, generated once, **never** regenerated),
`deviceName`, and `opSeq`. Settings are per-device preference and are
**out of sync scope** — no ops, no tombstones. So is the `backups` store.

### THREE CONCEPTS THAT ARE EASY TO CONFUSE

| | Answers |
|---|---|
| `record.deviceId` | the **last** device to write this record. `stamp()` sets it on every write, so it changes as a record moves between devices. |
| `record.provenance[0]` | the `created` event — so **that** is the creating device. Never read `record.deviceId` for that. |
| the op log | a third thing entirely: what **this device did**, not what happened to a record. |

**Absence of `provenance` is legal permanently.** Pre-v1.8 records have none
and nothing backfills it: fabricating a `created` event would assert a history
that did not happen. `stamp()` must never invent one.

### Conflict order comes from `seq`, NOT `updatedAt`
`restoreBird` deliberately reinstates a record's original timestamps — an undo
restores what was there, it is not a new edit. So after any delete+undo the
record carries an old `updatedAt`, and any `updatedAt`-keyed resolution would
let a stale remote copy win. `seq` is a per-device monotonic counter that only
increases.

**`nextSeq()` claims its number synchronously, before any `await`** — otherwise
two writes started in the same tick receive the same seq and conflict ordering
is silently corrupted. It persists the current *maximum*, not the captured
value, so out-of-order completion cannot re-issue a number after a reload.
Proven with 20 writes fired via `Promise.all`.

### The op-log ordering trap
`idbGetAll('oplog')` returns records in **key order**, and the key is a random
uuid — so a raw read is shuffled and any "last N" gets arbitrary ops. Always
read through `listOps()` / `getOpsSinceSeq()`. A guard test forbids raw
`idbGetAll('oplog')` and `idbGetAll('tombstones')` outside `db.js`.

### The resurrection fix (the one user-visible change)
Merge-importing an older export **no longer resurrects deleted birds** — they
are counted as `skipped`. Tombstones from both sides are considered and the
union is persisted, so protection survives a round trip. A genuinely *newer*
record still wins. Replace mode ignores tombstones: it is an explicit restore
of a point in time, and it **resets the sync baseline** (a v1.9 concern).

Exports carry `tombstones` but **never** the op log — that is device-local
history, asserted *absent* rather than empty.

## 14. Conventions a new session must not break

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
- **Sync-shape rules (v1.8), all guard-enforced:**
  - **Never call `logOp` outside `js/db.js`.** The op log must be a faithful
    record of the write path; a view logging directly would record something
    that never went through `saveBird`.
  - **Never read `oplog` or `tombstones` raw.** `idbGetAll` returns key order
    and the op-log key is a random uuid, so raw reads are shuffled. Use
    `listOps()` / `getOpsSinceSeq()`.
  - **`stamp()` must never invent `provenance`.** Pre-v1.8 records have none
    and a fabricated `created` event would assert a history that did not happen.
  - **A deletion writes an op AND a tombstone sharing one `seq`** — they are one
    logical operation. A restore deletes the tombstone.
  - **`settings` and `backups` are out of sync scope** — no ops, no tombstones.
- **Sync rules (v1.9), all guard-enforced — see §15:**
  - **Import from `js/db.js`, never from `js/db/`.** The facade is the API and
    its export set is pinned by a test.
  - **`origin: 'sync'` must never reach `logOp`.** That is echo prevention, and
    it is the invariant the pull path rests on. Every `logOp` call must name its
    origin as a *string literal* so the scan can see it.
  - **A sync-apply writes the record verbatim** — never `stamp()` it. Applying a
    remote record is not authorship.
  - **`updated_at` on a server row is the OP's `at`, never `record.updatedAt`**,
    which `restoreBird` deliberately moves backwards.
  - **A `200` alone never acks.** Count the returned rows; RLS blocks present as
    `200` with the row absent.
  - **Only a `200` short count names a poison record.** A `4xx` is
    request-level and must never be blamed on a record.
  - **Normalise server timestamps on arrival** (`toISO()`). Postgres writes
    `+00:00` where `nowISO()` writes `Z`, and every comparison here is
    lexicographic.
  - **The secret key never reaches the client**, and the publishable key travels
    only in the `apikey` header — never as `Authorization: Bearer`.
  - **Never write `lastSyncError` directly** — `recordSyncError()` preserves the
    `since` that decides when a failure is allowed to surface.
- **`docs/WRITEPATH-*.md` is GENERATED** — `node tools/gen-writepath.js 1.9`.
  Never hand-edit it; the v1.7 copy's line numbers drifted from its own grep
  output within days.
- **Every browser suite is either run or printed as skipped.** `run_all.py`
  derives its list from the difference between what exists on disk and what
  ran, and every exclusion carries its reason and the flag that lifts it. A
  suite must never be silently absent from the output.
- **`[hidden]` must always win** — `css/app.css` has a global `[hidden]{display:none!important}` because class-based `display` rules once resurrected hidden elements (this was a real bug: the parent-picker dropdown could never close).

---

## 15. Sync & accounts (v1.9) — the server half

v1.8 built the *shape* of sync with no network. v1.9 connects it to Supabase.
The design contract is [docs/SYNC-DESIGN.md](docs/SYNC-DESIGN.md), approved
before any code and amended — in commits — whenever implementation proved it
wrong. Read it before changing anything here; the amendments are where the
sharp edges are recorded.

### 15.1 The db.js split, and the facade rule

`js/db.js` was 866 lines and a sync layer was about to land on it. It is now a
**facade**: comment and re-export, nothing else.

| Module | Role |
|---|---|
| `js/db/storage.js` | IndexedDB access, the in-memory mirror, change events |
| `js/db/oplog.js` | the op log and tombstones |
| `js/db/records.js` | the write boundary: birds, generic stores, media |
| `js/db/io.js` | export, import, sharing, backups |
| `js/db/sync.js` | accounts, push, pull, conflicts, status |

> **No view imports anything under `js/db/`.** They import `js/db.js` and that
> is the whole contract. A guard pins the exact export set — a dropped
> re-export is otherwise invisible until a view calls it at runtime — and a
> second guard asserts the facade contains no logic.

The dependency direction `storage <- oplog <- records <- io`, with `sync` above
them, is guard-enforced. A cycle would hand one module a partly initialised
namespace and which one would depend on import order.

The split was done mechanically, block by block: of 59 top-level blocks, 55
moved byte-identical and 4 differ only by a prepended `export`. Zero behaviour
change, and the browser suite passed unchanged, suite for suite.

### 15.2 Push — replaying the op log

The op log is already an ordered, complete record of what this device did.
Push replays it. Nothing invents state.

- **Batches of 200 ops**, collapsed to one upsert per `(store, record_id)` —
  the last op wins, so three edits to one bird are one round trip.
- **`Prefer: resolution=merge-duplicates,return=representation`**.
- **The ack condition:** a write blocked by row-level security returns `200`
  with the row simply ABSENT. So a `200` alone never advances the cursor —
  count the rows that came back, and ack only on a full count.
- **Compaction:** an op with `seq <= lastAckedSeq` is prunable, keeping the
  most recent 500 as a forensic tail. Tombstones are never pruned. A
  never-synced device prunes nothing.

### 15.3 THE TIMESTAMP RULE (§2a) — the one to understand first

> **`updated_at` on the server row is the OP's `at` — when the operation
> happened. It is NEVER `record.updatedAt`.**

`restoreBird` deliberately reinstates a record's *original* timestamps: an undo
restores what was there, it is not a new edit. So `record.updatedAt` can move
**backwards**, and a sync layer that trusted it diverges permanently:

```
  10:00  A deletes a bird       → tombstone at 10:00, pushed
  10:01  B pulls the delete     → B applies it, writes its own tombstone
  10:05  A undoes the delete    → restoreBird reinstates updatedAt = 09:00
         push maps updated_at = 09:00   ← WRONG
  10:06  B pulls the restore    → 09:00 < B's 10:00 tombstone → B SKIPS it
                                → A has the bird, B does not, forever
```

Operation time cannot move backwards, so it can be trusted. Every timestamp
decision in sync reads operation time.

### 15.4 Pull — and the invariant the whole thing rests on

A cursor on `server_seq`, and nothing else. The trigger reassigns `server_seq`
on UPDATE as well as INSERT, so an edited row moves *above* the cursor and is
re-delivered.

> **`origin: 'sync'` LOGS NO OP.** This is echo prevention, and it is one
> careless line from being broken: a pulled change that logged an op would be
> pushed straight back and two devices would trade the same record forever.

> **A sync-apply writes the incoming record VERBATIM** — `updatedAt`,
> `deviceId`, `provenance` and all. `stamp()` would make a remote record
> locally-authored with a fresh timestamp, so it would beat the very version it
> came from in every later comparison and claim this device as its last writer.
> It follows `restoreBird`'s precedent, not `saveBird`'s: applying a remote
> record is not authorship.

**A pulled delete does not cascade.** `deleteBird` cascades so a *local* delete
leaves the database consistent; a pulled delete removes exactly the record its
row names. The origin device already ran its cascade and every record it
touched arrives as its own row. Re-cascading would delete records linked on
*this* device but not the origin's — data loss dressed as consistency.
Integrity is transiently dangling between the unlink rows and the delete row,
and clean once the page has applied; the suite asserts exactly that.

**The corollary:** a pulled record that BEATS a local tombstone must delete
that tombstone, or the record gets re-suppressed by the next merge and the
device flips between states.

### 15.5 Conflicts — and where they are actually decided

Per-record last-write-wins on operation time, tie-broken on `deviceId`
lexicographically. The tie-break is arbitrary but **stable**, which is the only
property that matters: two devices must reach the same verdict without talking
to each other. `tests/conflict.test.js` asserts that symmetry directly.

> **THE SERVER IS THE ONLY PLACE LWW CAN BE AUTHORITATIVE.** A client push is a
> blind upsert — it overwrites whatever is there — so a device offline for
> months replaces fresher data simply by pushing, and no client-side care can
> prevent it because the client cannot see what it is about to overwrite. The
> `server_seq` trigger carries the comparison; `server_seq` advances either
> way, so the loser re-pulls the winner.

**Cycle order** follows from that:

| Cycle | Order | Why |
|---|---|---|
| first login (`lastSyncAt` unset) | synthetic ops → **push** → pull | local records must reach the server before remote rows arrive |
| every later cycle | **pull** → resolve → push | LWW can only decide if the row meets the local op *before* either is overwritten |

Pulling first is safe *because* of echo prevention. A local op beaten by an
incoming row is marked `superseded` — kept in the log, because §4 promises the
losing version remains recoverable, but never pushed.

**First login** enqueues every local record as a synthetic op whose `at` is the
record's own `updatedAt`, never `now()`. A laptop last used months ago would
otherwise beat fresher data simply by logging in.

**Two devices that never synced generate different ids for the same physical
bird**, so the first sync leaves two records — both valid, both surviving. That
is not automatically solvable and guessing would be worse: a ring is the
natural business key but deliberately is **not** identity. So they are counted
and the fancier is told once, in Arabic, pointing at the duplicate finder that
already exists in الأدوات.

### 15.6 What a failure means — the 4xx table

Row-level security does **not** reject with a status; a blocked write returns
`200` with the row absent. That is the only signal that identifies a poison
*record*.

| Outcome | Meaning | Action |
|---|---|---|
| `200`, every row echoed | accepted | ack, advance, prune |
| `200`, rows missing | RLS blocked **those** records | retry ×3, then bisect |
| `4xx` | request-level failure | loud, **not acked**, nothing blamed on a record |
| `401` unrecoverable | session gone | not acked, nothing blamed |
| `5xx` / offline | transport | not acked, back off |

**Poison bisection**: after three identical short counts, split the batch and
retry each half until a single row is isolated. Record it in `syncAnomalies`,
ack past it, and continue — an anomaly is loud but never a roadblock, because a
correct-looking queue that never drains is worse than a named failure.

### 15.7 Auth

Invite-only: accounts are created through the admin API and public signups stay
disabled. The publishable key travels in the `apikey` header and **never** as a
`Bearer` value; the secret key appears nowhere in the client, ever.

> **Network failure is not an auth verdict.** `fetch` rejecting means no
> signal; a 5xx means the server is unwell. Neither says anything about the
> session, so neither ever clears a token. Only a 4xx does.

On a refresh rejection the instance **re-reads the stored tokens once** before
concluding the session is dead: the installed app and a browser tab share one
IndexedDB, so both can refresh with the same token and one loses. If the stored
token is no longer the one we sent, the other instance already won — adopt its
session rather than signing out both.

Refresh is **reactive**: use the token, refresh once on a 401. No stored
expiry, no timer to drift.

### 15.8 Client configuration (§5a)

`js/sync-config.js` ships **empty**. A build points itself somewhere by setting
`globalThis.ZAJIL_SYNC_CONFIG = { url, publishableKey }` before the app loads.
An unconfigured build is a fully working Zajil with sync inert.

The publishable key is safe to ship — that is what it is for — but writing a
live project URL into a public repository is a release decision, not something
that arrives in a feature commit. Two guards hold the line: the constants must
stay empty, and no `sb_secret_` / `service_role` string may appear anywhere in
`js/`.

### 15.9 Settings keys added

All in `settings`, which is out of sync scope — these are per-device by nature.

| Key | Purpose |
|---|---|
| `authAccessToken` | current access token |
| `authRefreshToken` | replaced on every refresh; the old one is spent |
| `authUserId` | the signed-in user; becomes `actorId` on new ops |
| `authEmail` | for the sync-status display |
| `syncCursor` | highest `server_seq` applied |
| `lastAckedSeq` | highest local op `seq` the server has verifiably accepted |
| `lastSyncAt` | last successful cycle; also "has this device ever synced" |
| `lastSyncError` | `{ key, status, at, since }` — `since` measures the silence window |
| `syncEnabled` | the user can turn sync off and keep working |
| `syncAnomalies` | capped at 100, newest kept — a surface, not a log |
| `syncDuplicateNotice` | the one-time post-first-sync count |

> **Tokens must never leave the device.** `exportAll` carries no `settings` at
> all, so nothing leaks today — the test is a **regression guard**, and it signs
> in first so real tokens are genuinely present, then walks the entire export
> payload and every backup snapshot for any key beginning `auth`.

### 15.10 Status UI — and what is allowed to interrupt

Sync is infrastructure and should be almost invisible when it works, so the
header row is **empty** in the healthy case rather than showing a reassuring
tick nobody needs.

> **Offline is not an error and never becomes one, however long it lasts.** It
> gets a calm tone and no "details" link, because there is nothing to fix. A
> red bar every time a fancier walks into a loft would train them to ignore
> warnings.

Only two things interrupt: a session that needs a password (immediately —
nothing else will fix it) and a rejection that needs us (once it has outlived
the ~2 minute silent window). Each interrupts once, not per cycle. Everything
else lives in the المزامنة card in الأدوات, where the last error is shown in
full with its status code.

Backoff is 2/4/8/16/32/60 s with ±25 % jitter, capped so a long outage
reconnects within a minute of the network returning. Three reconnect signals:
the `online` event, a slow heartbeat, and `visibilitychange` — a phone coming
out of a pocket being the likeliest moment a fancier walked back into signal.

### 15.11 Guards added this release

Every one was proven to fire by reintroducing its violation.

| Guard | Stops |
|---|---|
| the facade exports exactly the pinned set | a dropped re-export, invisible until a view calls it |
| `js/db.js` is re-exports only | logic drifting outside the boundary the guards police |
| the db modules form a DAG | a cycle handing out a half-initialised namespace |
| every `logOp` call names its origin as a **string literal** | a computed origin making the next guard blind |
| `origin: 'sync'` never reaches `logOp` | the echo: two devices trading one record forever |
| the sync-apply path never logs or stamps | a remote record re-authored as local |
| `js/db/sync.js` never writes a record itself | a silent write the mirror and views never see |
| no secret or service-role key in `js/` | a key that bypasses RLS reaching a browser |
| `js/sync-config.js` ships empty | a live project URL arriving in a feature commit |
| only one place writes `lastSyncError` | the silence window restarting on every cycle |
| §1's migration script is the complete schema | a fresh project created from a stale script |

The three v1.7 write guards were **tightened**, not merely widened: they now
exempt `js/db/` and **not** the facade. After the split `js/db.js` provably
contains zero writes, so it needs no write privilege — privileges should track
proof. Each is proven twice, from a view and from the facade.

### 15.12 Lessons register — what this release learned the hard way

Each of these cost a real debugging session. They are here so the next one
does not.

1. **Dashboard verification proves objects EXIST, never that a write
   SUCCEEDS.** All four schema checks were green while the table accepted
   nothing at all: the trigger called `nextval()` as the caller and
   `authenticated` had no usage on the sequence, so every insert failed `403`.
   The SQL Editor runs as `postgres` and never exercises the `authenticated`
   path. **The end-to-end client test is the only proof.**

2. **Only a `200` short count names a poison record.** RLS does not reject with
   a status. Folding a `4xx` into the poison path meant three retries, then
   bisection to single rows, then every record marked poison, acked past and
   **pruned** — the whole queue discarded because a grant was missing.

3. **Cross-format timestamps compare wrong, and wrongly in both directions.**
   Postgres writes `+00:00`, `nowISO()` writes `.000Z`; the same instant, and
   `+` (0x2B) sorts before `.` (0x2E). Each device then concluded its own copy
   was later, so two devices reached **opposite** verdicts and never converged.
   Normalise at the boundary — `toISO()` — and compare one spelling.

4. **An assertion that permits zero is not an assertion.** `<= 1` interruptions
   passes just as happily when none fire. Tightening it to "DOES interrupt" AND
   "exactly once" immediately exposed that push and pull each wrote
   `lastSyncError` directly, clobbering the window that decides when a failure
   surfaces. The same shape as the storage spike's vacuous pass.

5. **A prover that pipes output can lie.** `timeout` killing a pipeline
   discards whatever `grep`/`head`/`tail` were buffering, so a hung suite reads
   as "no failure line" — three wrong MISSED verdicts before it was noticed.
   Mutation runs write **unbuffered, to files**, never through a pipe.

6. **A test that dies is worse than a test that fails.** `pushOnce` returns
   different shapes per outcome, so indexing a key the failing path never set
   raised a `KeyError` and aborted the suite on the first failure, hiding five
   other proofs. Page results now read missing keys as `None`. Likewise a
   positional `.card[1]` selector broke the moment a card was added above it,
   and the suite died on a null instead of reporting.

7. **Two devices is the only honest convergence test.** `convergence.py` runs
   separate browser *contexts* — separate IndexedDB, separate identities —
   against one stateful server. Nothing less would have caught the ordering and
   supersession bugs.

---

## 16. Open items / awaiting the user's decision

### Open decisions
- **Local-network testing without HTTPS** has no service worker, so no offline
  or install. A hosted HTTPS deployment (GitHub Pages / Cloudflare Pages) is
  the way to exercise the offline promise on a phone in a loft.
- Whether to run the dev server as a persistent service on the workstation.

### Planned for v1.9 — split `js/db.js`
`db.js` is **866 lines** and now holds the IndexedDB layer, the in-memory
mirror, validation, the op log, tombstones, provenance, export/import and
backups. That is a structural signal, not a defect.

The reason to decide it deliberately: **every guard test keys on "outside
`js/db.js`"** — the `idbPut`/`idbDelete` write guard, the `logOp` guard, and the
raw-read guard. Splitting the file means updating those allow-lists on purpose
rather than discovering them broken. A likely split is `db/storage.js`
(IndexedDB + mirror), `db/sync.js` (op log, tombstones, seq) and `db/io.js`
(export/import/backups), with `db.js` re-exporting so callers do not move.

### Roadmap
1. **Design & typography pass** — the next planned piece of work. See §16.
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

## 17. Design & typography — the next piece of work

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

## 18. Change log

- **v1.0** — initial build: engine + tests first, then Tier 1, Tier 2, docs, sample data. Verified offline + RTL geometry.
- **v1.1** — data audit pass (0 structural errors). Fixed: `[hidden]` override bug (parent-picker dropdown could never close; same latent bug in the health dialog). Added readable **sex chips** (♂ ذكر / ♀ أنثى) in lists, pickers, detail, plus tree tinting and a legend. Added **add-sibling** flow (siblings derive from shared parents; creates placeholder parents when none exist). Added in-app example-data loader.
- **v1.2** — 8 code-verified UX fixes: inline creation of missing ancestors from the sire/dam pickers; **rings-first form** with a pre-seeded row; **save-&-add-another** carrying strain/colour/status/breeder/owner + ring prefix; **editable egg dates** that propagate a corrected hatch date to the chick's record; one-tap hatch date from the ring year; Enter no longer submits a half-entered bird; Latin keyboard hints on ring inputs; datalist autocomplete for strain/colour/breeder; save uses history-*replace* so the phone back gesture returns to the list.
- **v1.3** — added the 38-bird / 6-generation teaching loft (`example-loft-large.json`) + 5 asserting tests; both examples offered in the empty state and Tools; precached for offline.
- **v1.4** — pre-publish audit before going public (18 findings): removed a real name from the shipped sample data and real breeders' names from demo pedigrees, stripped private notes/paths from this file, moved commits to a noreply address, added the LICENSE, and fixed two service-worker bugs that only bite on GitHub Pages (per-origin cache deletion would have wiped sibling projects' offline caches; `addAll` read through the HTTP cache and could bake a stale deploy into a new version cache). Repo pushed public.
- **v1.5** — the ownership model (§5), register ownership filter, link-an-existing-bird to an egg, pair provenance and backdating. Plus a UI sweep across 11 routes × 3 viewports that found the real cause of the reported “page jumps to the top” bug: **the page scrolled behind open dialogs**. Dialogs now pin the page and restore position exactly; tall dialogs scroll themselves; Tab is trapped; race tabs remember scroll position.
- **v1.9** — sync and accounts against Supabase. `js/db.js` split into a facade
  over five modules (§15.1), mechanically and with zero behaviour change. Auth
  (invite-only, reactive refresh, the multi-instance re-read rule), push (op
  replay, affected-row-verified ack, poison bisection, op-log compaction), pull
  (cursor on `server_seq`, verbatim apply, echo prevention), conflicts
  (last-write-wins enforced **on the server**, because a client push is a blind
  upsert), first-login synthetic ops carrying each record's own `updatedAt`, the
  post-first-sync duplicate notice, and the status UI where offline is never
  styled as an error. Eleven guards added, each proven to fire. Six design
  amendments, each committed before the code it justified — the migration was
  incomplete twice, and both gaps were found by running against the real
  project rather than by reading. See §15.12 for the lessons register.
- **v1.8** — sync shape, all local: no server, no network code. Schema v2 adds
  `oplog` and `tombstones` (additive; a v1.7 database upgrades with zero data
  change, asserted against a real fixture). Device identity (`deviceId`,
  generated once). Every write in `db.js` logs an op carrying which fields
  changed and why (`user`/`import`/`restore`); every hard delete writes a
  tombstone sharing the op's `seq`; a restore clears it. Conflict order comes
  from `seq`, not `updatedAt`, because `restoreBird` reinstates old timestamps.
  `newBird()` seeds `provenance`; absence stays legal permanently for pre-v1.8
  records. `checkIntegrity` gains a live-record-with-tombstone check. Three new
  source guards. `docs/WRITEPATH` is now generated. One user-visible change:
  merge-importing an older export no longer resurrects deleted birds. Tests
  75 → 96 node, 183 → 276 browser. Merged as `4185578`, tagged `v1.8.0`.
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

## 19. Seed prompt for a new chat

> I'm continuing work on **Zajil** — an Arabic-first, offline-first
> PWA for racing-pigeon pedigree and loft management, in Jordan/Gulf.
>
> **Read `HANDOFF.md` first** — it has the full state, architecture,
> conventions, and open items. `ENGINE.md` has the genetics maths;
> `README.md` the user-facing overview.
>
> Key context: vanilla ES modules + IndexedDB, no build step, no dependencies.
> 138 node tests pass (`node tests/run.js`) and must stay passing — the four
> COI fixtures are contractual. RTL is structural via CSS logical properties.
> Serve with `python3 -m http.server 8123` from the repo root.
>
> Current state: **v1.9.0 on branch `sync/v1.9`, not yet merged**. `main` is at
> v1.8.1, live at https://nahdaeverything-web.github.io/Zajildb/ (public repo,
> all-rights-reserved licence). 138 node tests and 508 browser assertions pass,
> plus three opt-in live suites against a real Supabase project.
> Known issues are catalogued in `BACKLOG.md` — all verified, none blocking.
> **Read §14 (Conventions) before writing code**: v1.7 installed five shared
> primitives, v1.8 and v1.9 added sync rules, and guard tests fail the build if
> you go around any of them. **§15 is the sync architecture and §15.12 is the
> lessons register — read both before touching `js/db/sync.js`.**
> The release checklist for v1.9 is the top section of `BACKLOG.md`.
>
> What I want to work on next: **<describe your task here>**
