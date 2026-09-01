// views/tools.js — settings, backup/export/import (Tier 1 #6), the pedigree
// scanner hook (Tier 3 #12, strictly optional server feature), and the dev
// panel that runs the engine test suite in-app (quality bar requirement).

import {
  state, setSetting, currentLoft, Lofts, exportAll, importAll,
  listBackups, autoBackup, allBirds, deleteBird, restoreBird, idbGetAll,
  syncStatus, syncNow, setSyncEnabled, listSyncAnomalies,
} from '../db.js';
import { t, fmtDate, fmtNum, getLang, ringHTML } from '../i18n.js';
import {
  h, clear, field, select, toast, confirmDialog, downloadJSON,
  birdLabelHTML, birdLabelText, undoToast,
} from '../ui.js';
import { findDuplicateRings } from '../engine/rings.js';
import { todayISO } from '../dates.js';
import { rerender } from '../app.js';

export function renderTools() {
  const root = h('section', { class: 'view-tools' });
  root.append(h('div', { class: 'view-head' }, h('h1', {}, t('tools.title'))));
  root.append(settingsCard(), syncCard(), loftCard(), duplicatesCard(), examplesCard(),
              backupCard(), scannerCard(), devCard(), aboutCard());
  return root;
}

// ------------------------------------------------------------------ settings
function settingsCard() {
  const langSel = select([
    { value: 'ar', label: 'العربية' },
    { value: 'en', label: 'English' },
  ], state.settings.lang || 'ar');
  const numSel = select([
    { value: 'western', label: t('set.numerals.western') },
    { value: 'eastern', label: t('set.numerals.eastern') },
  ], state.settings.numerals || 'western');
  const dateSel = select([
    { value: 'gregorian', label: t('set.dates.gregorian') },
    { value: 'hijri', label: t('set.dates.hijri') },
    { value: 'both', label: t('set.dates.both') },
  ], state.settings.dates || 'both');
  const hcIn = h('input', { type: 'checkbox', checked: !!state.settings.highContrast });
  const depthIn = h('input', { class: 'input', type: 'number', min: 3, max: 15, dir: 'ltr', value: state.settings.coiDepth || 10 });

  langSel.addEventListener('change', async () => { await setSetting('lang', langSel.value); rerender(); });
  numSel.addEventListener('change', async () => { await setSetting('numerals', numSel.value); rerender(); });
  dateSel.addEventListener('change', async () => { await setSetting('dates', dateSel.value); rerender(); });
  hcIn.addEventListener('change', async () => { await setSetting('highContrast', hcIn.checked); rerender(); });
  depthIn.addEventListener('change', async () => {
    const v = Math.max(3, Math.min(15, +depthIn.value || 10));
    await setSetting('coiDepth', v);
  });

  return h('div', { class: 'card' },
    h('h2', {}, t('tools.title')),
    h('div', { class: 'form-grid' },
      field(t('set.language'), langSel),
      field(t('set.numerals'), numSel, t('set.numeralsHint')),
      field(t('set.dates'), dateSel),
      field(t('set.coiDepth'), depthIn),
      h('label', { class: 'check-row' }, hcIn, ' ', t('set.highContrast'))));
}

// ---------------------------------------------------------------------- loft
function loftCard() {
  const loft = currentLoft();
  const nameIn = h('input', { class: 'input', type: 'text', value: (loft && loft.name) || '',
                              placeholder: t('loft.unnamed') });
  const locIn = h('input', { class: 'input', type: 'text', value: (loft && loft.location) || '' });
  const save = h('button', {
    class: 'btn', onclick: async () => {
      if (!loft) return;
      loft.name = nameIn.value.trim();
      loft.location = locIn.value.trim();
      await Lofts.save(loft);
      toast(t('toast.saved'));
    },
  }, t('act.save'));
  return h('div', { class: 'card' },
    h('h2', {}, t('set.loft')),
    h('div', { class: 'form-grid' },
      field(t('set.loftName'), nameIn),
      field(t('set.loftLocation'), locIn)),
    save);
}

