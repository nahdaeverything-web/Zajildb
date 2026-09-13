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
  // checkVisibility, not computed display: a CLOSED <details> keeps layout boxes for
  // its contents in Chromium, and counting those as page content reports a collision
  // with a bar the fancier can see neither of.
  const vis = (el) => (el.checkVisibility ? el.checkVisibility({ contentVisibilityAuto: true, opacityProperty: true, visibilityProperty: true })
    : (() => { const cs = getComputedStyle(el); return cs.display !== 'none' && cs.visibility !== 'hidden' && +cs.opacity > 0; })());
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

# ─────────────────────────────────────────────────────────────────────────────────
# THE CARET CHECK — added at Phase 6, after the gate's first run.
#
# `npx eslint` had never been part of a gate. Its first run reported 73
# react-hooks/static-components errors: seven screens declared components inside their
# render bodies, so React remounted those subtrees on every render. Where the subtree held
# a text input, the input lost the caret after ONE keystroke. Measured on the bird form:
# typing «برق السريع» into the name field left «ب».
#
# Every screen suite already filled those fields and passed, because Playwright's fill()
# sets the value in one shot and never types a second character. So the assertion that
# catches this class of bug has to TYPE, with a delay, and then ask where the caret is.
# One call per screen that has a text field.
def check_caret(pg, check, testid, text, where, expect=None):
    """Type into a field character by character and prove the caret survived.

    A component created during render is a new type on every render, so React unmounts and
    remounts its DOM — and the field being typed into loses focus after the first
    character. fill() cannot see it; typing can."""
    pg.fill(f'[data-testid={testid}]', '')       # a known starting state; the claim is about typing
    pg.click(f'[data-testid={testid}]')
    pg.type(f'[data-testid={testid}]', text, delay=45)
    got = pg.locator(f'[data-testid={testid}]').input_value()
    focus = pg.evaluate("() => document.activeElement && document.activeElement.getAttribute('data-testid')")
    want = expect if expect is not None else text
    check(f'{where}: «{testid}» keeps the caret while it is typed into, character by character',
          got == want and focus == testid, f'value {got!r} (wanted {want!r}), focus {focus!r}')


# ── fidelity captures: as deterministic as they can honestly be ────────────────
#
# The PNGs under next/fidelity/ are COMMITTED, so every non-deterministic pixel shows up as
# a modified file on every run and drowns any real visual change. Two causes were measured:
# spinner frames, and rendered clock times.
#
# RULED (Phase 7 close): freeze the clock for the CAPTURE ONLY and restore real time after —
# never pin the suite to a permanent constant, because a fixed instant that some assertion
# silently depends on is a lie that fails once a year in a way nobody will diagnose. Where a
# capture shows a timestamp a capture-time freeze cannot reach, seed it from a fixed date in
# the fixture; where neither is clean, let the capture drift and SAY SO.
#
# The clock half of that ruling was implemented, measured, and then REMOVED, because it is
# both useless here and destructive:
#
#   · USELESS — freezing at capture time cannot change text already rendered into the DOM,
#     and Zajil has no ticking relative-time component (no setInterval anywhere in src/ or
#     app/), so nothing repaints from the clock while the shutter is open.
#   · DESTRUCTIVE — `page.clock.set_fixed_time()` WIPES THE PERFORMANCE TIMELINE. Measured:
#         after goto                       navigation entries = 1
#         after screenshot(animations=...)  navigation entries = 1
#         after set_fixed_time              navigation entries = 0   ← and it never comes back
#     `performance.getEntriesByType('navigation').length == 1` is precisely how the suites
#     prove "the register refreshed WITH NO RELOAD" (loft_home change_events#1). Installing
#     the fake clock destroys the evidence. It turned a green suite red, which is how this
#     was found rather than shipped.
#
# So what remains is the half that works: animations='disabled' — finite animations are
# fast-forwarded, infinite ones (the spinners) reset to their first frame. Captures whose
# drift is a rendered timestamp are handled in the fixture or left drifting; next/README.md
# lists which, and why.
def shot(target, path, pg=None, **kw):
    """Screenshot with animations stopped, so a spinner frame is not a diff.

    `target` may be a Page or a Locator; `pg` is accepted for call-site symmetry and is
    unused — it exists so a locator capture reads the same as a page capture."""
    kw.setdefault('animations', 'disabled')
    target.screenshot(path=path, **kw)
