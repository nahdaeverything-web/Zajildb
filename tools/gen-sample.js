// tools/gen-sample.js — writes ../sample-data.json (node only).
// A realistic Jordanian loft with a HAND-VERIFIED inbreeding family:
//   • "برق" (Barq) is the offspring of full siblings → COI exactly 0.25
//   • pairing his two children "سهم" × "شقراء" would give COI 0.28125
// Both worked by hand in ENGINE.md and asserted by tests/sample.test.js.

import { writeFileSync } from 'node:fs';
import { remapIds } from './idmap.js';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { haversineMetres, velocityMPM } from '../js/engine/velocity.js';

const LOFT = 'loft-zarqa';
const T = '2026-08-01T09:00:00.000Z'; // fixed updatedAt for determinism

const bird = (id, o) => withStatus({
  id, rings: [], name: '', sex: 'unknown', hatchDate: '', colour: '', strain: '',
  eyeSign: '', status: 'stock', sireId: null, damId: null, external: false,
  breeder: '', owner: 'لوفت الزرقاء', acquiredFrom: '', acquiredDate: '',
  notes: [], createdAt: T, updatedAt: T, loftId: LOFT, ...o,
});

// mirror js/db.js newBird(): a never-owned ancestor carries the reference
// status, so the shipped data satisfies the same invariant as live records
function withStatus(b) {
  if (b.external) b.status = 'reference';
  return b;
}
const ring = (raw, type = 'national') => {
  const parts = raw.split('-');
  return { country: parts[0] === 'FCI' ? parts[1] : parts[0], union: '', year: +(parts[parts.length - 2]), serial: parts[parts.length - 1], raw, type };
};

