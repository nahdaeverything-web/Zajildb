'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import s from './Nav.module.css';

/**
 * The six ruled destinations — kit v3.1 NAVIGATION NOTE, RULED 2026-09-02.
 * No home tab, no sign-in tab. Icons are the spec's own SVG paths, verbatim.
 *
 * `owns` lists the record routes that light a tab, mirroring the vanilla
 * router (js/app.js:119): a bird, its pedigree and its certificate belong to
 * الطيور; a pair belongs to التزاوج.
 */
const TABS = [
  { href: '/birds',    owns: ['/bird', '/pedigree', '/cert'], label: 'الطيور',
    icon: <><rect x="3" y="4" width="18" height="6" rx="2"/><rect x="3" y="14" width="18" height="6" rx="2"/></> },
  { href: '/breeding', owns: ['/pair'], label: 'التزاوج',
    icon: <><circle cx="9" cy="12" r="5"/><circle cx="15" cy="12" r="5"/></> },
  { href: '/races',    owns: [], label: 'السباقات',
    icon: <path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3"/> },
  { href: '/health',   owns: [], label: 'الصحة',
    icon: <path d="M3 12h4l2-5 3 10 2-5h7"/> },
  { href: '/stats',    owns: [], label: 'الإحصائيات',
    icon: <path d="M5 20V10M12 20V4M19 20v-7"/> },
  { href: '/tools',    owns: [], label: 'الأدوات',
    icon: <><path d="M4 8h6M14 8h6M4 16h10M18 16h2"/><circle cx="12" cy="8" r="2"/><circle cx="16" cy="16" r="2"/></> },
];

function isOn(pathname: string, t: (typeof TABS)[number]) {
  return pathname === t.href || pathname.startsWith(t.href + '/') ||
    t.owns.some((p) => pathname === p || pathname.startsWith(p + '/'));
}

export default function Nav() {
  const pathname = usePathname() ?? '';
  const items = TABS.map((t) => (
    <Link key={t.href} href={t.href} className={isOn(pathname, t) ? s.on : undefined}>
      <svg viewBox="0 0 24 24" aria-hidden="true">{t.icon}</svg>{t.label}
    </Link>
  ));
  return (
    <>
      <nav className={s.tabbar} aria-label="التنقل">{items}</nav>
      <nav className={s.rail} aria-label="التنقل">{items}</nav>
    </>
  );
}
