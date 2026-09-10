// engine/pedigree.js — pure pedigree traversal. No DOM, no IndexedDB.
//
// Every function takes `getBird(id) -> bird|null` so the engine is storage-
// agnostic and unit-testable. A bird's parents are `sireId` / `damId`.

/**
 * Breadth-first ancestor map from one or more roots.
 * Returns Map<id, minDepth> where roots have the depth they were seeded with.
 * Traversal stops descending past `maxDepth` (generations).
 */
export function ancestorDepths(getBird, rootIds, maxDepth = 10, rootDepth = 0) {
  const depth = new Map();
  const queue = [];
  for (const id of rootIds) if (id) queue.push([id, rootDepth]);
  while (queue.length) {
    const [id, d] = queue.shift();
    if (depth.has(id) && depth.get(id) <= d) continue;
    depth.set(id, d);
    if (d >= maxDepth) continue;
    const b = getBird(id);
    if (!b) continue;
    if (b.sireId) queue.push([b.sireId, d + 1]);
    if (b.damId) queue.push([b.damId, d + 1]);
  }
  return depth;
}

/**
 * Truncated parent graph for COI/kinship work.
 * Seeds at `rootDepth` (use 1 when roots are the subject's parents, so
 * `maxDepth` counts generations of the *subject's* pedigree).
 * Ancestors at depth === maxDepth are treated as founders (parents unknown).
 * Returns { depth: Map<id,minDepth>, parents: Map<id,{sireId,damId}> }.
 */
export function truncatedGraph(getBird, rootIds, maxDepth = 10, rootDepth = 1) {
  const depth = new Map();
  const parents = new Map();
  const queue = [];
  for (const id of rootIds) if (id) queue.push([id, rootDepth]);
  while (queue.length) {
    const [id, d] = queue.shift();
    if (depth.has(id) && depth.get(id) <= d) continue;
    depth.set(id, d);
    const b = getBird(id);
    if (b && d < maxDepth) {
      parents.set(id, { sireId: b.sireId || null, damId: b.damId || null });
      if (b.sireId) queue.push([b.sireId, d + 1]);
      if (b.damId) queue.push([b.damId, d + 1]);
    } else if (!parents.has(id)) {
      parents.set(id, { sireId: null, damId: null });
    }
  }
  return { depth, parents };
}

/**
 * Would setting `parentId` as a parent of `childId` create a cycle?
 * True iff childId === parentId, or childId is already an ancestor of parentId.
 * Returns { cycle: boolean, path: [ids] } — path names the offending link
 * chain parentId -> ... -> childId so the UI can say exactly which link loops.
 */
export function wouldCreateCycle(getBird, childId, parentId) {
  if (!childId || !parentId) return { cycle: false, path: [] };
  if (childId === parentId) return { cycle: true, path: [childId] };
  // DFS from parentId upward looking for childId
  const stack = [[parentId, [parentId]]];
  const seen = new Set();
  while (stack.length) {
    const [id, path] = stack.pop();
    if (seen.has(id)) continue;
    seen.add(id);
    const b = getBird(id);
    if (!b) continue;
    for (const pid of [b.sireId, b.damId]) {
      if (!pid) continue;
      if (pid === childId) return { cycle: true, path: [...path, pid] };
      stack.push([pid, [...path, pid]]);
    }
  }
  return { cycle: false, path: [] };
}

/**
 * Pedigree grid for rendering / certificates.
 * Returns an array of generations; generation g (0 = subject) is an array of
 * 2^g slots, each { id, bird } or null when unknown. Slot order within a
 * generation is [sire-line..., dam-line...] following the classic layout:
 * index i's parents land at 2i (sire) and 2i+1 (dam) in the next generation.
 * Layout direction (LTR/RTL mirroring) is entirely the renderer's concern.
 */
export function pedigreeGrid(getBird, subjectId, generations = 4) {
  const gens = [];
  let current = [subjectId ? { id: subjectId, bird: getBird(subjectId) } : null];
  gens.push(current);
  for (let g = 1; g <= generations; g++) {
    const next = new Array(2 ** g).fill(null);
    for (let i = 0; i < current.length; i++) {
      const slot = current[i];
      if (!slot || !slot.bird) continue;
      const { sireId, damId } = slot.bird;
      if (sireId) next[2 * i] = { id: sireId, bird: getBird(sireId) };
      if (damId) next[2 * i + 1] = { id: damId, bird: getBird(damId) };
    }
    gens.push(next);
    current = next;
  }
  return gens;
}

/** All descendants of a bird (BFS down), as Map<id, minDepth>. */
export function descendantDepths(getAllBirds, rootId, maxDepth = 20) {
  // getAllBirds() -> iterable of birds. Build child index once.
  const children = new Map();
  for (const b of getAllBirds()) {
    for (const pid of [b.sireId, b.damId]) {
      if (!pid) continue;
      if (!children.has(pid)) children.set(pid, []);
      children.get(pid).push(b.id);
    }
  }
  const depth = new Map();
  const queue = [[rootId, 0]];
  while (queue.length) {
    const [id, d] = queue.shift();
    if (id !== rootId) {
      if (depth.has(id) && depth.get(id) <= d) continue;
      depth.set(id, d);
    }
    if (d >= maxDepth) continue;
    for (const cid of children.get(id) || []) queue.push([cid, d + 1]);
  }
  return depth;
}