// -------------------------------------------------------------------- backup
function backupCard() {
  const last = state.settings.lastExport;
  const info = h('p', { class: 'muted' },
    last ? t('backup.lastExport', { d: fmtDate(last, { withTime: true }) }) : t('backup.never'));

  const exportBtn = h('button', {
    class: 'btn btn-primary', onclick: async () => {
      const payload = await exportAll();
      downloadJSON(payload, `zajil-export-${todayISO()}.json`);
      await setSetting('lastExport', new Date().toISOString());
      toast(t('toast.exported'));
      rerender();
    },
  }, '⬇ ' + t('backup.exportAll'));

  const modeSel = select([
    { value: 'merge', label: t('backup.importMode.merge') },
    { value: 'replace', label: t('backup.importMode.replace') },
  ], 'merge');
  const fileIn = h('input', { type: 'file', accept: '.json,application/json', class: 'input' });
  fileIn.addEventListener('change', async () => {
    const f = fileIn.files[0];
    if (!f) return;
    if (modeSel.value === 'replace' && !(await confirmDialog(t('confirm.replaceAll')))) { fileIn.value = ''; return; }
    try {
      const payload = JSON.parse(await f.text());
      const counts = await importAll(payload, modeSel.value);
      toast(t('backup.imported', { birds: counts.birds, pairs: counts.pairs, races: counts.raceResults }), { timeout: 6000 });
    } catch (err) {
      toast('⚠ ' + (err && err.message ? err.message : 'import failed'), { timeout: 6000 });
    }
    fileIn.value = '';
  });

  const backupsList = h('div', {});
  listBackups().then((backups) => {
    if (!backups.length) return;
    backupsList.append(h('h3', {}, t('backup.restoreAuto')));
    const sorted = [...backups].sort((a, b) => (a.id < b.id ? 1 : -1)); // newest first
    const sel = select(sorted.map((b) => ({
      value: b.id, label: fmtDate(b.id, { withTime: true }),
    })), sorted[0] && sorted[0].id);
    const btn = h('button', {
      class: 'btn', onclick: async () => {
        const b = backups.find((x) => x.id === sel.value);
        if (!b) return;
        if (!(await confirmDialog(t('backup.confirmSnapshot', { d: fmtDate(b.id, { withTime: true }) })))) return;
        await importAll(b.payload, 'replace');
        toast(t('toast.undone'));
      },
    }, t('act.import'));
    backupsList.append(h('div', { class: 'row-inline' }, sel, btn));
  });

  return h('div', { class: 'card' },
    h('h2', {}, t('backup.title')),
    info,
    h('p', { class: 'muted small' }, t('backup.auto', { h: 12, n: 7 })),
    h('div', { class: 'row-inline' }, exportBtn),
    h('h3', {}, t('backup.import')),
    h('div', { class: 'row-inline' }, modeSel, fileIn),
    backupsList);
}


// ---------------------------------------------------------------- sync card
/**
 * Everything about sync that is worth knowing, in one place (§10).
 *
 * The header says almost nothing on purpose; this is where the detail lives,
 * for whoever is curious or debugging. The last error is shown IN FULL,
 * including its status code — someone looking here wants the specifics, and
 * hiding them behind friendly wording would waste the trip.
 */
function syncCard() {
  const body = h('div', {});
  const card = h('div', { class: 'card' }, h('h2', {}, t('sync.card')), body);

  function refresh() {
    clear(body);
    const s = syncStatus();
    if (s.state === 'hidden') {
      body.append(h('p', { class: 'muted' },
        s.email ? t('sync.notSetUp') : t('sync.signedOut')));
      return;
    }
    const rows = h('div', { class: 'sync-facts' });
    const fact = (label, value) => rows.append(
      h('div', { class: 'row-inline' },
        h('span', { class: 'muted small' }, label),
        h('span', {}, value)));

    fact(t('sync.account'), h('bdi', {}, s.email || '—'));
    fact(t('sync.lastSync'), s.lastSyncAt ? fmtDate(s.lastSyncAt, { time: true }) : t('sync.never'));
    fact(t('sync.pendingN'), fmtNum(s.pending));
    body.append(rows);

    if (s.error) {
      // in full, status code and all — this is the page someone debugging opens
      body.append(h('p', { class: 'warn' },
        t('sync.lastError') + ': ' + t(s.error.key) +
        (s.error.status ? ` (${s.error.status})` : '') +
        (s.error.at ? ' — ' + fmtDate(s.error.at, { time: true }) : '')));
    }

    const anomalies = listSyncAnomalies();
    if (anomalies.length) {
      body.append(h('p', { class: 'warn' }, t('sync.anomalies', { n: anomalies.length })));
      const list = h('ul', { class: 'small muted' });
      for (const a of anomalies.slice(0, 10)) {
        list.append(h('li', {}, `${a.store} · ${String(a.recordId || '').slice(0, 8)}… · ` +
          `${a.status ?? '—'} ${String(a.body || '').slice(0, 80)}`));
      }
      body.append(list);
    }

    body.append(h('div', { class: 'row-inline' },
      h('button', {
        class: 'btn', disabled: s.state === 'syncing' ? '' : null,
        onclick: async (e) => {
          e.target.disabled = true;
          await syncNow();
          refresh();
        },
      }, t('sync.now')),
      h('button', {
        class: 'btn btn-small',
        onclick: async () => {
          await setSyncEnabled(state.settings.syncEnabled === false);
          refresh();
        },
      }, state.settings.syncEnabled === false ? t('sync.toggleOn') : t('sync.toggleOff'))));
  }

  refresh();
  return card;
}

