import * as db from '@/src/db.js';
import { configure } from '@/src/i18n.ext.js';

/**
 * vanilla's applySettings() — js/app.js:50.
 *
 * The i18n module keeps the display locale in module state (i18n.js:483-497) and
 * is told through configure(); NOTHING in it reads the settings mirror. So a
 * settings write alone changes no number and no date on screen — vanilla calls
 * this at boot and on every rerender, and the port must too.
 *
 * The document title is the one line not carried: the port states it once, in the
 * route metadata (app/layout.tsx), which is where Next puts it.
 */
export function applySettings() {
  const s = db.state.settings as Record<string, unknown>;
  configure({
    lang: (s.lang as string) || 'ar',
    numerals: (s.numerals as string) || 'western',
    dates: (s.dates as string) || (s.lang === 'en' ? 'gregorian' : 'both'),
  });
  if (typeof document !== 'undefined') {
    // The CLASS is carried because the capability is real (4A acceptance, item 8:
    // spec silence does not remove a vanilla feature). Its PALETTE is an open
    // question: tools-v1 names the control «التباين العالي (ضوء الشمس)» and no
    // approved spec defines the mode's colours, and vanilla's own overrides
    // (css/app.css:28) are Phase-1 hexes the palette guard rejects. Raised in the
    // 4D report; the moment the palette is ruled it attaches here, unchanged.
    document.documentElement.classList.toggle('high-contrast', !!s.highContrast);
  }
}

/**
 * vanilla's `setSetting(...) then rerender()` — js/views/tools.js:45-48, 97-99.
 *
 * setSetting deliberately emits nothing (db/storage.js:168) and never has, so a
 * view that writes a setting is responsible for showing the result. This re-applies
 * the locale and then raises the LAYER'S OWN change event, which is the signal the
 * React bridge already subscribes to — no second event system, and every mounted
 * view answers, exactly as vanilla's rerender() re-draws the whole screen.
 */
export async function saveSetting(key: string, value: unknown) {
  await db.setSetting(key, value);
  applySettings();
  db.emitChange({ type: 'settings', key });
}
