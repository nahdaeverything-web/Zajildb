// tools/gen-example-large.js — writes ../example-loft-large.json (node only).
// A deep teaching loft: 38 birds across 6 generations, built so that every
// genetics feature has something real to show:
//   • outcrossed birds            → COI 0%
//   • double-first-cousin matings → COI 12.5%   (الشيخ, خيال)
//   • father × daughter           → COI 25%     (عاصف)
//   • full-sibling young birds    → pairing them would be 25%+ (the warning)
//   • FCI-ringed birds with qualifying and non-qualifying results
// Deterministic: no Date.now(), no randomness.

import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { haversineMetres, velocityMPM } from '../js/engine/velocity.js';

const LOFT = 'loft-irbid-demo';
const T = '2026-08-01T09:00:00.000Z';
const OWNER = 'لوفت إربد التعليمي';

const birds = [];
const ring = (raw, type = 'national') => {
  const p = raw.split('-');
  return { country: p[0] === 'FCI' ? p[1] : p[0], union: '', year: +p[p.length - 2], serial: p[p.length - 1], raw, type };
};
function bird(id, o) {
  const b = {
    id, rings: [], name: '', sex: 'unknown', hatchDate: '', colour: '', strain: '',
    eyeSign: '', status: 'stock', sireId: null, damId: null, external: false,
    breeder: '', owner: OWNER, acquiredFrom: '', acquiredDate: '', notes: [],
    createdAt: T, updatedAt: T, loftId: LOFT, ...o,
  };
  // mirror js/db.js newBird(): a never-owned ancestor carries the reference
  // status, so the shipped data satisfies the same invariant as live records
  if (b.external) b.status = 'reference';
  birds.push(b);
  return id;
}

// ---------------------------------------------------- G0: imported foundation
const JANSSEN = 'يانسن', VANLOON = 'فان لون', VDA = 'فاندنابيل', SHAMI = 'شامي';
bird('x-remco', { name: 'Remco', sex: 'cock', hatchDate: '2016-03-04', colour: 'أزرق', strain: VDA, eyeSign: 'برتقالية', external: true, owner: '', breeder: 'استيراد — بلجيكا', rings: [ring('BE-2016-6012345')] });
bird('x-anka', { name: 'Anka', sex: 'hen', hatchDate: '2016-04-18', colour: 'أزرق مخطط', strain: VDA, external: true, owner: '', breeder: 'استيراد — بلجيكا', rings: [ring('BE-2016-6012388')] });
bird('x-julius', { name: 'Julius', sex: 'cock', hatchDate: '2017-02-22', colour: 'أشقر', strain: JANSSEN, eyeSign: 'لؤلؤية', external: true, owner: '', breeder: 'استيراد — هولندا', rings: [ring('NL-2017-1180022')] });
bird('x-witpen', { name: 'Witpen', sex: 'hen', hatchDate: '2017-03-30', colour: 'أزرق أبيض الجناح', strain: JANSSEN, external: true, owner: '', breeder: 'استيراد — هولندا', rings: [ring('NL-2017-1180067')] });
bird('x-kasper', { name: 'Kasper', sex: 'cock', hatchDate: '2016-05-11', colour: 'رمادي', strain: VANLOON, external: true, owner: '', breeder: 'استيراد — بلجيكا', rings: [ring('BE-2016-6055501')] });
bird('x-mieke', { name: 'Mieke', sex: 'hen', hatchDate: '2017-04-02', colour: 'رمادي فاتح', strain: VANLOON, external: true, owner: '', breeder: 'استيراد — بلجيكا', rings: [ring('BE-2017-6099210')] });
bird('x-tarek', { name: 'طارق', sex: 'cock', hatchDate: '2018-01-19', colour: 'أحمر', strain: SHAMI, external: true, owner: '', breeder: 'أبو محمد — حلب', rings: [ring('SY-2018-33001')] });
bird('x-najla', { name: 'نجلاء', sex: 'hen', hatchDate: '2018-02-27', colour: 'أبيض', strain: SHAMI, external: true, owner: '', rings: [ring('JO-2018-04120')] });

