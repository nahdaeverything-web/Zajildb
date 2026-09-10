// engine/coi.js — Coefficient of Inbreeding (Wright) + Ancestor Loss (AVK).
//
// Two independent computations that must agree (asserted in tests):
//   1. kinship()  — recursive coefficient-of-kinship (tabular-equivalent),
//      memoised. F(X) = f(sire_X, dam_X).
//   2. coiBreakdown() — Wright's path method: per common ancestor A,
//      contribution = Σ over valid path pairs (1/2)^(n1+n2+1) × (1 + F_A),
//      where a path pair is valid iff the two paths share no animal except A.
//
// Both run on a depth-truncated pedigree (ancestors beyond `maxDepth`
// generations of the subject are treated as unrelated founders), so the
// result is explicitly a "pedigree COI at N generations".

import { truncatedGraph } from './pedigree.js';

/**
 * Build a memoised kinship function over a truncated parent graph.
 * parents: Map<id, {sireId, damId}> (missing/null parent = founder).
 * f(a,b) = coefficient of kinship; F(x) = f(sire_x, dam_x).
 */
export function makeKinship(parents) {
  const memo = new Map();
  const ancMemo = new Map();

  function ancestorSet(id) {
    if (ancMemo.has(id)) return ancMemo.get(id);
    const set = new Set();
    const stack = [id];
    while (stack.length) {
      const cur = stack.pop();
      if (set.has(cur)) continue;
      set.add(cur); // includes self
      const p = parents.get(cur);
      if (!p) continue;
      if (p.sireId) stack.push(p.sireId);
      if (p.damId) stack.push(p.damId);
    }
    ancMemo.set(id, set);
    return set;
  }

  function f(a, b) {
    if (!a || !b) return 0;
    if (a === b) {
      const p = parents.get(a) || {};
      return 0.5 * (1 + f(p.sireId || null, p.damId || null));
    }
    const key = a < b ? a + '|' + b : b + '|' + a;
    if (memo.has(key)) return memo.get(key);
    memo.set(key, 0); // cycle guard; real pedigrees are acyclic (enforced at edit time)
    // Recurse on the animal that is NOT an ancestor of the other.
    let expand = b, other = a;
    if (ancestorSet(a).has(b)) { expand = a; other = b; }
    const p = parents.get(expand) || {};
    const val = 0.5 * (f(p.sireId || null, other) + f(p.damId || null, other));
    memo.set(key, val);
    return val;
  }

  f.ancestorSet = ancestorSet;
  return f;
}

/**
 * Inbreeding coefficient of an existing bird at maxDepth generations.
 * Returns { coi, generations }.
 */
export function inbreeding(getBird, birdId, maxDepth = 10) {
  const b = getBird(birdId);
  if (!b || !b.sireId || !b.damId) return { coi: 0, generations: maxDepth };
  return { coi: pairCOI(getBird, b.sireId, b.damId, maxDepth).coi, generations: maxDepth };
}

/**
 * Hypothetical COI of offspring of (sireId × damId) — kinship method only.
 * Cheap; use for lists and warnings. Returns { coi }.
 */
export function pairCOI(getBird, sireId, damId, maxDepth = 10) {
  if (!sireId || !damId) return { coi: 0 };
  const { parents } = truncatedGraph(getBird, [sireId, damId], maxDepth, 1);
  const f = makeKinship(parents);
  return { coi: f(sireId, damId) };
}

const MAX_PATHS_PER_ANCESTOR = 20000;
const MAX_PAIRS_PER_ANCESTOR = 200000;

/** All simple paths (arrays of ids, from -> ... -> to) going strictly upward. */
function pathsUp(parents, from, to, cap) {
  const out = [];
  const path = [];
  function dfs(id) {
    if (out.length >= cap) return;
    path.push(id);
    if (id === to) {
      out.push([...path]);
    } else {
      const p = parents.get(id);
      if (p) {
        if (p.sireId) dfs(p.sireId);
        if (p.damId) dfs(p.damId);
      }
    }
    path.pop();
  }
  dfs(from);
  return out;
}

