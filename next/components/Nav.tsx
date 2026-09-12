'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { t } from '@/src/i18n.ext.js';
import s from './Nav.module.css';

/**
 * The six ruled destinations — kit v3.1 NAVIGATION NOTE, RULED 2026-09-02.
 * No home tab, no sign-in tab. Icons are the spec's own SVG paths, verbatim.
 * Labels come from the dictionary (nav.*); nav.breeding is the ruled rename
 * «التزاوج» carried by i18n.ext.js, so the shell and every screen agree.
 *
 * `owns` lists the record routes that light a tab, mirroring the vanilla
 * router (js/app.js:119): a bird, its pedigree and its certificate belong to
 * الطيور; a pair belongs to التزاوج.
 */
const TABS = [
  { href: '/birds',    owns: ['/bird', '/pedigree', '/cert'], label: 'nav.birds',
    icon: <><rect x="3" y="4" width="18" height="6" rx="2"/><rect x="3" y="14" width="18" height="6" rx="2"/></> },
  { href: '/breeding', owns: ['/pair'], label: 'nav.breeding',
    icon: <><circle cx="9" cy="12" r="5"/><circle cx="15" cy="12" r="5"/></> },
  { href: '/races',    owns: [], label: 'nav.races',
    icon: <path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3"/> },
  { href: '/health',   owns: [], label: 'nav.health',
    icon: <path d="M3 12h4l2-5 3 10 2-5h7"/> },
  { href: '/stats',    owns: [], label: 'nav.stats',
    icon: <path d="M5 20V10M12 20V4M19 20v-7"/> },
  { href: '/tools',    owns: [], label: 'nav.tools',
    icon: <><path d="M4 8h6M14 8h6M4 16h10M18 16h2"/><circle cx="12" cy="8" r="2"/><circle cx="16" cy="16" r="2"/></> },
];

function isOn(pathname: string, tab: (typeof TABS)[number]) {
  return pathname === tab.href || pathname.startsWith(tab.href + '/') ||
    tab.owns.some((p) => pathname === p || pathname.startsWith(p + '/'));
}

// The bird form is a modal flow: add-edit-bird-v2 draws its own fixed action
// bar where the tab bar sits and no tab bar at all (the rail stays at ≥1100).
// The certificate is the same shape — certificate-v1 marks its options panel
// "app screen, no tab bar" and draws its own fixed «مشاركة / طباعة» bar there.
const NO_TABBAR = ['/bird/new', '/bird/edit', '/cert'];

// Both navs render the SAME six tabs and CSS decides which one is on screen, so a plain
// count of nav links is 12. Each nav carries its own data-testid and every link carries
// data-tab, so a test can ask about the one that is visible rather than guessing.
export default function Nav() {
  // a plain file server serves the export as /birds.html, /bird/new.html; a static host as the clean path — compare the clean one
  const pathname = (usePathname() ?? '').replace(/\.html$/, '');
  const items = TABS.map((tab) => (
    <Link key={tab.href} href={tab.href} className={isOn(pathname, tab) ? s.on : undefined} data-testid="nav-link" data-tab={tab.href}>
      <svg viewBox="0 0 24 24" aria-hidden="true">{tab.icon}</svg>{t(tab.label)}
    </Link>
  ));
  const modalFlow = NO_TABBAR.some((p) => pathname === p || pathname.startsWith(p + '/'));
  return (
    <>
      {!modalFlow && <nav className={s.tabbar} data-bottom-chrome="tabbar" data-testid="tabbar" aria-label="التنقل">{items}</nav>}
      <nav className={s.rail} data-testid="rail" aria-label="التنقل">{items}</nav>
    </>
  );
}
