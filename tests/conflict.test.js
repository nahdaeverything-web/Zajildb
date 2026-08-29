// tests/conflict.test.js — the last-write-wins comparison itself (§4).
//
// A pure function over two timestamps and two device ids, so it is tested here
// exactly. What it MEANS for two real devices is tests/e2e/convergence.py.

import { test, assert, assertEq } from './harness.js';
import { remoteWins } from '../js/db.js';
import { toISO } from '../js/dates.js';

const row = (at, device = 'device-remote') => ({ updated_at: at, device_id: device });
const local = (at, deviceId = 'device-local') => ({ at, deviceId });

test('conflict: with nothing local, the incoming row wins', () => {
  assertEq(remoteWins(row('2026-08-29T10:00:00.000Z'), null), true);
  assertEq(remoteWins(row('2026-01-01T00:00:00.000Z'), undefined), true,
    'even an old row wins when this device has nothing unpushed to compare');
});

test('conflict: the later operation wins', () => {
  assertEq(remoteWins(row('2026-08-29T10:05:00.000Z'), local('2026-08-29T10:00:00.000Z')), true);
  assertEq(remoteWins(row('2026-08-29T10:00:00.000Z'), local('2026-08-29T10:05:00.000Z')), false);
});

test('conflict: a tie breaks on deviceId, lexicographically', () => {
  // Arbitrary, but STABLE — which is the only property that matters. A tie
  // means the same millisecond on two devices, and both must reach the same
  // verdict without talking to each other.
  const at = '2026-08-29T10:00:00.000Z';
  assertEq(remoteWins({ updated_at: at, device_id: 'bbb' }, local(at, 'aaa')), true);
  assertEq(remoteWins({ updated_at: at, device_id: 'aaa' }, local(at, 'bbb')), false);
});

test('conflict: the tie-break is symmetric — both devices reach the SAME verdict', () => {
  // The property that actually matters: run the comparison from each side and
  // exactly one must consider itself the winner. If both did, or neither, the
  // two devices would diverge permanently.
  const at = '2026-08-29T10:00:00.000Z';
  for (const [x, y] of [['aaa', 'bbb'], ['bbb', 'aaa'], ['device-1', 'device-2'],
                        ['00000000-aaaa', '00000000-bbbb']]) {
    const xWins = remoteWins({ updated_at: at, device_id: x }, local(at, y));
    const yWins = remoteWins({ updated_at: at, device_id: y }, local(at, x));
    assert(xWins !== yWins,
      `both devices claimed the same outcome for ${x} vs ${y}: ${xWins} / ${yWins}`);
  }
});

test('conflict: identical device ids cannot both win', () => {
  // The same device seeing its own row back. It must not "win" against itself
  // and supersede its own pending op for no reason.
  const at = '2026-08-29T10:00:00.000Z';
  assertEq(remoteWins({ updated_at: at, device_id: 'same' }, local(at, 'same')), false);
});

test('conflict: a missing timestamp loses to a real one', () => {
  assertEq(remoteWins(row(undefined), local('2026-08-29T10:00:00.000Z')), false);
  assertEq(remoteWins(row('2026-08-29T10:00:00.000Z'), local(undefined)), true);
});

test('conflict: ISO strings compare correctly as strings', () => {
  // The comparison is lexicographic on ISO-8601, which is only valid because
  // every timestamp comes from nowISO() — same length, same UTC zone, zero
  // padded. A local-time or offset-bearing string would break this silently.
  const pairs = [
    ['2026-08-29T09:59:59.999Z', '2026-08-29T10:00:00.000Z'],
    ['2026-08-29T23:59:59.999Z', '2026-08-30T00:00:00.000Z'],
    ['2025-12-31T23:59:59.999Z', '2026-01-01T00:00:00.000Z'],
    ['2026-08-29T10:00:00.001Z', '2026-08-29T10:00:00.002Z'],
  ];
  for (const [earlier, later] of pairs) {
    assertEq(remoteWins(row(later), local(earlier)), true, `${later} should beat ${earlier}`);
    assertEq(remoteWins(row(earlier), local(later)), false, `${earlier} should lose to ${later}`);
  }
});

// --------------------------------------------------- timestamp normalisation

test('conflict: Postgres and nowISO() spell the same instant differently', () => {
  // The bug this exists for. Postgres serialises timestamptz as `+00:00`;
  // nowISO() produces `.000Z`. Same instant, and `+` (0x2B) sorts BEFORE `.`
  // (0x2E) — so an un-normalised comparison makes each device prefer its own
  // copy, and two devices reach OPPOSITE verdicts about one conflict.
  const server = '2026-08-29T12:00:00+00:00';
  const local = '2026-08-29T12:00:00.000Z';
  assertEq(Date.parse(server), Date.parse(local), 'these must be the same instant');
  assert(server < local, 'the raw strings really do compare unequal — that is the trap');
  assertEq(toISO(server), local, 'normalisation must make them identical');
});

test('conflict: normalisation makes cross-format comparison symmetric', () => {
  // The property the same-format symmetry test could not see.
  const at = '2026-08-29T12:00:00.000Z';
  const serverForm = '2026-08-29T12:00:00+00:00';
  const xWins = remoteWins({ updated_at: toISO(serverForm), device_id: 'bbb' }, { at, deviceId: 'aaa' });
  const yWins = remoteWins({ updated_at: toISO(at), device_id: 'aaa' }, { at: toISO(serverForm), deviceId: 'bbb' });
  assert(xWins !== yWins, `both devices claimed the same outcome: ${xWins} / ${yWins}`);
  assertEq(xWins, true, 'with equal instants the greater deviceId must win, not whoever is local');
});

test('conflict: toISO normalises every shape Postgres can return', () => {
  const cases = [
    ['2026-08-29T12:00:00+00:00', '2026-08-29T12:00:00.000Z'],
    ['2026-08-29T12:00:00.123+00:00', '2026-08-29T12:00:00.123Z'],
    ['2026-08-29T12:00:00Z', '2026-08-29T12:00:00.000Z'],
    ['2026-08-29T15:00:00+03:00', '2026-08-29T12:00:00.000Z'],   // an offset, not UTC
    ['2026-08-29T12:00:00.000Z', '2026-08-29T12:00:00.000Z'],    // already canonical
  ];
  for (const [input, expected] of cases) {
    assertEq(toISO(input), expected, `${input} should normalise to ${expected}`);
  }
});

test('conflict: toISO leaves nonsense alone rather than inventing a date', () => {
  // A comparison against nonsense should look wrong, not plausible.
  assertEq(toISO('not-a-date'), 'not-a-date');
  assertEq(toISO(''), '');
  assertEq(toISO(null), '');
  assertEq(toISO(undefined), '');
});
