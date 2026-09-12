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
  Since 4D acceptance also `no-undefined-token`: a stylesheet may not read a
  custom property that is declared nowhere. CSS fails silently here — an
  undeclared property is an empty value, not an error — so only a guard can
  see it. It found two on its first run: `--danger-tint`, read by six modules,
  and `--gold-ink`, read by the shared sync row and the dialog's warning list.
  Both were SANCTIONED in Phase 0.2 and declared in neither place, so every
  danger ground and both gold inks had been painting with nothing. A
  `var(--x, fallback)` is accepted, and properties set from script or by
  `next/font`'s `variable:` count as declared.
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
- Everything outside `next/` is read-only during the port. `next/` imports
  nothing from `../js`, `../css` or `../tools` (guarded); the engine and the
  dataset id mapper are byte-identical copies under `src/engine/` and `tests/`.

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

## Deferred to the PWA phase (recorded so nothing is lost)

Nothing here is a port decision: each assertion needs a service worker or a
real deployment, and `output: 'export'` has produced neither yet.

| item | what it needs | root counts |
|---|---|---|
| `version_display.py` #1 #4 #5 #6 #7 | a registered service worker that answers `GET_VERSION`, and the version string in its own source | 5 of 11 |
| `service_worker.py` | a registered service worker: precache, offline reload, update flow | 5 |
| `subpath_hosting.py` | the export served from `/zajil/`, with the worker scoped there and the manifest resolving | 8 |
| `live_deployment.py` | a real deployed origin | — |

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
