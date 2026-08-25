// views/races.js — Tier 2 #8/#9: race & training log with GPS velocity, and
// the FCI eligibility checker.

import { getBird, allBirds, state, Races, uuid } from '../db.js';
import { t, fmtDate, fmtNum, escapeHTML } from '../i18n.js';
import {
  h, clear, birdLabelHTML, birdPicker, field, select, toast, undoToast,
  confirmDialog, modal,
} from '../ui.js';
import { velocityMPM, haversineMetres } from '../engine/velocity.js';
import { resultQualifies, birdEligibility, FCI_MIN_FANCIERS, FCI_MIN_BIRDS, hasFCIRing } from '../engine/fci.js';

const RACE_TYPES = ['training', 'club', 'federation', 'national', 'one-loft', 'international'];
const vs = { tab: 'log' };

export function renderRaces() {
  const root = h('section', { class: 'view-races' });
  const tabs = h('div', { class: 'seg' },
    h('button', { class: 'seg-btn' + (vs.tab === 'log' ? ' active' : ''), onclick: () => { vs.tab = 'log'; swap(); } }, t('race.title')),
    h('button', { class: 'seg-btn' + (vs.tab === 'fci' ? ' active' : ''), onclick: () => { vs.tab = 'fci'; swap(); } }, t('fci.title')));
  const body = h('div', {});
  // remember where the user was in each tab, so switching away and back
  // doesn't lose their place in a long table
  const scrollMemory = { log: 0, fci: 0 };
  let activeTab = vs.tab;
  function swap() {
    scrollMemory[activeTab] = window.scrollY;
    activeTab = vs.tab;
    root.querySelectorAll('.seg-btn').forEach((b, i) => b.classList.toggle('active', ['log', 'fci'][i] === vs.tab));
    clear(body);
    body.append(vs.tab === 'log' ? logTab(swap) : fciTab());
    requestAnimationFrame(() => {
      const max = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      window.scrollTo(0, Math.min(scrollMemory[vs.tab] || 0, max));
    });
  }
  root.append(
    h('div', { class: 'view-head' },
      h('h1', {}, t('nav.races')),
      h('button', { class: 'btn btn-primary', onclick: () => resultDialog(null, swap) }, '+ ' + t('race.new'))),
    tabs, body);
  swap();
  return root;
}

function logTab(refresh) {
  const wrap = h('div', {});
  const results = [...state.raceResults.values()].sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  if (!results.length) {
    wrap.append(h('div', { class: 'empty-state' }, t('race.noRaces')));
    return wrap;
  }
  const tbl = h('table', { class: 'table' },
    h('thead', {}, h('tr', {},
      h('th', {}, t('common.date')), h('th', {}, t('race.bird')), h('th', {}, t('race.name')),
      h('th', {}, t('race.type')), h('th', {}, t('race.distance')), h('th', {}, t('race.velocity')),
      h('th', {}, t('race.position')), h('th', {}, 'FCI'), h('th', {}, ''))),
    h('tbody', {}, results.map((r) => {
      const b = getBird(r.birdId);
      const q = resultQualifies(r);
      return h('tr', {},
        h('td', {}, fmtDate(r.date)),
        h('td', { html: b ? `<a href="#/bird/${r.birdId}">${birdLabelHTML(b)}</a>` : '—' }),
        h('td', {}, h('bdi', {}, r.raceName || '—')),
        h('td', {}, t('raceType.' + (r.raceType || 'training'))),
        h('td', {}, r.distanceKm ? fmtNum(r.distanceKm, { dp: 1 }) + ' ' + t('race.km') : '—'),
        h('td', {}, r.velocity ? fmtNum(r.velocity, { dp: 0 }) + ' ' + t('race.mpm') : '—'),
        h('td', {}, r.position ? fmtNum(r.position, { group: false }) : '—'),
        h('td', {}, q.qualifies ? '✓' : '—'),
        h('td', {},
          h('button', { class: 'btn btn-small', onclick: () => resultDialog(r, refresh) }, t('act.edit')),
          h('button', {
            class: 'btn btn-small btn-danger', onclick: async () => {
              if (!await confirmDialog(t('confirm.deleteGeneric'))) return;
              const snap = await Races.remove(r.id);
              refresh();
              undoToast(t('toast.deleted'), async () => { await Races.restore(snap); refresh(); });
            },
          }, '✕')));
    })));
  wrap.append(h('div', { class: 'table-scroll' }, tbl));
  return wrap;
}