// ------------------------------------------------------ duplicate finder
/**
 * Birds sharing a normalised ring number. Real lofts do re-ring birds, so
 * duplicates are a warning not an error — but accidental clones need finding.
 * Link counts tell the user which copy is safe to delete.
 */
function duplicatesCard() {
  const body = h('div', {});

  async function refresh() {
    clear(body);
    // media counts too: deleteBird removes a bird's photos/documents, so a
    // copy holding the only scans must not be advertised as unlinked
    const mediaCount = new Map();
    for (const m of await idbGetAll('media')) {
      mediaCount.set(m.birdId, (mediaCount.get(m.birdId) || 0) + 1);
    }
    const dupes = findDuplicateRings(allBirds());
    if (!dupes.length) {
      body.append(h('p', { class: 'muted' }, t('dup.none')));
      return;
    }
    body.append(h('p', { class: 'warn' }, t('dup.found', { n: dupes.length })));
    for (const g of dupes) {
      const group = h('div', { class: 'dup-group' },
        h('div', { html: ringHTML(g.raw) }));
      for (const b of g.birds) {
        const links =
          allBirds().filter((x) => x.sireId === b.id || x.damId === b.id).length +
          [...state.pairs.values()].filter((p) => p.sireId === b.id || p.damId === b.id).length +
          [...state.raceResults.values()].filter((r) => r.birdId === b.id).length +
          [...state.healthEvents.values()].filter((e) => e.birdId === b.id).length +
          (mediaCount.get(b.id) || 0);
        group.append(h('div', { class: 'row-inline' },
          h('a', { href: '#/bird/' + b.id, html: birdLabelHTML(b) }),
          h('span', { class: 'muted small' },
            links ? t('dup.keepThis', { n: links }) : t('dup.noLinks')),
          h('button', {
            class: 'btn btn-small btn-danger',
            onclick: async () => {
              const label = birdLabelText(b);
              if (!await confirmDialog(t('confirm.deleteBird', { name: label }))) return;
              const snap = await deleteBird(b.id);
              refresh();
              undoToast(t('toast.deleted'), async () => { await restoreBird(snap); refresh(); });
            },
          }, t('act.delete'))));
      }
      body.append(group);
    }
  }
  refresh();
  return h('div', { class: 'card' }, h('h2', {}, t('dup.title')), body);
}

// ------------------------------------------------------- example datasets
function examplesCard() {
  const btn = (label, file) => h('button', {
    class: 'btn', onclick: async () => {
      const { loadExample } = await import('./birds.js');
      await loadExample(file);
      rerender();
    },
  }, '📚 ' + label);
  return h('div', { class: 'card' },
    h('h2', {}, t('bird.loadExample')),
    h('p', { class: 'muted small' }, t('bird.exampleHint')),
    h('div', { class: 'row-inline' },
      btn(t('bird.exampleSmall'), './sample-data.json'),
      btn(t('bird.exampleLarge'), './example-loft-large.json')));
}

// ------------------------------------------------ scanner hook (Tier 3 #12)
function scannerCard() {
  const urlIn = h('input', {
    class: 'input', type: 'url', dir: 'ltr',
    placeholder: 'https://…', value: state.settings.scanServerUrl || '',
  });
  urlIn.addEventListener('change', () => setSetting('scanServerUrl', urlIn.value.trim()));
  return h('div', { class: 'card' },
    h('h2', {}, t('scan.title')),
    h('p', { class: 'muted' }, t('scan.hint')),
    field(t('scan.serverUrl'), urlIn),
    state.settings.scanServerUrl ? null : h('p', { class: 'muted small' }, t('scan.notConfigured')));
}

// ------------------------------------------------------------------- about
/**
 * Ask the CONTROLLING service worker for its version.
 *
 * Deliberately NOT a constant in js/: a constant reports what the code says,
 * while this reports what is actually installed — and those disagree exactly
 * when it matters, i.e. when an update has been downloaded but not activated,
 * or when the app is running without a service worker at all.
 *
 * Resolves to null rather than rejecting: no controller (plain HTTP, first
 * load before activation), no reply, or a timeout all mean "cannot say".
 */