/**
 * Full Wright path-method COI with per-ancestor breakdown.
 * Returns {
 *   coi,                    // sum of contributions (=== kinship value)
 *   kinshipCOI,             // independent cross-check value
 *   generations,
 *   truncated,              // true if a path cap was hit (breakdown partial;
 *                           //   coi then reports kinshipCOI which stays exact)
 *   contributions: [{ ancestorId, ancestorF, nPathPairs, minPathLen, contribution }],
 * }
 */
export function coiBreakdown(getBird, sireId, damId, maxDepth = 10) {
  const generations = maxDepth;
  if (!sireId || !damId) {
    return { coi: 0, kinshipCOI: 0, generations, truncated: false, contributions: [] };
  }
  const { parents } = truncatedGraph(getBird, [sireId, damId], maxDepth, 1);
  const f = makeKinship(parents);
  const kinshipCOI = f(sireId, damId);

  const sireAnc = f.ancestorSet(sireId); // includes sire itself
  const damAnc = f.ancestorSet(damId);
  const common = [...sireAnc].filter((id) => damAnc.has(id));

  let truncated = false;
  const contributions = [];
  for (const A of common) {
    const p1s = pathsUp(parents, sireId, A, MAX_PATHS_PER_ANCESTOR);
    const p2s = pathsUp(parents, damId, A, MAX_PATHS_PER_ANCESTOR);
    if (p1s.length >= MAX_PATHS_PER_ANCESTOR || p2s.length >= MAX_PATHS_PER_ANCESTOR ||
        p1s.length * p2s.length > MAX_PAIRS_PER_ANCESTOR) {
      truncated = true;
      continue;
    }
    const pA = parents.get(A) || {};
    const FA = f(pA.sireId || null, pA.damId || null);
    let contribution = 0;
    let nPathPairs = 0;
    let minPathLen = Infinity;
    for (const p1 of p1s) {
      // set of intermediates on p1 (everything except the apex A)
      const inter1 = new Set(p1);
      inter1.delete(A);
      for (const p2 of p2s) {
        let shares = false;
        for (const id of p2) {
          if (id !== A && inter1.has(id)) { shares = true; break; }
        }
        if (shares) continue;
        const n1 = p1.length - 1;
        const n2 = p2.length - 1;
        contribution += Math.pow(0.5, n1 + n2 + 1) * (1 + FA);
        nPathPairs++;
        if (n1 + n2 < minPathLen) minPathLen = n1 + n2;
      }
    }
    if (nPathPairs > 0) {
      contributions.push({ ancestorId: A, ancestorF: FA, nPathPairs, minPathLen, contribution });
    }
  }
  contributions.sort((a, b) => b.contribution - a.contribution);
  const pathSum = contributions.reduce((s, c) => s + c.contribution, 0);
  return {
    coi: truncated ? kinshipCOI : pathSum,
    kinshipCOI,
    generations,
    truncated,
    contributions,
  };
}

/**
 * Ancestor Loss Coefficient (AVK) over N generations.
 * AVK = distinct known ancestors ÷ known (filled) pedigree slots × 100.
 * Also reports completeness = filled slots ÷ total slots × 100, because a
 * shallow pedigree can make AVK look better than it is.
 * Returns { avk, completeness, distinct, filled, total, generations }.
 */
export function ancestorLoss(getBird, birdId, generations = 5) {
  let filled = 0;
  const distinct = new Set();
  let current = [birdId];
  let total = 0;
  for (let g = 1; g <= generations; g++) {
    const next = [];
    for (const id of current) {
      const b = id ? getBird(id) : null;
      next.push(b ? b.sireId || null : null);
      next.push(b ? b.damId || null : null);
    }
    total += next.length;
    for (const id of next) {
      if (id) { filled++; distinct.add(id); }
    }
    current = next;
  }
  return {
    avk: filled ? (distinct.size / filled) * 100 : 100,
    completeness: total ? (filled / total) * 100 : 0,
    distinct: distinct.size,
    filled,
    total,
    generations,
  };
}
