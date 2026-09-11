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
- `output: 'export'` — no server, ever. Record views take `?id=`, never `[id]`.
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
| `auth_live.py` | fills `.sync-signin` and clicks the sign-in button (lines 111–113) | 18 |
| `convergence.py:248-252` — 2 of 36 | the duplicate-ring **toast**: asserts on `.toast` DOM text, which `js/app.js:213-214` renders from `takeSyncDuplicateNotice()` via `i18n.t('sync.duplicates')` and the shell's toast. The layer's half (the notice is counted once) passes at line 241. RULED Phase 4; a harness that grows fake shell components to satisfy assertions is fitted to the test, not the layer. | 2 |
