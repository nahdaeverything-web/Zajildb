"""THE NET — every stub-backed suite proves its stub intercepts (RULED 2026-10-08, after TF-6).

TF-6: the deploy gate read the backend host from the deployed config with the wrong shape, routed
no stub, and its sign-in reached the real dev project. "Safe by construction" — a build that
carries no endpoint, a made-up stub host — is not the same as asserted, and the next suite written
against a CONFIGURED build inherits the gap. So every suite that stubs the backend arms this net
BENEATH its stub and asserts, at its end, that nothing escaped.

    from _net import Net
    NET = Net()
    ctx = NET.arm(check=check, ctx=browser.new_context(...))   # BEFORE the suite's own ctx.route(STUB + '/**', …)
    ...
    NET.assert_empty(check)                                    # just before the summary line

Playwright matches routes newest-first and page routes before context routes, so a net armed on a
context before the stub is registered (on that context or on any of its pages) is the fallback
behind the stub: a request to the backend host family that no stub answers is ABORTED on the device
— it never leaves — and FAILED AT ONCE through the suite's own check(). At once, because a suite
whose sign-in was just aborted usually dies before its summary line (measured 2026-10-08 on gate.py
and sign_in.py): the escape must be a counted ✗ in the output before that. The end-of-suite line is
the zero assertion.
"""
import re

# the backend host family; the dev project, the production project and any project yet to be made
FAMILY = re.compile(r'^https://[a-z0-9-]+\.supabase\.co/.*')

LABEL = ('[NET] every request to the backend host family was answered by a stub'
         ' — nothing reached the real project')


class Net:
    def __init__(self):
        self.escaped = []
        self.check = None

    def _catch(self, route, request):
        hit = f'{request.method} {request.url[:80]}'
        self.escaped.append(hit)
        if self.check: self.check(f'[NET] a request to the backend host family was answered by NO stub — aborted on the device, never sent: {hit}', False)
        else: print(f'  ! [NET] aborted on the device, never sent: {hit}', flush=True)
        route.abort()

    def arm(self, ctx, check=None):
        """Register the fallback on a context, before the stub is routed on it or its pages.
        `check` is the suite's own check(name, condition, detail); each escape fails through it at once."""
        if check: self.check = check
        ctx.route(FAMILY, self._catch)
        return ctx

    def assert_empty(self, check):
        """The zero assertion at the suite's end."""
        check(LABEL, not self.escaped, '; '.join(self.escaped[:3]))
