# Zajil — the React port, complete

One page for whoever picks this up cold. Everything here is checkable; where a claim needs
a command, the command is given.

**Status:** the port is finished and gated. It has never been deployed. The vanilla app in
the repo root is what real users run today, at `https://nahdaeverything-web.github.io/Zajildb/`.
Nothing moves until the launch sequence is opened.

---

## 1. What this is

Zajil (زاجل) is an Arabic-first, offline-first PWA for racing-pigeon pedigree and loft
management. The repo root holds the **vanilla** app — plain ES modules, hash-routed, live
since v1.9.1. `next/` holds a **complete rebuild** of the same product as a static-export
Next.js app.

The two share a data layer **byte for byte**. All 17 modules — `db.js`, `db/{storage,oplog,
records,io,sync}.js`, `dates.js`, `i18n.js`, `sync-config.js` and the eight `engine/` files —
are identical between `js/` and `next/src/`, and the gate proves it every run. That is what
makes an export from one app importable by the other, and it is the single most important
property of the port.

```
zajil/
├── index.html  js/  css/  sw.js      the vanilla app — LIVE
├── design/approved/                  14 frozen specs — the port's actual source of truth
├── docs/SYNC-DESIGN.md               the sync design, incl. §1 the production schema
├── tests/                            the vanilla suites (548 browser + 141 node)
└── next/                             the port
    ├── app/ components/ styles/      TypeScript UI, CSS Modules, styles/tokens.css
    ├── src/                          the data layer — verbatim copies of js/
    ├── guards/                       11 prebuild + 5 postbuild guards
    ├── sw/ scripts/build-sw.mjs      the service worker, generated at build time
    ├── tests/                        the port's suites
    ├── fidelity/                     screenshots — REVIEW ARTEFACTS, see §7
    ├── CUTOVER.md                    THE PHASE 7 PLAN — read before any deploy
    ├── ROOT-FINDINGS.md              bugs found in vanilla and in the specs
    └── README.md                     the long-form record of how it was built
```

**The specs win, not the current app.** `design/approved/` holds 14 frozen HTML mockups.
Where a spec and today's vanilla screen disagree, the port implements the spec —
`design/README.md` records where that is deliberate. The exceptions are listed in §6.

---

## 2. How to run everything

One command runs the whole thing and refuses to report a total it could not verify:

```bash
cd next
node scripts/gate.mjs          # or: npm run gate
```

It needs one thing first, because a vanilla suite hardcodes the port (RF-1):

```bash
cd /path/to/zajil && python3 -m http.server 8123 &
```

Without it the gate **skips** the root control and says so rather than quietly passing.

The last full run:

```
1751 passed, 0 failed across 26 steps, 1 skipped  ·  13.9 min

  guards (prebuild) · build · typecheck · lint · build:harness
  engine (next/tests)          33/33      engine (root, control)     141/141
  e2e/run_all (ported root)   408/408      11 screen suites           532/532
  bridge / fidelity / sync      69/69      pwa/subpath_hosting         14/14
  root browser (control)      548/548      isolation                    EMPTY
```

The live suites are skipped by default because they read or write a real Supabase project:
`node scripts/gate.mjs --live` runs `auth_live` / `push_live` / `pull_live`, and they refuse
to start without credentials in the environment.

### The two things the gate protects

**The isolation contract.** The port changed nothing outside `next/`. Proven every run:

```bash
git diff --stat main..HEAD -- . ':(exclude)next/'     # must be EMPTY
```

Three commits are the *authorised* exceptions, each ruled individually: the design-kit
status-line correction (`08b42a4`), the service-worker deep-path redirect (`a98b228`), and
the comment that protects it in `tests/e2e/schema_upgrade.py`.

**The harness never ships.** `next/harness/` is copied into `app/test-harness/` only by
`npm run build:harness`. A normal build must contain no harness route and no harness
globals; a harness build must contain both. Both directions are asserted postbuild.

---

## 3. What the guards enforce

Every one was proved to fire by reintroducing its violation. That is the standard here: a
guard nobody has seen fail is a guard nobody knows works.

**Prebuild** (`guards/run.mjs`, runs before every build including the harness build):