// ------------------------------------------- G1: first home-bred generation
const G1 = [
  ['g1-amir', 'الأمير', 'cock', '2019-03-12', 'أزرق', VDA, 'x-remco', 'x-anka', 'JO-2019-06001', 'برتقالية'],
  ['g1-zumurruda', 'زمرّدة', 'hen', '2019-04-29', 'أزرق مخطط', VDA, 'x-remco', 'x-anka', 'JO-2019-06002', 'لؤلؤية'],
  ['g1-sultan', 'سلطان', 'cock', '2019-05-08', 'أشقر', JANSSEN, 'x-julius', 'x-witpen', 'JO-2019-06010', 'لؤلؤية'],
  ['g1-yasmin', 'ياسمين', 'hen', '2020-03-21', 'أشقر', JANSSEN, 'x-julius', 'x-witpen', 'JO-2020-07011', ''],
  ['g1-faris', 'الفارس', 'cock', '2020-04-02', 'رمادي', VANLOON, 'x-kasper', 'x-mieke', 'JO-2020-07020', 'برتقالية'],
  ['g1-lama', 'لمى', 'hen', '2020-04-02', 'رمادي', VANLOON, 'x-kasper', 'x-mieke', 'JO-2020-07021', ''],
  ['g1-shahm', 'شهم', 'cock', '2020-05-15', 'أحمر', SHAMI, 'x-tarek', 'x-najla', 'JO-2020-07030', ''],
  ['g1-ghazal', 'غزال', 'hen', '2020-06-01', 'أبيض', SHAMI, 'x-tarek', 'x-najla', 'JO-2020-07031', ''],
];
for (const [id, name, sex, hatch, colour, strain, s, d, r, eye] of G1) {
  bird(id, { name, sex, hatchDate: hatch, colour, strain, eyeSign: eye, status: 'breeder', sireId: s, damId: d, rings: [ring(r)] });
}

// --------------------------------------------------------------------- G2
const G2 = [
  ['g2-muhannad', 'مهنّد', 'cock', '2021-03-18', 'أزرق', `${VDA} × ${JANSSEN}`, 'g1-amir', 'g1-yasmin', 'JO-2021-08001'],
  ['g2-dana', 'دانة', 'hen', '2021-04-06', 'أشقر', `${JANSSEN} × ${VDA}`, 'g1-sultan', 'g1-zumurruda', 'JO-2021-08002'],
  ['g2-saqr', 'صقر الجبل', 'cock', '2021-05-02', 'رمادي', `${VANLOON} × ${SHAMI}`, 'g1-faris', 'g1-ghazal', 'JO-2021-08010'],
  ['g2-nasma', 'نسمة', 'hen', '2022-03-27', 'أحمر رصاصي', `${SHAMI} × ${VANLOON}`, 'g1-shahm', 'g1-lama', 'JO-2022-09011'],
  ['g2-burhan', 'برهان', 'cock', '2022-04-14', 'أزرق', `${VDA} × ${VANLOON}`, 'g1-amir', 'g1-lama', 'JO-2022-09020'],
  ['g2-rima', 'ريما', 'hen', '2022-04-14', 'رمادي', `${VANLOON} × ${VDA}`, 'g1-faris', 'g1-zumurruda', 'JO-2022-09021'],
];
for (const [id, name, sex, hatch, colour, strain, s, d, r] of G2) {
  bird(id, { name, sex, hatchDate: hatch, colour, strain, status: 'breeder', sireId: s, damId: d, rings: [ring(r)] });
}

