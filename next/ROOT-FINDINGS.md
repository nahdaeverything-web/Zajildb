# Root findings surfaced by the port

Inconsistencies in the **vanilla** tree (everything outside `next/`) that the
React port surfaced while copying and re-proving it. The root is read-only
during the port, so nothing here is fixed at source. Each entry names the
file and line, what is wrong, why it matters, and what the port did about it
on its own side. They land in the root `BACKLOG.md` as one docs commit at
Phase 7.

Rule for adding to this file: an entry needs a `file:line`, a reproduction,
and the port-side handling. An observation without evidence does not go in.

---

## RF-1 — `tests/e2e/write_boundary.py` hardcodes the server port

**Where:** [`tests/e2e/write_boundary.py:19`](../tests/e2e/write_boundary.py#L19)
```python
page.goto('http://127.0.0.1:8123/',wait_until='networkidle'); page.wait_for_timeout(800)
```
**What:** every other local suite reads `ZAJIL_URL` (29 of 32 files under
`tests/e2e/`); this one does not, so `ZAJIL_URL` has no effect on it.

**Why it matters:** it is the R6 class of defect — a test that talks to a
server it did not start. Point the runner at any other port and this suite
still tests whatever is (or is not) on 8123: a stale server, another
checkout, or nothing. In the port it went to an empty port and failed with
`undefined.importAll`, which is how it was found; against a forgotten server
it would have passed about the wrong tree.

**Port handling:** the copy at `next/tests/e2e/write_boundary.py` reads
`ZAJIL_URL` — a URL-only change, permitted by the Phase 2 order. Root
untouched.

**Fix at source (Phase 7):** `page.goto(os.environ.get('ZAJIL_URL', 'http://127.0.0.1:8123/'), …)` — the idiom its siblings use.

---

## RF-2 — root browser suites exit 0 on assertion failure

**Where:** 28 of the 31 local suites in `tests/e2e/` end by printing a
summary and never call `sys.exit`. Two representatives:
- [`tests/e2e/resurrection.py:127`](../tests/e2e/resurrection.py#L127) — `print(f'\n{ok} passed, {fail} failed')`, last line
- [`tests/e2e/tombstones.py:121`](../tests/e2e/tombstones.py#L121) — same

Only `auth_live.py`, `pull_live.py` and `push_live.py` exit nonzero on
failure.

**What:** the process exit code is 0 whether `fail` is 0 or 20. The ONLY
thing that converts failures into a nonzero exit is the runner —
[`tests/e2e/run_all.py:63`](../tests/e2e/run_all.py#L63) parses the
`… failed` token out of the summary text,
[`:67`](../tests/e2e/run_all.py#L67) flags the suite, and
[`:81`](../tests/e2e/run_all.py#L81) exits 1.

**Why it matters:** anyone who runs a suite directly
(`python3 tests/e2e/tombstones.py`), chains one with `&&`, or wires one into
CI without the runner gets **green on red**. Reproduced during the Phase 2
mutation proof: with tombstones deliberately broken, `resurrection.py`
printed `12 passed, 4 failed` and exited **0**. A suite whose exit code
cannot say "failed" is green-that-proves-nothing outside the one script that
knows to read its stdout.

**Port handling:** `next/tests/e2e/*.py` are verbatim copies except the
module token, so they inherit this; `next/tests/e2e/run_all.py` mirrors the
root runner's parsing and is the gate. The port's own new test
(`next/tests/bridge/react_bridge.py`) exits 1 on failure.

**Fix at source (Phase 7):** append `sys.exit(1 if fail else 0)` after the
summary print in each suite (28 one-line changes), and keep the runner's
parse as belt-and-braces. Then a direct run means what it says.
