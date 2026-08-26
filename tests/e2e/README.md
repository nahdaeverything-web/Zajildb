# Browser (end-to-end) suites

These drive a real Chromium against a served copy of the app. They are the
counterpart to `tests/run.js`: the node suite proves the **engine** maths, these
prove the **application** — routing, IndexedDB, RTL geometry, the service
worker, and offline behaviour.

They caught several real defects that unit tests could not: the picker that
silently detached a parent link, the page scrolling behind open dialogs, the
service worker deleting sibling projects' caches, and object URLs pinning every
photo for the life of the tab.

## Requirements

Not part of the app, and deliberately not a project dependency — the app itself
still has **zero** dependencies and no build step.

```bash
pip install playwright
playwright install chromium
```

## Running

```bash
# from the repo root, in one terminal:
python3 -m http.server 8123

# in another:
python3 tests/e2e/run_all.py          # all local suites
python3 tests/e2e/run_all.py --live   # ALSO run live_deployment.py
python3 tests/e2e/core_flows.py       # a single suite
```

Each suite prints `✓`/`✗` per assertion and exits non-zero on failure.

### Gotchas worth knowing before writing a suite

- **`wait_until='networkidle'` hangs** — the service worker holds the
  connection open, so the page never goes idle. Use `'load'` plus an explicit
  `wait_for_timeout`.
- **To seed a database without booting the app**, navigate to a same-origin
  URL that isn't the app (e.g. `BASE + '__seed__'`, which 404s). Loading `BASE`
  runs `initDB()` first, which creates a current-version database and makes
  opening an older version block forever.

### One suite is opt-in

**`live_deployment.py` does not run by default.** It needs the internet, and it
tests the **deployed** build at the GitHub Pages URL — not your working tree —
so a green result there says nothing about uncommitted changes, and a red one
may only mean the deploy is behind `main`.

`run_all.py` prints it as `[skip]` with the reason rather than leaving it
silently absent, so the suite list in the output always accounts for every file
in this directory. Run it with `--live`, or directly:

```bash
python3 tests/e2e/live_deployment.py
ZAJIL_LIVE_URL=https://example.github.io/zajil/ python3 tests/e2e/live_deployment.py
```

| Suite | Covers |
|---|---|
| `core_flows.py` | register, search, COI on a bird page, **RTL mirroring proven geometrically**, certificate, dev panel, breeding/races/stats |
| `example_data.py` | bundled example loaders, sex chips, the add-sibling flow |
| `entry_ergonomics.py` | rings-first form, save-and-add-another carry-over, ring-year hint, Enter guard, history replace |
| `teaching_loft.py` | the 38-bird / 6-generation dataset end to end |
| `picker_duplicates.py` | the bird picker must never clone an existing record |
| `picker_guards.py` | filter/exact-match interaction, Eastern-Arabic ring digits, onPick(null) propagation |
| `ownership.py` | external vs owned, the register ownership filter, pair provenance, link-existing-bird |
| `data_loss.py` | the four data-loss defects fixed in v1.6, each against its exact trigger |
| `subpath_hosting.py` | the app served from a subdirectory (GitHub Pages layout), offline included |
| `service_worker.py` | cache namespacing (must not wipe sibling projects), offline reload |
| `live_deployment.py` | the deployed site: HTTPS, SW scope, installability, offline |

## `diagnostics/`

Investigation scripts, not pass/fail suites — they print measurements. Kept
because they are how the scroll-jump bug was actually diagnosed:
`modaljump.py` (scroll position across a dialog's lifecycle), `shrink.py`
(re-render shrinking the page), `scrolltest.py` (distinguishes real scroll jumps
from Playwright's own scroll-into-view artifact), `tabmem.py`, `deljump.py`,
`sweep.py` (clicks every control on every route across three viewports).