const birds = [
  // --- external Belgian foundation (never owned; still first-class records)
  bird('e-gouden', { name: 'Gouden 47', sex: 'cock', hatchDate: '2018-03-02', colour: 'أزرق', strain: 'يانسن', external: true, breeder: 'استيراد — بلجيكا', owner: '', rings: [ring('BE-2018-3054047')] }),
  bird('e-blauwe', { name: 'Blauwe Duivin', sex: 'hen', hatchDate: '2018-04-11', colour: 'أزرق مخطط', strain: 'يانسن', external: true, breeder: 'استيراد — بلجيكا', owner: '', rings: [ring('BE-2018-3054112')] }),

  // --- founders: FULL SIBLINGS (both from Gouden 47 × Blauwe Duivin)
  bird('f-saqr', { name: 'الصقر', sex: 'cock', hatchDate: '2020-03-14', colour: 'أزرق', strain: 'يانسن', eyeSign: 'برتقالية', status: 'breeder', sireId: 'e-gouden', damId: 'e-blauwe', acquiredFrom: 'مزاد عمّان', acquiredDate: '2020-09-20', rings: [ring('JO-2020-10231')] }),
  bird('f-rih', { name: 'الريح', sex: 'hen', hatchDate: '2020-05-02', colour: 'أزرق مخطط', strain: 'يانسن', eyeSign: 'لؤلؤية', status: 'breeder', sireId: 'e-gouden', damId: 'e-blauwe', acquiredFrom: 'مزاد عمّان', acquiredDate: '2020-09-20', rings: [ring('JO-2020-10245')] }),

  // --- HAND-VERIFIED CASE 1: full-sib mating → COI = 0.25 exactly
  bird('b-barq', {
    name: 'برق', sex: 'cock', hatchDate: '2022-04-08', colour: 'أزرق', strain: 'يانسن',
    eyeSign: 'برتقالية غامقة', status: 'breeder', sireId: 'f-saqr', damId: 'f-rih',
    rings: [ring('JO-2022-20117'), ring('FCI-JO-2023-00871', 'FCI')],
    notes: [{ id: 'n1', at: '2023-11-05T10:00:00.000Z', text: 'حالة تحقق يدوي: أبوه وأمه أشقاء — معامل التربية الداخلية 25٪ بالضبط. الحلقة الدولية FCI-JO-2023-00871.' }],
  }),

  // --- unrelated Van Loon hen
  bird('u-malika', { name: 'الملكة', sex: 'hen', hatchDate: '2019-02-27', colour: 'رمادي', strain: 'فان لون', eyeSign: 'لؤلؤية', status: 'breeder', acquiredFrom: 'نادي الزرقاء', acquiredDate: '2021-01-15', rings: [ring('JO-2019-08812')] }),

  // --- Barq × Malika offspring (full sibs; pairing them = 0.28125, case 2)
  bird('c-sahm', { name: 'سهم', sex: 'cock', hatchDate: '2024-03-19', colour: 'أزرق', strain: 'يانسن', status: 'race team', sireId: 'b-barq', damId: 'u-malika', rings: [ring('JO-2024-31002'), ring('FCI-JO-2024-01455', 'FCI')] }),
  bird('c-shaqra', { name: 'شقراء', sex: 'hen', hatchDate: '2024-03-19', colour: 'أشقر', strain: 'يانسن', status: 'race team', sireId: 'b-barq', damId: 'u-malika', rings: [ring('JO-2024-31003')] }),

  // --- second breeding line (local Syrian strain)
  bird('f-raad', { name: 'رعد', sex: 'cock', hatchDate: '2021-06-11', colour: 'أحمر', strain: 'شامي', status: 'breeder', acquiredFrom: 'حلب — أبو محمد', acquiredDate: '2022-03-02', rings: [ring('SY-2021-44210')] }),
  bird('f-ghaima', { name: 'غيمة', sex: 'hen', hatchDate: '2021-08-01', colour: 'أبيض', strain: 'شامي', status: 'breeder', rings: [ring('JO-2021-15530')] }),
  bird('c-amal', { name: 'أمل', sex: 'hen', hatchDate: '2023-04-02', colour: 'أحمر رصاصي', strain: 'شامي', status: 'breeder', sireId: 'f-raad', damId: 'f-ghaima', rings: [ring('JO-2023-22871')] }),
  bird('c-fajr', { name: 'فجر', sex: 'cock', hatchDate: '2023-04-02', colour: 'أحمر', strain: 'شامي', status: 'race team', sireId: 'f-raad', damId: 'f-ghaima', rings: [ring('JO-2023-22872')] }),

  // --- cross line: Sahm's race mates / 2025 young birds (Barq grandchildren)
  bird('y-najm', { name: 'نجم', sex: 'cock', hatchDate: '2025-02-21', colour: 'أزرق', strain: 'يانسن × شامي', status: 'race team', sireId: 'c-sahm', damId: 'c-amal', rings: [ring('JO-2025-40118'), ring('FCI-JO-2025-02201', 'FCI')] }),
  bird('y-lulu', { name: 'لؤلؤة', sex: 'hen', hatchDate: '2025-02-21', colour: 'رمادي فاتح', strain: 'يانسن × شامي', status: 'young bird', sireId: 'c-sahm', damId: 'c-amal', rings: [ring('JO-2025-40119')] }),
  bird('y-wadhah', { name: 'وضاح', sex: 'cock', hatchDate: '2025-04-05', colour: 'أبيض', strain: 'يانسن × شامي', status: 'young bird', sireId: 'c-sahm', damId: 'c-amal', rings: [ring('JO-2025-40230')] }),

  // --- 2026 young birds from Barq × Malika (second use of the pair)
  bird('y-yaqut', { name: 'ياقوت', sex: 'unknown', hatchDate: '2026-03-11', colour: 'أزرق', strain: 'يانسن', status: 'young bird', sireId: 'b-barq', damId: 'u-malika', rings: [ring('JO-2026-51007')] }),
  bird('y-hudhud', { name: 'هدهد', sex: 'unknown', hatchDate: '2026-03-12', colour: 'أزرق مخطط', strain: 'يانسن', status: 'young bird', sireId: 'b-barq', damId: 'u-malika', rings: [ring('JO-2026-51008')] }),

  // --- others for register realism
  bird('o-asifa', { name: 'عاصفة', sex: 'hen', hatchDate: '2022-05-30', colour: 'أسود', strain: 'محلي', status: 'stock', rings: [ring('JO-2022-20940')] }),
  bird('o-tair', { name: 'الطيار', sex: 'cock', hatchDate: '2020-07-14', colour: 'أزرق', strain: 'محلي', status: 'lost', rings: [ring('JO-2020-11602')], notes: [{ id: 'n2', at: '2025-06-08T14:00:00.000Z', text: 'فُقد في سباق الجفر 2025-06-07، الرقم JO-2020-11602 — بلاغ للنادي.' }] }),
  bird('o-dura', { name: 'درّة', sex: 'hen', hatchDate: '2018-03-25', colour: 'رمادي', strain: 'فان لون', status: 'dead', rings: [ring('JO-2018-05233')] }),
];

