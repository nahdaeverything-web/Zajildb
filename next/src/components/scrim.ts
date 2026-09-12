'use client';
import { useEffect, useRef } from 'react';

/**
 * Dismiss-on-scrim, done so it cannot fire by accident.
 *
 * Every dialog in the approved specs closes when you tap the scrim
 * (breeding-v1.html:355, :383, :397 — `onclick="if(event.target===this)closeAll()"`), and
 * that one-liner is what the port first copied. It has a real hazard: a click is
 * pointerdown-then-pointerup, and a sheet whose content re-lays out between the two — a
 * picker list collapsing as the query is cleared, a validation list appearing — moves the
 * thing under the finger. The pointer went down on the heading and came up on the scrim,
 * and the sheet closed with the work in it.
 *
 * Reproduced at Phase 6: clearing a picker query and then clicking the sheet's own heading
 * dismissed the sheet. So the scrim closes only when the gesture BEGAN on it as well as
 * ended on it, which is what a tap on the scrim actually is.
 */
export function useScrim(onClose: () => void) {
  const startedOnScrim = useRef(false);
  return {
    onPointerDown: (e: React.PointerEvent) => { startedOnScrim.current = e.target === e.currentTarget; },
    onClick: (e: React.MouseEvent) => {
      if (startedOnScrim.current && e.target === e.currentTarget) onClose();
      startedOnScrim.current = false;
    },
  };
}

/**
 * Lock the page behind a sheet.
 *
 * Vanilla locks it with a reference-counted flag while any modal is up, and the
 * certificate's zoom overlay in this port already does the same thing by hand. The three
 * bottom sheets did not: measured at Phase 6, a wheel over the scrim above an open sheet
 * scrolled the list behind it from scrollY 0 to 600 — so a fancier filling a sheet on a
 * phone loses their place in the register behind it, and the scrim stops covering what it
 * is there to cover.
 *
 * Counted, because two sheets can be open at once (a pair sheet over the ring sheet): the
 * last one to close is the one that gives the page back.
 */
let locks = 0;
let restore = '';

export function useScrollLock() {
  useEffect(() => {
    if (locks === 0) { restore = document.body.style.overflow; document.body.style.overflow = 'hidden'; }
    locks += 1;
    return () => {
      locks = Math.max(0, locks - 1);
      if (locks === 0) document.body.style.overflow = restore;
    };
  }, []);
}
