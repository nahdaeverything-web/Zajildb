import type { Metadata, Viewport } from 'next';
import Script from 'next/script';
import { alexandria, plexMono } from './fonts';
import Nav from '@/components/Nav';
import ShellHost from '@/src/components/ShellHost';
import BackupBanner from '@/src/components/BackupBanner';
import SyncNotices from '@/src/components/SyncNotices';
import AppSettings from '@/src/components/AppSettings';
import ServiceWorker from '@/src/components/ServiceWorker';
import HarnessGlobals from '@/src/harness-globals';
import '../styles/tokens.css';
import './globals.css';
import s from './layout.module.css';

// The SAME basePath the export was built with — next/script does not rewrite `src`, and a
// root-absolute path would 404 under a subdirectory deployment, leaving sync silently
// unconfigured. Built the way ServiceWorker.tsx:20 builds the worker's path, for the same
// reason and from the same variable.
const BASE = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/$/, '');

export const metadata: Metadata = {
  title: 'زاجل',
  description: 'إدارة اللوفت وشجرة النسب — يعمل دون اتصال',
};
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',      // index.html:5 — the safe-area insets the fixed bars use
  themeColor: '#128C6E',     // index.html:6, retuned to the kit's brand (--brand)
};

// Structural RTL: the document direction is set once, here. Layout follows
// it through logical properties; nothing below should ever say left/right.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl" className={`${alexandria.variable} ${plexMono.variable}`}>
      <body>
        {/* THE CONFIG INJECTION POINT — CUTOVER §a.3. Committed empty; a deploy pipeline
            rewrites public/sync-config.js after the guards run and before upload.
            beforeInteractive puts it in the initial HTML and runs it before any Next module,
            so globalThis.ZAJIL_SYNC_CONFIG is set before any screen can call syncConfig().
            It is a normal public asset, so the worker precaches it by URL and the config
            survives offline — a config fetched at runtime would 404 there. */}
        <Script src={`${BASE}/sync-config.js`} strategy="beforeInteractive" />
        <BackupBanner />
        <main className={s.main}>{children}</main>
        <Nav />
        <ShellHost />
        <SyncNotices />
        <AppSettings />
        <ServiceWorker />
        <HarnessGlobals />
      </body>
    </html>
  );
}