// ------------------------------------------------------------------- races
const ZARQA = { lat: 32.0728, lon: 36.0876 };
const POINTS = {
  aqaba: { name: 'العقبة', lat: 29.5321, lon: 35.0063 },
  maan: { name: 'معان', lat: 30.1962, lon: 35.7340 },
  jafr: { name: 'الجفر', lat: 30.3427, lon: 36.1470 },
  quweira: { name: 'القويرة', lat: 29.8030, lon: 35.3120 },
};
let rid = 0;
function race(birdId, pointKey, date, relH, relM, arrH, arrM, o = {}) {
  const p = POINTS[pointKey];
  const releaseTime = `${date}T${String(relH).padStart(2, '0')}:${String(relM).padStart(2, '0')}:00`;
  const arrivalTime = `${date}T${String(arrH).padStart(2, '0')}:${String(arrM).padStart(2, '0')}:00`;
  const distanceKm = Math.round(haversineMetres(p, ZARQA) / 100) / 10;
  const velocity = Math.round(velocityMPM(p, ZARQA, releaseTime, arrivalTime));
  return {
    id: 'r-' + (++rid), birdId, date, raceType: 'club', organisation: 'نادي الزرقاء للحمام الزاجل',
    country: 'JO', raceName: 'سباق ' + p.name, releasePoint: p, loftPoint: ZARQA,
    releaseTime, arrivalTime, distanceKm, velocity,
    position: null, fanciersEntered: 14, birdsEntered: 96,
    loftId: LOFT, updatedAt: T, ...o,
  };
}

const raceResults = [
  // 2025 old-bird series — سهم strong season; federation race qualifies for FCI
  race('c-sahm', 'quweira', '2025-04-12', 6, 30, 10, 4, { position: 3 }),
  race('c-sahm', 'maan', '2025-04-26', 6, 15, 9, 2, { position: 1, raceName: 'سباق معان الربيعي' }),
  race('c-sahm', 'aqaba', '2025-05-17', 6, 0, 10, 41, {
    position: 2, raceType: 'federation', raceName: 'بطولة الاتحاد — العقبة',
    organisation: 'الاتحاد الأردني لهواة الحمام الزاجل', fanciersEntered: 27, birdsEntered: 214,
  }),
  race('c-fajr', 'quweira', '2025-04-12', 6, 30, 10, 22, { position: 11 }),
  race('c-fajr', 'aqaba', '2025-05-17', 6, 0, 11, 5, {
    position: 19, raceType: 'federation', raceName: 'بطولة الاتحاد — العقبة',
    organisation: 'الاتحاد الأردني لهواة الحمام الزاجل', fanciersEntered: 27, birdsEntered: 214,
  }),
  race('o-tair', 'jafr', '2025-06-07', 5, 45, 9, 30, { position: null, raceName: 'سباق الجفر — فُقد الطير' }),
  // 2026 young-bird series — نجم the star; national race FCI-qualifying
  race('y-najm', 'quweira', '2026-04-04', 6, 20, 9, 58, { position: 2 }),
  race('y-najm', 'maan', '2026-04-18', 6, 10, 8, 51, { position: 1 }),
  race('y-najm', 'aqaba', '2026-05-09', 5, 50, 10, 12, {
    position: 4, raceType: 'national', raceName: 'السباق الوطني — العقبة',
    organisation: 'الاتحاد الأردني لهواة الحمام الزاجل', fanciersEntered: 41, birdsEntered: 388,
  }),
  race('y-lulu', 'quweira', '2026-04-04', 6, 20, 10, 31, { position: 27 }),
  // training tosses (never FCI-eligible)
  race('y-wadhah', 'jafr', '2026-03-20', 7, 0, 8, 55, { raceType: 'training', raceName: 'تدريب الجفر', fanciersEntered: 1, birdsEntered: 22 }),
  race('y-yaqut', 'jafr', '2026-06-14', 6, 40, 8, 47, { raceType: 'training', raceName: 'تدريب الجفر', fanciersEntered: 1, birdsEntered: 18 }),
];

