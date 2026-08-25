// views/bird-detail.js — one bird: identity, parents, media, notes,
// progeny analysis (Tier 2 #7), race record, health log, FCI status,
// share (Tier 3 #13), delete with undo.

import {
  getBird, allBirds, state, saveBird, deleteBird, restoreBird,
  mediaForBird, deleteMedia, restoreMedia, exportBirdWithAncestry, nowISO, uuid,
} from '../db.js';
import { t, fmtDate, fmtNum, fmtPercent, statusLabel, escapeHTML, ringHTML } from '../i18n.js';
import {
  h, clear, birdLabelHTML, birdLabelText, sexIcon, sexChipHTML, primaryRing,
  toast, undoToast, confirmDialog, modal, downloadJSON, fmtCOIBadge, onViewTeardown,
} from '../ui.js';
import { inbreeding, ancestorLoss } from '../engine/coi.js';
import { descendantDepths } from '../engine/pedigree.js';
import { birdEligibility } from '../engine/fci.js';
import { navigate, navigateReplace } from '../app.js';

export function renderBirdDetail(id) {
  const bird = getBird(id);
  if (!bird) { navigateReplace('#/birds'); return null; }
  const root = h('section', { class: 'view-bird-detail' });
  const depth = +(state.settings.coiDepth || 10);
  const { coi } = inbreeding(getBird, id, depth);
  const avk = ancestorLoss(getBird, id, 5);

  const sire = bird.sireId ? getBird(bird.sireId) : null;
  const dam = bird.damId ? getBird(bird.damId) : null;

  // ---------------------------------------------------------------- header
  const head = h('div', { class: 'detail-head' },
    h('div', { class: 'detail-title' },
      h('h1', { html: birdLabelHTML(bird) }),
      h('span', { html: sexChipHTML(bird.sex) }),
      bird.external ? h('span', { class: 'chip chip-ext' }, t('bird.externalShort')) : null),
    h('div', { class: 'detail-actions' },
      h('a', { class: 'btn', href: '#/pedigree/' + id }, '🌳 ' + t('act.viewPedigree')),
      h('a', { class: 'btn', href: '#/cert/' + id }, '📜 ' + t('act.certificate')),
      h('a', { class: 'btn', href: '#/bird/' + id + '/edit' }, t('act.edit')),
      h('button', { class: 'btn', onclick: addSibling }, '👥 ' + t('bird.addSibling')),
      h('button', { class: 'btn', onclick: shareBird }, t('act.share')),
      h('button', { class: 'btn btn-danger', onclick: del }, t('act.delete'))));

  async function addSibling() {
    // Siblings share parents — that IS the link. If parents exist, prefill
    // them; otherwise offer to create placeholder external parents so the
    // relationship is modelled correctly from day one.
    if (bird.sireId || bird.damId) {
      const q = [];
      if (bird.sireId) q.push('sire=' + bird.sireId);
      if (bird.damId) q.push('dam=' + bird.damId);
      navigate('#/bird/new?' + q.join('&'));
      return;
    }
    modal(t('bird.addSibling'), h('div', {},
      h('p', {}, t('bird.siblingHint')),
      h('p', { class: 'muted' }, t('bird.siblingNoParents'))), {
      actions: [
        { label: t('act.cancel') },
        {
          label: t('bird.createPlaceholders'), kind: 'primary',
          onClick: () => {
            (async () => {
              const { newBird } = await import('../db.js');
              const sire = await saveBird(newBird({ name: t('bird.unknownSire'), sex: 'cock', external: true }));
              const dam = await saveBird(newBird({ name: t('bird.unknownDam'), sex: 'hen', external: true }));
              bird.sireId = sire.id;
              bird.damId = dam.id;
              await saveBird(bird);
              navigate('#/bird/new?sire=' + sire.id + '&dam=' + dam.id);
            })();
          },
        },
      ],
    });
  }

  async function del() {
    const ok = await confirmDialog(t('confirm.deleteBird', { name: birdLabelText(bird) }));
    if (!ok) return;
    const snapshot = await deleteBird(id);
    navigateReplace('#/birds');
    undoToast(t('toast.deleted'), async () => {
      await restoreBird(snapshot);
      toast(t('toast.undone'));
    });
  }

  function shareBird() {
    const races = h('input', { type: 'checkbox', checked: true });
    const media = h('input', { type: 'checkbox', checked: true });
    modal(t('share.title'), h('div', {},
      h('p', { class: 'muted' }, t('share.hint')),
      h('label', { class: 'check-row' }, races, ' ', t('share.includeRaces')),
      h('label', { class: 'check-row' }, media, ' ', t('share.includeMedia'))), {
      actions: [
        { label: t('act.cancel') },
        {
          label: t('act.export'), kind: 'primary',
          onClick: () => {
            exportBirdWithAncestry(id, { includeRaces: races.checked, includeMedia: media.checked })
              .then((payload) => {
                const ring = primaryRing(bird).replace(/[^\w-]+/g, '_') || id.slice(0, 8);
                downloadJSON(payload, `zajil-bird-${ring}.json`);
                toast(t('toast.exported'));
              });
          },
        },
      ],
    });
  }

  // ---------------------------------------------------------------- facts
  const factRows = [
    [t('bird.rings'), (bird.rings || []).map((r) =>
      `${ringHTML(r.raw)} <span class="chip">${escapeHTML(t('ringType.' + r.type))}</span>`).join('<br>') || '—'],
    [t('bird.hatchDate'), escapeHTML(fmtDate(bird.hatchDate))],
    [t('bird.status'), escapeHTML(statusLabel(bird.status))],
    [t('bird.colour'), escapeHTML(bird.colour || '—')],
    [t('bird.strain'), escapeHTML(bird.strain || '—')],
    [t('bird.eyeSign'), escapeHTML(bird.eyeSign || '—')],
    [t('bird.breeder'), escapeHTML(bird.breeder || '—')],
    [t('bird.owner'), escapeHTML(bird.owner || '—')],
    [t('bird.acquiredFrom'), bird.acquiredFrom ? escapeHTML(bird.acquiredFrom) + (bird.acquiredDate ? ' · ' + escapeHTML(fmtDate(bird.acquiredDate)) : '') : '—'],
    [t('bird.sire'), sire ? `<a href="#/bird/${sire.id}">${birdLabelHTML(sire)}</a>` : '—'],
    [t('bird.dam'), dam ? `<a href="#/bird/${dam.id}">${birdLabelHTML(dam)}</a>` : '—'],
    [t('ped.coiAtN', { n: depth }), fmtCOIBadge(coi)],
    [t('ped.avk'), escapeHTML(fmtPercent(avk.avk / 100, 1)) + ` <span class="muted">(${escapeHTML(t('ped.completeness'))}: ${escapeHTML(fmtPercent(avk.completeness / 100, 0))})</span>`],
  ];
  const facts = h('dl', { class: 'facts' });
  for (const [k, v] of factRows) {
    facts.append(h('div', { class: 'fact' }, h('dt', {}, k), h('dd', { html: v })));
  }

  // ------------------------------------------------------------ FCI status
  const results = [...state.raceResults.values()].filter((r) => r.birdId === id);
  const elig = birdEligibility(bird, results);
  const fciBox = h('div', { class: 'card' },
    h('h2', {}, t('fci.title')),
    h('p', {}, elig.hasRing ? '✓ ' + t('fci.hasRing') : '✗ ' + t('fci.noRing')),
    h('p', { class: 'muted' }, t('fci.qualifying') + ': ' + fmtNum(elig.qualifyingResults.length) +
      ' / ' + fmtNum(results.length)));

  // -------------------------------------------------------- progeny analysis
  const progBox = h('div', { class: 'card' }, h('h2', {}, t('prog.title')));
  progBox.append(progenyAnalysis(id));

  // ------------------------------------------------------------ race record
  const raceBox = h('div', { class: 'card' }, h('h2', {}, t('bird.raceRecord')));
  if (!results.length) raceBox.append(h('p', { class: 'muted' }, t('race.noRaces')));
  else {
    const tbl = h('table', { class: 'table' },
      h('thead', {}, h('tr', {},
        h('th', {}, t('common.date')), h('th', {}, t('race.name')),
        h('th', {}, t('race.distance')), h('th', {}, t('race.position')),
        h('th', {}, t('race.velocity')))),
      h('tbody', {}, results.sort((a, b) => (b.date || '').localeCompare(a.date || '')).map((r) =>
        h('tr', {},
          h('td', {}, fmtDate(r.date)),
          h('td', {}, h('bdi', {}, r.raceName || t('raceType.' + (r.raceType || 'training')))),
          h('td', {}, r.distanceKm ? fmtNum(r.distanceKm, { dp: 1 }) + ' ' + t('race.km') : '—'),
          h('td', {}, r.position ? fmtNum(r.position, { group: false }) : '—'),
          h('td', {}, r.velocity ? fmtNum(r.velocity, { dp: 0 }) + ' ' + t('race.mpm') : '—')))));
    raceBox.append(h('div', { class: 'table-scroll' }, tbl));
  }

  // ------------------------------------------------------------- health log
  const events = [...state.healthEvents.values()]
    .filter((e) => e.birdId === id || (e.wholeLoft && e.loftId === bird.loftId));
  const healthBox = h('div', { class: 'card' }, h('h2', {}, t('bird.healthLog')));
  if (!events.length) healthBox.append(h('p', { class: 'muted' }, t('health.noEvents')));
  else {
    healthBox.append(h('ul', { class: 'plain-list' },
      events.sort((a, b) => (b.date || '').localeCompare(a.date || '')).slice(0, 20).map((e) =>
        h('li', {},
          h('span', { class: 'muted' }, fmtDate(e.date) + ' — '),
          t('health.' + e.eventType),
          e.medication ? h('bdi', {}, ': ' + e.medication) : '',
          e.wholeLoft ? h('span', { class: 'chip' }, t('health.wholeLoft')) : ''))));
  }

  // ------------------------------------------------------------------ notes
  const notesBox = h('div', { class: 'card' }, h('h2', {}, t('common.notes')));
  const notesList = h('ul', { class: 'plain-list notes-list' });
  function renderNotes() {
    clear(notesList);
    for (const n of [...(bird.notes || [])].sort((a, b) => (b.at || '').localeCompare(a.at || ''))) {
      notesList.append(h('li', {},
        h('span', { class: 'muted' }, fmtDate(n.at, { withTime: true }) + ' — '),
        h('bdi', {}, n.text)));
    }
  }
  renderNotes();
  const noteIn = h('textarea', { class: 'input', rows: 2 });
  const noteBtn = h('button', {
    class: 'btn btn-small', onclick: async () => {
      const text = noteIn.value.trim();
      if (!text) return;
      bird.notes = bird.notes || [];
      bird.notes.push({ id: uuid(), at: nowISO(), text });
      await saveBird(bird);
      noteIn.value = '';
      renderNotes();
    },
  }, '+ ' + t('bird.addNote'));
  notesBox.append(notesList, noteIn, noteBtn);

  // ------------------------------------------------------------------ media
  const mediaBox = h('div', { class: 'card' }, h('h2', {}, t('bird.photos') + ' / ' + t('bird.documents')));
  const gallery = h('div', { class: 'gallery' });
  mediaBox.append(gallery);
  mediaForBird(id).then((items) => {
    // the user may have navigated away while this was resolving — creating URLs
    // for a detached gallery would leak them with no way to reach them again
    if (!gallery.isConnected) return;
    if (!items.length) { gallery.append(h('p', { class: 'muted' }, t('common.none'))); return; }
    for (const m of items) {
      const url = URL.createObjectURL(m.blob);
      onViewTeardown(() => URL.revokeObjectURL(url));
      const fig = h('figure', { class: 'media-item' });
      if (m.kind === 'photo' || (m.blob.type || '').startsWith('image/')) {
        fig.append(h('img', { src: url, alt: m.name || '', loading: 'lazy' }));
      } else {
        fig.append(h('a', { href: url, download: m.name || 'document', class: 'btn' }, '📄 ', h('bdi', {}, m.name || 'document')));
      }
      fig.append(h('figcaption', {},
        m.kind === 'photo' ? t('photo.' + (m.subtype || 'other')) : t('bird.documents'),
        ' ',
        h('button', {
          class: 'btn btn-small', onclick: async () => {
            if (await confirmDialog(t('confirm.deleteGeneric'))) {
              const snap = await deleteMedia(m.id);
              fig.remove();
              undoToast(t('toast.deleted'), async () => {
                if (!snap) return;            // nothing to restore (double-delete)
                await restoreMedia(snap);     // emits, so the gallery refreshes
                toast(t('toast.undone'));
              });
            }
          },
        }, '✕')));
      gallery.append(fig);
    }
  });

  root.append(head, h('div', { class: 'card' }, facts),
    h('div', { class: 'detail-grid' }, progBox, fciBox, raceBox, healthBox, notesBox, mediaBox));
  return root;
}