// ------------------------------- G3: the instructive inbreeding generation
bird('g3-sheikh', {
  name: 'الشيخ', sex: 'cock', hatchDate: '2023-03-09', colour: 'أزرق', strain: `${VDA} × ${JANSSEN}`,
  eyeSign: 'برتقالية غامقة', status: 'breeder', sireId: 'g2-muhannad', damId: 'g2-dana',
  rings: [ring('JO-2023-10001'), ring('FCI-JO-2023-00120', 'FCI')],
  notes: [{ id: 'n-sheikh', at: '2023-06-01T08:00:00.000Z', text: 'تزاوج أولاد عم مزدوج: أبواه مهنّد ودانة يعودان لنفس الجدّين من الطرفين — COI المتوقع ١٢٫٥٪. راقب الخصوبة في الأجيال القادمة.' }],
});
bird('g3-khayal', { name: 'خيال', sex: 'hen', hatchDate: '2023-03-22', colour: 'رمادي', strain: `${VANLOON} × ${SHAMI}`, status: 'breeder', sireId: 'g2-saqr', damId: 'g2-nasma', rings: [ring('JO-2023-10002')] });
bird('g3-marwan', { name: 'مروان', sex: 'cock', hatchDate: '2023-04-11', colour: 'أزرق مخطط', strain: 'مختلط', status: 'breeder', sireId: 'g2-burhan', damId: 'g2-nasma', rings: [ring('JO-2023-10010')] });
bird('g3-noor', { name: 'نور', sex: 'hen', hatchDate: '2023-04-28', colour: 'أشقر', strain: 'مختلط', status: 'breeder', sireId: 'g2-muhannad', damId: 'g2-rima', rings: [ring('JO-2023-10011')] });
bird('g3-jasur', { name: 'جسور', sex: 'cock', hatchDate: '2023-05-14', colour: 'رمادي', strain: 'مختلط', status: 'race team', sireId: 'g2-saqr', damId: 'g2-dana', rings: [ring('JO-2023-10020'), ring('FCI-JO-2023-00121', 'FCI')] });
bird('g3-asif', {
  name: 'عاصف', sex: 'cock', hatchDate: '2023-06-02', colour: 'أحمر', strain: SHAMI,
  status: 'stock', sireId: 'g1-shahm', damId: 'g2-nasma', rings: [ring('JO-2023-10030')],
  notes: [{ id: 'n-asif', at: '2023-07-01T08:00:00.000Z', text: 'تحذير: أبوه شهم هو أيضًا جدّ أمه نسمة — أب × ابنة، COI ٢٥٪. سُجّل للدراسة ولا يُستخدم للتربية.' }],
});

// --------------------------------------------------------------------- G4
bird('g4-malik', { name: 'الملك', sex: 'cock', hatchDate: '2024-03-15', colour: 'أزرق', strain: 'مختلط', status: 'breeder', sireId: 'g3-sheikh', damId: 'g3-khayal', rings: [ring('JO-2024-11001'), ring('FCI-JO-2024-00455', 'FCI')] });
bird('g4-sadim', { name: 'سديم', sex: 'hen', hatchDate: '2024-04-02', colour: 'رمادي', strain: 'مختلط', status: 'breeder', sireId: 'g3-marwan', damId: 'g3-noor', rings: [ring('JO-2024-11002')] });
bird('g4-wisam', { name: 'وسام', sex: 'cock', hatchDate: '2024-04-20', colour: 'رمادي فاتح', strain: 'مختلط', status: 'race team', sireId: 'g3-jasur', damId: 'g2-rima', rings: [ring('JO-2024-11010'), ring('FCI-JO-2024-00456', 'FCI')] });
bird('g4-lulu', { name: 'لؤلؤ', sex: 'hen', hatchDate: '2025-03-08', colour: 'أشقر', strain: 'مختلط', status: 'breeder', sireId: 'g3-sheikh', damId: 'g3-noor', rings: [ring('JO-2025-12001')] });
bird('g4-shihab', { name: 'شهاب', sex: 'cock', hatchDate: '2025-03-24', colour: 'أزرق', strain: 'مختلط', status: 'race team', sireId: 'g3-marwan', damId: 'g3-khayal', rings: [ring('JO-2025-12010'), ring('FCI-JO-2025-00781', 'FCI')] });
bird('g4-bushra', { name: 'بشرى', sex: 'hen', hatchDate: '2025-04-11', colour: 'أحمر', strain: 'مختلط', status: 'breeder', sireId: 'g3-asif', damId: 'g2-dana', rings: [ring('JO-2025-12011')] });

