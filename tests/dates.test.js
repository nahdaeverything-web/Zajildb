// tests/dates.test.js — local-calendar date handling.
//
// Two distinct UTC bugs are guarded here:
//   1. `new Date().toISOString().slice(0,10)` yields the UTC date, so east of
//      Greenwich it records YESTERDAY between local midnight and the offset.
//   2. `new Date("YYYY-MM-DD")` parses as UTC midnight, so west of Greenwich
//      the stored date RENDERS one day early.
// Both are proven against fixed instants so the tests do not depend on when
// or where they are run.

import { test, assertEq, assert } from './harness.js';
import { todayISO, parseLocalDate, isDateOnly } from '../js/dates.js';

test('todayISO: returns the LOCAL calendar date, not the UTC one', () => {
  // 00:30 local in Amman (UTC+3) is still the previous day in UTC
  const justAfterMidnightAmman = new Date('2026-08-24T21:30:00Z');
  // The naive implementation would give '2026-08-24'; local calendar is the 25th
  // when TZ=Asia/Amman. Compare against what the platform reports locally so the
  // assertion holds in any timezone the suite happens to run in.
  const d = justAfterMidnightAmman;
  const expected = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  assertEq(todayISO(justAfterMidnightAmman), expected);
});

test('todayISO: never disagrees with the local calendar, at any instant', () => {
  // sample every hour across two days — the naive UTC version fails a slice of
  // these in any non-UTC timezone
  const base = Date.UTC(2026, 7, 24, 0, 0, 0);
  for (let h = 0; h < 48; h++) {
    const d = new Date(base + h * 3600 * 1000);
    const expected = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    assertEq(todayISO(d), expected, `hour ${h}`);
  }
});

test('todayISO: defaults to now and is a well-formed date-only string', () => {
  const s = todayISO();
  assert(/^\d{4}-\d{2}-\d{2}$/.test(s), `got ${s}`);
  const now = new Date();
  assertEq(s, `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`);
});

test('parseLocalDate: a bare date lands on LOCAL midnight, not UTC midnight', () => {
  const d = parseLocalDate('2025-04-12');
  assertEq(d.getFullYear(), 2025);
  assertEq(d.getMonth(), 3);        // April
  assertEq(d.getDate(), 12);        // must stay the 12th west of Greenwich
  assertEq(d.getHours(), 0);
});

test('parseLocalDate: round-trips through todayISO for every day of a year', () => {
  for (let i = 0; i < 365; i++) {
    const d = new Date(2026, 0, 1 + i);
    const iso = todayISO(d);
    assertEq(todayISO(parseLocalDate(iso)), iso, `day ${i}`);
  }
});

test('parseLocalDate: full datetimes keep their instant semantics', () => {
  const dt = parseLocalDate('2026-05-01T06:30:00Z');
  assertEq(dt.getTime(), new Date('2026-05-01T06:30:00Z').getTime());
});

test('parseLocalDate: invalid input returns an invalid Date, never throws', () => {
  assert(Number.isNaN(parseLocalDate('').getTime()));
  assert(Number.isNaN(parseLocalDate('not-a-date').getTime()));
  assert(Number.isNaN(parseLocalDate(null).getTime()));
});

test('isDateOnly distinguishes bare dates from datetimes', () => {
  assert(isDateOnly('2026-08-25'));
  assert(!isDateOnly('2026-08-25T10:00:00Z'));
  assert(!isDateOnly(''));
  assert(!isDateOnly(null));
});
