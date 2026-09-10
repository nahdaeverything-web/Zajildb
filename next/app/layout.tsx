import type { Metadata } from 'next';
import { alexandria, plexMono } from './fonts';
import '../styles/tokens.css';
import './globals.css';

export const metadata: Metadata = {
  title: 'زاجل',
  description: 'إدارة اللوفت وشجرة النسب — يعمل دون اتصال',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl" className={`${alexandria.variable} ${plexMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
