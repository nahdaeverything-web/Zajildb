// The row and status glyphs of design/approved/tools-v2.html, transcribed path for path. The
// three NOT-YET-BUILT rows' glyphs (plan, pro, notifications) are not here because the rows
// are not built. `teaching` is the one glyph the spec does not draw: the teaching-data row
// is a port addition (design/README.md, tools-v2 deviation 4) and reuses the import arrow.
import s from './tools.module.css';

export const ICON = {
  account:    <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  sync:       <path d="M20 7h-4V3M4 17h4v4M18.5 5.5A8 8 0 0 0 5 9M5.5 18.5A8 8 0 0 0 19 15" />,
  loft:       <path d="M4 20V8l8-5 8 5v12M8 20v-6h8v6" />,
  location:   <><path d="M12 21s6-5.3 6-11a6 6 0 1 0-12 0c0 5.7 6 11 6 11z" /><circle cx="12" cy="10" r="2" /></>,
  phone:      <path d="M7 3h3l2 5-2 1a16 16 0 0 0 5 5l1-2 5 2v3c0 2-2 4-4 4C9 20 4 15 3 7c0-2 2-4 4-4z" />,
  website:    <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" /></>,
  logo:       <><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="10" r="2" /><path d="M4 17l5-4 3 2 3-3 5 5" /></>,
  export:     <path d="M12 4v11M7 10l5 5 5-5M4 20h16" />,
  import:     <path d="M12 20V9M7 14l5-5 5 5M4 4h16" />,
  teaching:   <path d="M12 20V9M7 14l5-5 5 5M4 4h16" />,
  restore:    <path d="M4 7h16v13H4zM8 7V4h8v3M8 11h8" />,
  duplicates: <><circle cx="9" cy="9" r="5" /><path d="M13 13l7 7M15 4h5v5" /></>,
  integrity:  <><path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z" /><path d="M8 12l3 3 5-6" /></>,
  language:   <><circle cx="12" cy="12" r="9" /><path d="M7 9h10M9 15h6M12 3c2.5 2.6 3.5 5.6 3.5 9S14.5 18.4 12 21M12 3C9.5 5.6 8.5 8.6 8.5 12S9.5 18.4 12 21" /></>,
  numerals:   <path d="M6 5h4v14M16 5h2v14M5 10h6M15 10h4" />,
  dates:      <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4M17 3v4M3 10h18" /></>,
  coi:        <path d="M5 18c3-8 11-8 14 0M8 8a4 4 0 1 1 8 0M4 4l16 16" />,
  contrast:   <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  scanner:    <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M7 8h10M7 12h6M7 16h8" /></>,
  dev:        <path d="M8 9l-4 3 4 3M16 9l4 3-4 3M14 5l-4 14" />,
  version:    <><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7h.01" /></>,
  // status-line glyphs
  check:      <path d="M5 12l4 4 10-10" />,
  offline:    <path d="M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M12 19h.01M4 4l16 16" />,
  clock:      <><circle cx="12" cy="12" r="9" /><path d="M12 7v6l4 2" /></>,
  alert:      <><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 17h.01" /></>,
  list:       <path d="M4 5h16v14H4zM8 9h8M8 13h5" />,
  plus:       <path d="M4 12h16M12 4v16" />,
  off:        <path d="M4 4l16 16M5 12h14" />,
  chevron:    <path d="M15 6l-6 6 6 6" />,
} as const;

export type IconName = keyof typeof ICON;

export function Icon({ name, small, className }: { name: IconName; small?: boolean; className?: string }) {
  return <svg className={`${s.icon} ${small ? s.sm : ''} ${className || ''}`} viewBox="0 0 24 24" aria-hidden="true">{ICON[name]}</svg>;
}
