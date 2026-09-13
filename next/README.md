# Zajil — React/Next port (`next/`)

The rebuild of Zajil as a static-export Next.js app, implementing the frozen
specs in `../design/approved/` — **not** the current vanilla screens. Where a
spec and today's app differ, the spec wins; `../design/README.md` says where
that is deliberate. The vanilla app in the repo root keeps running untouched
until a cutover ruling.

## Rules that are enforced, not remembered

- `npm run build` runs `guards/run.mjs` first (`prebuild`). Palette, no root
  imports, `<html lang="ar" dir="rtl">`, no gradients / blurred shadows, no
  dynamic route segments; since 4A also `ui-imports` (views, components and
  the harness reach the data layer only through `src/db.js` and
  `src/db/react.ts` — never `src/db/storage|oplog|records|io|sync`) and
  `strings` (`guards/strings.mjs`: every Arabic string a shipped spec renders
  is a key, a `{param}` template, recorded mock content in
  `strings.mock.json`, or a pending ruling in `strings.pending.json` — which
  the build accepts but reports as ⚠). Each guard was proved to fire by
  reintroducing its violation — see the Phase 0.5 and 4A-guards commits.
  Since 4B `npm run build:harness` runs the same prebuild guards before its
  build (it spawns `next build` directly, outside the npm lifecycle, so it
  had skipped them — an unsanctioned hex reached a green harness build).
  Since 4D also `no-hardcoded-version`: no source file may carry a
  `zajil-vX.Y.Z` string (version_display #8). The About row shows whatever
  the SERVICE WORKER reports, so a constant in the source is a second source
  of truth that goes stale the first time a build ships without it.
  Since Phase 6 acceptance also `base-path-consistent` (postbuild): `basePath` is a
  build-time constant, so what was ASKED for (`NEXT_PUBLIC_BASE_PATH`), what the EXPORT
  carries (the asset URLs Next wrote into the documents) and what the WORKER baked
  (`BUILT_FOR` and its first precache entry) must all agree. A worker whose prefix does not
  match its host registers happily and caches NOTHING — all ~130 precache URLs 404, the
  atomic install rejects, and the registration's `.catch` swallows it, so the app reports a
  registered worker with no offline mode and no error anywhere. The check that matters is
  the export against the request: a variable set for the postbuild step but not for
  `next build` gives a root-absolute export with a prefixed worker, and nothing downstream
  would notice. It runs BEFORE `sw-precache-sound`, because a prefix mismatch otherwise
  reports 130 missing files instead of the one cause. Proved to fire three ways: a base path
  requested against a root export, a worker baked for a different prefix, and a prefixed
  export with no base path requested.
  Since Phase 7 also `no-utc-date`: no file may compute a calendar date with
  `new Date().toISOString().slice(0,10)`. That is the UTC date, and east of
  Greenwich it names YESTERDAY between local midnight and the offset —
  `src/dates.js` exists for exactly this and `todayISO()` is the local date.
  The ROOT tree has had this guard since v1.4 (`tests/guards.test.js:87-92`)
  and the port never received it, which is how `app/cert/view.tsx` came to
  stamp a printed pedigree certificate with the UTC day: a certificate printed
  at 01:00 in Amman carried yesterday's date. Vanilla does not have the bug —
  it formats a full instant in local time, so only the port's date-only
  conversion introduced it. Unlike the root's, this guard also covers the
  PYTHON SUITES, because the same slice in an assertion is a test that fails
  for three hours a night and passes the rest of the day. That is how it was
  found: the Phase 7 gate ran at 00:29 local and `screens/health.py` failed two
  assertions that had passed twelve hours earlier. Proved to fire on both a
  `.tsx` source file and a `.py` suite, and to leave prose comments alone.
  Since 4D acceptance also `no-undefined-token`: a stylesheet may not read a
  custom property that is declared nowhere. CSS fails silently here — an
  undeclared property is an empty value, not an error — so only a guard can
  see it. It found two on its first run: `--danger-tint`, read by six modules,
  and `--gold-ink`, read by the shared sync row and the dialog's warning list.
  Both were SANCTIONED in Phase 0.2 and declared in neither place, so every
  danger ground and both gold inks had been painting with nothing. A
  `var(--x, fallback)` is accepted, and properties set from script or by
  `next/font`'s `variable:` count as declared.
  Since 5 also `sw-precache-sound` (postbuild): the generated worker's precache list
  must name only files that are on disk, must carry the app's own cache prefix, must
  bake the base path it was generated with, must include the harness route in a harness
  build and never in a normal one, must hold the nine assets the app cannot work
  offline without, and must precache EVERY navigable document. Each branch was proved
  to fire. An install is one atomic call for the shell, so an entry that is not there
  leaves no cache at all — and that looks exactly like a worker that has not activated
  yet, which is why a guard and not a reading has to say it.
- `output: 'export'` — no server, ever. Record views take `?id=`, never `[id]`.
- **Ruling C (4B addendum) — fixed elements must not hide content.** Every
  screen test proves it geometrically at 430x900 and 900x900 (never on a
  full-page capture, where a fixed bar is painted at its scroll position and
  only *looks* mid-page): scrolled to the end, no interactive element is under
  a fixed bar, and a toast covers neither the screen's chrome nor the last
  element. Helper: `tests/e2e/screens/_layout.py`. The clearance comes from the
  specs' own bottom paddings (100–200px measured) — none needed changing. What
  did need fixing was the toast: shared-states drew it 12px above the tab bar
  because its gallery had nothing else fixed, so on real screens it sat on top
  of the certificate CTAs, both FABs and the form's action bar. Each such bar
  now carries `data-bottom-chrome`, and `ShellHost` seats the stack 12px above
  the highest one it measures — live, so it stays right across breakpoints and
  across a navigation that happens while a toast is up.
- **Rulings at 4C acceptance** (the addendum rulings C and D are above):
  1. **entry_ergonomics#1 is RETIRED, not forced.** It asserts that the rings
     section leads the bird form; the approved `add-edit-bird-v2.html` orders
     the basics card photo → name → ring. The spec is the reason, and it wins.
     Every other assertion of that suite is mapped in `bird_form.py`.
  2. **Coordinates**: vanilla's separator tolerance is kept (it accepts
     «29.5321 35.0063 N») AND the spec's ±90 / ±180 range check is applied on
     top — an impossible coordinate errors rather than producing a nonsense
     distance.
  3. **The races log is filtered to the selected season**, and the season
     control offers «كل المواسم». A header stating a season above unfiltered
     rows was the quiet mismatch. The FCI checker is NOT filtered — it answers
     «is this bird eligible», not «this season» — and the control is hidden on
     that tab.
  4. **The health banner** derives from the most recent vaccination of any
     scope: it is the last vaccination that matters, whoever it covered.
  5. **Interim mappings, accepted and recorded**: the stats race card counts a
     season's *meetings* as its distinct race names, and the breeding card
     matches pairs by `season === String(seasonStart())` — the stored plain
     year. Both resolve when a real season field lands after the port.
  6. **The toast stack is capped at two visible**; a third replaces the oldest
     (`MAX_TOASTS` in `src/components/shell.ts`). §02 draws a stack and vanilla
     appends without a cap, but the clearance ruling C measured holds at two.
  7. **The pending-string category is empty.** The photo-tile label became a
     key in the app's own voice (`media.photo`), and the pedigree-tab COI line
     is now phrased as the vanilla dictionary phrases COI elsewhere
     (`ped.coiAtN` + `ped.completeness`), so the spec's spelled-out variant is
     ruled rather than pending.

