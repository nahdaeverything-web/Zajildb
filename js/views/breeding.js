// views/breeding.js — Tier 1 #4: breeding season manager.
// Pairs → nest boxes → rounds → eggs → hatch → ring → wean.
// Ringing a hatched egg creates the chick's Bird record auto-linked to its
// parents. The relationship/COI check surfaces at pair creation, BEFORE the
// mating is recorded.

import {
  getBird, allBirds, state, Pairs, newBird, saveBird, uuid, nowISO,
} from '../db.js';
import { t, fmtDate, fmtNum, escapeHTML } from '../i18n.js';
import {
  h, clear, birdLabelHTML, birdLabelText, birdPicker, field, toast,
  undoToast, confirmDialog, modal,
} from '../ui.js';
import { validatePairSexes, validateBird } from '../engine/validate.js';
import { relationshipSummary } from './pedigree.js';
import { navigate } from '../app.js';

const vs = { season: String(new Date().getFullYear()) };

export function renderBreeding() {
  const root = h('section', { class: 'view-breeding' });
  const seasons = [...new Set([vs.season, ...[...state.pairs.values()].map((p) => p.season)])]
    .filter(Boolean).sort().reverse();
  const seasonSel = h('select', { class: 'input input-compact' },
    seasons.map((s) => h('option', { value: s, selected: s === vs.season }, fmtNum(+s, { group: false }))));
  seasonSel.addEventListener('change', () => { vs.season = seasonSel.value; refresh(); });

  const listWrap = h('div', { class: 'pairs-list' });

  function refresh() {
    clear(listWrap);
    const pairs = [...state.pairs.values()].filter((p) => p.season === vs.season)
      .sort((a, b) => (a.nestBox || '').localeCompare(b.nestBox || '', undefined, { numeric: true }));
    if (!pairs.length) {
      listWrap.append(h('div', { class: 'empty-state' }, t('br.noPairs')));
      return;
    }
    for (const p of pairs) listWrap.append(pairCard(p, refresh));
  }

  root.append(
    h('div', { class: 'view-head' },
      h('h1', {}, t('br.title')),
      h('div', { class: 'head-tools' },
        h('span', { class: 'muted' }, t('br.season') + ':'), seasonSel,
        h('button', { class: 'btn btn-primary', onclick: () => newPairDialog(refresh) }, '+ ' + t('br.newPair')))),
    listWrap);
  refresh();
  return root;
}

function newPairDialog(refresh) {
  const relOut = h('div', { class: 'rel-check card-inset' },
    h('p', { class: 'muted' }, t('br.pairCOIWarning')));
  let sireId = null, damId = null;
  function check() {
    clear(relOut);
    relOut.append(h('p', { class: 'muted' }, t('br.pairCOIWarning')));
    if (sireId && damId) relOut.append(relationshipSummary(sireId, damId));
  }
  const sireP = birdPicker({ filter: (b) => b.sex !== 'hen', placeholder: t('bird.sire'), onPick: (v) => { sireId = v; check(); }, allowClear: false, allowCreate: { sex: 'cock' } });
  const damP = birdPicker({ filter: (b) => b.sex !== 'cock', placeholder: t('bird.dam'), onPick: (v) => { damId = v; check(); }, allowClear: false, allowCreate: { sex: 'hen' } });
  const nestIn = h('input', { class: 'input', type: 'text' });
  const seasonIn = h('input', { class: 'input', type: 'number', value: vs.season, dir: 'ltr' });
  // a bought pair was paired before you owned it — the date must be settable
  const startIn = h('input', { class: 'input', type: 'date', value: new Date().toISOString().slice(0, 10) });
  const acqFromIn = h('input', { class: 'input', type: 'text' });
  const acqDateIn = h('input', { class: 'input', type: 'date' });
  const errBox = h('div', { class: 'problems' });

  modal(t('br.newPair'), h('div', {},
    h('div', { class: 'form-grid' },
      field(t('bird.sire'), sireP),
      field(t('bird.dam'), damP),
      field(t('br.nestBox'), nestIn),
      field(t('br.season'), seasonIn),
      field(t('br.startDate'), startIn),
      field(t('br.acquiredFrom'), acqFromIn),
      field(t('br.acquiredDate'), acqDateIn)),
    h('p', { class: 'muted small' }, t('br.boughtHint')),
    relOut, errBox), {
    wide: true,
    actions: [
      { label: t('act.cancel') },
      {
        label: t('act.save'), kind: 'primary',
        onClick: () => {
          errBox.innerHTML = '';
          const errors = validatePairSexes(sireId && getBird(sireId), damId && getBird(damId));
          if (!sireId || !damId) errors.push({ key: 'bird.chooseBird', params: {} });
          if (errors.length) {
            errBox.append(h('ul', { class: 'problem-errors' }, errors.map((e) => h('li', {}, t(e.key, e.params)))));
            return false; // keep modal open
          }
          Pairs.save({
            id: uuid(), sireId, damId,
            season: seasonIn.value || vs.season,
            nestBox: nestIn.value.trim(),
            status: 'active',
            startDate: startIn.value || nowISO().slice(0, 10),
            acquiredFrom: acqFromIn.value.trim(),
            acquiredDate: acqDateIn.value,
            rounds: [],
          }).then(() => { toast(t('toast.saved')); refresh(); });
        },
      },
    ],
  });
}

