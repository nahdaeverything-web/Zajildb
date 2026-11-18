'use client';
import { useEffect } from 'react';
import * as db from '@/src/db.js';
import { t } from '@/src/i18n.ext.js';
import { toast } from './shell';

/**
 * The two things sync is allowed to interrupt for — js/app.js:195-217, the shell's
 * own wiring, so it lives in the layout rather than in any one screen.
 *
 *  · 'sync-interrupt' — §11: only a session that needs a password and a rejection
 *    that needs the fancier ever interrupt. Everything else waits in الأدوات.
 *  · 'sync-complete'  — said ONCE, after the first sync on a device that had local
 *    data: two devices that never synced minted different ids for the same physical
 *    bird, so both records are real. Only the fancier can say they are one bird; the
 *    duplicate finder in الأدوات groups them, and this is what points at it.
 *
 * Both are vanilla's PLAIN toast (js/app.js passes only a timeout); a kind would be
 * a visual decision no spec makes.
 *
 * Renders nothing.
 */
export default function SyncNotices() {
  useEffect(() => { const off = db.onChange((ev: { type?: string; key?: string; files?: { name: string; reason: string }[] } | null) => {
    if (!ev) return;
    // PHOTO SYNC, STAGE 1 (RULED 2026-11-18): a file the server will not take is SAID, once, and its bytes stay here.
    // ONE notice per pass: the shell shows two toasts at most, so a notice per file would lose all but the last two
    if (ev.type === 'photo-refused' && ev.files && ev.files.length) {
      const f = ev.files;
      toast(f.length === 1 ? t('media.refused.' + (f[0].reason === 'type' ? 'type' : 'size'), { name: f[0].name }) : t('media.refused.many', { n: f.length }), { timeout: 12000 });
      return;
    }
    if (ev.type === 'sync-interrupt' && ev.key) { toast(t(ev.key), { timeout: 10000 }); return; }
    if (ev.type === 'sync-complete') {
      db.takeSyncDuplicateNotice().then((n: number | null) => { if (n) toast(t('sync.duplicates', { n }), { timeout: 8000 }); });
    }
  }); return () => { off(); }; }, []);
  return null;
}
