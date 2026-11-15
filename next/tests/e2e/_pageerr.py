"""THE PAGE-ERROR RECORD (TF-12, RULED 2026-11-14) — test-only.

On 2026-11-14 one full gate failed one check, once:
    ✗ zero page errors across 10 devices  ["Cannot read properties of undefined (reading 'name')"]
and that line was everything there was: every suite's `pageerror` hook kept `str(e)`, the message alone. No stack,
no screen, no device, no step — so one sighting could say nothing about its source. This helper is what every hook
now calls instead:

    page.on('pageerror', lambda e, _p=page: errs.append(perr(e, _p)))

It returns the message FIRST (so a suite that looks for a substring still finds it) followed by the page address,
the device (which context, which page in it, the viewport, a label if the suite passes one), the step (the last ✓/✗
line this process printed before the error — read off stdout, so no suite's check() had to change) and the stack.
It also prints the whole record at once, where it happens in the output, and appends it to $ZAJIL_PAGEERR_LOG when
that is set, because the gate keeps only a failed suite's ✗ lines.
"""
import os, sys, time

_T0 = time.time(); _last = {'line': '(no check printed yet)'}; _n = {'n': 0}

class _Tee:
    def __init__(self, w): self._w = w
    def write(self, s):
        for line in str(s).splitlines():
            t = line.strip()
            if t[:1] in ('✓', '✗'): _last['line'] = t[:200]
        return self._w.write(s)
    def __getattr__(self, k): return getattr(self._w, k)

if not isinstance(sys.stdout, _Tee): sys.stdout = _Tee(sys.stdout)

def _safe(f, default='?'):
    try: return f()
    except Exception: return default

def perr(e, page=None, device=None):
    _n['n'] += 1
    msg = str(e); stack = ' ⏎ '.join(str(getattr(e, 'stack', '') or '').splitlines())[:1500]
    url = _safe(lambda: page.url)
    vp = _safe(lambda: '{width}x{height}'.format(**page.viewport_size))
    where = _safe(lambda: f'context {page.context.browser.contexts.index(page.context) + 1}, page {page.context.pages.index(page) + 1}')
    dev = f'{device + " · " if device else ""}{where} · viewport {vp}'
    rec = f'{msg} | at {url} | device: {dev} | step: after «{_last["line"]}» | {time.time() - _T0:.1f} s into {os.path.basename(sys.argv[0])} | stack: {stack or "(none given)"}'
    print(f'    !! PAGE ERROR #{_n["n"]}: {rec}', flush=True)
    log = os.environ.get('ZAJIL_PAGEERR_LOG')
    if log:
        try:
            with open(log, 'a', encoding='utf-8') as f: f.write(time.strftime('%Y-%m-%dT%H:%M:%S ') + rec + '\n')
        except Exception: pass
    return rec
