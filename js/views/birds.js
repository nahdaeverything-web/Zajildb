// views/birds.js — Tier 1 #1: the bird register.
// Fast with 1000+ records: in-memory filter + chunked rendering.

import { allBirds, state } from '../db.js';
import { t, fmtNum, statusLabel, escapeHTML } from '../i18n.js';
import { h, clear, birdLabelHTML, sexChipHTML, primaryRing, toast } from '../ui.js';
import { ringKey } from '../engine/rings.js';
import { loftStatuses } from '../db.js';

const CHUNK = 150;

/**
 * Fetch a bundled example loft and import it (works offline via the SW cache).
 * Merges — never destroys whatever the user has already entered.
 */
export async function loadExample(file = './sample-data.json') {
  const { importAll } = await import('../db.js');
  const payload = await (await fetch(file)).json();
  const counts = await importAll(payload, 'merge');
  toast(t('bird.exampleLoaded', { n: counts.birds }), { timeout: 7000 });
}

// View state survives navigation within a session.
const vs = { q: '', status: '', sex: '', own: '', sort: 'newest' };

function searchText(b) {
  return [
    b.name, b.strain, b.colour, b.eyeSign, b.breeder, b.owner, b.acquiredFrom,
    ...(b.rings || []).map((r) => r.raw),
    ...(b.notes || []).map((n) => n.text),
  ].filter(Boolean).join(' ').toLowerCase();
}

function filtered() {
  let birds = allBirds();
  if (vs.own === 'owned') birds = birds.filter((b) => !b.external);
  else if (vs.own === 'external') birds = birds.filter((b) => b.external);
  if (vs.status) birds = birds.filter((b) => b.status === vs.status);
  if (vs.sex) birds = birds.filter((b) => b.sex === vs.sex);
  const q = vs.q.trim().toLowerCase();
  if (q) {
    const rk = ringKey(q);
    birds = birds.filter((b) =>
      searchText(b).includes(q) ||
      (rk && (b.rings || []).some((r) => ringKey(r).includes(rk))));
  }
  const key = {
    newest: (a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''),
    name: (a, b) => (a.name || '￿').localeCompare(b.name || '￿'),
    hatch: (a, b) => (b.hatchDate || '').localeCompare(a.hatchDate || ''),
    ring: (a, b) => primaryRing(a).localeCompare(primaryRing(b)),
  }[vs.sort];
  return birds.sort(key);
}

export function renderBirds() {
  const root = h('section', { class: 'view-birds' });

  const search = h('input', {
    type: 'search', class: 'input search-input', value: vs.q,
    placeholder: t('act.search') + '…', 'aria-label': t('act.search'),
  });
  const statusSel = h('select', { class: 'input input-compact' },
    h('option', { value: '' }, t('bird.status') + ': ' + t('common.all')),
    loftStatuses().map((s) => h('option', { value: s, selected: vs.status === s }, statusLabel(s))));
  const sexSel = h('select', { class: 'input input-compact' },
    h('option', { value: '' }, t('bird.sex') + ': ' + t('common.all')),
    ['cock', 'hen', 'unknown'].map((s) => h('option', { value: s, selected: vs.sex === s }, t('sex.' + s))));
  const ownSel = h('select', { class: 'input input-compact' },
    h('option', { value: '' }, t('filter.ownership') + ': ' + t('common.all')),
    h('option', { value: 'owned', selected: vs.own === 'owned' }, t('filter.ownedOnly')),
    h('option', { value: 'external', selected: vs.own === 'external' }, t('filter.externalOnly')));
  const sortSel = h('select', { class: 'input input-compact' },
    [['newest', '↓ ' + t('common.date')], ['name', t('bird.name')], ['hatch', t('bird.hatchDate')], ['ring', t('bird.ring')]]
      .map(([v, l]) => h('option', { value: v, selected: vs.sort === v }, l)));

  const count = h('div', { class: 'muted result-count' });
  const list = h('div', { class: 'bird-list', role: 'list' });
  const sentinel = h('div', { class: 'list-sentinel' });

  let rows = [];
  let shown = 0;

  function renderChunk() {
    const frag = document.createDocumentFragment();
    const end = Math.min(shown + CHUNK, rows.length);
    for (; shown < end; shown++) frag.append(row(rows[shown]));
    list.append(frag);
    sentinel.hidden = shown >= rows.length;
  }

  function row(b) {
    return h('a', {
      class: 'bird-row', role: 'listitem', href: '#/bird/' + b.id,
      html: `
        <span class="bird-row-main">${birdLabelHTML(b)}</span>
        <span class="bird-row-meta">
          ${sexChipHTML(b.sex)}
          ${b.strain ? `<bdi class="chip">${escapeHTML(b.strain)}</bdi>` : ''}
          <span class="chip chip-status">${escapeHTML(statusLabel(b.status))}</span>
          ${b.hatchDate ? `<span class="muted">${escapeHTML(fmtNum(+b.hatchDate.slice(0, 4), { group: false }))}</span>` : ''}
          ${b.external ? `<span class="chip chip-ext">${escapeHTML(t('bird.externalShort'))}</span>` : ''}
        </span>`,
    });
  }

  function refresh() {
    rows = filtered();
    shown = 0;
    clear(list);
    const ext = rows.filter((b) => b.external).length;
    count.textContent = t('common.results', { n: rows.length }) +
      (ext && !vs.own ? ` — ${t('filter.externalOnly')}: ${fmtNum(ext)}` : '');
    if (!state.birds.size) {
      list.append(h('div', { class: 'empty-state' },
        h('p', {}, t('bird.noBirds')),
        h('div', { class: 'row-inline', style: 'justify-content:center' },
          h('a', { class: 'btn btn-primary', href: '#/bird/new' }, '+ ' + t('act.newBird'))),
        h('p', { class: 'muted small' }, t('bird.loadExample')),
        h('div', { class: 'row-inline', style: 'justify-content:center' },
          h('button', { class: 'btn', onclick: () => loadExample('./sample-data.json') }, '📚 ' + t('bird.exampleSmall')),
          h('button', { class: 'btn', onclick: () => loadExample('./example-loft-large.json') }, '📚 ' + t('bird.exampleLarge')))));
      sentinel.hidden = true;
      return;
    }
    renderChunk();
  }

  let debounce = null;
  search.addEventListener('input', () => {
    vs.q = search.value;
    clearTimeout(debounce);
    debounce = setTimeout(refresh, 120);
  });
  statusSel.addEventListener('change', () => { vs.status = statusSel.value; refresh(); });
  sexSel.addEventListener('change', () => { vs.sex = sexSel.value; refresh(); });
  ownSel.addEventListener('change', () => { vs.own = ownSel.value; refresh(); });
  sortSel.addEventListener('change', () => { vs.sort = sortSel.value; refresh(); });

  const io = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) renderChunk();
  });
  io.observe(sentinel);

  root.append(
    h('div', { class: 'view-head' },
      h('h1', {}, t('nav.birds')),
      h('a', { class: 'btn btn-primary', href: '#/bird/new' }, '+ ' + t('act.newBird'))),
    h('div', { class: 'filter-bar' }, search, ownSel, statusSel, sexSel, sortSel),
    count, list, sentinel,
  );
  refresh();
  return root;
}
