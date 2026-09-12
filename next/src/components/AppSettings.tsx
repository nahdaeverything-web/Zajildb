'use client';
import { useEffect } from 'react';
import * as db from '@/src/db.js';
import { applySettings } from './settings';
import { initDB } from './boot';

/**
 * The boot half of vanilla's applySettings() — js/app.js:241. A device that was
 * left on eastern numerals must come back on them, so the locale is applied once
 * the layer has loaded its settings, before any screen formats a number.
 *
 * It is re-applied after an IMPORT because an import can replace the settings
 * store wholesale (vanilla rebuilds the shell for the same reason, app.js:218).
 *
 * Renders nothing.
 */
export default function AppSettings() {
  useEffect(() => {
    let live = true;
    initDB().then(() => { if (live) applySettings(); });
    const off = db.onChange((ev: { type?: string } | null) => { if (ev && ev.type === 'import') applySettings(); });
    return () => { live = false; off(); };
  }, []);
  return null;
}
