'use client';
import { useEffect } from 'react';
import { t } from '@/src/i18n.ext.js';
import { toast } from './shell';

/**
 * Register the service worker — js/app.js:265-277, carried behaviour for behaviour.
 *
 * Optional by design: the app is fully functional without it, so the whole thing sits in
 * a try/catch that swallows. Offline-first means never blocking on this.
 *
 * ONE CHANGE from vanilla, and it is a bug fix rather than a preference: vanilla registers
 * `'./sw.js'`, which is document-relative. That was safe there because the app is one
 * document at the root. This export has documents one level deep — bird/new.html and
 * bird/edit.html — where './sw.js' resolves to /bird/sw.js, a 404, and the scope would be
 * /bird/ even if it existed. So the path is built from the SAME basePath the export was
 * built with, and the scope is stated rather than inferred: subpath_hosting asserts that
 * registration.scope ends with the deployment prefix.
 */
const BASE = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/$/, '');

export default function ServiceWorker() {
  useEffect(() => {
    const container = typeof navigator === 'undefined' ? null : navigator.serviceWorker;
    if (!container || location.protocol === 'file:') return;
    let cancelled = false;
    try {
      // updateViaCache:'none' — the default ('imports') already bypasses the HTTP cache for
      // the top-level worker script, but a host's max-age is exactly what sw.js's
      // cache:'reload' precache exists to defeat, so the assumption is stated not inherited
      container.register(`${BASE}/sw.js`, { scope: `${BASE}/`, updateViaCache: 'none' }).then((reg) => {
        if (cancelled) return;
        // «يتوفر تحديث» when a worker was already in charge, «جاهز للعمل دون اتصال» the
        // first time — the difference is whether this is an update or an install
        reg.addEventListener('updatefound', () => {
          const w = reg.installing;
          if (!w) return;
          w.addEventListener('statechange', () => {
            if (w.state === 'installed') {
              toast(container.controller ? t('toast.updated') : t('toast.installed'));
            }
          });
        });
      }).catch(() => { /* offline-first: never block on this */ });
    } catch { /* the API is present but disabled: nothing to do, and nothing to break */ }
    return () => { cancelled = true; };
  }, []);
  return null;
}