/** Progeny analysis: every descendant's race record, aggregated. */
export function progenyAnalysis(birdId) {
  const wrap = h('div', {});
  const desc = descendantDepths(allBirds, birdId);
  if (!desc.size) {
    wrap.append(h('p', { class: 'muted' }, t('prog.noProgeny')));
    return wrap;
  }
  const direct = [...desc.entries()].filter(([, d]) => d === 1).length;
  const perBird = new Map(); // id -> {results, wins, top10, velSum, velN, best}
  for (const r of state.raceResults.values()) {
    if (!desc.has(r.birdId) || r.raceType === 'training') continue;
    let s = perBird.get(r.birdId);
    if (!s) { s = { results: 0, wins: 0, top10: 0, velSum: 0, velN: 0, bestPos: Infinity }; perBird.set(r.birdId, s); }
    s.results++;
    const pos = +r.position || 0;
    if (pos === 1) s.wins++;
    if (pos >= 1 && pos <= 10) s.top10++;
    if (pos >= 1 && pos < s.bestPos) s.bestPos = pos;
    if (r.velocity) { s.velSum += +r.velocity; s.velN++; }
  }
  let totResults = 0, totWins = 0, totTop10 = 0, velSum = 0, velN = 0;
  for (const s of perBird.values()) {
    totResults += s.results; totWins += s.wins; totTop10 += s.top10;
    velSum += s.velSum; velN += s.velN;
  }
  const statGrid = h('div', { class: 'stat-grid' },
    stat(t('prog.offspringCount'), fmtNum(direct)),
    stat(t('prog.descendants'), fmtNum(desc.size)),
    stat(t('prog.raced'), fmtNum(perBird.size)),
    stat(t('prog.totalResults'), fmtNum(totResults)),
    stat(t('prog.wins'), fmtNum(totWins)),
    stat(t('prog.top10'), fmtNum(totTop10)),
    stat(t('prog.avgVelocity'), velN ? fmtNum(velSum / velN, { dp: 0 }) + ' ' + t('race.mpm') : '—'));
  wrap.append(statGrid);

  // Best performers: rank by wins, then top10, then results.
  const ranked = [...perBird.entries()]
    .sort((a, b) => b[1].wins - a[1].wins || b[1].top10 - a[1].top10 || b[1].results - a[1].results)
    .slice(0, 5);
  if (ranked.length) {
    wrap.append(h('h3', {}, t('prog.bestPerformers')),
      h('ul', { class: 'plain-list' }, ranked.map(([bid, s]) => {
        const b = getBird(bid);
        return h('li', {},
          h('a', { href: '#/bird/' + bid, html: birdLabelHTML(b) }),
          h('span', { class: 'muted' },
            ` — ${t('prog.wins')}: ${fmtNum(s.wins)} · ${t('prog.top10')}: ${fmtNum(s.top10)} · ${t('prog.totalResults')}: ${fmtNum(s.results)}`));
      })));
  }
  return wrap;
}

function stat(label, value) {
  return h('div', { class: 'stat' },
    h('div', { class: 'stat-value' }, value),
    h('div', { class: 'stat-label' }, label));
}