function fciTab() {
  const wrap = h('div', {});
  wrap.append(h('p', { class: 'muted' }, t('fci.rule', { f: FCI_MIN_FANCIERS, b: FCI_MIN_BIRDS })));
  const rows = [];
  for (const b of allBirds()) {
    const results = [...state.raceResults.values()].filter((r) => r.birdId === b.id);
    const e = birdEligibility(b, results);
    if (!e.hasRing && !results.length) continue;
    rows.push({ bird: b, e, results });
  }
  rows.sort((a, b2) => (b2.e.hasRing ? 1 : 0) - (a.e.hasRing ? 1 : 0) ||
    b2.e.qualifyingResults.length - a.e.qualifyingResults.length);
  if (!rows.length) {
    wrap.append(h('div', { class: 'empty-state' }, t('common.none')));
    return wrap;
  }
  const tbl = h('table', { class: 'table' },
    h('thead', {}, h('tr', {},
      h('th', {}, t('race.bird')), h('th', {}, t('fci.hasRing')),
      h('th', {}, t('fci.qualifying')), h('th', {}, t('fci.nonQualifying')))),
    h('tbody', {}, rows.map(({ bird, e }) =>
      h('tr', { class: e.hasRing && e.qualifyingResults.length ? 'row-ok' : '' },
        h('td', { html: `<a href="#/bird/${bird.id}">${birdLabelHTML(bird)}</a>` }),
        h('td', {}, e.hasRing ? '✓' : '✗'),
        h('td', {}, fmtNum(e.qualifyingResults.length)),
        h('td', { html: e.nonQualifying.length ? e.nonQualifying.map(({ result, reasons }) =>
          `<span class="muted small">${escapeHTML(result.raceName || fmtDate(result.date))}: ${reasons.map((k) => escapeHTML(t(k))).join('، ')}</span>`).join('<br>') : '—' })))));
  wrap.append(h('div', { class: 'table-scroll' }, tbl));
  return wrap;
}

