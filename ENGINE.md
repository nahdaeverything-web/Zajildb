# ENGINE.md — the genetics maths in Zajil, written so a fancier can check it

Everything in this document is implemented in `js/engine/` as pure functions
with no UI or database code, and every worked example below is locked in the
automated test suite (`node tests/run.js`, or the dev panel inside the app:
**Tools → Dev panel → Run tests**). If the implementation ever drifts from
this document, the tests fail.

---

## 1. The pedigree is a graph, not a tree

Each bird stores at most two links: `sireId` (father) and `damId` (mother).
Ancestors are found by walking those links upward. Nothing is ever copied or
denormalised: if the same cock appears in eight places in a pedigree, all
eight are the *same record*, which is exactly what makes inbreeding
computable.

**Cycle rule.** A bird can never be its own ancestor. When you set a parent,
Zajil walks upward from the proposed parent; if it reaches the bird being
edited, the edit is refused and the app names the chain that would close the
loop (e.g. *A ← B ← C*). This is a hard error, never a warning.

## 2. Coefficient of Inbreeding — Wright's formula

The COI (معامل التربية الداخلية) of a bird X estimates the probability that
both copies of a gene in X are descended from one single copy in a common
ancestor of X's parents.

**Wright's path formula.** For every common ancestor A of the sire S and dam
D, and every pair of paths (S up to A, D up to A) that share **no animal
except A itself**:

    F(X) = Σ (1/2)^(n₁ + n₂ + 1) × (1 + F(A))

where

- `n₁` = number of generation steps from the sire up to A,
- `n₂` = number of generation steps from the dam up to A,
- `F(A)` = the common ancestor's **own** inbreeding coefficient, computed the
  same way (this is why an inbred common ancestor contributes *more*).

The app shows the term of this sum for each common ancestor — that is the
**breakdown table** on the pedigree screen. A bare percentage cannot inform
a breeding decision; the breakdown shows *which* ancestor the blood
concentrates through.

**Cross-check.** Zajil also computes the same quantity by the standard
recursive kinship (tabular) method:

    f(A,A) = ½ (1 + F(A))
    f(A,B) = ½ (f(sire_A, B) + f(dam_A, B))   (expanding whichever of A,B
                                               is not an ancestor of the other)
    F(X)   = f(S, D)

The two methods must agree to machine precision; the test suite asserts it on
a deliberately messy linebred pedigree. If the breakdown ever has to be
truncated (pathological pedigrees with tens of thousands of paths), the
*total* COI shown still comes from the kinship method and stays exact.

### Worked examples (hand-checkable)

**Full siblings mated** (both parents shared, grandparents unrelated):
two common ancestors, one path pair each with n₁ = n₂ = 1:

    F = (1/2)³ + (1/2)³ = 0.125 + 0.125 = **0.25**

**Parent × own offspring**: one common ancestor — the parent itself —
with n₁ = 0 (the sire *is* A), n₂ = 1:

    F = (1/2)^(0+1+1) = **0.25**

**Grandparent × granddaughter**: n₁ = 0, n₂ = 2:

    F = (1/2)³ = **0.125**

**Unrelated pair**: no common ancestor, sum is empty: **0**.

**Inbred common ancestor** (this exact family ships in `sample-data.json`):

- The Belgian pair *Gouden 47* × *Blauwe Duivin* produced the full siblings
  **الصقر** and **الريح**.
- Mating them gave **برق**: F(برق) = **0.25** exactly (first example above).
- برق × the unrelated **الملكة** gave the full siblings **سهم** and **شقراء**.
- Pairing سهم × شقراء (the app will warn you!) would give:
  - via برق: (1/2)³ × (1 + 0.25) = 0.125 × 1.25 = 0.15625
  - via الملكة: (1/2)³ × (1 + 0) = 0.125
  - total = **0.28125** — the inbred sire contributes more than the
    outbred dam, which is the whole point of the (1 + F_A) factor.

Check either number in the app with the relationship finder; the tests
assert both to 15 decimal places.

### Depth, and what the number does NOT mean

COI is computed to a configurable depth (default **10 generations**;
Tools → settings). Ancestors beyond the horizon are treated as unrelated
founders. The app therefore always labels the figure
"**pedigree COI at N generations**" and shows pedigree completeness next to
it, because:

- a *shallow or incomplete pedigree understates COI* — missing links can only
  remove paths, never add them;
- this is a **statistic of the recorded pedigree, not a genetic test**. Two
  full siblings can inherit different halves of their parents' genes; COI is
  the expectation, not a measurement.

## 3. Ancestor Loss Coefficient (AVK)

COI can read low while the gene pool is already narrow — e.g. the same four
foundation birds appearing everywhere beyond generation 3 while the parents
themselves share no recent ancestor. AVK (Ahnenverlustkoeffizient, معامل
فقدان الأسلاف) catches that:

    AVK = distinct known ancestors ÷ known pedigree slots × 100  (over N generations)

100 % = every slot a different bird (full outcross). Lower = ancestors
repeat. Zajil computes it over 5 generations by default and reports pedigree
**completeness** (known slots ÷ total slots) alongside, since an AVK from a
half-empty pedigree flatters the collection.

Worked example: 2 generations, 6 slots. If the same grandsire fills two of
them, distinct = 5, filled = 6 → AVK = 83.3 %.

## 4. Relationship finder

For any two birds Zajil reports:

- the **relationship name** (full/half siblings, uncle-niece, first cousins,
  direct line, …), derived from the generation distances to the nearest
  common ancestors;
- the **hypothetical COI of the pairing** — which is simply the kinship
  coefficient f(A,B) of the two birds, i.e. the COI any offspring would have.

This runs automatically when you create a pair, *before* the mating is
recorded. Warning bands: ≥ 25 % severe, ≥ 12.5 % high, ≥ 6.25 % moderate.

## 5. Race velocity

Velocity uses the great-circle (haversine) distance between release point
and loft, over the flight time, in the conventional unit **metres per
minute**:

    velocity = haversine(release, loft) / minutes(arrival − release)

Reference check (in the tests): Aqaba → Amman ≈ 280 km; released 06:00,
home 10:00 → 280 000 m ÷ 240 min ≈ 1 167 m/min.

## 6. FCI eligibility

A result counts toward FCI international awards only if the race had at
least **20 fanciers** and **150 pigeons** entered, it was not a training
toss, and the bird carries an **FCI ring** (ring type `FCI` on the bird —
birds carry multiple rings, and eligibility follows the ring, not the bird's
national registration). The checker (السباقات → فاحص أهلية FCI) names the
exact reason a result fails.