| guard | what it refuses |
|---|---|
| `palette` | any colour not sanctioned in `styles/tokens.css` |
| `no-root-imports` | the port reaching outside `next/` |
| `html-rtl` | losing `<html lang="ar" dir="rtl">` |
| `no-gradient-no-blur` | gradients and blurred shadows — a house rule |
| `no-harness-route` | the harness in a normal build |
| `no-secret-key` | a Supabase **secret** key or a service-role key anywhere under `next/`. (This guard failed on an earlier draft of this very file, which quoted the literals it hunts for — so the table now describes them instead.) |
| `no-dynamic-segments` | `app/**/[id]/` — a static export cannot enumerate user data, so records route on a query param |
| `ui-imports` | a view touching `src/db/storage\|oplog\|records\|io\|sync` directly, **including through the facade's re-exported write primitives** |
| `no-undefined-token` | a stylesheet reading a custom property declared nowhere. Scoped per module — pooling declarations across files is what let `--gap` pass while both tree connector systems were dead |
| `no-hardcoded-version` | a `zajil-vX.Y.Z` literal in source; the About row must report what the WORKER says |
| `no-utc-date` | `new Date().toISOString().slice(0,10)` — the UTC date, which names yesterday east of Greenwich. Covers the python suites too |
| `strings` | any Arabic string a shipped spec renders that is not a key, a template, recorded mock content, or a pending ruling |

**Postbuild** (`guards/postbuild.mjs`, after every build):

| guard | what it refuses |
|---|---|
| `no-sync-config-in-build` | an endpoint or key of any kind in `out/` — matched by SHAPE, so a custom domain or a legacy JWT is caught too. On a hit it **deletes `out/`**, because a pipeline that uploads regardless of exit code would publish exactly what the guard exists to prevent |
| `base-path-consistent` | a mismatch between what was asked (`NEXT_PUBLIC_BASE_PATH`), what the export carries, and what the worker baked. A worker on the wrong prefix registers happily and caches **nothing**, with no runtime signal at all |
| `sw-precache-sound` | a precache list with a missing file, a dead route, or the harness in it |
| `no-harness-globals-in-build`, `no-harness-output` | the harness leaking into a normal build |

---

## 4. Findings — `ROOT-FINDINGS.md`

Bugs the port found in the **vanilla app** and in the **frozen specs**. They are recorded
there in full, with diffs where a fix is proposed.

| | |
|---|---|
| **RF-1** | `tests/e2e/write_boundary.py` hardcodes port 8123 — why the gate needs that server |
| **RF-2** | root browser suites exit 0 on assertion failure |
| **RF-3** | the free-tier dev project auto-pauses after ~7 days; a paused project's hostname leaves DNS and presents to the client **identically to a regional block** |
| **RF-4** | a bird share fails outright when an ancestor's photo is on another device — **open, with the fix diffed** |
| **RF-5** | root `package.json` says 1.4.1 while `sw.js` says `zajil-v1.9.1`; the version grep is unanchored and can read a comment |
| **RF-6** | twelve document-relative URLs and the blank page they produced — **fixed at source** |
| **RF-8** | the committed fidelity captures encode the timezone of the machine that made them — an artefact defect, with a one-argument fix, **not applied** |
| **RF-7** | the register's desktop table sorts by year alone, so same-year birds fall back to uuid order — stable but arbitrary, and it disagrees with the phone grouping. **A design question, recorded** |
| **SF-1** | `certificate-v1.html` puts its phone media query before the base rules it overrides |
| **SF-2** | the design kit's bird-status list disagreed with `DEFAULT_STATUSES` — **the kit was wrong, the data right**; corrected, and four specs draw «نشط» as mock content the port does not render |

Also recorded there: **the refuted ruling**, kept because the refutation came from the tree's
own assertions rather than from an argument.

### The two findings worth reading even if you skip the rest

**The caret bug.** Components declared inside a render body are a *new type* every render, so
React unmounts and remounts them — measured: typing «برق السريع» into the bird form produced
«ب». 73 instances across 8 files. The permanent guard is `check_caret` in
`tests/e2e/screens/_layout.py`, which types character by character and asserts focus never
moves. Lint alone could not find them: the rule reports at the *use* site, so a component
used only inside `.map()` is invisible to it.

**The invisible failure.** A `<script type="module">` whose `src` 404s raises **no**
`pageerror`. So "zero page errors" passes on a completely blank page — measured. Any suite
whose safety net is page errors alone is not watching anything. The companion mistake:
`subpath_hosting.py` accumulated failed responses for the page's whole life but asserted on
them at line 48, before its last three navigations, so a later 404 was recorded and never
looked at. Both are fixed; the shape is worth remembering.

---

## 5. Deferred — the things that are NOT done

**`live_deployment.py` — 11 assertions, the only uncovered ones left.** They need a real
deployed origin. The suite as it exists cannot gate the port: there is no port copy, every
DOM token in it is vanilla-only, and the URL and scope are hardcoded (it documents a
`ZAJIL_LIVE_URL` env var that nothing reads). Ruled: it **splits** — the vanilla original,
URL-parameterised, becomes the rollback verifier; a ported copy becomes the deploy gate.
Both are stage 2 of the cutover. See `CUTOVER.md` §0.4.