- **Rulings at 4A acceptance** (each recorded where it applies):
  `nav.breeding` is a deliberate rename to «التزاوج» (i18n.ext.js overrides
  vanilla's «التربية»; every spec and the kit say so) · ONE season rule
  everywhere a season is displayed — split-year with a 1 July turnover
  (`src/components/season.ts`); breeding's stored `season` stays vanilla's
  plain year · ownership is kit-over-spec: the external marker and the
  «الخارجية فقط» pill are on loft home although loft-home-v1 draws neither ·
  capabilities the specs are silent on are carried, not dropped: per-photo
  delete, add-note, the FCI per-bird line · the mini-tree plate shrinks at
  phone width for real ring lengths (spec-vs-real-data) · spec wording that a
  ruling settled lives in `guards/strings.ruled.json` (accepted silently, the
  ruling is the record); `strings.pending.json` holds only what still awaits
  one.
- **Bird form (4B)** — `/bird/new` and `/bird/edit?id=` share `app/bird/form.tsx`
  (add-edit-bird-v2). It is a modal flow: the spec draws its own fixed action
  bar and no tab bar, so `Nav` hides the tab bar on those two routes (the rail
  stays at ≥1100). The parent picker has no design of its own — vanilla's
  `birdPicker` rules (search, blocked match, inline create, abandon keeps the
  committed parent, explicit clear) are rendered in the spec's parent-slot
  grammar. Errors go to shared-states' error dialog and mark the field;
  warnings to its warnings dialog; the duplicate ring shows live in the spec's
  warnbox. Capabilities the spec is silent on are carried: several rings with
  types, hatch-from-ring-year, the remaining vanilla fields (second card),
  documents, save-and-new with carry-over. The shell's dialog overlay is now a
  fixed full-viewport scrim (z 40) — the gallery had drawn it inside a static
  frame, so on a screen a fixed action bar could sit above it.
- **Pedigree tree (4B)** — `/pedigree?id=` (pedigree-tree-v1): the wall chart
  as designed, four ancestor generations by default. Carried from vanilla
  where the spec is silent (raised in the 4B report): the 3 / 4 / 5 generation
  control (`?gens=` too; the chart's width and height follow the deepest
  column, the sixth ruler label comes from a `{n}` template), the COI
  breakdown table with AVK, and the relationship finder — both below the
  chart in the spec's card grammar. An unknown slot's «add» opens the CHILD's
  edit form, where the parent is picked or created. Share = the profile's
  export; print = `window.print()` with the spec's wall-chart print rules
  (`@page` cannot live in a CSS Module and was dropped).
- **Breeding (4B)** — the spec's two levels are two routes: `/breeding`
  (list for a season, `?season=`) and `/pair?id=` (the pair with its rounds
  and eggs) — design/README.md breeding note 1. Shared pieces live in
  `app/breeding/shared.tsx`: the sheets (new pair with the kin box, link an
  existing bird, ring a chick) and every mutation, each a fresh copy through
  `Pairs.save` / `saveBird` as vanilla. Spec rules the app did not have
  (raised in the 4B report): the nest-box number is required and one active
  pair per nest and season; a bird already linked to an egg this season
  cannot be linked again; the ring sheet needs a ring and warns when its year
  differs from the hatch year (the spec's fixed-format warning was not
  carried — real rings are not all JO-YYYY-NNNNN). Deletes for the pair, a
  round or an egg confirm inline (spec) and undo through the shell; the
  stored `season` stays a plain year and is shown as the spec shows it.
- **Tools & settings (4D)** — nine cards in the spec's three groups behind its
  sticky index, at `/tools`. RULING 1 (Phase 4 order): the sync card's
  signed-out state is the explanation line plus a «تسجيل الدخول» button that
  navigates to `/sign-in`; the inline form the spec draws inside the card is
  superseded, and the not-configured state is unchanged and carries no button
  (there is nothing on that device to sign into). RULING 2: breeder name,
  phone, website and `logoMediaId` join the loft record through `Lofts.save`,
  so the certificate's branding block has real fields to read; the logo is
  device-local media like a photo, so its bytes go to the media store and only
  its metadata reaches the op log. The dev panel is collapsed and runs the
  COPIED engine suite (`tests/engine.test.js`, 21 tests — the count vanilla's
  panel runs, not the node runner's 33). Three things the port was missing and
  this screen exposed, all fixed here:
    - `applySettings()` (js/app.js:50) was never ported, so numerals, the date
      mode, the language and high contrast were stored and then ignored. It now
      lives in `src/components/settings.ts`, is applied at boot by
      `<AppSettings />` and re-applied after an import. `saveSetting()` is
      vanilla's `setSetting(...) then rerender()`: `setSetting` deliberately
      emits nothing (db/storage.js:168), so the write re-applies the locale and
      raises the LAYER'S OWN change event, which the React bridge already
      listens to. `signOut()` and `setSyncEnabled()` emit nothing either, so the
      card calls `refreshSyncStatus()` after them exactly as js/views/tools.js
      calls `refresh()`.
    - `initDB()` is not re-entrant: it mints the default loft when it finds no
      loft, so two calls in flight both mint one, and a second device then stops
      adopting the remote loft (db/sync.js:830). Vanilla calls it once in
      `boot()`; the port has a screen and the shell mounting independently, so
      `src/components/boot.ts` makes the single call a single PROMISE that every
      caller awaits. Caught by convergence.py, not by reasoning.
    - The loft and settings cards declared their field components inside the
      render body, so React remounted each input on every keystroke and a text
      field lost the caret after one character.
  HIGH CONTRAST — RULED at 4D acceptance, and now implemented in
  `styles/tokens.css` under `:root.high-contrast`. No approved spec defines the
  mode's colours, so they are **derived from the tokens** rather than carried
  from vanilla's Phase-1 hexes (css/app.css:28), which the palette guard
  rejects: the brand stays, every muted ink step collapses to `--ink` at weight
  500, borders take `--ink-3`'s value so a hairline becomes a line, both
  surfaces go pure white, and every tint is dropped to white. **Not one new
  colour** — every value was already sanctioned, which is what token-derived
  buys, so the guard's list did not have to grow. `screens/tools.py` measures
  the tokens themselves rather than trusting the class name, and
  `fidelity/high-contrast/` holds the before/after captures.
  Two measured places the ruled palette leaves below WCAG AA, reported for a
  design pass rather than changed here: white on `--brand` is 4.20:1
  (`--brand-deep` would be 6.12:1 and is already sanctioned), and `--gold` used
  as TEXT is 2.65:1 on white (`--gold-ink` is 6.37:1) — the latter is
  pre-existing and reads the same in normal mode.
  DEVIATION [ruling D]: the spec's duplicate group is labelled «نسختان» — its own
  mock's two-copy count, which lies at every other count — so the port renders
  the number plus the invariant noun, the grammar ruling D fixed for the tiles.
- **Certificate (4D)** — `/cert?id=`, from certificate-v1 with the wiring of
  js/views/cert.js. The options panel on the start side and the scaled preview,
  both formats (A4 landscape and the 9:16 phone sheet, each a different sheet
  rather than the same one cropped), 3/4/5 generations, the three photo
  switches, the branding block that RULING 2's loft fields feed, the QR slot,
  the print rules, the phone's «تكبير» reading mode, and the `@page` rule —
  restored the way the spec itself does it, as a `<style>` element whose text
  follows the format (certificate-v1.html:303, rewritten at :504), because a
  CSS Module cannot hold `@page` and a page box has nothing to scope to.
  CONTENT LANGUAGE is independent of the app language, as vanilla's cert.js
  already had it: the sheet is rendered with the dictionary switched and the app
  language put back, so an English certificate prints inside an Arabic app with
  the app's own direction untouched. The certificate counts the SUBJECT as
  generation 1, so its rows read `pedigreeGrid` from index g-1 and its COI line
  is computed over depth-1 ancestor generations — which is what makes
  «{n} أجيال · {f} من {tot} سلفًا» a true statement about the sheet in hand (the
  spec's own «5 أجيال · 30 سلفًا»).
  The tab bar is hidden here, as on the bird form: certificate-v1 marks its
  panel "app screen, no tab bar" and draws its own fixed «مشاركة / طباعة» bar
  where the tab bar sits. The rail stays at ≥1100.
  DEVIATIONS, all raised in the 4D report, none resolved silently:
    - RULED at 4D acceptance: the spec's certificate NUMBER («ZJ-2026-00417») is
      not rendered, and no register is invented. A number implies an authority
      that can verify it, and Zajil has none yet. The cell is out, and the story
      rule that hid it (`.head .meta > div:first-child`) went with it. The number
      and the QR slot are recorded together as **reserved for a future
      verification surface**: the QR box is drawn and says «قريبًا», and when a
      public bird page exists it is the thing a number would point at.
    - RULED at 4D acceptance: «مشاركة» keeps the app's one share, the profile's
      export. Real PDF and 9:16 image generation is a **post-port feature**, and
      the QR / public-page surface above is its natural companion — the same
      commit that can render a sheet to a file is the one that can give it a URL.
    - The spec's body ground `#DDE2E6` was RULED NOT sanctioned in Phase 0.2
      (document chrome, not an app surface), so the screen uses `--page` and the
      preview draws the sheet's edge with the palette's own hairline.
    - SPEC DEFECT, logged as **SF-1** in `ROOT-FINDINGS.md` and accepted at 4D:
      certificate-v1 puts its ≤700px block BEFORE the base rules for `.zoom-btn`
      and `.cta`, so at one-class specificity the base rule wins and the phone
      rules never apply — «تكبير» stays `display:none` and the action bar stays
      sticky. Both are restated at the end of the module, where they win. It
      applies to certificate-v1 only; no other approved spec orders its blocks
      this way.
    - ROOT DEFECT, logged as **RF-4** in `ROOT-FINDINGS.md` with the diff:
      `js/db/io.js:237` reads every media row through `blobToDataURL`, and a row
      whose bytes are on ANOTHER device has no blob — the ordinary state after a
      sync (SYNC-DESIGN §7: metadata syncs, blobs do not).
      `readAsDataURL(undefined)` throws, so the whole share rejects. **Nothing
      outside `next/` was changed**: `js/db/io.js` is byte-identical to `main`,
      the isolation diff is empty, and the root browser suite is 544/544. What
      the port changed is its own two share paths, which now say so instead of
      failing silently (`app/cert/view.tsx:216`, `app/bird/view.tsx:116`), and
      the certificate suite asserts the contract that holds either way: a share
      always answers.
- **PWA (Phase 5)** — a HAND-WRITTEN service worker, generated at build time.
  `sw/sw.template.js` is the source; `scripts/build-sw.mjs` runs first in `postbuild`,
  fills two placeholders from the FINISHED export, and writes `out/sw.js`.
  RECOMMENDATION AND REASONS, as the Phase 5 order asked for before building. Three
  independent reviews reached the same answer; next-pwa, `@ducanh2912/next-pwa` and
  Serwist were all examined against this tree:
    - **A custom worker source is unavoidable in every option**, so a library buys
      nothing on the contract that gates most of the deferred assertions.
      `src/components/version.ts` listens only on its own `MessageChannel` port and
      accepts only `{type:'VERSION'}`; no library ships that handler, and
      `version_display` #5 greps the shipped worker for a top-level VERSION constant.
      Once the constant and the message handler are hand-written, the remaining sixty
      lines of cache-first logic are the cheap part.
    - **The cache NAME is the version in vanilla, and no library models that.** It is
      the CacheStorage key, the sweep discriminator and the reply payload at once.
      Serwist's precache cache is not versioned per release, so there is no per-version
      cache to create and delete and nothing to report.
    - **A library cannot see 60 of the 131 things that matter.** Serwist's configurator
      globs `.next/`, where the RSC navigation payloads do not exist — they are created
      by the export, as `.txt`, and they are exactly what an offline client-side
      navigation fetches. A walk of `out/` gets all of them for free.
    - **Serwist's output cannot reach `out/`.** Its default destination is `public/sw.js`
      and it runs after `next build`, which has already copied `public/` into `out/`;
      `scripts/clean-out.mjs` wipes `out/` before every build, so nothing can be
      pre-seeded either. Any option needs a post-export step writing into `out/`, which
      is the whole of the hand-written approach.
    - **Both next-pwa packages are disqualified twice.** They are webpack plugins, so on
      Next 16 (Turbopack by default) they would force the project onto a bundler it has
      never built with; and a webpack plugin runs BEFORE Next prerenders, so it cannot
      see the sixteen documents it is supposed to precache. `next-pwa`'s last publish was
      2022 and the maintained fork's own README points at Serwist.
    - **`@serwist/turbopack` wants `app/serwist/[path]/route.ts`** — a route handler and a
      dynamic segment. `output: 'export'` refuses both, and the `no-dynamic-segments`
      guard refuses the segment independently.
    - **Cost:** 132 template lines plus an 89-line generator, zero new dependencies, on a
      project whose whole dependency list is next, react and react-dom.
  THE STRATEGY IS VANILLA'S, carried rule for rule from `sw.js`: cache-first with
  `ignoreSearch` and no revalidation; non-GET and cross-origin never answered, so
  Supabase sync passes through untouched; install with `cache:'reload'` Requests against
  a host's `max-age`; activate deleting only the app's own prefix, because CacheStorage
  is per-ORIGIN and `<user>.github.io` is shared with sibling projects;
  `GET_VERSION` → `{type:'VERSION', version}`.
  THREE DEPARTURES, each forced by the export's shape and each measured, not reasoned:
    1. **The navigation fallback.** Vanilla answers every navigation miss with the one
       cached `index.html`, because it is a single-document hash-routed SPA. This export
       has sixteen documents and `index.html` is a client-side redirect to `/birds`, so
       answering a `/tools` navigation with it would land the fancier somewhere else. The
       navigation branch resolves the request's own document first — the flat export means
       `/tools` is the file `tools.html` — and falls back to `index.html` only for a path
       it has never heard of. Asserted offline, both ways.
    2. **A network failure answers with a 504 instead of rejecting.** A rejected
       `respondWith` surfaces as a request error in the page, and both intent suites
       assert zero page errors across their offline sections. The suites now also state
       the window in which a 4xx/5xx is a host failure rather than the worker's own
       synthetic one.
    3. **Install is split.** Vanilla's `addAll` is atomic over 41 hand-checked paths. This
       list is ~130 build-named ones, about half of them navigation payloads, so keeping
       it atomic would mean one 404 on one payload costs the app its whole offline mode —
       and on GitHub Pages that is not hypothetical, since every `/_next/` path needs
       `.nojekyll` to be served at all. Documents, chunks, stylesheets, fonts, datasets,
       manifest and icons install atomically, exactly as vanilla does; the payloads are
       added one by one with their failures reported. Proved both ways in
       `tests/e2e/service_worker.py`: a 404 on a payload leaves ~130 entries cached and the
       app boots offline, while a 404 on a shell entry still leaves NO cache, because a
       half-installed shell is worse than none.
  THE INSTALL SURFACE — `app/manifest.webmanifest` (static, so `start_url` and `scope`
  stay the relative `./` that make subpath hosting work, and the icon `src`s stay
  relative with it), the three vanilla icons carried verbatim into `public/icons/`,
  `app/apple-icon.png`, and `themeColor` plus `viewportFit: 'cover'` on the `viewport`
  export, which is where Next 16 puts them. The manifest's `theme_color` and
  `background_color` are the kit's `--brand` and `--page`, not vanilla's `#0e7a5f` /
  `#f6f4ef`: those are Phase-1 hexes the palette guard rejects, the same ruling class as
  the high-contrast palette. The icon ARTWORK is still drawn in the Phase-1 green —
  raised for an icon pass, not repainted here.
  SUBPATH HOSTING — `basePath` now comes from `NEXT_PUBLIC_BASE_PATH`, because it is a
  build-time constant: one build serves one prefix, and `output: 'export'` forbids the
  rewrites that could normalise it at request time. `assetPrefix` would not do, since it
  prefixes `/_next` assets but neither routes nor `next/link` hrefs. The worker bakes the
  prefix its shell was generated with and says so loudly if it is installed somewhere
  else, because every entry is prefix-qualified and a mismatch would 404 all of them and
  leave a registered worker with no cache — indistinguishable from "not activated yet".
  `tests/pwa/subpath_hosting.py` proves the whole of it under `/zajil/` with its own
  build. THE LIVE TARGET IS `/Zajildb/`, so the release build needs
  `NEXT_PUBLIC_BASE_PATH=/Zajildb`; nothing yet asserts that the artefact's prefix
  matches the host it is deployed to, and that belongs with the deployment work.
  ONE VANILLA BUG FIXED IN PASSING — `js/app.js:267` registers `'./sw.js'`, which is
  document-relative. That was safe there because the app is one document at the root;
  this export has `bird/new.html` and `bird/edit.html` one level deep, where it would
  resolve to `/bird/sw.js` and scope the worker to `/bird/`. The port registers from the
  base path with an explicit scope. `.nojekyll` is now shipped from `public/`, which the
  vanilla root has and the export did not.
  KNOWN COSTS, recorded rather than hidden: a version bump refetches the whole ~2 MB,
  because the cache is keyed by version and written once — per-entry revisioning is what
  a library would buy and this gives up; and the update path still needs two reloads to
  show a new version, which is vanilla's inherited wart (HANDOFF.md:339).
- Everything outside `next/` is read-only during the port. `next/` imports
  nothing from `../js`, `../css` or `../tools` (guarded); the engine and the
  dataset id mapper are byte-identical copies under `src/engine/` and `tests/`.

## Coverage honesty (Phase 6)

Every assertion in the 31 root browser suites was mapped to the port, assertion by
assertion, by nine auditors and two adversarial critics. 460 root assertions across 23
local suites reconcile; the critics recounted eight suites by hand and found the counts
right, then checked ~55 "covered" claims and found five where the port's assertion did not
test the root's claim.

Twelve gaps were real. **All twelve are now closed**, and closing three of them found
defects:

| root assertion | how it was carried | what closing it found |
|---|---|---|
| `entry_ergonomics` — one ring row pre-seeded | `bird_form.py` counts the rows on a fresh form | — |
| `picker_duplicates:46` — no create row for an existing NAME | `bird_form.py` types a name into a parent picker | — |
| `picker_guards#8` — a refused save writes no pair | the port's version never pressed save, so it could not fail for its own reason; it does now | — |
| `core_flows:67` — `<html dir=ltr>` | `tools.py` clicks «English» and checks the document, the labels, and that it persists across a navigation | the English half of the app had shipped entirely untested |
| `core_flows:70` — LTR: subject left of ancestors | `pedigree_tree.py` re-measures the chart with the app in English | — |
| `core_flows:81` — the cert page is RTL | `certificate.py` asserts the Arabic sheet's own `dir` and `lang` | — |
| `example_data:81` — a legend under the tree | re-authored onto the legend the spec replaced it with | the legend had no testid |
| `change_events#7` — no view writes IndexedDB directly | the `ui-imports` guard now covers `db.idbPut/idbDelete/idbClear` and `db.emitChange` | the guard checked only IMPORT paths, and `src/db.js` re-exports the write primitives — the exact bypass it existed to stop passed green |
| `change_events#1` — an external write refreshes the register | was `check(…, True)`, which cannot fail; now reads the DOM and the navigation count | — |
| `core_flows#4` — ring search normalised | was weakened to `>= 1`, which a build listing all 38 would pass; now exactly 1 | — |
| `data_loss#4` — object URLs revoked on leaving | `bird_profile.py` wraps `createObjectURL`/`revokeObjectURL`, seeds a real photo, and leaves through the app's own back link | the first attempt was vacuous: a document navigation destroys the counters, so it had to be a client-side one |
| `data_loss#5` — photos survive a snapshot restore | `tools.py` takes a real `autoBackup()` and restores it through the card | — |
| `data_loss#7` — the loft card is usable after a foreign replace-import | `tools.py` completes one and reads the card | the card kept the PREVIOUS loft's name and location, so Save would have written them onto the new loft. Both it and the certificate panel are keyed by the loft id now |
| `teaching_loft#7` — عاصف's 25% COI on the detail screen | `bird_profile.py`, against the engine's own number | the port's only 25% assertion was a different bird, dataset and inbreeding path |
| `sync_ui#1` — the shell has a status row | the port's substitute tested `typeof window.__zajilDb`, a tautology; now it drives a visible state on an EMPTY loft | the row lived inside the loft home's non-empty branch, so an empty loft with a paused or failing sync said nothing |
| `sync_ui#24` — a MASKED password field | `sign_in.py` reads the input types, and the autocomplete pairing vanilla uses | the email field said `autocomplete="email"`, breaking the `username`/`current-password` pairing a password manager looks for |
| `sync_ui#30` — the button is usable again | `sign_in.py` reads its enabled state after a failure | — |
| `sync_ui#33` — ENTER submits | `sign_in.py` presses Enter against a stubbed project | it was carried only by `auth_live`, which the runner skips by default |

**What is still uncovered: the 11 assertions of `live_deployment.py`, and nothing else.**
Every one has a local counterpart that proves the same behaviour against a python
http.server, and not one of them can prove what GitHub Pages actually serves. They close
with the cutover.

## The fidelity pass (Phase 6)

All fourteen approved files were audited state by state against the port, one auditor each.
`add-edit-bird-v1` is superseded by v2 — the whole diff is two hunks moving the desktop rail
to the side the kit specifies, so v1 drops nothing — and `zajil-prototype` is the pre-spec
whole-app mock. Both were audited as such. `tools-v1` came back with no unreachable state at
all.

CAVEAT, stated because it changes how much weight this carries: the two adversarial critics
that were to check the auditors' work both died on a session limit. The eight defects below
were each verified and fixed by hand, with a measurement before and after, so those stand on
their own evidence. The 598 "reachable" and 467 "asserted" counts are the auditors' own and
have NOT been independently checked — the equivalent critics on the coverage audit found
five false "covered" claims out of ~55 sampled, so treat these as a good-faith survey rather
than a proof.

| | |
|---|---|
| spec states enumerated | 670 |
| reachable in the port | 598 |
| ruled out, with the ruling named | 47 |
| **not reachable** | **25** |
| states an assertion proves | 467 |
| deliberate differences, each with its authorisation | 222 |

Eight of the twenty-four were real defects, and they are fixed. Each was a silent failure —
CSS that cannot parse is dropped, and a layout that collapses still renders:

- **Both tree connector systems were dead.** The specs declare `--gap` in their `:root` as
  "the column gap AND the connector stub length" (20px for the pedigree tree, 18px for the
  certificate), and `split-generic.mjs` strips `:root`. So both modules read `--gap` four
  times and declared it nowhere: every `padding-inline-start:var(--gap)` resolved to
  nothing and every `calc(-1 * var(--gap))` was invalid. The trees had no column gaps and
  no connector lines. **The `no-undefined-token` guard had passed** because it pooled
  declarations from every stylesheet in the tree — but custom properties are SCOPED, so a
  `--gap:14px` inside `.mini` in one module proved nothing about another module's `.gen`.
  The guard now admits only the token sheet's `:root` plus the file's own declarations, and
  fires on a cross-module one.
- **The certificate had no desktop layout at all.** The generator mapped the spec's `.app`
  to `.screen` inside the two media queries and missed the base rule and the phone one, so
  the class never existed in the DOM: no two-column desktop, no preview-above-panel stack
  on the phone. Measured before the fix: the panel floating at x=684 with the preview
  1396px below it. No assertion had measured the screen's shape; two do now.
- **The 9:16 certificate head hid the wrong cell.** The spec's rule hides its first meta
  cell, the certificate NUMBER, which the 4D ruling keeps out entirely — so with that cell
  gone the rule hid the ISSUE DATE and the story head showed nothing. README had already
  recorded that rule as removed; it had not been.
- **The stats COI card's two columns were one.** The port wraps the two halves in an
  unstyled `.main`, which made them a single grid item, so the aside sat under the bars in
  the same column. `display:contents` promotes them without touching markup, and both are
  now placed explicitly — `grid-row` alone had put them in swapped columns.
- **The loft home could not combine a filter with a year.** The spec ANDs them and lights
  both pills, and vanilla ANDs every filter (js/views/birds.js:35-40) — but the port's
  handlers cleared each other, so «إناث» + «2024» was unreachable. The pills also now say
  `aria-pressed`, which matters more once two can be lit.
- **The table's sort direction was invisible.** The spec reveals a caret on the active
  column and rotates it 180° when descending; the port rendered a bare span and never set
  the `desc` class, so both rules were dead. `aria-sort` said the direction and nothing
  showed it.
- **The certificate CTA and every nav tab had no focus ring, and printing kept the nav.**
  The specs write those selectors for a `<button>`; the port renders navigations, which are
  anchors, so the selectors matched nothing. Measured: `outline: 0px none` under keyboard
  focus. And every spec with a print block hides the navigation — the port's Nav module had
  no print rule, so a printed pedigree carried the tab bar across it.
- **The three bottom sheets did not lock the page behind them.** Measured: a wheel over the
  scrim scrolled the register behind from scrollY 0 to 600. Vanilla locks with a
  reference-counted flag and the certificate's zoom already did it by hand;
  `src/components/scrim.ts` now does it for all three, counted, because a ring sheet can
  open over a pair sheet.

One fix had to be done properly rather than copied. Every spec dialog closes on
`onclick="if(event.target===this)closeAll()"`, and that one-liner has a hazard: a click is
pointerdown-then-pointerup, and a sheet that re-lays out between them moves what is under
the finger. Reproduced — clearing a picker query and then clicking the sheet's own heading
dismissed the sheet with the work in it. `useScrim` requires the gesture to BEGIN on the
scrim as well as end there, and `breeding.py` asserts the hazard cannot come back.

THE ONE GAP THAT RECURS, and the ruling it needs: the «نشط» status chip. Four of the
fourteen specs draw it — the form's status segment, the profile's hero meta row, and the
prototype's — and the design kit defines the bird's status field as
«(نشط/تربية/فريق السباق/ميت/مباع/مفقود)» (ZAJIL-DESIGN-KIT.md:101). The DATA LAYER's
`DEFAULT_STATUSES` is `['breeder', 'race team', 'young bird', 'stock', 'sold', 'lost',
'dead']` (db/storage.js:116) — no «نشط», and three statuses the kit does not list. The port
follows the data, and 4A acceptance item 4 accepted dropping the hero chip on that basis.
So this is not a port omission: it is the kit and the data model disagreeing, and it needs a
ruling either way — «نشط» becomes a real status (a stored-list migration for every existing
loft) or the kit's line is corrected. Recorded here because a port cannot settle it.

The other sixteen are presentation-level and need a design ruling rather than a fix. They
are listed in the Phase 6 report: the «نشط» status chip on the form and the profile hero,
the per-record document title, the form's field-level error state (a dead branch, because
both duplicate-ring keys are warnings and never errors), the gallery tile as an interactive
control, the health banner's dose-line order and its gold due state, the certificate panel's
placeholder icons and its print-chrome state, the breeding sheet's scroll-back on a refused
save, the FCI rule line's emphasis and the FCI table's chip and row tint, the loft home's
emphasised numerals, search magnifier, add-button icon, filter divider and the ring plate's
empty gold year cell, and the sign-in early-access mail fallback that its own required
fields make unreachable.

## One gate (Phase 6)

Two things the gate got wrong about ITSELF on its first runs, both fixed, both worth the
note: its summary filter read `N passed` and so never matched the runners' own
`N assertions passed` line — it reported the whole ported root suite as its smallest
constituent, 6. And it ran the root control from `next/`, where that suite's
CWD-relative `open('sw.js')` cannot find the file (RF-5). A gate that mis-parses a total
is worse than one that refuses to guess, so a step whose summary it cannot read is a
FAILURE and says so. Do not run `node guards/run.mjs` while the gate is running: the
harness build puts `app/test-harness/` in place for a few seconds and the
`no-harness-route` guard is right to object to it.

    cd next && npm run gate          # everything, with totals
    cd next && npm run gate -- --live   # …plus the live suites

`scripts/gate.mjs` owns the order and counts the assertions itself. It exists because a
gate a person assembles by hand is a gate that gets assembled differently each time — and
because the first thing it did was report two steps that had never been in any gate:
`npx tsc --noEmit` and `npx eslint`. A step whose summary it cannot parse is a FAILURE, not
a zero. The root browser suite runs as a CONTROL when a server is up at 8123 (RF-1: one
root suite hardcodes that port), and says so as a skip when there is not.

## What the first gate run found

`npx eslint` had never run in a gate. Its first run reported 79 errors, and one of them was
the most serious defect found anywhere in the port.

- **73 × `react-hooks/static-components`** — seven screens declared components inside
  their render bodies, so React remounted those subtrees on every render. Where the
  subtree held a text input, **the input lost the caret after one keystroke**. Measured
  before fixing: typing «برق السريع» into the bird form's name field left «ب». The bird
  form, the races result sheet and the health event sheet were all unusable for typing.
  Every screen suite already filled those fields and passed, because Playwright's `fill()`
  sets a value in one shot and never types a second character. `_layout.py` now has
  `check_caret`, which types character by character and asks where the caret went; every
  screen with a text field calls it.
- **A blind spot worth knowing about:** `react-hooks/static-components` reports at the USE
  site and does not see a component used only inside a `.map()` callback. `app/birds/view.tsx`
  therefore reported ZERO problems while declaring five components in its render body,
  used once per bird in both the phone list and the desktop table. A clean lint is not
  proof on its own; the adversarial review found those five, and they are hoisted too.
- **4 × `react-hooks/set-state-in-effect`** — two restructured (the certificate now seeds
  its format and language during render instead of from mount effects, so there is no
  frame showing the wrong one), two kept with a one-line directive and the reason in place.
- **2 × `react-hooks/immutability`** — the races and health date headers were decided by
  assigning to a variable as the `.map()` ran, and that form collapsed every falsy date to
  null. A run of results saved with no date got a «—» header EACH, and a first row with no
  date got none. Deciding it from the previous row fixes both; `races.py` asserts the
  single «—» header.
- The verbatim copies (`src/db/**`, `src/engine/**`, `src/i18n.js`, the node test files)
  are excluded from lint in `eslint.config.mjs`: a finding in one of them is a ROOT
  finding, not something to fix here, and linting them would invite the edit the isolation
  contract forbids. `@next/next/no-img-element` is off for the three files that render
  device-local blobs through object URLs, which is what `images.unoptimized` exists for.

Two more defects came out of closing the coverage gaps rather than from lint:

- **The loft card kept the previous loft's values.** It holds a draft seeded from the loft
  on mount, and a replace-import can swap the loft record underneath it (`db/io.js`
  repoints `currentLoftId` when the imported payload does not carry the stored one). So
  after importing another device's export the card showed the OLD name and location, and
  Save would have written them onto the new loft. Both it and the certificate's options
  panel are now keyed by the loft's id, so a loft that changes identity remounts.
- **The sync status row was invisible on an empty loft.** Vanilla appends it once above the
  view (js/app.js:75-77) so it shows whatever the screen contains, and every other port
  screen renders it straight after its header — but the loft home had it inside the
  non-empty branch. A fancier with an empty loft and a paused or failing sync was told
  nothing. Found by re-authoring `sync_ui` #1, which had been re-authored into a tautology.

## `fidelity/` — what those PNGs are, and why most of them drift

**They are REVIEW ARTEFACTS, not a visual-regression signal.** They are committed, and the
suites overwrite them on every run, so a modified PNG means "the suite ran", not "something
changed". Do not read one as a regression, and do not commit one as evidence of a change.

RULED at the Phase 7 close: freeze the clock for the CAPTURE ONLY, never pin the suite to a
permanent constant — a fixed instant some assertion silently depends on is a lie that fails
once a year in a way nobody will diagnose. Where a value a capture-time freeze cannot reach
is shown, seed it in the fixture; where neither is clean, let it drift and **say so**. This
is the saying-so, and it is longer than expected, because a four-agent audit found seven
causes where two were visible.

**What was done.** All 34 captures now go through `shot()` in
`tests/e2e/screens/_layout.py`, which passes `animations='disabled'`. Run-to-run on one
machine that took the drift from **16 captures to 8**: the seven `shared-states` spinner
captures became reproducible, and `loft-home/small-1400` was fixed by seeding fixture ids.

**The clock half of the ruling was implemented, measured, and REMOVED.**
`page.clock.set_fixed_time()` **wipes the performance timeline** —
`performance.getEntriesByType('navigation').length` goes 1 → 0 and never comes back — which
is exactly how `loft_home`'s `change_events#1` proves the register refreshed *with no
reload*. It turned a green suite red, which is how it was caught rather than shipped. (Two
traps for anyone who retries it: Playwright's **Python** clock takes **seconds**, so a
millisecond value pins the page to the year 58691; and it only affects rendering if installed
*before* the page renders, which is not what "freeze around the shutter" means.)

### The seven causes, and what each actually needs

| | cause | fixed by |
|---|---|---|
| 1 | **CSS animation frames** — the spinners | `animations='disabled'` ✅ **done** |
| 2 | **UUID order leaking into sort order** — see RF-7 | a total comparator, or seeded fixture ids. Done for `loft-home/small-*` only |
| 3 | **Wall-clock timestamps rendered into the DOM** — a note's `at`, `lastSyncAt`, the auto-backup id | fixture-seeded values. **Not done**: reaching past the UI the assertion exercises |
| 4 | **Fixed chrome randomly missing from `full_page` shots** | a preceding `Locator.screenshot()` makes the tab bar's inclusion a coin flip — measured **1 of 6** with element shots first, **6 of 6** without. Needs the full-page shot taken before the element shots, or on a fresh navigation. **Not done** |
| 5 | **The service-worker install toast** | a race on the FIRST page of each context only. `service_workers='block'`, or `wait_toasts_clear()` *before* the capture rather than after. **Not done** |
| 6 | **Data derived from *today*** | drifts across a **day boundary**, not run to run. Re-running all 12 suites at a date one day earlier changed **43 of 143** captures — all 8 certificate PNGs, and `certificate/story-ar-430` even changed *width* 436 → 450 px as a longer date widened the document. Only a pre-navigation clock freeze fixes this, which is what the ruling forbids. **Left drifting, by ruling** |
| 7 | **The machine's timezone** — see RF-8 | `new_context(timezone_id='Asia/Amman')`. **Not done** |

### What still drifts run-to-run on this machine

Eight captures, all case 3 — a timestamp the app rendered from an action the suite performed
through the UI:

| capture | the value |
|---|---|
| `bird-profile/overview-{430,900,1400}` | the note the suite types into `note-input`, stamped by the app's own note path |
| `tools/signed-in-{430,900,1400}` | `lastSyncAt`, from a real sign-in against the mock |
| `tools/{full-900, dev-open-900}` | the auto-backup id in the restore `<select>` — **900 only**, because at 430 and 1400 the select clips the time off |

Seeding those means reaching past the UI the assertion is exercising. They drift, honestly,
and they are listed by name. An honest drifting capture beats a frozen lie.

**The bigger point, which the audit made and the run-to-run number hides: these captures are
not portable and never were.** Case 6 means they change every day; case 7 means they encode
the machine that made them. Treat them as "what Samir's machine rendered on the day", which
is a useful thing for a human to look at and a useless thing to diff.

### The nineteen orphans — DELETED, and one claim about them was wrong

`fidelity/` held **162** PNGs while the 34 capture sites write **143**. The other nineteen —
`fidelity/high-contrast/` (12) and `fidelity/pwa/` (7) — were committed and **no suite wrote
them**: captured by hand, the high-contrast set at 4D acceptance (`a428bb3`), the PWA set at
Phase 5 (`48faa77`). The only `high-contrast` string in `tests/` is a class assertion at
`tools.py:170`, not a capture.

They were frozen from **before the Phase 6 fidelity fixes** (`2c4b3b7`) — before the two dead
tree-connector systems were repaired, before the certificate had a desktop layout at all,
before the focus rings and the print rules. They never drifted, which made them look more
trustworthy than the 143 that do while being the least trustworthy of the set. **Ruled at the
pre-launch close: deleted.** If those views are worth capturing, a suite regenerates them.
`fidelity/` is now 143 PNGs and every one of them has a suite that writes it.

**A correction, because it was recorded here on an agent's word and it was wrong.** An
earlier draft of this section said `loft-home/full-1400.png` was written twice, at
`loft_home.py:71` and again at `:193`. It was not — that loop is `for w in (430, 900)` and
always has been. The file is written once. What WAS real is the state it was written in: the
single capture sat at the end of the desktop block, *after* two clicks on «الاسم» had sorted
the table by name and then reversed it, so the filename said "full at 1400" and the picture
was "full at 1400, sorted by name, descending". The capture now happens immediately after the
table is asserted present, on its default sort.



## Tests

    node tests/run.js        # the root engine suite against src/engine/ — 33/33

## Two files you did not write

`AGENTS.md` and `CLAUDE.md` are **create-next-app output**: Next.js API
guidance for coding agents, re-added by `next dev` if removed. They are not
Zajil project rules — those live in the root `HANDOFF.md`, `BACKLOG.md` and
`design/README.md`. Each carries a first-line comment saying so.

## Fonts

Self-hosted under `public/fonts/` (OFL 1.1, licences beside the faces), wired
through `app/fonts.ts`. Alexandria is one variable file subset to Arabic +
Latin; IBM Plex Mono is the two static weights the specs load.

## Post-port optimisation candidates (RULED at Phase 5 acceptance — not Phase 6 work)

Neither of these is a regression: both match what vanilla does today, and both were
recorded rather than fixed so the decision stays visible.

| candidate | what it costs now | why it is not urgent | what would fix it |
|---|---|---|---|
| **A version bump refetches the whole ~2 MB precache** | the cache is keyed by the version and written once, so every hashed `_next/static` file is fetched again even when byte-identical to the previous deploy | vanilla has the same shape at a smaller size, and the fetch is once per release on a connection the fancier is already using to get the new build | per-entry revisioning — a manifest of `{url, revision}` and a cache that carries entries forward when the revision is unchanged. This is the one thing a Workbox-style library would have bought (see the Phase 5 recommendation) |
| **An update needs two reloads to show** | the first reload activates the new worker, the second renders from it; the About row reports the old version in between | vanilla behaves identically and it is the release ritual today (HANDOFF.md:339) | either prompt from the `updatefound` toast with a reload action, or hold the new worker and swap on `controllerchange`. Both change update UX, which is a design decision, not a refactor |

## Cutover considerations (Phase 7 — recorded, not acted on)

**IndexedDB is per-origin.** Every user's data today lives in the database
`zajil` (version 2) under the GitHub Pages origin the vanilla app is served
from. `zajildb.com` is a **different origin**: a browser there opens an
**empty** `zajil` database. Nothing carries over by itself, and no amount of
shared code changes that — it is a browser security boundary, not an app
choice.

Cutover therefore needs an explicit **data path** for every existing user:

- **Export / import** — the vanilla Tools card («تصدير كل البيانات (JSON)»)
  writes a full export; the port's Tools card must import it. The schema is
  identical by construction (same store list, same keyPath, same version), so
  an export from vanilla imports into the port without translation. This
  works for everyone, including users who never signed in.
- **Sign in and pull** — for accounts that synced, the server holds their
  records; signing in on the new origin and running the first-login pull
  (SYNC-DESIGN §6) repopulates the device. Photos do **not** travel this way
  (blob sync is BACKLOG P2): «الصورة على جهاز آخر» is the expected result.

Also origin-bound, and therefore also new on the other side: the service
worker registration and its caches (Phase 5), and any `localStorage`. The
cutover plan must say which path each class of user takes, in what order,
and what the vanilla app shows once it is retired. **No cutover without a
ruling.**

## Intent lists at 4D — where every assertion went

The Phase 4D order named six lists. Each one is accounted for here; nothing is
skipped silently.

| list | root | where it is now |
|---|---|---|
| `sync_ui.py` | 60 | **41** ported whole to `tests/e2e/sync_ui.py` (the status row, the interrupt rule, the الأدوات card, the backoff curve, the unconfigured build). Four kinds of change and no others: the module token, the shell's DOM (`#sync-row` → `[data-testid=sync-row]`; the healthy row is not rendered at all rather than rendered `display:none`, which is what "not taking up space" asserted), the routes, and RULING 1. **19** moved with the form RULING 1 superseded: the signed-out card, the create-account prohibition, the unconfigured state and the sign-out flow are in `screens/tools.py`; the form's own error states are in `screens/sign_in.py`. The file holds 62 `check(` calls but two sit in an if/else, so 60 execute — which is what the root runner reports, and 60 = 41 + 19. |
| `version_display.py` | 11 | **#2 #3 #9 #10** re-authored in `screens/tools.py` (the About row renders, is never blank, and shows the «غير معروف» fallback with no service worker). **#8** became the `no-hardcoded-version` guard, proved to fire. **#1 #4 #5 #6 #7** need a registered service worker answering `GET_VERSION` — PWA phase, listed below. |
| `auth_live.py` | 18 | **ported whole**, opt-in behind `--live-auth`, with the six form assertions re-authored onto `/sign-in` (RULING 1). NOT RUN here: the sign-in screen runs the first-login cycle, so a live run WRITES to the real project, exactly like `--live-push`. That is an explicit authorisation, not a gate. |
| `convergence.py:248-252` | 2 | **CLOSED.** `src/components/SyncNotices.tsx` reproduces js/app.js:195-217 and the assertions were re-authored onto the port's toast. convergence.py is 36/36. |
| `picker_duplicates.py` #8–10 | 3 | re-authored in `screens/tools.py` against the real duplicate finder: it lists a clone, says what each copy is linked to (with the kinds), and the group is gone once the surplus copy is deleted. |
| `subpath_hosting.py` | 8 | needs the app deployed under a subdirectory with a service worker scoped to it — PWA phase, listed below. |

## The PWA phase (Phase 5) — what closed and what is left

Everything here needed a service worker or a real deployment. Phase 5 built the worker,
so three of the four rows are closed; only a deployed origin is still missing.

| item | what it needs | root counts |
|---|---|---|
| ~~`version_display.py`~~ — **CLOSED at 5** | all 11 ported to `tests/e2e/version_display.py` and green. #8 became a stronger claim than the root's four-file spot check: no shipped file in the whole export carries the version, only the generated worker. | 11 |
| ~~`service_worker.py`~~ — **CLOSED at 5** | all 5 ported to `tests/e2e/service_worker.py`, plus 7 the port needs and vanilla did not: the precache is populated rather than an empty shell from a failed install, a clean URL finds its OWN document offline, an unknown route falls back to the shell, the harness route serves the harness, and the install split proved both ways. | 5 → 12 |
| ~~`subpath_hosting.py`~~ — **CLOSED at 5** | all 8 ported to `tests/pwa/subpath_hosting.py` (its own directory because it needs its own build), plus 6 more: assets resolve under the prefix and not at the origin root, the manifest is the prefixed one with a relative scope that follows it, a click stays inside the prefix, a clean URL under the prefix works offline, the version row reports the worker under the prefix, and nothing 4xx/5xx was served while online. | 8 → 14 |
| `live_deployment.py` — **11 assertions, the ONLY uncovered ones left; RULED at Phase 6 acceptance to be the FIRST GATE OF THE CUTOVER** | a real deployed origin, built with `NEXT_PUBLIC_BASE_PATH=/Zajildb`. Each has a local counterpart that proves the same behaviour against a python http.server — secure context, the six nav links, no failed requests, the worker's scope, the versioned cache, an installable manifest, the 38-bird load, offline boot, offline data, offline COI, zero page errors — and none of them can prove what GitHub Pages actually serves. See the Phase 6 coverage table. | 11 |

## Deferred to Phase 4 (recorded so nothing is lost)

Root browser suites — or assertions inside them — that test the data layer
**through the vanilla shell** and therefore cannot run against a port with
placeholder screens. Each returns to scope when the screen it drives is
ported. Nothing here is skipped silently: the Phase 4 order must account for
every line.

| item | why it waits | root counts |
|---|---|---|
| `record_factory.py` | fills `.ring-input`, submits `button.btn-primary` | 8 |
| `change_events.py` | navigates `#/breeding`, finds «زوج جديد» | 8 |
| `ownership.py` | drives `#/bird/new`, clicks | 10 |
| `data_loss.py` | drives `#/bird/new`, clicks | 8 |
| `pull.py` | one `#/bird/` navigation (line 356) — the URL-and-module rule stays clean rather than carrying a documented exception | 58 |
| ~~`auth_live.py`~~ — **PORTED at 4D** | opt-in behind `--live-auth`; the six form assertions re-authored onto `/sign-in`. See the intent-list table above. | 18 |
| ~~`convergence.py:248-252`~~ — **CLOSED at 4D** | the duplicate-ring toast now has a shell to be raised in: `src/components/SyncNotices.tsx` reproduces js/app.js:195-217 (the sync-interrupt message and the sync-complete duplicate notice, both vanilla's PLAIN toast), mounted once in the layout. The three assertions were re-authored onto the port's `[data-testid=toast]` and pass; convergence.py is 36/36. | 2 |