function resultDialog(existing, refresh) {
  const r = existing ? { ...existing } : { id: uuid() };
  const birdP = birdPicker({ value: r.birdId || null, allowClear: false });
  const nameIn = h('input', { class: 'input', type: 'text', value: r.raceName || '' });
  const dateIn = h('input', { class: 'input', type: 'date', value: r.date || '' });
  const typeSel = select(RACE_TYPES.map((rt) => ({ value: rt, label: t('raceType.' + rt) })), r.raceType || 'club');
  const orgIn = h('input', { class: 'input', type: 'text', value: r.organisation || '' });
  const countryIn = h('input', { class: 'input', type: 'text', value: r.country || '', dir: 'ltr' });
  const posIn = h('input', { class: 'input', type: 'number', min: 0, value: r.position || '', dir: 'ltr' });
  const fanciersIn = h('input', { class: 'input', type: 'number', min: 0, value: r.fanciersEntered || '', dir: 'ltr' });
  const birdsIn = h('input', { class: 'input', type: 'number', min: 0, value: r.birdsEntered || '', dir: 'ltr' });
  const relNameIn = h('input', { class: 'input', type: 'text', value: (r.releasePoint && r.releasePoint.name) || '' });
  const relCoordIn = h('input', { class: 'input', type: 'text', dir: 'ltr', placeholder: '29.5321, 35.0063', value: r.releasePoint && r.releasePoint.lat != null ? `${r.releasePoint.lat}, ${r.releasePoint.lon}` : '' });
  const loftCoordIn = h('input', { class: 'input', type: 'text', dir: 'ltr', placeholder: '31.9539, 35.9106', value: r.loftPoint && r.loftPoint.lat != null ? `${r.loftPoint.lat}, ${r.loftPoint.lon}` : (state.settings.loftCoords || '') });
  const relTimeIn = h('input', { class: 'input', type: 'datetime-local', value: r.releaseTime || '' });
  const arrTimeIn = h('input', { class: 'input', type: 'datetime-local', value: r.arrivalTime || '' });
  const distIn = h('input', { class: 'input', type: 'number', step: '0.1', value: r.distanceKm || '', dir: 'ltr' });
  const velIn = h('input', { class: 'input', type: 'number', step: '1', value: r.velocity || '', dir: 'ltr' });

  function parseCoords(s) {
    const m = String(s).trim().match(/(-?\d+(?:\.\d+)?)[\s,;]+(-?\d+(?:\.\d+)?)/);
    return m ? { lat: +m[1], lon: +m[2] } : null;
  }
  const calcBtn = h('button', {
    class: 'btn btn-small', type: 'button', onclick: () => {
      const a = parseCoords(relCoordIn.value), b = parseCoords(loftCoordIn.value);
      if (!a || !b) return;
      distIn.value = (haversineMetres(a, b) / 1000).toFixed(1);
      if (relTimeIn.value && arrTimeIn.value) {
        const v = velocityMPM(a, b, relTimeIn.value, arrTimeIn.value);
        if (v) velIn.value = Math.round(v);
      }
    },
  }, '⟳ ' + t('race.calcVelocity'));

  modal(existing ? t('act.edit') : t('race.new'), h('div', {},
    h('div', { class: 'form-grid' },
      field(t('race.bird'), birdP),
      field(t('race.name'), nameIn),
      field(t('common.date'), dateIn),
      field(t('race.type'), typeSel),
      field(t('race.org'), orgIn),
      field(t('race.country'), countryIn),
      field(t('race.position'), posIn),
      field(t('race.fanciers'), fanciersIn),
      field(t('race.birdsEntered'), birdsIn)),
    h('h3', {}, t('race.velocity')),
    h('div', { class: 'form-grid' },
      field(t('race.releasePoint'), relNameIn),
      field(t('race.coords'), relCoordIn),
      field(t('race.loftCoords'), loftCoordIn),
      field(t('race.releaseTime'), relTimeIn),
      field(t('race.arrivalTime'), arrTimeIn),
      field(t('race.distance') + ' (' + t('race.km') + ')', distIn),
      field(t('race.velocity') + ' (' + t('race.mpm') + ')', velIn)),
    calcBtn), {
    wide: true,
    actions: [
      { label: t('act.cancel') },
      {
        label: t('act.save'), kind: 'primary',
        onClick: () => {
          if (!birdP.value) return false;
          const rel = parseCoords(relCoordIn.value);
          const loft = parseCoords(loftCoordIn.value);
          if (loftCoordIn.value.trim()) {
            import('../db.js').then(({ setSetting }) => setSetting('loftCoords', loftCoordIn.value.trim()));
          }
          Races.save({
            ...r,
            birdId: birdP.value,
            raceName: nameIn.value.trim(),
            date: dateIn.value,
            raceType: typeSel.value,
            organisation: orgIn.value.trim(),
            country: countryIn.value.trim(),
            position: posIn.value ? +posIn.value : null,
            fanciersEntered: fanciersIn.value ? +fanciersIn.value : null,
            birdsEntered: birdsIn.value ? +birdsIn.value : null,
            releasePoint: rel ? { name: relNameIn.value.trim(), ...rel } : (relNameIn.value.trim() ? { name: relNameIn.value.trim() } : null),
            loftPoint: loft,
            releaseTime: relTimeIn.value || null,
            arrivalTime: arrTimeIn.value || null,
            distanceKm: distIn.value ? +distIn.value : null,
            velocity: velIn.value ? +velIn.value : null,
          }).then(() => { toast(t('toast.saved')); refresh(); });
        },
      },
    ],
  });
}
