import type { Metadata, Viewport } from 'next';
import { alexandria, plexMono } from './fonts';
import Nav from '@/components/Nav';
import ShellHost from '@/src/components/ShellHost';
import SyncNotices from '@/src/components/SyncNotices';
import AppSettings from '@/src/components/AppSettings';
import HarnessGlobals from '@/src/harness-globals';
import '../styles/tokens.css';
import './globals.css';
import s from './layout.module.css';

export const metadata: Metadata = {
  title: 'زاجل',
  description: 'إدارة اللوفت وشجرة النسب — يعمل دون اتصال',
};
export const viewport: Viewport = { width: 'device-width', initialScale: 1 };

// Structural RTL: the document direction is set once, here. Layout follows
// it through logical properties; nothing below should ever say left/right.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl" className={`${alexandria.variable} ${plexMono.variable}`}>
      <body>
        <main className={s.main}>{children}</main>
        <Nav />
        <ShellHost />
        <SyncNotices />
        <AppSettings />
        <HarnessGlobals />
      </body>
    </html>
  );
}
