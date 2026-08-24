// views/cert.js — Tier 1 #5: print-ready pedigree certificate.
// Certificate language is chosen independently of the UI language; the
// Arabic certificate mirrors (subject RIGHT, ancestors extending LEFT)
// because the pedigree grid follows its container's `dir`.

import { getBird, state, currentLoft } from '../db.js';
import { t, getLang, configure, fmtDate, escapeHTML, ringHTML } from '../i18n.js';
import { h, clear, birdLabelHTML, primaryRing, sexIcon } from '../ui.js';
import { buildTree } from './pedigree.js';
import { inbreeding } from '../engine/coi.js';
import { fmtPercent } from '../i18n.js';
import { navigate, navigateReplace } from '../app.js';

const vs = { gens: 5, lang: null };

export function renderCertificate(id) {
  const bird = getBird(id);
  if (!bird) { navigateReplace('#/birds'); return null; }
  const root = h('section', { class: 'view-cert' });
  const uiLang = getLang();
  if (!vs.lang) vs.lang = uiLang;

  const toolbar = h('div', { class: 'cert-toolbar no-print' },
    h('a', { class: 'btn', href: '#/bird/' + id }, '← ' + t('act.back')),
    h('span', { class: 'muted' }, t('ped.generations') + ':'),
    h('div', { class: 'seg' }, [3, 4, 5].map((g) => h('button', {
      class: 'seg-btn' + (vs.gens === g ? ' active' : ''),
      onclick: () => { vs.gens = g; redraw(); },
    }, String(g)))),
    h('span', { class: 'muted' }, t('cert.language') + ':'),
    h('div', { class: 'seg' }, [['ar', 'العربية'], ['en', 'English']].map(([l, label]) => h('button', {
      class: 'seg-btn' + (vs.lang === l ? ' active' : ''),
      onclick: () => { vs.lang = l; redraw(); },
    }, label))),
    h('button', { class: 'btn btn-primary', onclick: () => window.print() }, '🖨 ' + t('act.print')));

  const page = h('div', { class: 'cert-page' });

  function redraw() {
    toolbar.querySelectorAll('.seg')[0].querySelectorAll('.seg-btn')
      .forEach((b, i) => b.classList.toggle('active', [3, 4, 5][i] === vs.gens));
    toolbar.querySelectorAll('.seg')[1].querySelectorAll('.seg-btn')
      .forEach((b, i) => b.classList.toggle('active', ['ar', 'en'][i] === vs.lang));

    // Render the certificate in ITS language, then restore the UI language.
    configure({ lang: vs.lang });
    clear(page);
    page.dir = vs.lang === 'ar' ? 'rtl' : 'ltr';
    page.lang = vs.lang;

    const loft = currentLoft();
    const depth = +(state.settings.coiDepth || 10);
    const { coi } = inbreeding(getBird, id, depth);

    page.append(
      h('div', { class: 'cert-head' },
        h('div', { class: 'cert-brand' }, '🕊 ', t('app.name')),
        h('h1', {}, t('cert.title')),
        loft && loft.name ? h('div', { class: 'cert-loft' },
          t('cert.issuedBy') + ': ', h('bdi', {}, loft.name),
          loft.location ? h('span', { class: 'muted' }, ' — ', h('bdi', {}, loft.location)) : null) : null),
      h('div', { class: 'cert-subject' },
        h('div', { class: 'cert-subject-main', html: birdLabelHTML(bird) + ' ' + sexIcon(bird.sex) }),
        h('div', { class: 'cert-subject-meta' },
          [ bird.hatchDate ? `${t('bird.hatchDate')}: ${fmtDate(bird.hatchDate)}` : null,
            bird.colour ? `${t('bird.colour')}: ${bird.colour}` : null,
            bird.strain ? `${t('bird.strain')}: ${bird.strain}` : null,
            `${t('ped.coiAtN', { n: depth })}: ${fmtPercent(coi, 1)}`,
          ].filter(Boolean).map((s) => h('span', { class: 'cert-meta-item' }, h('bdi', {}, s))))),
      h('div', { class: 'cert-tree' }, buildTree(id, vs.gens, { linkCards: false })),
      h('div', { class: 'cert-foot' },
        h('div', {}, t('cert.date') + ': ' + fmtDate(new Date().toISOString())),
        h('div', { class: 'cert-sign' }, t('cert.signature') + ': ____________________')),
    );
    configure({ lang: uiLang });
  }

  redraw();
  root.append(toolbar, page);
  return root;
}
