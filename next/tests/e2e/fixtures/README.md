# Test fixtures

- `example-loft-large.PRE-v1.9.1.json` — the full teaching loft as the datasets shipped it BEFORE
  v1.9.1 rewrote every dataset id to uuid5: the ids are the readable keys (`loft-irbid-demo`,
  `x-remco`, …) and the loft record carries no `loftId` field. Produced 2026-10-12 by running
  `tools/gen-example-large.js` with `remapIds` replaced by the identity
  (`(p) => ({ payload: p, map: new Map() })`) and the output path redirected; 68 rows, 67 with a
  `loftId`. It reproduces the real dev project's state measured in ROOT-FINDINGS RF-17, where a
  device that loaded the teaching loft before and after v1.9.1 pushed both generations.
  `screens/example_remove.py` merge-imports it beside the shipped file so one device holds both.
