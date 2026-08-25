# Zajil — making an excluded test suite visible

**Commit:** `65088a9` on `hardening/v1.7` · **Not pushed**

---

## The question

> `tests/e2e/live_deployment.py` is committed but did not appear in the
> `run_all.py` output — 15 suites ran and it wasn't one of them.
> Is it deliberately excluded from the runner, or did the runner miss it?

**Deliberate, not missed.** But the distinction was invisible to anyone reading
the output, which is the real defect.

---

## How `run_all.py` selected suites (before)

Verbatim:

```python
HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL = sorted(f for f in glob.glob(os.path.join(HERE, '*.py'))
               if os.path.basename(f) not in ('run_all.py', 'live_deployment.py'))
if '--live' in sys.argv:
    LOCAL.append(os.path.join(HERE, 'live_deployment.py'))
```

And the docstring:

```
live_deployment.py is skipped unless --live is passed, since it needs the
internet and exercises the deployed build rather than the working tree.
```

So the exclusion was explicit in the code and explained in the docstring —
but **nothing reached the output.** A reader saw a list of 15 suites with no
indication that a sixteenth committed file existed and had not run.

---

## Running it directly

```
$ python3 tests/e2e/live_deployment.py

  ✓ secure context (HTTPS)
  ✓ app rendered
  ✓ no failed requests
  ✓ service worker registered at the right scope
  ✓ versioned cache created
  ✓ manifest valid & installable
  ✓ 38-bird example loaded from the live site
  ✓ OFFLINE: app boots with no connection
  ✓ OFFLINE: data intact
  ✓ OFFLINE: pedigree + COI compute
  ✓ zero page errors

11 passed, 0 failed
```

### Why this green does not belong in the default count

It exercises the **deployed build** at
`https://nahdaeverything-web.github.io/Zajildb/`, which is currently
**v1.6.0** — not `hardening/v1.7`, and not the working tree.

That means:

- a **green** result says nothing about uncommitted or unpushed changes;
- a **red** result may only mean the deploy is behind `main`, not that anything
  is broken;
- folding it in would inflate the headline from 148 to 159 with 11 assertions
  that were never about this branch.

Hence opt-in. The problem was never the exclusion — only its invisibility.

---

## The fix

### 1. `run_all.py` — an explicit opt-in table

```python
# Suites that are NOT part of the default run, with the reason shown in the
# output. A suite must never be silently absent: if it does not run, the
# summary says so and why.
OPT_IN = {
    'live_deployment.py': (
        '--live',
        'needs the internet and tests the DEPLOYED build, not the working tree',
    ),
}

LOCAL = sorted(f for f in glob.glob(os.path.join(HERE, '*.py'))
               if os.path.basename(f) not in ({'run_all.py'} | set(OPT_IN)))
skipped = []
for name, (flag, reason) in OPT_IN.items():
    if flag in sys.argv:
        LOCAL.append(os.path.join(HERE, name))
    else:
        skipped.append((name, flag, reason))
LOCAL = sorted(LOCAL)
```

and at the end of the run:

```python
for name, flag, reason in skipped:
    print(f'  [skip] {name:26} not run — {reason} (add {flag})')

print(f'\n  {total_pass} assertions passed, {total_fail} failed, '
      f'{len(failed_suites)} suite(s) errored'
      + (f', {len(skipped)} skipped' if skipped else ''))
```

The suite list is now derived from the **difference** between what exists on
disk and what ran, so a future opt-in suite cannot vanish the same way.

### 2. `tests/e2e/README.md` — a section saying so

> ### One suite is opt-in
>
> **`live_deployment.py` does not run by default.** It needs the internet, and
> it tests the **deployed** build at the GitHub Pages URL — not your working
> tree — so a green result there says nothing about uncommitted changes, and a
> red one may only mean the deploy is behind `main`.
>
> `run_all.py` prints it as `[skip]` with the reason rather than leaving it
> silently absent, so the suite list in the output always accounts for every
> file in this directory.

---

## Verification

Default run, after the change:

```
  [ok  ] subpath_hosting.py         8 passed, 0 failed
  [ok  ] teaching_loft.py           13 passed, 0 failed
  [ok  ] write_boundary.py          6 passed, 0 failed
  [skip] live_deployment.py         not run — needs the internet and tests the DEPLOYED build, not the working tree (add --live)

  148 assertions passed, 0 failed, 0 suite(s) errored, 1 skipped
```

Node suite unchanged:

```
75 passed, 0 failed
```

---

## The general point

The runner built its suite list as *a glob minus an exclusion set*, so anything
excluded simply disappeared — no line, no count, no trace. A test runner is
only trustworthy if its output accounts for **every** suite it can see,
including the ones it chose not to run.

That is now the invariant: the summary reports on the difference between what
exists and what ran, and every exclusion carries its reason and the flag that
lifts it.

---

## State

- `hardening/v1.7`, **14 commits**, not pushed
- `pre-v1.7-baseline` tagged
- node **75 passed, 0 failed** · browser **148 passed, 0 failed, 1 skipped**
- `live_deployment.py` — 11 passed, 0 failed when run directly, against the
  deployed **v1.6.0**
