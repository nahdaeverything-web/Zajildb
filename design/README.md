# Design archive

**These are specifications, not application code.** Nothing in this folder is
loaded, precached, imported, or served by Zajil. `sw.js` does not list it,
`index.html` does not reference it, and no module under `js/` imports from it.
That isolation is checked, not assumed:

```bash
grep -rn "design/" sw.js js/ index.html      # expect no matches
```

The app is vanilla ES modules with no build step. A design file here may use
whatever it likes — inline styles, its own fonts, a support script — because it
never runs alongside the app.

## Layout

| | |
|---|---|
| `approved/` | **Frozen.** The specification the app is measured against. |
| `drafts/` | Working material and stateful references. Not authoritative. |
| `ZAJIL-DESIGN-KIT.md` | The design contract: brief, inventory, responsive rules. |

## approved/ is frozen

A file in `approved/` is the agreed answer to "what should this screen be?".
Changing one is a design decision, not an edit.

- **Changes need sign-off**, and a commit message saying *why* the design
  changed — not just that it did.
- **Never overwrite.** A new version is a new file: `<screen>-vN.html`.
  `add-edit-bird-v1.html` stays exactly as it is when `add-edit-bird-v2.html`
  arrives, so the two can be compared and so a decision already made is not
  quietly replaced.
- **Nothing here is edited in passing.** If a spec contradicts the app, or
  contradicts another spec, that is raised as a question — it is not resolved by
  changing the file.

## Versions

| File | What it is |
|---|---|
| `approved/zajil-prototype.html` | **The v3 design system anchor** — brand `#128C6E`. Sign-in, loft home, bird profile. The reference for colour, type, spacing and component shape across every other screen. |
| `approved/add-edit-bird-v1.html` | **The canonical add/edit bird spec.** Self-contained and corrected; this is the one to build against. |

## drafts/

| File | What it is |
|---|---|
| `add-edit-bird-states.dc.html` | Interactive states reference: add / edit / sibling modes and validation states. **Depends on `support.js`** and is not the canonical spec — `approved/add-edit-bird-v1.html` is. Useful for seeing what each state looks like, not for deciding what it should be. |
| `support.js` | Required by the `.dc.html` reference above. |

## Not here, deliberately

The earlier certificate-style bird-profile mockup is **obsolete** and is not
archived. `approved/zajil-prototype.html` supersedes it.
