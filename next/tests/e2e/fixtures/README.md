# Test fixtures

- `example-loft-large.PRE-v1.9.1.json` — the full teaching loft as the datasets shipped it BEFORE
  v1.9.1 rewrote every dataset id to uuid5: the ids are the readable keys (`loft-irbid-demo`,
  `x-remco`, …) and the loft record carries no `loftId` field. Produced 2026-10-12 by running
  `tools/gen-example-large.js` with `remapIds` replaced by the identity
  (`(p) => ({ payload: p, map: new Map() })`) and the output path redirected; 68 rows, 67 with a
  `loftId`. It reproduces the real dev project's state measured in ROOT-FINDINGS RF-17, where a
  device that loaded the teaching loft before and after v1.9.1 pushed both generations.
  `screens/example_remove.py` merge-imports it beside the shipped file so one device holds both.

- `picked-3000x2000.jpg` — a SYNTHETIC 3000×2000 JPEG (generated 2026-11-17 with PIL from a seeded random pattern, 2.1 MB). No person, no place, no camera. Used by `screens/bird_form.py` for the picked-photo preview.

- `picked-second.png` — a SYNTHETIC 8×6 PNG of one flat colour (written 2026-11-18 byte by byte with zlib; no camera, no person). Used by `screens/bird_form.py` as the second picked photo, so the strip's two picked tiles can be told apart by their decoded size.
