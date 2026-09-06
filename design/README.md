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
| Design system (sign-in, loft home, bird profile) | `approved/zajil-prototype.html` | approved |
| Add/edit bird | `approved/add-edit-bird-v2.html` | **approved — the file the React port implements** |
| Add/edit bird | `approved/add-edit-bird-v1.html` | superseded by v2 (rail side fix) |
| Pedigree tree | `approved/pedigree-tree-v1.html` | approved |
| Races | `approved/races-v1.html` | approved |
| Health | `approved/health-v1.html` | approved |

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