**The 16 presentation differences.** The fidelity pass over the 14 specs left 16 states that
need a design ruling rather than a fix — none is a correctness defect and none blocks a
cutover. They are listed with a recommendation for each in `CUTOVER.md`'s appendix, grouped
as *carry the spec* (7), *follow the data and correct the spec* (4), and *genuine design
questions* (5). A seventeenth was found later and is vanilla-vs-port rather than spec-vs-port:
the port never renders `backup.warn30`, the only in-app prompt that puts an export in a
fancier's hands. Ruled: restore it before cutover.

**The two PWA costs**, accepted as-is and logged as post-port optimisation candidates, not
work:
- a version bump refetches the whole ~2 MB precache;
- an update needs two reloads to show — the same dance vanilla does every release.

**The export's chunking.** The user-facing export builds the whole loft, every photo
base64-expanded, as one string on the main thread. Ruled FIX before cutover; the *mechanism*
is an open decision, because `src/db/io.js` is byte-identical to vanilla's and changing it
ends that identity or changes both apps. `CUTOVER.md`'s open-decisions register has the
three candidate shapes.

---

## 6. Where the port deliberately differs from vanilla

Recorded in full in `README.md` under the departures and the fidelity pass. In outline: the
port implements the **specs**, so several screens differ from today's app by design; record
routes are **query-param** (`/bird?id=…`) rather than hash, because a static export cannot
enumerate user data; and the service worker is **generated** from `sw/sw.template.js` at
build time, so its precache list cannot drift from what was actually built.

---

## 7. `next/fidelity/` — what those PNGs are

**Review artefacts, not a visual-regression signal.** They are captured by the suites as they
run so a human can look at what the screens actually rendered. Do not read a modified PNG as
a regression, and do not commit one as evidence of a change.

Where determinism actually stands, measured: **16 of the 34 drifted run-to-run. Eight do
now.** But run-to-run is the small half of the story — a four-agent audit found **seven**
causes where two were visible, and two of them mean these files were never portable:
**data derived from *today*** (re-running at a date one day earlier changed 43 of 143
captures, including all 8 certificate PNGs) and **the machine's timezone** (RF-8). Treat
them as "what one machine rendered on the day". `README.md` has the full table.

- All 34 go through `shot()` in `tests/e2e/screens/_layout.py`, which passes
  `animations='disabled'` — that made the seven `shared-states` captures reproducible, since
  their drift was a spinner frame.
- `loft-home/small-1400.png` needed seeded ids. It is the desktop table, which sorts by
  **year alone**, so same-year birds tie and the stable sort falls back to IndexedDB key
  order — uuid. Fresh uuids every run were the whole cause.
- The remaining eight — `bird-profile/overview-*` and `tools/{signed-in-*, dev-open-900,
  full-900}` — show a timestamp the app rendered from an action the suite performed through
  the UI. Seeding those would mean reaching past the UI the assertion exercises. They drift,
  and `README.md` lists them.

**Nineteen of the 162 PNGs are orphans.** `fidelity/high-contrast/` (12) and `fidelity/pwa/`
(7) are committed and no suite writes them — they were captured by hand at 4D and Phase 5,
so they are frozen from **before** the Phase 6 fidelity fixes and show screens that no longer
exist. They never drift, which makes them look more trustworthy than the 143 that do.

**The clock freeze was implemented, measured, and removed.** `page.clock.set_fixed_time()`
wipes the performance timeline — `performance.getEntriesByType('navigation').length` goes
1 → 0 and does not come back — which is exactly how `loft_home` proves the register refreshed
*with no reload*. It turned a green suite red, which is how it was caught rather than shipped.

---

## 8. Before anything deploys

**Read `next/CUTOVER.md` first.** It is the Phase 7 plan: sections a–h, the order of
operations as 15 stages, and an open-decisions register. Nothing in it has been executed.

The three findings in its §0 are the ones that would otherwise be discovered in production:

1. **Both service workers name the same cache.** `sw.js` is `zajil-v1.9.1` and the port
   composes the same string from `next/package.json`. Since each sweeps `zajil-*` keys that
   are `!== VERSION`, an identical version means **neither deploy ever evicts the other** —
   the port's 138 entries land beside vanilla's 40 and stay, in both directions. The release
   must bump `next/package.json`.
2. **A configured release is currently impossible, by design.** `src/sync-config.js` is
   byte-identical to vanilla's and two tests assert it empty. The config injection point is
   recommended in §a.3 and **not built**.
3. **The verification query proves objects, not paths.** All four introspection checks once
   went green on a Supabase project that accepted nothing, because the SQL editor runs as
   `postgres`. Only `push_live` / `pull_live` against the real project prove a write lands.

And the one that decides whether people keep their birds: **IndexedDB is per-origin**, so
nothing at the old origin follows to a new domain. §d spells out the options and recommends
export/import — sync is the wrong tool, because media *metadata* syncs and blobs do not.
