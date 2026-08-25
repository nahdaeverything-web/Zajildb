// views/health.js — Tier 2 #10: health & treatment log, per bird or whole loft.

import { getBird, state, Health, uuid } from '../db.js';
import { t, fmtDate } from '../i18n.js';
import {
  h, clear, birdLabelHTML, birdPicker, field, select, toast, undoToast,
  confirmDialog, modal,
} from '../ui.js';

import { todayISO } from '../dates.js';

const EVENT_TYPES = ['vaccination', 'treatment', 'illness', 'check'];

export function renderHealth() {
  const root = h('section', { class: 'view-health' });
  const listWrap = h('div', {});

  function refresh() {
    clear(listWrap);
    const events = [...state.healthEvents.values()].sort((a, b) => (b.date || '').localeCompare(a.date || ''));
    if (!events.length) {
      listWrap.append(h('div', { class: 'empty-state' }, t('health.noEvents')));
      return;
    }
    const tbl = h('table', { class: 'table' },
      h('thead', {}, h('tr', {},
        h('th', {}, t('common.date')), h('th', {}, t('health.type')),
        h('th', {}, t('health.scope')), h('th', {}, t('health.medication')),
        h('th', {}, t('common.notes')), h('th', {}, ''))),
      h('tbody', {}, events.map((e) => {
        const b = e.birdId ? getBird(e.birdId) : null;
        return h('tr', {},
          h('td', {}, fmtDate(e.date)),
          h('td', {}, t('health.' + e.eventType)),
          h('td', { html: e.wholeLoft ? `<span class="chip">${t('health.wholeLoft')}</span>` :
            (b ? `<a href="#/bird/${e.birdId}">${birdLabelHTML(b)}</a>` : '—') }),
          h('td', {}, h('bdi', {}, e.medication || '—')),
          h('td', {}, h('bdi', {}, e.notes || '')),
          h('td', {}, h('button', {
            class: 'btn btn-small btn-danger', onclick: async () => {
              if (!await confirmDialog(t('confirm.deleteGeneric'))) return;
              const snap = await Health.remove(e.id);
              refresh();
              undoToast(t('toast.deleted'), async () => { await Health.restore(snap); refresh(); });
            },
          }, '✕')));
      })));
    listWrap.append(h('div', { class: 'table-scroll' }, tbl));
  }

  root.append(
    h('div', { class: 'view-head' },
      h('h1', {}, t('health.title')),
      h('button', { class: 'btn btn-primary', onclick: () => eventDialog(refresh) }, '+ ' + t('health.new'))),
    listWrap);
  refresh();
  return root;
}

function eventDialog(refresh) {
  const typeSel = select(EVENT_TYPES.map((e) => ({ value: e, label: t('health.' + e) })), 'vaccination');
  const scopeSel = select([
    { value: 'bird', label: t('health.singleBird') },
    { value: 'loft', label: t('health.wholeLoft') },
  ], 'bird');
  const birdP = birdPicker({ allowClear: false });
  const birdField = field(t('race.bird'), birdP);
  const dateIn = h('input', { class: 'input', type: 'date', value: todayISO() });
  const medIn = h('input', { class: 'input', type: 'text' });
  const notesIn = h('textarea', { class: 'input', rows: 2 });
  scopeSel.addEventListener('change', () => { birdField.hidden = scopeSel.value === 'loft'; });

  modal(t('health.new'), h('div', { class: 'form-grid' },
    field(t('health.type'), typeSel),
    field(t('health.scope'), scopeSel),
    birdField,
    field(t('common.date'), dateIn),
    field(t('health.medication'), medIn),
    field(t('common.notes'), notesIn)), {
    actions: [
      { label: t('act.cancel') },
      {
        label: t('act.save'), kind: 'primary',
        onClick: () => {
          const wholeLoft = scopeSel.value === 'loft';
          if (!wholeLoft && !birdP.value) return false;
          Health.save({
            id: uuid(),
            eventType: typeSel.value,
            wholeLoft,
            birdId: wholeLoft ? null : birdP.value,
            date: dateIn.value,
            medication: medIn.value.trim(),
            notes: notesIn.value.trim(),
          }).then(() => { toast(t('toast.saved')); refresh(); });
        },
      },
    ],
  });
}