function askServiceWorkerVersion(timeoutMs = 2000) {
  return new Promise((resolve) => {
    const sw = navigator.serviceWorker && navigator.serviceWorker.controller;
    if (!sw) { resolve(null); return; }
    let settled = false;
    const done = (v) => { if (!settled) { settled = true; resolve(v); } };
    const timer = setTimeout(() => done(null), timeoutMs);
    try {
      const channel = new MessageChannel();
      channel.port1.onmessage = (e) => {
        clearTimeout(timer);
        done(e.data && e.data.type === 'VERSION' ? e.data.version : null);
      };
      sw.postMessage({ type: 'GET_VERSION' }, [channel.port2]);
    } catch {
      clearTimeout(timer);
      done(null);
    }
  });
}

function aboutCard() {
  // starts as the fallback, so the row is never blank while the reply is
  // in flight and never blank if it never arrives
  const value = h('span', { class: 'about-version' }, t('about.version', { v: t('about.unknown') }));
  askServiceWorkerVersion().then((version) => {
    value.textContent = t('about.version', { v: version || t('about.unknown') });
  });
  return h('div', { class: 'card' },
    h('h2', {}, t('about.title')),
    value,
    h('p', { class: 'muted small' }, t('about.hint')));
}

// ------------------------------------------------------- dev panel + tests
function devCard() {
  const out = h('pre', { class: 'test-output', dir: 'ltr' });
  const runBtn = h('button', {
    class: 'btn', onclick: async () => {
      out.textContent = t('common.loading');
      try {
        // Fresh import each run isn't possible (module cache), but tests are
        // pure and re-runnable: harness stores them once.
        await import('../../tests/engine.test.js');
        const { runAll } = await import('../../tests/harness.js');
        const { passed, failed, results } = await runAll();
        out.textContent = results.map((r) => `${r.ok ? '✓' : '✗'} ${r.name}${r.ok ? '' : ' — ' + r.error}`).join('\n') +
          `\n\n${t('dev.passed', { p: passed, f: failed })}`;
        out.classList.toggle('test-fail', failed > 0);
      } catch (err) {
        out.textContent = '✗ ' + err.message;
        out.classList.add('test-fail');
      }
    },
  }, '▶ ' + t('dev.run'));

  const rtBtn = h('button', {
    class: 'btn', onclick: async () => {
      out.textContent = t('common.loading');
      try {
        const before = await exportAll();
        // Serialise → parse → compare the data portion (what a real
        // export/import round-trip preserves).
        const parsed = JSON.parse(JSON.stringify(before));
        const norm = (p) => JSON.stringify({
          birds: p.birds, pairs: p.pairs, raceResults: p.raceResults,
          healthEvents: p.healthEvents, lofts: p.lofts,
          media: (p.media || []).map((m) => ({ id: m.id, birdId: m.birdId, dataURL: m.dataURL })),
        });
        if (norm(before) !== norm(parsed)) throw new Error('serialisation not stable');
        out.textContent = '✓ ' + t('dev.roundtripOK') +
          `\n  birds=${before.birds.length} pairs=${before.pairs.length} races=${before.raceResults.length} media=${before.media.length}`;
        out.classList.remove('test-fail');
      } catch (err) {
        out.textContent = '✗ ' + t('dev.roundtripFail', { msg: err.message });
        out.classList.add('test-fail');
      }
    },
  }, '⇄ ' + t('dev.roundtrip'));

  const integrityBtn = h('button', {
    class: 'btn', onclick: async () => {
      const { checkIntegrity } = await import('../engine/integrity.js');
      const problems = checkIntegrity({
        birds: state.birds, pairs: state.pairs,
        raceResults: state.raceResults, healthEvents: state.healthEvents,
      });
      out.textContent = problems.length
        ? t('integrity.found', { n: problems.length }) + '\n' +
          problems.map((p2) => '  ✗ ' + t(p2.key, p2.params)).join('\n')
        : '✓ ' + t('integrity.clean');
      out.classList.toggle('test-fail', problems.length > 0);
    },
  }, '🔗 ' + t('integrity.title'));

  return h('div', { class: 'card' },
    h('h2', {}, t('dev.title')),
    h('div', { class: 'row-inline' }, runBtn, rtBtn, integrityBtn),
    out);
}
