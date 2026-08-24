// views/stats.js — Tier 2 #11: loft statistics. COI distribution across the
// collection, breakdowns by strain, status, sex, FCI ring count.

import { getBird, allBirds, state } from '../db.js';
import { t, fmtNum, fmtPercent, statusLabel } from '../i18n.js';
import { h, birdLabelHTML } from '../ui.js';
import { inbreeding } from '../engine/coi.js';
import { hasFCIRing } from '../engine/fci.js';

export function renderStats() {
  const root = h('section', { class: 'view-stats' });
  const birds = allBirds().filter((b) => !b.external);
  const depth = +(state.settings.coiDepth || 10);

  root.append(h('div', { class: 'view-head' }, h('h1', {}, t('stats.title'))));

  // headline numbers
  const fciCount = birds.filter(hasFCIRing).length;
  root.append(h('div', { class: 'stat-grid card' },
    stat(t('stats.totalBirds'), fmtNum(birds.length)),
    stat(t('sex.cock'), fmtNum(birds.filter((b) => b.sex === 'cock').length)),
    stat(t('sex.hen'), fmtNum(birds.filter((b) => b.sex === 'hen').length)),
    stat(t('stats.birdsWithFCI'), fmtNum(fciCount))));

  // COI distribution
  const bands = [
    ['stats.coiBand.zero', (c) => c === 0],
    ['0–3.125%', (c) => c > 0 && c < 0.03125],
    ['3.125–6.25%', (c) => c >= 0.03125 && c < 0.0625],
    ['6.25–12.5%', (c) => c >= 0.0625 && c < 0.125],
    ['12.5–25%', (c) => c >= 0.125 && c < 0.25],
    ['≥25%', (c) => c >= 0.25],
  ];
  const cois = birds.map((b) => ({ b, coi: inbreeding(getBird, b.id, depth).coi }));
  const counts = bands.map(([label, fn]) => [label, cois.filter((x) => fn(x.coi)).length]);
  const maxCount = Math.max(1, ...counts.map(([, n]) => n));
  const avg = cois.length ? cois.reduce((s, x) => s + x.coi, 0) / cois.length : 0;
  const top = [...cois].sort((a, b) => b.coi - a.coi).slice(0, 5).filter((x) => x.coi > 0);

  const hist = h('div', { class: 'hist' });
  for (const [label, n] of counts) {
    hist.append(h('div', { class: 'hist-row' },
      h('span', { class: 'hist-label' }, label.startsWith('stats.') ? t(label) : label),
      h('div', { class: 'hist-track' },
        h('div', { class: 'hist-bar', style: `inline-size:${(n / maxCount) * 100}%` })),
      h('span', { class: 'hist-n' }, fmtNum(n))));
  }
  const coiCard = h('div', { class: 'card' },
    h('h2', {}, t('stats.coiDistribution') + ' — ' + t('ped.coiAtN', { n: depth })),
    hist,
    h('p', {}, t('stats.avgCOI') + ': ' + fmtPercent(avg, 2)));
  if (top.length) {
    coiCard.append(h('p', {}, t('stats.maxCOI') + ':'),
      h('ul', { class: 'plain-list' }, top.map(({ b, coi }) =>
        h('li', { html: `<a href="#/bird/${b.id}">${birdLabelHTML(b)}</a> — ${fmtPercent(coi, 1)}` }))));
  }
  root.append(coiCard);

  // by status / strain
  root.append(breakdownCard(t('stats.byStatus'), groupCount(birds, (b) => statusLabel(b.status))));
  root.append(breakdownCard(t('stats.byStrain'), groupCount(birds.filter((b) => b.strain), (b) => b.strain)));
  return root;
}

function groupCount(items, keyFn) {
  const m = new Map();
  for (const it of items) {
    const k = keyFn(it) || '—';
    m.set(k, (m.get(k) || 0) + 1);
  }
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
}

function breakdownCard(title, entries) {
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return h('div', { class: 'card' },
    h('h2', {}, title),
    entries.length ? h('div', { class: 'hist' }, entries.map(([label, n]) =>
      h('div', { class: 'hist-row' },
        h('bdi', { class: 'hist-label' }, label),
        h('div', { class: 'hist-track' }, h('div', { class: 'hist-bar', style: `inline-size:${(n / max) * 100}%` })),
        h('span', { class: 'hist-n' }, fmtNum(n))))) :
      h('p', { class: 'muted' }, t('common.none')));
}

function stat(label, value) {
  return h('div', { class: 'stat' },
    h('div', { class: 'stat-value' }, value),
    h('div', { class: 'stat-label' }, label));
}
