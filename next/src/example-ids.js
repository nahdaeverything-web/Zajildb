// src/example-ids.js — THE SHIPPED DATASETS' OWN IDS (RF-22, RULED 2026-11-01): a fixed, known set.
//
// Example-data membership is decided by these and by nothing else — not by the loft a record is filed in, and not by
// the shape of its id. Listed as the generators' readable keys (tools/gen-sample.js, tools/gen-example-large.js),
// which ARE the ids the datasets shipped with before v1.9.1; since v1.9.1 each ships as the uuid5 of its key
// (tools/idmap.js). Both generations are on real devices (RF-17), so src/example-data.js exampleIds() holds both:
// every key here, and its uuid5. Read from the datasets at commit 823db27^ (keys) and checked against the shipped
// files (uuid5) by tests/e2e/screens/example_remove.py — a key added to a generator and not to this list fails there.
export const EXAMPLE_ID_KEYS = Object.freeze({
  lofts: Object.freeze([   // 2
    'loft-irbid-demo', 'loft-zarqa',
  ]),
  birds: Object.freeze([   // 58
    'x-remco', 'x-anka', 'x-julius', 'x-witpen', 'x-kasper', 'x-mieke', 'x-tarek', 'x-najla', 'g1-amir',
    'g1-zumurruda', 'g1-sultan', 'g1-yasmin', 'g1-faris', 'g1-lama', 'g1-shahm', 'g1-ghazal', 'g2-muhannad',
    'g2-dana', 'g2-saqr', 'g2-nasma', 'g2-burhan', 'g2-rima', 'g3-sheikh', 'g3-khayal', 'g3-marwan', 'g3-noor',
    'g3-jasur', 'g3-asif', 'g4-malik', 'g4-sadim', 'g4-wisam', 'g4-lulu', 'g4-shihab', 'g4-bushra', 'g5-faris26',
    'g5-najma26', 'g5-sahm26', 'g5-ghaima26', 'e-gouden', 'e-blauwe', 'f-saqr', 'f-rih', 'b-barq', 'u-malika',
    'c-sahm', 'c-shaqra', 'f-raad', 'f-ghaima', 'c-amal', 'c-fajr', 'y-najm', 'y-lulu', 'y-wadhah', 'y-yaqut',
    'y-hudhud', 'o-asifa', 'o-tair', 'o-dura',
  ]),
  pairs: Object.freeze([   // 9
    'lp-malik-sadim-26', 'lp-wisam-lulu-26', 'lp-shihab-bushra-26', 'lp-sheikh-khayal-24', 'lp-marwan-noor-24',
    'p-barq-malika-26', 'p-sahm-amal-26', 'p-wadhah-asifa-26', 'p-raad-ghaima-23',
  ]),
  raceResults: Object.freeze([   // 29
    'lr-1', 'lr-2', 'lr-3', 'lr-4', 'lr-5', 'lr-6', 'lr-7', 'lr-8', 'lr-9', 'lr-10', 'lr-11', 'lr-12', 'lr-13',
    'lr-14', 'lr-15', 'lr-16', 'lr-17', 'r-1', 'r-2', 'r-3', 'r-4', 'r-5', 'r-6', 'r-7', 'r-8', 'r-9', 'r-10',
    'r-11', 'r-12',
  ]),
  healthEvents: Object.freeze([   // 13
    'lh-1', 'lh-2', 'lh-3', 'lh-4', 'lh-5', 'lh-6', 'lh-7', 'h-1', 'h-2', 'h-3', 'h-4', 'h-5', 'h-6',
  ]),
});
