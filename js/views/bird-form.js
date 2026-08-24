// views/bird-form.js — create/edit a bird. Validation gate:
// errors (cycles, sex contradictions, impossible ages) BLOCK the save and
// name the offending link; warnings (duplicate rings…) need confirmation.

import { getBird, allBirds, newBird, saveBird, addMedia, nowISO, uuid } from '../db.js';
import { loftStatuses } from '../db.js';
import { t, statusLabel } from '../i18n.js';
import { h, field, select, birdPicker, toast, modal } from '../ui.js';
import { parseRing, RING_TYPES } from '../engine/rings.js';
import { validateBird } from '../engine/validate.js';
import { navigateReplace } from '../app.js';

export function renderBirdForm(birdId, query = null, carryOver = null) {
  const existing = birdId ? getBird(birdId) : null;
  const draft = existing ? JSON.parse(JSON.stringify(existing)) : newBird(carryOver ? carryOver.carry : {});
  // "add sibling" / "add offspring" entry points prefill the parents
  if (!existing && query) {
    const qs = query.get('sire'), qd = query.get('dam');
    if (qs && getBird(qs)) draft.sireId = qs;
    if (qd && getBird(qd)) draft.damId = qd;
  }
  const isNew = !existing;

  const root = h('section', { class: 'view-form' });
  const form = h('form', { class: 'bird-form', novalidate: true });

  // --- basic fields
  const nameIn = h('input', { class: 'input', type: 'text', value: draft.name || '' });
  const sexSel = select(['unknown', 'cock', 'hen'].map((s) => ({ value: s, label: t('sex.' + s) })), draft.sex);
  const hatchIn = h('input', { class: 'input', type: 'date', value: draft.hatchDate || '' });
  const colourIn = h('input', { class: 'input', type: 'text', value: draft.colour || '', list: 'dl-colours' });
  const strainIn = h('input', { class: 'input', type: 'text', value: draft.strain || '', list: 'dl-strains' });
  const eyeIn = h('input', { class: 'input', type: 'text', value: draft.eyeSign || '' });
  const statusSel = select(loftStatuses().map((s) => ({ value: s, label: statusLabel(s) })), draft.status);
  const breederIn = h('input', { class: 'input', type: 'text', value: draft.breeder || '', list: 'dl-breeders' });
  const ownerIn = h('input', { class: 'input', type: 'text', value: draft.owner || '' });
  const acqFromIn = h('input', { class: 'input', type: 'text', value: draft.acquiredFrom || '' });
  const acqDateIn = h('input', { class: 'input', type: 'date', value: draft.acquiredDate || '' });
  const externalIn = h('input', { type: 'checkbox', checked: !!draft.external });

  // --- rings editor
  const ringsWrap = h('div', { class: 'rings-editor' });
  function ringRow(r) {
    const rawIn = h('input', {
      class: 'input ring-input', type: 'text', dir: 'ltr', value: r.raw || '',
      placeholder: 'JO-2026-12345', lang: 'en', autocapitalize: 'characters',
      autocorrect: 'off', spellcheck: 'false', enterkeyhint: 'next',
    });
    const typeSel = select(RING_TYPES.map((rt) => ({ value: rt, label: t('ringType.' + rt) })), r.type || 'national');
    const del = h('button', { class: 'btn btn-small', type: 'button' }, '✕');
    const row = h('div', { class: 'ring-row' }, rawIn, typeSel, del);
    row._get = () => {
      const parsed = parseRing(rawIn.value, typeSel.value);
      parsed.type = typeSel.value === 'national' && parsed.type === 'FCI' ? 'FCI' : typeSel.value;
      if (parsed.type === 'FCI') typeSel.value = 'FCI';
      return parsed;
    };
    del.addEventListener('click', () => row.remove());
    return row;
  }
  for (const r of draft.rings || []) ringsWrap.append(ringRow(r));
  if (!ringsWrap.children.length) {
    // ring numbers are the bird's identity — always start with one row,
    // pre-filled with the country-year prefix during batch entry
    ringsWrap.append(ringRow(carryOver && carryOver.ringPrefix
      ? { raw: carryOver.ringPrefix, type: carryOver.ringType || 'national' } : {}));
  }
  const addRing = h('button', { class: 'btn btn-small', type: 'button', onclick: () => ringsWrap.append(ringRow({})) }, '+ ' + t('bird.ring'));

  // --- parents
  const sirePicker = birdPicker({
    value: draft.sireId,
    filter: (b) => b.id !== draft.id && b.sex !== 'hen',
    placeholder: t('bird.sire'),
    allowCreate: { sex: 'cock' },
  });
  const damPicker = birdPicker({
    value: draft.damId,
    filter: (b) => b.id !== draft.id && b.sex !== 'cock',
    placeholder: t('bird.dam'),
    allowCreate: { sex: 'hen' },
  });

  // --- photos & documents (saved immediately after the bird itself saves)
  const pendingMedia = [];
  const photoIn = h('input', { type: 'file', accept: 'image/*', multiple: true, class: 'input' });
  const photoKind = select([['body'], ['eye'], ['wing'], ['other']].map(([k]) => ({ value: k, label: t('photo.' + k) })), 'body');
  const docIn = h('input', { type: 'file', accept: 'image/*,.pdf', multiple: true, class: 'input' });
  photoIn.addEventListener('change', () => {
    for (const f of photoIn.files) pendingMedia.push({ kind: 'photo', subtype: photoKind.value, file: f });
  });
  docIn.addEventListener('change', () => {
    for (const f of docIn.files) pendingMedia.push({ kind: 'document', subtype: 'other', file: f });
  });

  // --- validation display
  // one-tap hatch date from the ring year (older stock: the ring year is
  // often all the fancier knows)
  const hatchHint = h('div', { class: 'hatch-hint' });
  function updateHatchHint() {
    hatchHint.innerHTML = '';
    if (hatchIn.value) return;
    for (const row of ringsWrap.querySelectorAll('.ring-row')) {
      const r = row._get();
      if (r.year) {
        hatchHint.append(h('button', {
          class: 'btn btn-small', type: 'button',
          onclick: () => { hatchIn.value = r.year + '-01-01'; updateHatchHint(); },
        }, '📅 ' + t('bird.useRingYear', { year: String(r.year) })),
        h('span', { class: 'field-hint' }, t('bird.approxFromRing')));
        return;
      }
    }
  }
  ringsWrap.addEventListener('input', updateHatchHint);
  hatchIn.addEventListener('input', updateHatchHint);
  updateHatchHint();

  const problems = h('div', { class: 'problems' });

  function collect() {
    const rings = [...ringsWrap.querySelectorAll('.ring-row')].map((r) => r._get()).filter((r) => r.raw);
    return {
      ...draft,
      name: nameIn.value.trim(),
      sex: sexSel.value,
      hatchDate: hatchIn.value,
      colour: colourIn.value.trim(),
      strain: strainIn.value.trim(),
      eyeSign: eyeIn.value.trim(),
      status: statusSel.value,
      breeder: breederIn.value.trim(),
      owner: ownerIn.value.trim(),
      acquiredFrom: acqFromIn.value.trim(),
      acquiredDate: acqDateIn.value,
      external: externalIn.checked,
      sireId: sirePicker.value,
      damId: damPicker.value,
      rings,
    };
  }

  function problemText(p) {
    const params = { ...p.params };
    if (params.role) params.role = t('bird.' + params.role);
    if (params.path) {
      params.path = params.path.map((id) => {
        const b = getBird(id);
        return b ? (b.name || (b.rings && b.rings[0] && b.rings[0].raw) || id.slice(0, 6)) : id.slice(0, 6);
      }).join(' ← ');
    }
    if (params.otherId && !params.otherName) {
      const ob = getBird(params.otherId);
      params.otherName = ob ? (ob.name || '') : '';
    }
    return t(p.key, params);
  }

  async function doSave(bird, andNew = false) {
    await saveBird(bird);
    for (const m of pendingMedia) {
      await addMedia(bird.id, m.kind, m.subtype, m.file.name, m.file);
    }
    if (andNew) {
      // stay in the entry rhythm: fresh form carrying the batch-constant
      // fields (strain, colour, status, breeder, owner, ring prefix)
      toast(t('toast.savedNext', { name: bird.name || (bird.rings[0] && bird.rings[0].raw) || '' }));
      const r0 = bird.rings && bird.rings[0];
      const next = renderBirdForm(null, null, {
        carry: {
          strain: bird.strain, colour: bird.colour, status: bird.status,
          breeder: bird.breeder, owner: bird.owner,
        },
        ringPrefix: r0 && r0.country && r0.year ? `${r0.country}-${r0.year}-` : '',
        ringType: r0 ? r0.type : 'national',
      });
      root.replaceWith(next);
      const focusTarget = next.querySelector('.ring-input');
      if (focusTarget) { focusTarget.focus(); focusTarget.setSelectionRange(focusTarget.value.length, focusTarget.value.length); }
      return;
    }
    toast(t('toast.saved'));
    // replace, not push: the phone back gesture must return to the list,
    // never to a stale/blank form
    navigateReplace('#/bird/' + bird.id);
  }

  let saveAndNew = false;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const andNew = saveAndNew;
    saveAndNew = false;
    const bird = collect();
    const { errors, warnings } = validateBird(bird, getBird, allBirds());
    problems.innerHTML = '';
    if (errors.length) {
      problems.append(h('div', { class: 'problem-errors' },
        h('strong', {}, t('val.fixErrors')),
        h('ul', {}, errors.map((p) => h('li', {}, problemText(p))))));
      problems.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    if (warnings.length) {
      modal(t('val.warningsTitle'),
        h('ul', {}, warnings.map((p) => h('li', {}, problemText(p)))), {
          actions: [
            { label: t('act.cancel') },
            { label: t('act.saveAnyway'), kind: 'primary', onClick: () => { doSave(bird, andNew); } },
          ],
        });
      return;
    }
    await doSave(bird, andNew);
  });

  // Enter must never save a half-entered bird — advance focus instead
  form.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target instanceof HTMLInputElement) {
      e.preventDefault();
      const els = [...form.querySelectorAll('input, select, textarea')]
        .filter((x) => !x.disabled && x.offsetParent !== null);
      const i = els.indexOf(e.target);
      if (i >= 0 && i < els.length - 1) els[i + 1].focus();
    }
  });

  const datalist = (id, values) => {
    const dl = h('datalist', { id });
    for (const v of values) dl.append(h('option', { value: v }));
    return dl;
  };
  const distinct = (fn) => [...new Set(allBirds().map(fn).filter(Boolean))].sort();

  form.append(
    h('div', { class: 'form-section form-section-first' },
      h('h2', {}, t('bird.rings')),
      ringsWrap, addRing),
    h('div', { class: 'form-grid' },
      field(t('bird.name'), nameIn),
      field(t('bird.sex'), sexSel),
      field(t('bird.hatchDate'), h('div', {}, hatchIn, hatchHint)),
      field(t('bird.status'), statusSel),
      field(t('bird.colour'), colourIn),
      field(t('bird.strain'), strainIn),
      field(t('bird.eyeSign'), eyeIn),
      field(t('bird.breeder'), breederIn),
      field(t('bird.owner'), ownerIn),
      field(t('bird.acquiredFrom'), acqFromIn),
      field(t('bird.acquiredDate'), acqDateIn),
    ),
    datalist('dl-strains', distinct((b) => b.strain)),
    datalist('dl-colours', distinct((b) => b.colour)),
    datalist('dl-breeders', distinct((b) => b.breeder)),
    h('div', { class: 'form-section' },
      h('h2', {}, t('bird.sire') + ' / ' + t('bird.dam')),
      h('div', { class: 'form-grid' },
        field(t('bird.sire'), sirePicker),
        field(t('bird.dam'), damPicker))),
    h('div', { class: 'form-section' },
      h('label', { class: 'check-row' }, externalIn, ' ', t('bird.external'))),
    h('div', { class: 'form-section' },
      h('h2', {}, t('bird.photos') + ' / ' + t('bird.documents')),
      h('div', { class: 'form-grid' },
        field(t('bird.addPhoto'), h('div', {}, photoKind, photoIn)),
        field(t('bird.addDocument'), docIn))),
    problems,
    h('div', { class: 'form-actions' },
      h('button', { class: 'btn', type: 'button', onclick: () => history.back() }, t('act.cancel')),
      isNew ? h('button', {
        class: 'btn', type: 'submit',
        onclick: () => { saveAndNew = true; },
      }, t('act.saveAndNew')) : null,
      h('button', { class: 'btn btn-primary', type: 'submit' }, t('act.save'))),
  );

  root.append(
    h('div', { class: 'view-head' },
      h('h1', {}, isNew ? t('act.newBird') : t('act.edit'))),
    form);
  return root;
}
