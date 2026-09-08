# Design archive

**Design specs, not app code.** Nothing here is loaded, precached, or imported
by the app. `sw.js` does not list it, `index.html` does not reference it, and no
module under `js/` imports from it. That isolation is checked, not assumed:

```bash
grep -rn "design/" sw.js js/ index.html      # expect no matches
```

A design file may use whatever it likes — inline styles, its own fonts, a
support script — because it never runs alongside the app.

## approved/ is frozen

Changing a file in `approved/` is a design decision, not an edit.

- **Changes require explicit sign-off**, and a commit message saying **what
  changed and why** — not just that it did.
- **Naming: `<screen>-vN.html`. Never overwrite.** A revision is a new `-vN`
  file, so `add-edit-bird-v1.html` still exists unchanged when
  `add-edit-bird-v2.html` arrives and the two can be compared.
- **Nothing here is edited in passing.** If a spec contradicts the app, or
  another spec, that is raised as a question — never resolved by changing the
  file.

## Versions

| Screen | File | Status |
|---|---|---|
| Sign-in | `approved/sign-in-v1.html` | approved |
| Loft home | `approved/loft-home-v1.html` | approved |
| Bird profile | `approved/bird-profile-v1.html` | approved |
| Design system | `approved/zajil-prototype.html` | Design system reference — loft home, bird profile and sign-in are each superseded by their own approved specs; use the prototype only for tokens, type scale and shared component style. |
| Add/edit bird | `approved/add-edit-bird-v2.html` | **approved — the file the React port implements** |
| Add/edit bird | `approved/add-edit-bird-v1.html` | superseded by v2 (rail side fix) |
| Pedigree tree | `approved/pedigree-tree-v1.html` | approved |
| Races | `approved/races-v1.html` | approved |
| Health | `approved/health-v1.html` | approved |
| Breeding | `approved/breeding-v1.html` | approved |
| Stats | `approved/stats-v1.html` | approved |
| Shared states (component gallery) | `approved/shared-states-v1.html` | approved |

Where two versions of a screen are listed, **the highest `-vN` is the one to
build**. Earlier versions stay in place unchanged so a decision already made
can still be read — that is what "never overwrite" is for.

**Sign-in (`sign-in-v1.html`) — two notes.** The early-access form's
**submission target is not wired**: it is a design placeholder until launch, so
the spec shows the request and the `وصلنا طلبك` acknowledgement without saying
where the request goes. And its `box-shadow` rules are **focus rings**
(`0 0 0 3px var(--brand-tint)` on `:focus`), a sanctioned accessibility pattern
— not the decorative shadow the design kit rules out.

**Races (`races-v1.html`) — the spec DELIBERATELY departs from the app.**
Today the races modal **fails silently**: `js/views/races.js:178` returns
`false` with no message when no bird is chosen, and `:142` returns with no
message when the coordinates will not parse. The spec replaces both with
**visible inline errors** — a `.field.err` state, a per-field `.msg`, a modal
alert banner, and a scroll back to the first bad field. **Implement the spec,
not the current behaviour.** Note it fixes *two* silent failures, not one: the
required-bird case and the unparseable-coordinates case.

**Health (`health-v1.html`) — the spec DELIBERATELY departs from the app, in
three places.** Two are ruled and intended: it adds an **edit path** for health
events (today the row offers only ✕ — `js/views/health.js:39-46` has no edit
button, and `eventDialog` mints a fresh `id: uuid()` at
`js/views/health.js:88`, so the dialog can only ever create), and it adds
**visible inline errors** where the dialog fails silently today
(`js/views/health.js:86` returns `false` with no message). **Implement the
spec, not the current behaviour.**

The third is raised, not resolved: the **التطعيم القادم** panel. It has **no
counterpart in the app and no data to compute it from**. A `healthEvent`
carries only `id, eventType, wholeLoft, birdId, date, medication, notes` — no
interval, no due date — and `medication` is free text, so "the annual PMV" is
not derivable from a record. In the spec the panel is static markup; its only
script is `document.getElementById('next').hidden = …`. Building it needs a
data-model decision (a recurrence interval on the event, or a convention over
`medication`) that has not been made. Flagged for a ruling — not designed
around.

**Breeding (`breeding-v1.html`) — the spec DELIBERATELY differs from today's
app, in three ways. Implement the spec, not the current behaviour.**

1. **Restructured into two levels** — a flat pair **list**, and a pair
   **detail** view holding that pair's rounds and eggs. Today `renderBreeding`
   puts everything on one screen: every pair is a card with its rounds and
   eggs expanded inline (`js/views/breeding.js:113-184`). **This implies a new
   sub-route (e.g. `#/pair/<id>`) that does not exist today** — the app
   resolves only `#/birds`, `#/breeding`, `#/races`, `#/health`, `#/stats`,
   `#/tools` plus `#/bird/`, `#/pedigree/` and `#/cert/`, and there is no
   `#/pair` anywhere in `js/`. Intentional. Note the spec itself models the
   two levels as in-page state (`openPair(id)` / `back()` switching a `view`
   variable), so the routing is the port's to add.
