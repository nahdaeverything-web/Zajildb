"""The Arabic-coverage scan, shared (2026-11-13): arabic_typography.py walks every route with it; screens/sync_auto.py runs it on
states no route walk reaches — the unsent row, the sync screen, the destructive questions, the form's question. See
arabic_typography.py for why the fallback-divergence trick is the detector."""
SCAN = """() => {
  const ARABIC = /[\\u0600-\\u06FF\\u0750-\\u077F]/;
  const cv = document.createElement('canvas').getContext('2d');
  const covers = (family, text) => {
    const w = ['monospace', 'serif', 'sans-serif'].map((g) => {
      cv.font = `20px ${family}, ${g}`; return cv.measureText(text).width;
    });
    return Math.abs(w[0] - w[1]) < 0.01 && Math.abs(w[1] - w[2]) < 0.01;
  };
  const out = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (!el.getClientRects().length) continue;              // not rendered
    const own = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim();
    if (!ARABIC.test(own)) continue;
    const cs = getComputedStyle(el);
    const face = cs.fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, '');
    const ls = cs.letterSpacing;
    const spaced = ls && ls !== 'normal' && parseFloat(ls) !== 0;
    const arabic = own.replace(/[^\\u0600-\\u06FF\\u0750-\\u077F]/g, '');
    const uncovered = arabic.length > 1 && !covers(JSON.stringify(face), arabic);
    if (!uncovered && !spaced) continue;
    out.push({ why: (uncovered ? 'NO-ARABIC-COVERAGE ' : '') + (spaced ? 'LETTER-SPACED' : ''),
               face, ls, testid: el.getAttribute('data-testid') || '',
               text: own.slice(0, 40) });
  }
  return out;
}"""
