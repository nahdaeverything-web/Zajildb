"""The language detector, shared by screens/language.py (a local build) and live_deployment.py
(the deployed origin). DERIVED FROM THE DICTIONARY the app ships, never typed: a visible string
"renders in English" when it is the `en` value of a key whose `ar` value differs, an instance of
that key's template, or contains a multi-word phrase of it — and the same the other way round.
It needs no list of surfaces: whatever is on screen is examined.

Nothing here reaches into the app: it reads the DOM and drives the controls a fancier uses, so it
runs unchanged against a production build that carries no harness globals."""
import io
import os
import re

NEXT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))


def norm(s):
    return re.sub(r'\s+', ' ', s).strip()


def parse_dict(path):
    src = io.open(path, encoding='utf-8').read()
    heads = list(re.finditer(r"^\s*'([^'\n]+)':\s*\{", src, re.M))
    out = {}
    for i, m in enumerate(heads):
        body = src[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(src)]
        vals = {}
        for lang in ('ar', 'en'):
            v = re.search(r"\b%s\s*:\s*(['\"`])((?:\\.|(?!\1).)*)\1" % lang, body, re.S)
            if v:
                vals[lang] = re.sub(r'\\(.)', r'\1', v.group(2))
        if len(vals) == 2:
            out[m.group(1)] = vals
    return out


DICT = {**parse_dict(os.path.join(NEXT, 'src', 'i18n.js')), **parse_dict(os.path.join(NEXT, 'src', 'i18n.ext.js'))}
SCRIPT = {'en': re.compile(r'[A-Za-z]'), 'ar': re.compile(r'[؀-ۿ]')}
PUNCT = ' :،,.·…!?؟—-()«»"\''
_PARAM = r'\{[A-Za-z]+\}'


def _lexicon(lang):
    """What `lang` looks like on screen: exact values, template shapes, multi-word phrases —
    only for keys whose two languages actually differ."""
    other = 'ar' if lang == 'en' else 'en'
    letters = lambda s: len(SCRIPT[lang].findall(s))                      # noqa: E731
    exact, templates, phrases = {}, [], []
    for key, e in DICT.items():
        v = norm(e[lang])
        if v == norm(e[other]) or letters(v) < 2:
            continue
        parts = re.split(_PARAM, v)
        if len(parts) > 1:
            if letters(''.join(parts)) >= 4:
                templates.append((re.compile('^' + '.+?'.join(re.escape(p) for p in parts) + '$'), key))
        else:
            exact[v] = key
            exact.setdefault(v.strip(PUNCT), key)
        for p in parts:
            p = p.strip(PUNCT)
            if len(p.split()) >= 2 and letters(p) >= 6:
                phrases.append((p, key))
    return exact, templates, phrases


def _legit(lang):
    """Everything the `lang` dictionary itself can put on screen — a string it produces is
    never leakage from the other language («English», the language button, is Arabic UI)."""
    vals, tpls = set(), []
    for e in DICT.values():
        v = norm(e[lang]); parts = re.split(_PARAM, v)
        if len(parts) > 1:
            tpls.append(re.compile('^' + '.+?'.join(re.escape(p) for p in parts) + '$'))
        else:
            vals.add(v); vals.add(v.strip(PUNCT))
    return vals, tpls


LEX = {'en': _lexicon('en'), 'ar': _lexicon('ar')}
LEGIT = {'en': _legit('en'), 'ar': _legit('ar')}
STATS = {'scanned': 0}

# Text a person can SEE: rendered text nodes (checkVisibility, so a closed <details> and a
# display:none nav do not count), the selected <option> of a visible <select>, and placeholders.
VISIBLE = """() => {
  const seen = (e) => e.checkVisibility({ checkVisibilityCSS: true, contentVisibilityAuto: true, opacityProperty: true, visibilityProperty: true });
  const where = (el) => { const a = el.closest('[data-testid]'); return a ? a.getAttribute('data-testid') : el.tagName.toLowerCase(); };
  const out = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const s = n.textContent.replace(/\\s+/g, ' ').trim(); if (!s) continue;
    const el = n.parentElement;
    if (!el || ['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE'].includes(el.tagName)) continue;
    if (el.tagName === 'OPTION' ? !(el.selected && seen(el.parentElement)) : !seen(el)) continue;
    out.push({ s, where: where(el) });
  }
  for (const el of document.querySelectorAll('input[placeholder], textarea[placeholder]'))
    if (seen(el) && !el.value && el.placeholder.trim()) out.push({ s: el.placeholder.trim(), where: 'placeholder:' + where(el) });
  return out;
}"""


def leaks(pg, app_lang, data=frozenset()):
    """Visible strings in the OTHER language while `app_lang` is applied: [(where, string, key)].
    `data` is the fancier's own content (bird names, a loft name) — never a UI string."""
    other = 'en' if app_lang == 'ar' else 'ar'
    exact, templates, phrases = LEX[other]
    ok_vals, ok_tpls = LEGIT[app_lang]
    found = []
    for item in pg.evaluate(VISIBLE):
        s = norm(item['s']); STATS['scanned'] += 1
        if s in data or s in ok_vals or s.strip(PUNCT) in ok_vals or any(rx.match(s) for rx in ok_tpls):
            continue
        key = exact.get(s) or exact.get(s.strip(PUNCT)) \
            or next((k for rx, k in templates if rx.match(s)), None) \
            or next((k for ph, k in phrases if ph in s), None)
        if key:
            found.append((item['where'], s, key))
    return found


def say(found, n=5):
    seen, out = set(), []
    for w, s, k in found:
        if (w, s) not in seen:
            seen.add((w, s)); out.append(f'{w} «{s[:44]}» ← {k}')
    return f'{len(out)} distinct: ' + ' | '.join(out[:n]) if out else ''


def strings_of(o, acc):
    if isinstance(o, str):
        acc.add(norm(o))
    elif isinstance(o, dict):
        for v in o.values():
            strings_of(v, acc)
    elif isinstance(o, list):
        for v in o:
            strings_of(v, acc)
    return acc


# ── the controls a fancier uses ──────────────────────────────────────────────────────
def open_row(pg, row):   # tools-v2 keeps its controls inside disclosure rows; tools-v1 has none
    r = pg.locator(f'[data-row={row}]')
    if r.count() and r.get_attribute('open') is None:
        r.locator('summary').click(); pg.wait_for_timeout(300)


def set_lang(pg, v, settle=900):
    """Through the language control itself — saveSetting → applySettings → the layer's change event."""
    open_row(pg, 'lang')
    pg.locator(f'[data-testid=set-lang] [data-testid=seg-btn][data-value={v}]').click(); pg.wait_for_timeout(settle)


def tab(pg, href, settle=1500):
    pg.locator(f'[data-testid=nav-link][data-tab="{href}"]:visible').click(); pg.wait_for_timeout(settle)


def nav_labels(pg, which):
    return [x.strip() for x in pg.locator(f'[data-testid={which}] [data-testid=nav-link]').all_inner_texts()]


TABS = ['/birds', '/breeding', '/races', '/health', '/stats', '/tools']
NAV = {lang: [DICT[k][lang] for k in ('nav.birds', 'nav.breeding', 'nav.races', 'nav.health', 'nav.stats', 'nav.tools')] for lang in ('ar', 'en')}
BANNER = {lang: DICT['backup.warn30'][lang] for lang in ('ar', 'en')}
