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
| Design system (sign-in, loft home, bird profile) | `approved/zajil-prototype.html` | approved |
| Add/edit bird | `approved/add-edit-bird-v2.html` | **approved — the file the React port implements** |
| Add/edit bird | `approved/add-edit-bird-v1.html` | superseded by v2 (rail side fix) |
| Pedigree tree | `approved/pedigree-tree-v1.html` | approved |

Where two versions of a screen are listed, **the highest `-vN` is the one to
build**. Earlier versions stay in place unchanged so a decision already made
can still be read — that is what "never overwrite" is for.

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
