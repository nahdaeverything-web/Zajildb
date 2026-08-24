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
| App version (service worker) | `zajil-v1.4.1` |
| JS source | ~3,770 lines (`js/`) |
| CSS | 363 lines (one file) |
| Automated tests | **33 passing, 0 failing** (`node tests/run.js`) |
| Browser E2E checks run to date | 63 across 4 suites, all passing (ad-hoc Playwright, not committed) |
| Example datasets | 20-bird loft + 38-bird / 6-generation teaching loft |
| Version control | git (`main`) — see the repo history |

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
Only `localhost` (or real HTTPS) gets those. See §10.

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
4. ✅ Breeding season manager — pairs → nest boxes → rounds → eggs → hatch → ring → wean, chick auto-linked to parents
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
- **Playwright E2E** (ad-hoc, in scratch — worth committing, see §11): RTL mirroring proven *geometrically* (Arabic subject's bounding box is right of its ancestors; flips in English), Eastern-Arabic numerals apply everywhere **except** ring numbers, 5-gen certificate renders and prints to PDF, dev panel passes in-browser.
- **Offline test**: install service worker → set browser offline → reload → navigate → COI still computes. Passes with zero errors.
- **Engine audit against a real loft's records**: 0 structural errors.

---

## 10. Known limitations & gotchas

1. **LAN = no offline/install.** Plain HTTP isn't a secure context. Needs real HTTPS (Cloudflare tunnel — `cloudflared` is installed; or free static hosting; or a trusted local cert).
2. **Static server isn't persistent** — dies on reboot/logout. No systemd unit yet.
3. **Service worker version must be bumped** (`sw.js` → `const VERSION`) whenever app files change, **and new files must be added to the `SHELL` precache list**, or offline users get stale/missing modules.
4. **Two reloads** are needed to see an update (first installs the new SW, second runs it).
5. `state.birds` mirrors IndexedDB in memory. Any new write path **must** update both (use the `saveBird` / `Pairs.save` / etc. helpers, never raw `idbPut`).
6. COI path enumeration is capped (`MAX_PATHS_PER_ANCESTOR`, `MAX_PAIRS_PER_ANCESTOR`). On pathological pedigrees the *breakdown* truncates and the UI says so; the *total* still comes from the exact kinship method.
7. Certificate rendering temporarily switches the i18n language and restores it — don't render certificates concurrently with other views.
8. `js/i18n.js` is large (473 lines) and holds every string. Adding a feature means adding keys there for **both** `ar` and `en`.

---

## 11. Conventions a new session must not break

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
- **`[hidden]` must always win** — `css/app.css` has a global `[hidden]{display:none!important}` because class-based `display` rules once resurrected hidden elements (this was a real bug: the parent-picker dropdown could never close).

---

## 12. Open items / awaiting the user's decision

### Open decisions
- **Local-network testing without HTTPS** has no service worker, so no offline
  or install. A hosted HTTPS deployment (GitHub Pages / Cloudflare Pages) is
  the way to exercise the offline promise on a phone in a loft.
- Whether to run the dev server as a persistent service on the workstation.

### Roadmap
1. **Commit the Playwright E2E suite.** ~80 browser checks currently live only as ad-hoc scripts; they have caught several real bugs and should be repeatable in CI.
2. Tier 3 #14 **public loft page** — small, and it serves the “shareable to buyers” pillar.
3. Tier 3 #12 **scanner** — biggest effort; needs an Arabic-handwriting vision model server. Must stay strictly optional.
4. Club mode — the business case (a federation is the paying customer). Schema is ready; UI is not.

---

## 13. Change log

- **v1.0** — initial build: engine + tests first, then Tier 1, Tier 2, docs, sample data. Verified offline + RTL geometry.
- **v1.1** — data audit pass (0 structural errors). Fixed: `[hidden]` override bug (parent-picker dropdown could never close; same latent bug in the health dialog). Added readable **sex chips** (♂ ذكر / ♀ أنثى) in lists, pickers, detail, plus tree tinting and a legend. Added **add-sibling** flow (siblings derive from shared parents; creates placeholder parents when none exist). Added in-app example-data loader.
- **v1.2** — 8 code-verified UX fixes: inline creation of missing ancestors from the sire/dam pickers; **rings-first form** with a pre-seeded row; **save-&-add-another** carrying strain/colour/status/breeder/owner + ring prefix; **editable egg dates** that propagate a corrected hatch date to the chick's record; one-tap hatch date from the ring year; Enter no longer submits a half-entered bird; Latin keyboard hints on ring inputs; datalist autocomplete for strain/colour/breeder; save uses history-*replace* so the phone back gesture returns to the list.
- **v1.3** — added the 38-bird / 6-generation teaching loft (`example-loft-large.json`) + 5 asserting tests; both examples offered in the empty state and Tools; precached for offline.

---

## 14. Seed prompt for a new chat

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
> What I want to work on next: **<describe your task here>**
