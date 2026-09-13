'use client';
import { useEffect, useState } from 'react';

import { t } from '@/src/i18n.ext.js';
import * as db from '@/src/db.js';

import s from './BackupBanner.module.css';

/**
 * «مرّ أكثر من ٣٠ يومًا على آخر تصدير» — the export-freshness nudge.
 *
 * RESTORED at the pre-launch close. The string has been in the dictionary since v1.4
 * (`src/i18n.js:437`) and NO component in the port read it, while vanilla banners it on every
 * route (`js/app.js:123-134`). It is the only prompt in the app that puts an export in a
 * fancier's hands — and after the cutover plan it carries more weight than it used to, because
 * §d asks every existing fancier to export once in order to migrate at all, and §h asks Samir
 * to keep a copy off both origins.
 *
 * The condition is vanilla's, unchanged: stale is no export at all, or one more than 30 days
 * old, AND the loft is not empty — a brand-new loft has nothing to lose and should not be
 * nagged on its first run.
 */
const THIRTY_DAYS = 30 * 24 * 3600 * 1000;

export default function BackupBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    let alive = true;
    const read = () => {
      // Read-only, and ONLY once the app has booted itself. This must NEVER call initDB():
      // a first run with no lofts makes one (storage.js:136-142), and a banner that mounts on
      // every route would then race the screen's own boot. It did — four convergence
      // assertions failed with three lofts instead of two, and `adoptRemoteLoftIfPristine`
      // correctly refused to guess which to adopt. The screen owns the boot; this only looks.
      if (!db.state.ready) return;
      const last = (db.state.settings as Record<string, unknown>).lastExport as string | undefined;
      const stale = !last || Date.now() - new Date(last).getTime() > THIRTY_DAYS;
      if (alive) setShow(Boolean(stale && db.state.birds.size > 0));
    };
    read();                       // already booted (a client-side route change)
    const off = db.onChange(read);
    // initDB emits no change of its own, so a first load needs one look after it settles
    const settle = setTimeout(read, 600);
    return () => { alive = false; clearTimeout(settle); off(); };
  }, []);

  if (!show) return null;
  return (
    <div className={s.banner} role="status" data-testid="backup-warn">
      <span>{t('backup.warn30')}</span>
      <a className={s.act} href="/tools" data-testid="backup-warn-act">{t('act.export')}</a>
    </div>
  );
}
