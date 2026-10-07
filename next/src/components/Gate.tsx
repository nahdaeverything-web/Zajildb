'use client';
import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import * as db from '@/src/db.js';
import { useZajilStore } from '@/src/db/react';
import { initDB } from './boot';
import SignInView from '@/app/sign-in/view';

/**
 * THE SIGN-IN GATE — RULED 2026-10-07.
 *
 * It keys off two things the device really has, and nothing else:
 *   · a session            -> through, online or offline (the session is read from settings,
 *                             never from the network);
 *   · no session, no data  -> the sign-in screen; nothing else to show;
 *   · no session, data     -> the sign-in screen showing THE LOFT — its name and the breeder's
 *                             name if recorded, never an account — with export on the gate
 *                             itself. Export is the escape hatch, not a bypass: there is no
 *                             way into the loft from here without signing in.
 * Nothing re-arms on the collision CLEAR, because CLEAR leaves no data and stores a session.
 *
 * Two things stand outside it, both raised in the order's report rather than decided here:
 *   · a build with no sync configuration has nothing to sign into, so it cannot gate;
 *   · the test harness route is a test surface, absent from any production build
 *     (the no-harness-route guard), and the suites drive the layer through it.
 */
type Loft = { name?: string; breederName?: string };

export default function Gate({ children }: { children: React.ReactNode }) {
  // trailingSlash is on (RULED 2026-09-25): the exported path is '/sign-in/', so the slash goes before comparing
  const pathname = (usePathname() ?? '').replace(/\.html$/, '').replace(/\/$/, '');
  const [booted, setBooted] = useState(false);
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  // every layer change re-evaluates the gate: a sign-in's first cycle and a sign-out's refresh
  // both raise one, so the gate opens and closes with the session without a reload
  useZajilStore((x) => x);

  if (pathname === '/test-harness' || pathname.startsWith('/test-harness/')) return <>{children}</>;
  if (!booted) return <>{children}</>;                       // every screen shows its own Loading until the layer is up
  if (!(db.syncConfig() as { configured: boolean }).configured) return <>{children}</>;
  if ((db.authState() as { signedIn: boolean }).signedIn) return <>{children}</>;

  const lofts = [...(db.state.lofts.values() as Iterable<Loft & { id: string }>)];
  const records = db.state.birds.size + db.state.pairs.size + db.state.raceResults.size + db.state.healthEvents.size;
  const hasData = records > 0 || lofts.some((l) => !db.isPristineLoft(l));
  const loft = (db.currentLoft() as Loft | null) || lofts[0] || null;
  return <SignInView gate={hasData ? { loft: loft?.name || '', breeder: loft?.breederName || '' } : { empty: true }} />;
}
