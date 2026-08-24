// views/pedigree.js — Tier 1 #2/#3: pedigree tree (3/4/5 generations) and the
// COI panel with per-ancestor breakdown, AVK, and the relationship finder.
//
// RTL mirroring: the tree is a CSS grid laid out in *logical* order —
// column 1 is the subject, deeper generations in later columns. CSS grid
// tracks flow with the document direction, so in Arabic the subject sits on
// the RIGHT and ancestors extend LEFT with no special-casing here.

import { getBird, state } from '../db.js';
import { t, fmtNum, fmtPercent, fmtDate, escapeHTML } from '../i18n.js';
import { h, clear, birdLabelHTML, sexIcon, sexChipHTML, birdPicker, fmtCOIBadge } from '../ui.js';
import { pedigreeGrid } from '../engine/pedigree.js';
import { coiBreakdown, ancestorLoss } from '../engine/coi.js';
import { describeRelationship, pairingWarningLevel } from '../engine/relationship.js';
import { navigate, navigateReplace } from '../app.js';

const vs = { gens: 4 };

export function renderPedigree(id) {
  const bird = getBird(id);
  if (!bird) { navigateReplace('#/birds'); return null; }
  const root = h('section', { class: 'view-pedigree' });
  const depth = +(state.settings.coiDepth || 10);

  const genBtns = h('div', { class: 'seg' },
    [3, 4, 5].map((g) => h('button', {
      class: 'seg-btn' + (vs.gens === g ? ' active' : ''),
      onclick: () => { vs.gens = g; navigate('#/pedigree/' + id); rerenderTree(); },
    }, fmtNum(g, { group: false }))));

  const treeWrap = h('div', { class: 'tree-scroll' });
  function rerenderTree() {
    clear(treeWrap);
    treeWrap.append(buildTree(id, vs.gens));
    root.querySelectorAll('.seg-btn').forEach((b, i) => b.classList.toggle('active', [3, 4, 5][i] === vs.gens));
  }
  rerenderTree();

  root.append(
    h('div', { class: 'view-head' },
      h('h1', { html: t('ped.title') + ' — ' + birdLabelHTML(bird) }),
      h('div', { class: 'head-tools' },
        h('span', { class: 'muted' }, t('ped.generations') + ':'), genBtns,
        h('a', { class: 'btn', href: '#/cert/' + id }, '📜 ' + t('act.certificate')))),
    treeWrap,
    h('div', { class: 'sex-legend muted small' },
      h('span', { html: sexChipHTML('cock') }),
      h('span', { html: sexChipHTML('hen') }),
      h('span', { html: sexChipHTML('unknown') })),
    coiPanel(bird, depth),
    relationshipFinder(id, depth),
  );
  return root;
}

/** The tree itself — reusable for the certificate view. */
export function buildTree(subjectId, gens, { linkCards = true } = {}) {
  const grid = pedigreeGrid(getBird, subjectId, gens);
  const rows = 2 ** gens;
  const tree = h('div', {
    class: 'ped-grid',
    style: `--ped-cols:${gens + 1};--ped-rows:${rows};`,
  });
  for (let g = 0; g < grid.length; g++) {
    const span = 2 ** (gens - g);
    for (let i = 0; i < grid[g].length; i++) {
      const slot = grid[g][i];
      const cell = h(linkCards && slot ? 'a' : 'div', {
        class: 'ped-cell' + (slot ? ' ped-known gen-' + g : ' ped-unknown') +
          (slot && slot.bird ? ' sex-' + slot.bird.sex : ''),
        style: `grid-column:${g + 1};grid-row:${i * span + 1} / span ${span};`,
        href: linkCards && slot ? '#/bird/' + slot.id : undefined,
      });
      if (slot && slot.bird) {
        const b = slot.bird;
        cell.innerHTML = `
          <span class="ped-name">${birdLabelHTML(b)}</span>
          <span class="ped-meta">${sexIcon(b.sex)}${b.hatchDate ? ' · ' + escapeHTML(fmtNum(+b.hatchDate.slice(0, 4), { group: false })) : ''}${b.strain ? ' · <bdi>' + escapeHTML(b.strain) + '</bdi>' : ''}</span>`;
      } else if (slot) {
        cell.innerHTML = `<span class="ped-name">${birdLabelHTML(null)}</span>`;
      } else {
        cell.innerHTML = `<span class="ped-name muted">${escapeHTML(t('ped.unknownAncestor'))}</span>`;
      }
      tree.append(cell);
    }
  }
  return tree;
}