function pairCard(pair, refresh) {
  const sire = getBird(pair.sireId), dam = getBird(pair.damId);
  const card = h('div', { class: 'card pair-card' });

  const offspring = allBirds().filter((b) => b.sireId === pair.sireId && b.damId === pair.damId);

  card.append(
    h('div', { class: 'pair-head' },
      h('div', { class: 'pair-parents', html: `♂ <a href="#/bird/${pair.sireId}">${birdLabelHTML(sire)}</a>` +
        ` &nbsp;×&nbsp; ♀ <a href="#/bird/${pair.damId}">${birdLabelHTML(dam)}</a>` }),
      h('div', { class: 'pair-meta' },
        pair.nestBox ? h('span', { class: 'chip' }, t('br.nestBox') + ' ', h('bdi', {}, pair.nestBox)) : null,
        pair.acquiredFrom ? h('span', { class: 'chip' }, t('br.bought') + ': ', h('bdi', {}, pair.acquiredFrom)) : null,
        h('span', { class: 'chip ' + (pair.status === 'active' ? 'chip-ok' : '') },
          pair.status === 'active' ? t('br.active') : t('br.separated')),
        h('button', {
          class: 'btn btn-small', onclick: async () => {
            pair.status = pair.status === 'active' ? 'separated' : 'active';
            await Pairs.save(pair); refresh();
          },
        }, pair.status === 'active' ? t('br.separated') : t('br.active')),
        h('button', {
          class: 'btn btn-small btn-danger', onclick: async () => {
            if (!await confirmDialog(t('confirm.deleteGeneric'))) return;
            const snap = await Pairs.remove(pair.id);
            refresh();
            undoToast(t('toast.deleted'), async () => { await Pairs.restore(snap); refresh(); });
          },
        }, t('act.delete')))),
  );

  const roundsWrap = h('div', { class: 'rounds' });
  for (const round of pair.rounds || []) roundsWrap.append(roundBlock(pair, round, refresh));
  card.append(roundsWrap,
    h('button', {
      class: 'btn btn-small', onclick: async () => {
        pair.rounds = pair.rounds || [];
        pair.rounds.push({ id: uuid(), number: pair.rounds.length + 1, eggs: [] });
        await Pairs.save(pair); refresh();
      },
    }, '+ ' + t('br.addRound')));

  if (offspring.length) {
    card.append(h('h3', {}, t('br.offspringOf')),
      h('ul', { class: 'plain-list' }, offspring.map((b) =>
        h('li', {}, h('a', { href: '#/bird/' + b.id, html: birdLabelHTML(b) })))));
  }
  return card;
}

function roundBlock(pair, round, refresh) {
  const block = h('div', { class: 'round-block' },
    h('h3', {}, t('br.round') + ' ' + fmtNum(round.number, { group: false })));
  const eggList = h('div', { class: 'egg-list' });
  for (const egg of round.eggs || []) eggList.append(eggRow(pair, round, egg, refresh));
  block.append(eggList,
    h('button', {
      class: 'btn btn-small', onclick: async () => {
        round.eggs = round.eggs || [];
        // a second egg of a clutch is laid within a day or two of the first —
        // and for a bought clutch the first egg's date is already backdated
        const prev = round.eggs[round.eggs.length - 1];
        round.eggs.push({
          id: uuid(),
          laidDate: (prev && prev.laidDate) || nowISO().slice(0, 10),
          state: 'laid',
        });
        await Pairs.save(pair); refresh();
      },
    }, '+ ' + t('br.addEgg')));
  return block;
}