// -------------------------------------------------- G5: 2026 young birds
bird('g5-faris26', { name: 'فارس ٢٦', sex: 'cock', hatchDate: '2026-03-14', colour: 'أزرق', strain: 'مختلط', status: 'young bird', sireId: 'g4-malik', damId: 'g4-sadim', rings: [ring('JO-2026-13001'), ring('FCI-JO-2026-01120', 'FCI')] });
bird('g5-najma26', { name: 'نجمة ٢٦', sex: 'hen', hatchDate: '2026-03-15', colour: 'أزرق مخطط', strain: 'مختلط', status: 'young bird', sireId: 'g4-malik', damId: 'g4-sadim', rings: [ring('JO-2026-13002')] });
bird('g5-sahm26', { name: 'سهم ٢٦', sex: 'cock', hatchDate: '2026-04-02', colour: 'رمادي', strain: 'مختلط', status: 'young bird', sireId: 'g4-wisam', damId: 'g4-lulu', rings: [ring('JO-2026-13010')] });
bird('g5-ghaima26', { name: 'غيمة ٢٦', sex: 'hen', hatchDate: '2026-04-19', colour: 'أحمر', strain: 'مختلط', status: 'young bird', sireId: 'g4-shihab', damId: 'g4-bushra', rings: [ring('JO-2026-13011')] });

// ------------------------------------------------------------------ races
const IRBID = { lat: 32.5556, lon: 35.8500 };
const POINTS = {
  aqaba: { name: 'العقبة', lat: 29.5321, lon: 35.0063 },
  maan: { name: 'معان', lat: 30.1962, lon: 35.7340 },
  jafr: { name: 'الجفر', lat: 30.3427, lon: 36.1470 },
  quweira: { name: 'القويرة', lat: 29.8030, lon: 35.3120 },
  azraq: { name: 'الأزرق', lat: 31.8333, lon: 36.8167 },
};
let rid = 0;
function race(birdId, key, date, relH, relM, arrH, arrM, o = {}) {
  const pt = POINTS[key];
  const releaseTime = `${date}T${String(relH).padStart(2, '0')}:${String(relM).padStart(2, '0')}:00`;
  const arrivalTime = `${date}T${String(arrH).padStart(2, '0')}:${String(arrM).padStart(2, '0')}:00`;
  return {
    id: 'lr-' + (++rid), birdId, date, raceType: 'club',
    organisation: 'نادي إربد للحمام الزاجل', country: 'JO',
    raceName: 'سباق ' + pt.name, releasePoint: pt, loftPoint: IRBID,
    releaseTime, arrivalTime,
    distanceKm: Math.round(haversineMetres(pt, IRBID) / 100) / 10,
    velocity: Math.round(velocityMPM(pt, IRBID, releaseTime, arrivalTime)),
    position: null, fanciersEntered: 16, birdsEntered: 118,
    loftId: LOFT, updatedAt: T, ...o,
  };
}
const NAT = { raceType: 'national', organisation: 'الاتحاد الأردني لهواة الحمام الزاجل', fanciersEntered: 46, birdsEntered: 412 };
const FED = { raceType: 'federation', organisation: 'الاتحاد الأردني لهواة الحمام الزاجل', fanciersEntered: 24, birdsEntered: 187 };