// ------------------------------------------------------------------- pairs
const pairs = [
  {
    id: 'p-barq-malika-26', sireId: 'b-barq', damId: 'u-malika', season: '2026',
    nestBox: '3', status: 'active', startDate: '2026-01-20', loftId: LOFT, updatedAt: T,
    rounds: [
      {
        id: 'p1r1', number: 1,
        eggs: [
          { id: 'p1r1e1', laidDate: '2026-02-19', state: 'hatched', hatchDate: '2026-03-11', chickId: 'y-yaqut', ringed: true, weaned: true, weanDate: '2026-04-06' },
          { id: 'p1r1e2', laidDate: '2026-02-21', state: 'hatched', hatchDate: '2026-03-12', chickId: 'y-hudhud', ringed: true, weaned: true, weanDate: '2026-04-06' },
        ],
      },
      {
        id: 'p1r2', number: 2,
        eggs: [
          { id: 'p1r2e1', laidDate: '2026-08-14', state: 'laid' },
          { id: 'p1r2e2', laidDate: '2026-08-16', state: 'laid' },
        ],
      },
    ],
  },
  {
    id: 'p-sahm-amal-26', sireId: 'c-sahm', damId: 'c-amal', season: '2026',
    nestBox: '5', status: 'separated', startDate: '2026-01-20', loftId: LOFT, updatedAt: T,
    rounds: [
      {
        id: 'p2r1', number: 1,
        eggs: [
          { id: 'p2r1e1', laidDate: '2026-02-25', state: 'failed' },
          { id: 'p2r1e2', laidDate: '2026-02-27', state: 'hatched', hatchDate: '2026-03-17', chickId: null, ringed: false, weaned: false },
        ],
      },
    ],
  },
  {
    // mid-cycle pair: eggs still incubating — lets a learner drive the
    // hatch → ring → wean flow themselves
    id: 'p-wadhah-asifa-26', sireId: 'y-wadhah', damId: 'o-asifa', season: '2026',
    nestBox: '7', status: 'active', startDate: '2026-07-30', loftId: LOFT, updatedAt: T,
    rounds: [{
      id: 'p4r1', number: 1,
      eggs: [
        { id: 'p4r1e1', laidDate: '2026-08-18', state: 'laid' },
        { id: 'p4r1e2', laidDate: '2026-08-20', state: 'laid' },
      ],
    }],
  },
  {
    id: 'p-raad-ghaima-23', sireId: 'f-raad', damId: 'f-ghaima', season: '2023',
    nestBox: '1', status: 'separated', startDate: '2023-02-01', loftId: LOFT, updatedAt: T,
    rounds: [{
      id: 'p3r1', number: 1,
      eggs: [
        { id: 'p3r1e1', laidDate: '2023-03-10', state: 'hatched', hatchDate: '2023-04-02', chickId: 'c-amal', ringed: true, weaned: true, weanDate: '2023-04-28' },
        { id: 'p3r1e2', laidDate: '2023-03-12', state: 'hatched', hatchDate: '2023-04-02', chickId: 'c-fajr', ringed: true, weaned: true, weanDate: '2023-04-28' },
      ],
    }],
  },
];

// ------------------------------------------------------------------ health
const healthEvents = [
  { id: 'h-1', eventType: 'vaccination', wholeLoft: true, birdId: null, date: '2026-02-01', medication: 'لقاح باراميكسو (نيوكاسل الحمام) — Colombovac PMV', notes: 'قبل موسم التزاوج، كامل اللوفت', loftId: LOFT, updatedAt: T },
  { id: 'h-2', eventType: 'vaccination', wholeLoft: true, birdId: null, date: '2025-02-03', medication: 'لقاح باراميكسو PMV', notes: '', loftId: LOFT, updatedAt: T },
  { id: 'h-3', eventType: 'treatment', wholeLoft: true, birdId: null, date: '2026-03-25', medication: 'رونيدازول — وقاية من الترايكوموناس', notes: 'كورس ٥ أيام في ماء الشرب', loftId: LOFT, updatedAt: T },
  { id: 'h-4', eventType: 'illness', wholeLoft: false, birdId: 'y-lulu', date: '2026-05-02', medication: '', notes: 'إسهال أخضر بعد سباق القويرة — عزل ومتابعة، تعافت خلال أسبوع', loftId: LOFT, updatedAt: T },
  { id: 'h-5', eventType: 'treatment', wholeLoft: false, birdId: 'y-lulu', date: '2026-05-03', medication: 'أمبروليوم — كوكسيديا', notes: '', loftId: LOFT, updatedAt: T },
  { id: 'h-6', eventType: 'check', wholeLoft: false, birdId: 'b-barq', date: '2026-01-10', medication: '', notes: 'فحص ما قبل الموسم — وزن وريش ممتازان', loftId: LOFT, updatedAt: T },
];

const payload = {
  format: 'zajil-export',
  version: 1,
  kind: 'sample-data',
  exportedAt: T,
  lofts: [{
    id: LOFT, name: 'لوفت الزرقاء', location: 'الزرقاء، الأردن',
    statuses: ['breeder', 'race team', 'young bird', 'stock', 'sold', 'lost', 'dead'],
    createdAt: '2021-01-01T00:00:00.000Z', updatedAt: T,
  }],
  birds, pairs, raceResults, healthEvents, media: [],
};

const out = join(dirname(fileURLToPath(import.meta.url)), '..', 'sample-data.json');
// The readable keys above are documentation — `sireId: 'b-barq'` says what the
// line means. They are turned into real uuids HERE, mechanically, with every
// reference re-linked in the same pass, so the shipped data obeys the project's
// own "UUIDs only" rule without the source becoming unreadable. Deterministic:
// the same key always yields the same uuid, so regeneration does not churn.
const { payload: shipped, map } = remapIds(payload);
writeFileSync(out, JSON.stringify(shipped, null, 1));
console.log(`  ${map.size} readable keys mapped to uuids`);
console.log(`sample-data.json: ${birds.length} birds, ${pairs.length} pairs, ${raceResults.length} results, ${healthEvents.length} health events`);