function coiPanel(bird, depth) {
  const panel = h('div', { class: 'card coi-panel' },
    h('h2', {}, t('ped.coi')));
  if (!bird.sireId || !bird.damId) {
    panel.append(h('p', { class: 'muted' }, t('ped.noCommonAncestors')));
    return panel;
  }
  const br = coiBreakdown(getBird, bird.sireId, bird.damId, depth);
  const avk = ancestorLoss(getBird, bird.id, 5);

  panel.append(
    h('p', { class: 'coi-headline', html: `${escapeHTML(t('ped.coiAtN', { n: depth }))}: ${fmtCOIBadge(br.coi)}` }),
    h('p', { class: 'muted small' }, t('ped.coiCaveat')),
    h('p', {}, h('strong', {}, t('ped.avk') + ': '), fmtPercent(avk.avk / 100, 1),
      h('span', { class: 'muted' }, ` (${t('ped.completeness')}: ${fmtPercent(avk.completeness / 100, 0)})`),
      h('div', { class: 'muted small' }, t('ped.avkHint'))),
  );

  if (br.truncated) panel.append(h('p', { class: 'warn' }, t('ped.breakdownTruncated')));

  if (br.contributions.length) {
    const tbl = h('table', { class: 'table' },
      h('thead', {}, h('tr', {},
        h('th', {}, t('ped.commonAncestor')),
        h('th', {}, t('ped.pathPairs')),
        h('th', {}, t('ped.ancestorF')),
        h('th', {}, t('ped.contribution')))),
      h('tbody', {}, br.contributions.map((c) => {
        const a = getBird(c.ancestorId);
        return h('tr', {},
          h('td', { html: a ? `<a href="#/bird/${c.ancestorId}">${birdLabelHTML(a)}</a>` : c.ancestorId.slice(0, 8) }),
          h('td', {}, fmtNum(c.nPathPairs)),
          h('td', {}, fmtPercent(c.ancestorF, 1)),
          h('td', {}, fmtPercent(c.contribution, 2)));
      })));
    panel.append(h('h3', {}, t('ped.breakdown')), h('div', { class: 'table-scroll' }, tbl));
  } else {
    panel.append(h('p', { class: 'muted' }, t('ped.noCommonAncestors')));
  }
  return panel;
}

/** Relationship finder: this bird × any other. Also used before pairing. */
function relationshipFinder(id, depth) {
  const out = h('div', { class: 'rel-result' });
  const picker = birdPicker({
    filter: (b) => b.id !== id,
    onPick: (otherId) => {
      clear(out);
      if (!otherId) return;
      out.append(relationshipSummary(id, otherId, depth));
    },
  });
  return h('div', { class: 'card' },
    h('h2', {}, t('rel.finder')),
    picker, out);
}

/** Shared with the breeding view: relationship + hypothetical-COI warning. */
export function relationshipSummary(aId, bId, depth = 8) {
  const rel = describeRelationship(getBird, aId, bId, depth);
  const level = pairingWarningLevel(rel.hypotheticalCOI);
  const coiStr = fmtPercent(rel.hypotheticalCOI, 2);
  const wrap = h('div', {});
  wrap.append(
    h('p', {}, h('strong', {}, t('rel.title') + ': '), t(rel.key, rel.params)),
    h('p', {}, t('rel.hypCOI') + ': ', h('span', { html: fmtCOIBadge(rel.hypotheticalCOI) })),
    h('p', { class: 'warn-' + level }, t('rel.warn.' + level, { coi: coiStr })),
  );
  return wrap;
}