const raceResults = [
  // 2025 old birds — جسور and وسام carry the team
  race('g3-jasur', 'azraq', '2025-03-29', 7, 0, 8, 44, { position: 5 }),
  race('g3-jasur', 'jafr', '2025-04-19', 6, 30, 10, 12, { position: 2 }),
  race('g3-jasur', 'aqaba', '2025-05-24', 5, 45, 12, 8, { position: 6, raceName: 'السباق الوطني — العقبة', ...NAT }),
  race('g4-wisam', 'azraq', '2025-03-29', 7, 0, 8, 51, { position: 9 }),
  race('g4-wisam', 'maan', '2025-05-03', 6, 15, 11, 3, { position: 1, raceName: 'بطولة الاتحاد — معان', ...FED }),
  race('g4-wisam', 'aqaba', '2025-05-24', 5, 45, 12, 30, { position: 14, raceName: 'السباق الوطني — العقبة', ...NAT }),
  race('g3-marwan', 'jafr', '2025-04-19', 6, 30, 10, 58, { position: 24 }),
  // 2026 season — شهاب peaks, young birds start
  race('g4-shihab', 'azraq', '2026-03-28', 7, 0, 8, 39, { position: 1 }),
  race('g4-shihab', 'quweira', '2026-04-25', 6, 0, 12, 2, { position: 3, raceName: 'بطولة الاتحاد — القويرة', ...FED }),
  race('g4-shihab', 'aqaba', '2026-05-23', 5, 40, 12, 15, { position: 8, raceName: 'السباق الوطني — العقبة', ...NAT }),
  race('g4-wisam', 'quweira', '2026-04-25', 6, 0, 12, 26, { position: 11, raceName: 'بطولة الاتحاد — القويرة', ...FED }),
  race('g5-faris26', 'azraq', '2026-06-13', 6, 45, 8, 30, { position: 4 }),
  race('g5-faris26', 'jafr', '2026-07-04', 6, 20, 10, 6, { position: 2 }),
  race('g5-sahm26', 'azraq', '2026-06-13', 6, 45, 8, 58, { position: 17 }),
  race('g5-najma26', 'azraq', '2026-06-13', 6, 45, 9, 12, { position: 31 }),
  // training tosses — never FCI-eligible, good for showing the checker
  race('g5-ghaima26', 'azraq', '2026-06-06', 7, 30, 9, 2, { raceType: 'training', raceName: 'تدريب الأزرق', fanciersEntered: 1, birdsEntered: 24 }),
  race('g5-faris26', 'azraq', '2026-06-06', 7, 30, 8, 47, { raceType: 'training', raceName: 'تدريب الأزرق', fanciersEntered: 1, birdsEntered: 24 }),
];

// ------------------------------------------------------------------ pairs
const pairs = [
  {
    id: 'lp-malik-sadim-26', sireId: 'g4-malik', damId: 'g4-sadim', season: '2026',
    nestBox: '1', status: 'active', startDate: '2026-01-25', loftId: LOFT, updatedAt: T,
    rounds: [
      { id: 'lp1r1', number: 1, eggs: [
        { id: 'lp1r1e1', laidDate: '2026-02-21', state: 'hatched', hatchDate: '2026-03-14', chickId: 'g5-faris26', ringed: true, weaned: true, weanDate: '2026-04-09' },
        { id: 'lp1r1e2', laidDate: '2026-02-23', state: 'hatched', hatchDate: '2026-03-15', chickId: 'g5-najma26', ringed: true, weaned: true, weanDate: '2026-04-09' },
      ] },
      // second round mid-cycle: drive hatch → ring → wean yourself
      { id: 'lp1r2', number: 2, eggs: [
        { id: 'lp1r2e1', laidDate: '2026-08-14', state: 'laid' },
        { id: 'lp1r2e2', laidDate: '2026-08-16', state: 'laid' },
      ] },
    ],
  },
  {
    id: 'lp-wisam-lulu-26', sireId: 'g4-wisam', damId: 'g4-lulu', season: '2026',
    nestBox: '4', status: 'active', startDate: '2026-02-10', loftId: LOFT, updatedAt: T,
    rounds: [{ id: 'lp2r1', number: 1, eggs: [
      { id: 'lp2r1e1', laidDate: '2026-03-11', state: 'hatched', hatchDate: '2026-04-02', chickId: 'g5-sahm26', ringed: true, weaned: true, weanDate: '2026-04-28' },
      { id: 'lp2r1e2', laidDate: '2026-03-13', state: 'failed' },
    ] }],
  },
  {
    id: 'lp-shihab-bushra-26', sireId: 'g4-shihab', damId: 'g4-bushra', season: '2026',
    nestBox: '6', status: 'active', startDate: '2026-03-01', loftId: LOFT, updatedAt: T,
    rounds: [{ id: 'lp3r1', number: 1, eggs: [
      { id: 'lp3r1e1', laidDate: '2026-03-28', state: 'hatched', hatchDate: '2026-04-19', chickId: 'g5-ghaima26', ringed: true, weaned: true, weanDate: '2026-05-15' },
      // hatched but not yet ringed: shows the "ring chick" step
      { id: 'lp3r1e2', laidDate: '2026-03-30', state: 'hatched', hatchDate: '2026-04-20', chickId: null, ringed: false, weaned: false },
    ] }],
  },
  {
    id: 'lp-sheikh-khayal-24', sireId: 'g3-sheikh', damId: 'g3-khayal', season: '2024',
    nestBox: '1', status: 'separated', startDate: '2024-01-20', loftId: LOFT, updatedAt: T,
    rounds: [{ id: 'lp4r1', number: 1, eggs: [
      { id: 'lp4r1e1', laidDate: '2024-02-22', state: 'hatched', hatchDate: '2024-03-15', chickId: 'g4-malik', ringed: true, weaned: true, weanDate: '2024-04-10' },
    ] }],
  },
  {
    id: 'lp-marwan-noor-24', sireId: 'g3-marwan', damId: 'g3-noor', season: '2024',
    nestBox: '3', status: 'separated', startDate: '2024-01-20', loftId: LOFT, updatedAt: T,
    rounds: [{ id: 'lp5r1', number: 1, eggs: [
      { id: 'lp5r1e1', laidDate: '2024-03-10', state: 'hatched', hatchDate: '2024-04-02', chickId: 'g4-sadim', ringed: true, weaned: true, weanDate: '2024-04-29' },
    ] }],
  },
];