function eggRow(pair, round, egg, refresh) {
  const row = h('div', { class: 'egg-row egg-' + egg.state });
  const label = {
    laid: '🥚 ' + t('br.egg.laid'),
    hatched: '🐣 ' + t('br.egg.hatched'),
    failed: '✕ ' + t('br.egg.failed'),
  }[egg.state] || t('br.egg.laid');
  // dates are tap-to-edit: fanciers record events late and backfill —
  // a hatch-date change also corrects the chick's permanent record
  const dateInput = (key) => h('input', {
    class: 'input egg-date', type: 'date', value: egg[key] || '',
    onchange: async (e) => {
      egg[key] = e.target.value;
      await Pairs.save(pair);
      if (key === 'hatchDate' && egg.chickId) {
        const chick = getBird(egg.chickId);
        if (chick) { chick.hatchDate = e.target.value; await saveBird(chick); }
      }
    },
  });
  row.append(h('span', { class: 'egg-label' }, label),
    h('label', { class: 'egg-date-label small' }, t('br.laidDate') + ':', dateInput('laidDate')));

  if (egg.state === 'laid') {
    row.append(
      h('button', {
        class: 'btn btn-small', onclick: async () => {
          egg.state = 'hatched';
          egg.hatchDate = nowISO().slice(0, 10);
          await Pairs.save(pair); refresh();
        },
      }, t('br.markHatched')),
      h('button', {
        class: 'btn btn-small', onclick: async () => {
          egg.state = 'failed';
          await Pairs.save(pair); refresh();
        },
      }, t('br.markFailed')));
  }

  if (egg.state === 'hatched') {
    row.append(h('label', { class: 'egg-date-label small' }, t('br.hatch') + ':', dateInput('hatchDate')));
    if (!egg.chickId) {
      row.append(
        h('button', {
          class: 'btn btn-small btn-primary', onclick: () => ringChickDialog(pair, egg, refresh),
        }, t('br.ringChick')),
        h('button', {
          class: 'btn btn-small', onclick: () => linkExistingDialog(pair, egg, refresh),
        }, t('br.linkExisting')));
    } else {
      const chick = getBird(egg.chickId);
      row.append(h('a', { href: '#/bird/' + egg.chickId, html: '🐦 ' + birdLabelHTML(chick) }),
        h('button', {
          class: 'btn btn-small', title: t('br.unlink'),
          onclick: async () => {
            // unlink only detaches the egg; the bird record and its parents stay
            egg.chickId = null; egg.ringed = false; egg.weaned = false; egg.weanDate = '';
            await Pairs.save(pair); refresh();
          },
        }, '⛓'));
      if (!egg.weaned) {
        row.append(h('button', {
          class: 'btn btn-small', onclick: async () => {
            egg.weaned = true; egg.weanDate = nowISO().slice(0, 10);
            await Pairs.save(pair); refresh();
          },
        }, t('br.wean')));
      } else {
        row.append(h('span', { class: 'chip chip-ok' }, t('br.weaned')),
          h('label', { class: 'egg-date-label small' }, dateInput('weanDate')));
      }
    }
  }
  return row;
}

/**
 * Attach an ALREADY-RECORDED bird to a hatched egg — the case where you bought
 * a pair whose young were ringed by the seller, or imported a shared bird.
 * Setting the egg's chick rewrites that bird's parents, so it goes through the
 * same validation as the bird form: cycles and sex contradictions are refused.
 */
function linkExistingDialog(pair, egg, refresh) {
  const picker = birdPicker({
    filter: (b) => b.id !== pair.sireId && b.id !== pair.damId,
    allowClear: false,
  });
  const errBox = h('div', { class: 'problems' });
  modal(t('br.linkExisting'), h('div', {},
    h('p', { class: 'muted' }, t('br.linkExistingHint')),
    field(t('bird.one'), picker),
    errBox), {
    actions: [
      { label: t('act.cancel') },
      {
        label: t('act.confirm'), kind: 'primary',
        onClick: () => {
          errBox.innerHTML = '';
          const bird = picker.value ? getBird(picker.value) : null;
          if (!bird) return false;
          const candidate = { ...bird, sireId: pair.sireId, damId: pair.damId };
          const { errors } = validateBird(candidate, getBird, allBirds());
          if (errors.length) {
            errBox.append(h('ul', { class: 'problem-errors' },
              errors.map((e) => h('li', {}, t('br.linkBlocked', { reason: t(e.key, e.params) })))));
            return false; // keep the dialog open so the user can pick another
          }
          (async () => {
            await saveBird(candidate);
            egg.chickId = bird.id;
            egg.ringed = (bird.rings || []).length > 0;
            if (egg.hatchDate && !bird.hatchDate) {
              await saveBird({ ...candidate, hatchDate: egg.hatchDate });
            }
            await Pairs.save(pair);
            toast(t('br.linked'));
            refresh();
          })();
        },
      },
    ],
  });
}

function ringChickDialog(pair, egg, refresh) {
  const ringIn = h('input', {
    class: 'input', type: 'text', dir: 'ltr', placeholder: 'JO-2026-12345',
    lang: 'en', autocapitalize: 'characters', autocorrect: 'off', spellcheck: 'false',
  });
  const nameIn = h('input', { class: 'input', type: 'text' });
  const sexSel = h('select', { class: 'input' },
    ['unknown', 'cock', 'hen'].map((s) => h('option', { value: s }, t('sex.' + s))));
  modal(t('br.ringChick'), h('div', { class: 'form-grid' },
    field(t('bird.ring'), ringIn),
    field(t('bird.name'), nameIn),
    field(t('bird.sex'), sexSel)), {
    actions: [
      { label: t('act.cancel') },
      {
        label: t('act.save'), kind: 'primary',
        onClick: () => {
          (async () => {
            const { parseRing } = await import('../engine/rings.js');
            const chick = newBird({
              name: nameIn.value.trim(),
              sex: sexSel.value,
              hatchDate: egg.hatchDate || '',
              status: 'young bird',
              sireId: pair.sireId,
              damId: pair.damId,
              rings: ringIn.value.trim() ? [parseRing(ringIn.value.trim())] : [],
            });
            const sire = getBird(pair.sireId);
            if (sire && sire.strain) chick.strain = sire.strain;
            await saveBird(chick);
            egg.chickId = chick.id;
            egg.ringed = !!ringIn.value.trim();
            await Pairs.save(pair);
            toast(t('br.chickCreated'));
            refresh();
          })();
        },
      },
    ],
  });
}
