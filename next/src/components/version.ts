'use client';
import { useEffect, useState } from 'react';

/**
 * The installed version, asked of the CONTROLLING service worker — js/views/tools.js:394.
 *
 * Deliberately NOT a constant in the source: a constant reports what the code says, while
 * this reports what is actually installed, and those disagree exactly when it matters (an
 * update downloaded but not activated, or no service worker at all). The root suite
 * version_display.py asserts that no source file hardcodes a version string; the port
 * keeps that property and guards it (`no-hardcoded-version`).
 *
 * Resolves to null rather than rejecting: no controller, no reply, or a timeout all mean
 * "cannot say", and the caller shows about.unknown.
 */
export function askServiceWorkerVersion(timeoutMs = 2000): Promise<string | null> {
  return new Promise((resolve) => {
    const sw = typeof navigator !== 'undefined' && navigator.serviceWorker && navigator.serviceWorker.controller;
    if (!sw) { resolve(null); return; }
    let settled = false;
    const done = (v: string | null) => { if (!settled) { settled = true; resolve(v); } };
    const timer = setTimeout(() => done(null), timeoutMs);
    try {
      const channel = new MessageChannel();
      channel.port1.onmessage = (e: MessageEvent) => {
        clearTimeout(timer);
        done(e.data && e.data.type === 'VERSION' ? (e.data.version as string) : null);
      };
      sw.postMessage({ type: 'GET_VERSION' }, [channel.port2]);
    } catch {
      clearTimeout(timer);
      done(null);
    }
  });
}

/** null until the reply arrives (or never, if there is no service worker). */
export function useAppVersion(): string | null {
  const [v, setV] = useState<string | null>(null);
  useEffect(() => { let live = true; askServiceWorkerVersion().then((x) => { if (live) setV(x); }); return () => { live = false; }; }, []);
  return v;
}
