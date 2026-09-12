"""Ruling C (4B addendum): fixed elements must not hide content.

Proved geometrically at the REAL viewport — never on a full-page capture, where a
fixed bar is painted at its scroll position and looks like it sits mid-page. The
page is scrolled to the very bottom and then, from bounding boxes only:

  1. no interactive element of the page overlaps any fixed bottom bar, and the
     lowest one clears it by at least the kit's 12px unit;
  2. a toast that is up covers nothing — neither page content (the last list
     row's tap target) nor the screen's own chrome (a CTA, a FAB, an action
     bar) — and sits exactly 12px above the bottom chrome, as the spec draws it.

Every screen test calls these at 430x900 and 900x900. Both are regression
guards: the clearance comes from the specs' own bottom paddings, and the 12px
from the shell's measured toast placement.
"""

CLEARANCE = 12          # the kit's unit — the spec's own gap between a toast and the bar below it
CHROME_BAND = 240       # only chrome anchored near the bottom of the viewport can cover the end of the page

PROBE = """(band) => {
  const vh = innerHeight, vw = innerWidth;
  const vis = (el) => { const cs = getComputedStyle(el); return cs.display !== 'none' && cs.visibility !== 'hidden' && +cs.opacity > 0; };
  const box = (el) => { const r = el.getBoundingClientRect(); return { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right) }; };
  const name = (el) => el.getAttribute('data-testid') || el.getAttribute('data-bottom-chrome') || (typeof el.className === 'string' && el.className.split(' ')[0]) || el.tagName;
  const fixedAncestor = (el) => { let p = el; while (p && p !== document.body) { if (getComputedStyle(p).position === 'fixed') return p; p = p.parentElement; } return null; };
  const bars = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!vis(el) || getComputedStyle(el).position !== 'fixed') continue;
    if (el.closest('[data-testid=toast-stack]')) continue;         // the toast is reported on its own
    const r = box(el);
    if (r.bottom - r.top < 1 || r.right - r.left < 1) continue;
    if (r.bottom < vh - band) continue;                            // not anchored to the bottom edge
    bars.push({ name: name(el), ...r });
  }
  const items = [];
  for (const el of document.querySelectorAll('a[href], button, input, select, textarea, [role=tab], [role=switch], [role=menuitem]')) {
    if (!vis(el) || fixedAncestor(el)) continue;                   // inside a bar = chrome, not page content
    const r = box(el);
    if (r.bottom - r.top < 1 || r.bottom < 0 || r.top > vh) continue;
    items.push({ name: name(el), ...r });
  }
  items.sort((a, b) => b.bottom - a.bottom);
  const toasts = [...document.querySelectorAll('[data-testid=toast]')].filter(vis).map((el) => ({ name: name(el), ...box(el) }));
  return { vh, vw, atBottom: Math.ceil(scrollY + vh) >= document.documentElement.scrollHeight - 2,
           docH: Math.round(document.documentElement.scrollHeight), bars, items, toasts };
}"""


def _overlaps(a, b):
    return not (a['bottom'] <= b['top'] or a['top'] >= b['bottom'] or a['right'] <= b['left'] or a['left'] >= b['right'])


def _vgap(a, b):
    """Vertical gap from a (above) to b (below) when they share horizontal space, else None."""
    if a['right'] <= b['left'] or a['left'] >= b['right']:
        return None
    return b['top'] - a['bottom']


def probe(pg, band=CHROME_BAND):
    return pg.evaluate(PROBE, band)


def scroll_to_bottom(pg):
    pg.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
    pg.wait_for_timeout(350)


def wait_toasts_clear(pg, timeout=9000):
    """Let outstanding toasts expire, so what is measured next is the toast the action
    under test raised — the case shared-states §02 draws — and not a pile-up left over
    from earlier steps."""
    pg.wait_for_function("() => document.querySelectorAll('[data-testid=toast]').length === 0", timeout=timeout)


def check_clearance(pg, check, where, widths=(430, 900), clearance=CLEARANCE):
    """[ruling C] At each viewport: scrolled to the bottom, no interactive element is
    under a fixed bar, and the lowest clears it by >= the kit's 12px."""
    start = pg.viewport_size
    for w in widths:
        pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(200)
        scroll_to_bottom(pg)
        r = probe(pg)
        hidden = [(i, b) for i in r['items'] for b in r['bars'] if _overlaps(i, b)]
        gaps = [g for i in r['items'] for b in r['bars'] if (g := _vgap(i, b)) is not None and g >= 0]
        lowest = r['items'][0] if r['items'] else None
        low_gap = min([g for b in r['bars'] if (g := _vgap(lowest, b)) is not None], default=None) if lowest else None
        bars = ' + '.join(f"{b['name']}[{b['top']}]" for b in r['bars']) or 'none'
        ok = r['atBottom'] and not hidden and (low_gap is None or low_gap >= clearance)
        detail = (f"under {hidden[0][1]['name']}: {hidden[0][0]['name']}" if hidden
                  else f"last «{lowest['name'] if lowest else '—'}» clears {bars} by {low_gap}px"
                       f"{'' if gaps else ' (no bar shares its column)'}")
        check(f'[ruling C] {where} @{w}: bottom of the page — nothing interactive is under a fixed bar', ok, detail)
    if start:
        pg.set_viewport_size(start); pg.wait_for_timeout(150)


def check_toast_clear(pg, check, where, clearance=CLEARANCE):
    """[ruling C] With the page scrolled to its end and a toast up: the toast covers
    neither the screen's own chrome (a CTA, a FAB, an action bar) nor the LAST
    interactive element — the last list row's tap target stays tappable — and it sits
    exactly one 12px unit above the bottom chrome. A toast passing over mid-page
    content is what an overlay is for; the end of the content is what must stay clear."""
    scroll_to_bottom(pg)
    r = probe(pg)
    if not r['toasts']:
        check(f'[ruling C] {where}: a toast is up to measure', False, 'no toast on screen')
        return
    # the whole stack is what covers content: the spec's §02 stack is a flex column and
    # vanilla appends too (ui.js toast()), so measure the union of every toast on screen
    ts = r['toasts']
    t = { 'name': f"{len(ts)} toast(s)", 'top': min(x['top'] for x in ts), 'bottom': max(x['bottom'] for x in ts),
          'left': min(x['left'] for x in ts), 'right': max(x['right'] for x in ts) }
    last = r['items'][0] if r['items'] else None
    over_content = [last] if last and _overlaps(t, last) else []
    over_chrome = [b for b in r['bars'] if _overlaps(t, b)]
    below = [g for b in r['bars'] if (g := _vgap(t, b)) is not None and g >= 0]
    gap = min(below, default=None)
    seat = r['vh'] - t['bottom'] if gap is None else gap
    ok = not over_content and not over_chrome and clearance - 1 <= seat <= clearance + 1
    detail = (f"covers the last element «{over_content[0]['name']}» [{over_content[0]['top']}..{over_content[0]['bottom']}] with the toast at [{t['top']}..{t['bottom']}]" if over_content else
              f"covers chrome {over_chrome[0]['name']}" if over_chrome else
              f"{len(ts)} toast(s), seated {seat}px above {'the bottom edge' if gap is None else 'the chrome'}")
    check(f'[ruling C] {where}: the toast covers nothing and sits {clearance}px above the bottom chrome', ok, detail)
