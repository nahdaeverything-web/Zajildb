# زاجل — Zajil

**Arabic-first, offline-first pedigree & loft management for racing pigeons.**
Built for fanciers in Jordan and the Gulf; usable by anyone.

**[Try it live →](https://nahdaeverything-web.github.io/zajildb/)** · installs to
your home screen and keeps working with no connection.

زاجل تطبيق لإدارة اللوفت وأنساب الحمام الزاجل: عربي أولًا، يعمل دون اتصال
بالكامل، ويفهم هيكل السباقات في الأردن والخليج (نوادي، اتحاد، سباقات اللوفت
الواحد، أهلية FCI).

## What makes it different

1. **Arabic-first, true RTL.** The layout *mirrors* — it is not a translation
   skin. The pedigree tree in Arabic puts the subject on the **right** with
   ancestors extending **left** (this is structural: the tree is a CSS grid
   placed in logical order, so it follows the document direction). Ring
   numbers always render in Western digits, LTR-isolated, so an Arabic note
   containing `JO-2024-31002` never scrambles. Eastern Arabic numerals
   (٠١٢٣٤٥٦٧٨٩) are a user preference; Hijri dates display alongside
   Gregorian (storage is always ISO Gregorian).
2. **Fully offline.** IndexedDB is the source of truth; a service worker
   precaches the entire app shell. Nothing ever blocks on the network. Sync
   does not exist yet — the app is *correct with sync permanently disabled* —
   and every record already carries `loftId` + `updatedAt` so a future sync
   must be per-field last-write-wins, never whole-record overwrite.
3. **Regional race structures.** Race types `training | club | federation |
   national | one-loft | international`, per-race fancier/bird counts, and an
   **FCI eligibility checker** (≥ 20 fanciers, ≥ 150 pigeons, FCI ring on the
   bird) that no hobby app models.

## Running it

Static files, no build step, no dependencies.

```bash
git clone https://github.com/nahdaeverything-web/zajildb.git
cd zajildb
python3 -m http.server 8123        # or any static host
# open http://localhost:8123
```

**Requirements:** any modern browser. Offline mode and home-screen install need
a *secure context* — i.e. `https://` or `localhost`. Opening the files directly
over `file://`, or over plain HTTP on a LAN IP, still runs the app but without
the service worker (no offline, no install).

Install to the home screen from the browser menu (it is a PWA); after the
first load it works with no connection at all.

**To explore with ready-made data** — the empty bird list, or **الأدوات →
تحميل بيانات تجريبية**, offers two bundled lofts (both merge alongside your
own records; neither deletes anything):

| File | Contents | Good for |
|---|---|---|
| `sample-data.json` | 20 birds, 4 pairs, 12 results — Zarqa loft | a quick look; hand-verified 25% COI bird (برق) |
| `example-loft-large.json` | **38 birds, 6 generations, 5 pairs, 17 results, 7 health events** — Irbid teaching loft | learning: a **100%-complete 5-generation pedigree** (فارس ٢٦), 12.5% double-first-cousin cases (الشيخ, خيال), a 25% father×daughter case (عاصف), full-sibling young birds that trigger the severe pairing warning, FCI-qualifying vs non-qualifying results, and a round of eggs mid-incubation to drive hatch → ring → wean yourself |

Both datasets are regenerated deterministically (`node tools/gen-sample.js`,
`node tools/gen-example-large.js`) and their pedigrees and COI values are
asserted in the test suite.

## Data model

Stable UUIDs everywhere. **Never keyed on ring number** — birds carry
*multiple* rings (`national | FCI | club | private`) and FCI eligibility
depends on which one; re-ringed and duplicate rings are warnings, not
identity crises.

| Store | Contents |
|---|---|
| `birds` | id, `rings[]` `{country, union, year, serial, raw, type}`, name, sex (`cock/hen/unknown`), hatchDate, colour, strain, eyeSign, status (configurable per loft), `sireId`, `damId`, `external` (ancestors never owned are first-class records), breeder, owner, acquiredFrom/Date, `notes[]`, `loftId`, `updatedAt` |
| `pairs` | sire, dam, season, nest box, status, `rounds[] → eggs[]` (laid → hatched → ringed → weaned, each egg can link its `chickId`) |
| `raceResults` | birdId, race name/date, `raceType`, organisation, country, release point + loft point (GPS), release/arrival times, distance, velocity (m/min), position, `fanciersEntered`, `birdsEntered` |
| `healthEvents` | vaccination / treatment / illness / check, per bird or whole loft |
| `lofts` | name, location, custom status list — **club-mode hook**: every record is scoped by `loftId` from day one, so a club administrator view, ring issuance tracking, and one-entry race propagation can be added without a schema change |
| `media` | photos (body/eye/wing) and scanned documents as blobs, keyed to birds |
| `backups` | automatic internal snapshots (see below) |

## COI method (short version)

Wright's path formula with the (1 + F_A) correction for inbred common
ancestors, computed on a depth-truncated pedigree (default 10 generations,
configurable), cross-checked against an independent recursive-kinship
implementation, with a per-ancestor **contribution breakdown** in the UI.
The four canonical cases — full siblings 0.25, parent×offspring 0.25,
grandparent×granddaughter 0.125, unrelated 0 — are locked in the test suite,
plus a hand-verified inbred-ancestor case (0.28125) that ships in the sample
data. AVK (ancestor loss) is shown alongside because COI can read low while
the gene pool is already narrow. **Full maths with worked examples: [ENGINE.md](ENGINE.md).**

## Backup & restore

- **Export**: الأدوات → تصدير كل البيانات — one JSON file containing every
  loft, bird, pair, result, health event, and all photos/documents (base64).
  The app warns if you have not exported for 30 days.
- **Import**: the same screen. *Merge* keeps the newer record when ids
  collide (by `updatedAt`); *Replace* wipes first (with confirmation).
- **Automatic snapshots**: every 12 h the app stores an internal data-only
  snapshot (last 7 kept) inside IndexedDB — restorable from the same screen.
  They protect against mistakes, **not** against losing the device: export a
  real file regularly.
- **Share one bird**: from any bird page — exports the bird with its full
  ancestor closure (optionally races + media) as a file any Zajil user
  imports. No account needed on either side.

## Quality bar (as built)

- Engine (traversal, COI, AVK, relationships, rings, FCI, velocity,
  validation) is a separate pure-function module: `js/engine/`.
- **Tests**: `node tests/run.js` — **33 tests**, including the four mandatory
  COI fixtures. The engine subset (21) also runs *inside the app*
  (الأدوات → لوحة المطوّر) together with an export/import round-trip check;
  the 12 dataset-fixture tests are node-only.
- Validation: pedigree **cycles refused by name**, sex contradictions and
  parent-younger-than-child are hard errors; duplicate rings are warnings.
- Every destructive action confirms, and deletion offers **undo** (bird
  deletion restores media and re-attaches offspring links).
- Accessibility: 44 px touch targets, one-handed phone layout, and a
  high-contrast (bright-sunlight) mode in settings.
- Entry ergonomics for backfilling an existing loft: ring-first form with
  **save-&-add-another** (carries strain/status/owner and the ring prefix),
  **inline creation of missing ancestors** from the sire/dam pickers,
  **add-sibling** (siblings are derived from shared parents — the shortcut
  pre-fills them, creating placeholder parents when none are recorded),
  one-tap hatch date from the ring year, editable egg dates that propagate
  to chick records, and an in-app example loft (empty state or Tools →
  «تحميل بيانات تجريبية») for learning.

## Layout

```
index.html  manifest.webmanifest  sw.js  sample-data.json
css/app.css            — all styling incl. RTL logical properties + print CSS
js/engine/             — pure genetics/validation engine (no DOM, no DB)
js/{db,i18n,ui,app}.js — IndexedDB layer, ar/en + numerals + dates, DOM kit, router
js/views/              — register, bird, pedigree, breeding, races, health, stats, tools, certificate
tests/                 — harness + engine suite + sample-data suite (node & in-app)
tools/gen-sample.js    — regenerates sample-data.json deterministically
tools/gen-example-large.js — regenerates the 38-bird teaching loft
```

Working on this project? Start with **[HANDOFF.md](HANDOFF.md)** — full state,
architecture, invariants, open questions, and a seed prompt for a new session.

## Deliberately not here (v3+)

Race weather routing, one-loft campaign management, finance — competitors do
these; they are not why anyone switches. Still open from tier 3: the paper
pedigree **scanner** (needs a server-side vision model that reads Arabic
handwriting — the settings hook exists, the app never depends on it) and the
**public loft page** (needs any static publishing target; the share-a-bird
file covers the buyer use case meanwhile).

## License

**All rights reserved** — see [LICENSE](LICENSE).

The source is published so the pedigree and inbreeding maths can be inspected
and checked (that is the point of [ENGINE.md](ENGINE.md)). You may read it and
run an unmodified copy privately for your own loft; redistribution, derivative
works, and commercial use need written permission. This is a *source-available*
licence, not an open-source one.

Your loft data is yours: Zajil stores it locally on your own device and sends
it nowhere.