2. **Adds delete for eggs and for rounds** (**حذف البيضة**, **حذف البطن**,
   each with an undo toast). Today both are permanent: there is no delete
   control for either, and the mark-hatched / mark-failed buttons render only
   while `egg.state === 'laid'` (`js/views/breeding.js:209-224`), so a
   mis-tap cannot be walked back.
3. **Adds a visible label to the wean-date input** (**تاريخ الفطام**). Today
   that input renders with no label at all (`js/views/breeding.js:256`).

Unchanged, and worth knowing before porting: pairs still have **no edit
path** — `تعديل` does not appear in the spec, so `season`, `nestBox`,
`startDate`, `acquiredFrom` and `acquiredDate` remain write-once at creation
(`js/views/breeding.js:97-105`), exactly as today.

**Bird profile (`bird-profile-v1.html`) — the flat placeholder fill is
deliberate.** An earlier draft used a gradient on the photo placeholder; this
file **fixes** that, so zero `gradient` is the correct state, not an omission.
Two other copies of this screen exist in the design drops and neither is
archived: the 29,137-byte `zajil-screen-3-bird-profile.html` is identical
apart from three injected lines (a `<template id="__bundler_thumbnail">`
block from the design tool), and the 271,521-byte "standalone" file is a
bundler-wrapped preview.

**Stats (`stats-v1.html`) — the spec DELIBERATELY differs from today's app in
five ways. Implement the spec, not the current behaviour.**

1. **COI honesty.** Birds missing a parent get their own **«نسب غير معروف»**
   band, are **excluded from both the average and the distribution**, and the
   count is stated outright. Today they are silently counted as COI 0
   (`js/engine/coi.js:70` returns `{coi: 0}` when either parent is missing),
   which puts unknown-parentage birds in the «صفر» band and drags the average
   down — in a young loft, where most birds have no recorded parents, that
   makes «متوسط COI» actively misleading.
2. **«حسب السلالة» shows «غير محددة»** rather than dropping strain-less birds.
   Today `js/views/stats.js:61` filters them out before grouping, so the card
   silently totals less than «عدد الطيور» with nothing saying by how much.
   Both breakdown cards now show a total.
3. **A fifth headline tile «غير معروف»**, so the sex tiles reconcile. Today
   there are four tiles and cocks + hens need not equal the total.
4. **A whole-view empty state.** Today an empty loft renders four zeros, six
   zero-height bars and «متوسط COI: 0.00%» with no explanation and no call to
   action.
5. **Two new season cards** — **أداء السباقات** and **التربية** — which have
   no counterpart in the app at all, including a **نسبة الفقس** figure and the
   rule **«لا تُحتسب نتائج التدريب»**.

**Shared states (`shared-states-v1.html`) — NOT a screen.** It is the
canonical spec for the components used across every screen: the sync status
row, toasts, confirm dialogs, validation, the notice banner, empty states,
loading, and the offline media placeholder. **Where any screen spec and this
file disagree about a shared component, THIS file wins.**

Two deliberate differences from today's app:

1. **The delete-bird confirm names the affected relations** («علاقات
   مرتبطة»). Today it names only the bird: `confirm.deleteBird` reads
   «حذف الطير «{name}»؟ سيُفصل عن أبنائه وتُحذف صوره.» The count the spec
   wants is already computable, and is in fact already computed elsewhere —
   `js/views/tools.js:333-338` sums offspring + pairs + race results + health
   events + media for the duplicate finder. The same sum belongs in the
   confirm.
2. **«دون اتصال» is the common failure presentation; the amber «تعذّرت
   المزامنة» is the exception.** This matches how the app actually behaves
   rather than how a naive reading would suggest: `js/db/sync.js:1023-1025`
   maps `sync.err.network` and `sync.err.config` to the calm `offline` state,
   and everything else stays quiet until it outlives `SOFT_FAIL_WINDOW_MS`.
   Only an expired session goes straight to `error`.

**Sanctioned palette extensions:** `#2FBF95` and `#A83223` — solid fills that
need more contrast than the card tints provide. Both appear exactly once, and
they are the only inline colour literals in the file; everything else comes
from the tokens.

**Design contract:** [`ZAJIL-DESIGN-KIT.md`](ZAJIL-DESIGN-KIT.md) — brief,
inventory, responsive rules; brand `#128C6E`.

## drafts/

Working material and stateful `.dc` references. Not authoritative.

| File | What it is |
|---|---|
| `add-edit-bird-states.dc.html` | Interactive states reference: add / edit / sibling modes and validation states. **Depends on `support.js`**, and is **not** the canonical spec — `approved/add-edit-bird-v1.html` is. Useful for seeing what a state looks like, not for deciding what it should be. |
| `pedigree-tree-states.dc.html` | Interactive states reference for the pedigree tree. **Depends on `support.js`**, and is **not** the canonical spec — `approved/pedigree-tree-v1.html` is. |
| `support.js` | Required by both `.dc.html` references above. |

## Not here, deliberately

The earlier certificate-style bird-profile mockup is **obsolete** and is not
archived. `approved/zajil-prototype.html` supersedes it.