// ----------------------------------------------------------------- health
const healthEvents = [
  { id: 'lh-1', eventType: 'vaccination', wholeLoft: true, birdId: null, date: '2026-01-15', medication: 'لقاح باراميكسو PMV — Colombovac', notes: 'كامل اللوفت قبل موسم التزاوج', loftId: LOFT, updatedAt: T },
  { id: 'lh-2', eventType: 'treatment', wholeLoft: true, birdId: null, date: '2026-03-02', medication: 'رونيدازول — وقاية من الترايكوموناس', notes: 'كورس ٥ أيام في ماء الشرب', loftId: LOFT, updatedAt: T },
  { id: 'lh-3', eventType: 'vaccination', wholeLoft: true, birdId: null, date: '2026-05-10', medication: 'لقاح الجدري', notes: 'للفراخ قبل موسم السباق', loftId: LOFT, updatedAt: T },
  { id: 'lh-4', eventType: 'illness', wholeLoft: false, birdId: 'g5-najma26', date: '2026-06-20', medication: '', notes: 'خمول بعد سباق الأزرق — عزل ٤ أيام، تعافت', loftId: LOFT, updatedAt: T },
  { id: 'lh-5', eventType: 'treatment', wholeLoft: false, birdId: 'g5-najma26', date: '2026-06-21', medication: 'أمبروليوم — كوكسيديا', notes: '', loftId: LOFT, updatedAt: T },
  { id: 'lh-6', eventType: 'check', wholeLoft: false, birdId: 'g4-shihab', date: '2026-03-20', medication: '', notes: 'فحص ما قبل السباق — ريش وعضلات ممتازة', loftId: LOFT, updatedAt: T },
  { id: 'lh-7', eventType: 'treatment', wholeLoft: true, birdId: null, date: '2025-09-14', medication: 'علاج الديدان — فينبيندازول', notes: 'بعد موسم السباق', loftId: LOFT, updatedAt: T },
];

const payload = {
  format: 'zajil-export', version: 1, kind: 'example-large', exportedAt: T,
  lofts: [{
    id: LOFT, name: OWNER, location: 'إربد، الأردن',
    statuses: ['breeder', 'race team', 'young bird', 'stock', 'sold', 'lost', 'dead'],
    createdAt: '2019-01-01T00:00:00.000Z', updatedAt: T,
  }],
  birds, pairs, raceResults, healthEvents, media: [],
};

const out = join(dirname(fileURLToPath(import.meta.url)), '..', 'example-loft-large.json');
writeFileSync(out, JSON.stringify(payload, null, 1));
console.log(`example-loft-large.json: ${birds.length} birds, ${pairs.length} pairs, ${raceResults.length} results, ${healthEvents.length} health events`);
