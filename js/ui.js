// ui.js — small DOM helpers, modals, toasts, undo, and the bird picker.

import { t, escapeHTML, ringHTML, fmtNum, fmtPercent } from './i18n.js';
import { allBirds, newBird, saveBird } from './db.js';
import { ringKey, parseRing } from './engine/rings.js';

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); return node; }

// --- view teardown -----------------------------------------------------------
// Views can hold resources the DOM alone doesn't release: object URLs pin their
// Blob for the life of the tab, observers and document listeners keep running.
// The router runs these before swapping views.
const _teardowns = [];
export function onViewTeardown(fn) { _teardowns.push(fn); }
export function runViewTeardowns() {
  while (_teardowns.length) {
    try { _teardowns.pop()(); } catch { /* teardown must never block navigation */ }
  }
}

// -------------------------------------------------------------------- naming

export function primaryRing(bird) {
  if (!bird || !Array.isArray(bird.rings) || !bird.rings.length) return '';
  const fci = bird.rings.find((r) => r.type === 'FCI');
  return (fci || bird.rings[0]).raw || '';
}

/** Bird label as HTML (ring LTR-isolated + name bidi-isolated). */
export function birdLabelHTML(bird) {
  if (!bird) return `<span class="muted">${escapeHTML(t('common.unknown'))}</span>`;
  const ring = primaryRing(bird);
  const bits = [];
  if (ring) bits.push(ringHTML(ring));
  if (bird.name) bits.push(`<bdi>${escapeHTML(bird.name)}</bdi>`);
  if (!bits.length) bits.push(`<span class="muted">${escapeHTML(bird.id.slice(0, 8))}</span>`);
  return bits.join(' · ');
}

/** Plain text label for <option> and title attributes. */
export function birdLabelText(bird) {
  if (!bird) return t('common.unknown');
  const ring = primaryRing(bird);
  return [ring, bird.name].filter(Boolean).join(' · ') || bird.id.slice(0, 8);
}

export function sexIcon(sex) {
  if (sex === 'cock') return '♂';
  if (sex === 'hen') return '♀';
  return '?';
}

/** Sex as a readable chip: symbol + word + colour. HTML string. */
export function sexChipHTML(sex) {
  const s = sex || 'unknown';
  return `<span class="chip sex-chip sex-${s}">${sexIcon(s)} ${escapeHTML(t('sex.' + s))}</span>`;
}

// -------------------------------------------------------------------- toasts

let toastWrap = null;
export function toast(msg, { timeout = 3000, actionLabel = null, onAction = null } = {}) {
  if (!toastWrap) {
    toastWrap = h('div', { class: 'toast-wrap' });
    document.body.append(toastWrap);
  }
  const node = h('div', { class: 'toast', role: 'status' },
    h('span', {}, msg),
    actionLabel ? h('button', {
      class: 'btn btn-small toast-action',
      onclick: () => { node.remove(); onAction && onAction(); },
    }, actionLabel) : null,
  );
  toastWrap.append(node);
  if (timeout) setTimeout(() => node.remove(), timeout);
  return node;
}

/** Undo toast: 8 seconds to reverse a destructive action. */
export function undoToast(msg, onUndo) {
  toast(msg, { timeout: 8000, actionLabel: t('act.undo'), onAction: onUndo });
}

// -------------------------------------------------------------------- modals

// --- background scroll lock -------------------------------------------------
// Without this the page scrolls BEHIND an open dialog: on a touch device the
// swipe bleeds through to the page, and closing the dialog leaves the user
// somewhere else entirely — usually back at the top. Reference-counted
// because a confirm dialog can open on top of another modal.
let _modalDepth = 0;
let _savedScrollY = 0;
const _modalClosedListeners = new Set();

/** Is any dialog currently open? The router defers refreshes while one is. */
export function isModalOpen() { return _modalDepth > 0; }
/** Fires when the LAST open dialog closes. */
export function onModalsClosed(fn) { _modalClosedListeners.add(fn); return () => _modalClosedListeners.delete(fn); }

function lockBodyScroll() {
  if (_modalDepth++ > 0) return;
  _savedScrollY = window.scrollY;
  const body = document.body;
  body.style.position = 'fixed';
  body.style.insetBlockStart = `-${_savedScrollY}px`;
  body.style.insetInlineStart = '0';
  body.style.inlineSize = '100%';
  body.classList.add('modal-open');
}

function unlockBodyScroll() {
  if (--_modalDepth > 0) return;
  _modalDepth = 0;
  const body = document.body;
  body.style.position = '';
  body.style.insetBlockStart = '';
  body.style.insetInlineStart = '';
  body.style.inlineSize = '';
  body.classList.remove('modal-open');
  window.scrollTo(0, _savedScrollY);
  for (const fn of _modalClosedListeners) { try { fn(); } catch { /* never block closing */ } }
}

export function modal(title, contentNode, { actions = [], wide = false } = {}) {
  const overlay = h('div', { class: 'modal-overlay' });
  const box = h('div', {
    class: 'modal' + (wide ? ' modal-wide' : ''),
    role: 'dialog', 'aria-modal': 'true', 'aria-label': title, tabindex: '-1',
  },
    h('div', { class: 'modal-head' },
      h('h2', {}, title),
      h('button', { class: 'btn btn-icon', 'aria-label': t('act.close'), onclick: close }, '✕')),
    h('div', { class: 'modal-body' }, contentNode),
    actions.length ? h('div', { class: 'modal-actions' },
      actions.map((a) => h('button', {
        class: 'btn ' + (a.kind === 'primary' ? 'btn-primary' : a.kind === 'danger' ? 'btn-danger' : ''),
        onclick: () => { const r = a.onClick ? a.onClick() : true; if (r !== false) close(); },
      }, a.label))) : null,
  );
  let closed = false;
  function close() {
    if (closed) return;          // guard: close() can fire from several paths
    closed = true;
    overlay.remove();
    document.removeEventListener('keydown', esc);
    unlockBodyScroll();
  }
  function esc(e) {
    if (e.key === 'Escape') { close(); return; }
    if (e.key !== 'Tab') return;
    // trap Tab inside the dialog
    const items = [...box.querySelectorAll('a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])')]
      .filter((el) => !el.disabled && el.offsetParent !== null);
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  document.addEventListener('keydown', esc);
  overlay.append(box);
  document.body.append(overlay);
  lockBodyScroll();
  // Focus the dialog itself, not its first field: focusing a bird picker would
  // immediately pop its dropdown open. This is also the correct a11y pattern —
  // it announces the dialog without triggering any field's behaviour.
  box.focus({ preventScroll: true });
  return { close, box };
}

/** Confirm dialog. Resolves true/false. Destructive actions must pass through here (or undoToast). */
export function confirmDialog(message, { danger = true } = {}) {
  return new Promise((resolve) => {
    const m = modal(t('act.confirm'), h('p', {}, message), {
      actions: [
        { label: t('act.cancel'), onClick: () => { resolve(false); } },
        { label: t('act.confirm'), kind: danger ? 'danger' : 'primary', onClick: () => { resolve(true); } },
      ],
    });
    m.box.querySelector('.modal-head button').addEventListener('click', () => resolve(false));
  });
}

// --------------------------------------------------------------- bird picker

/**
 * Searchable bird selector. Returns a root node with .value (bird id or null)
 * and .onchange callback. `filter` optionally restricts candidates.
 */
export function birdPicker({ value = null, filter = null, placeholder = null, onPick = null, allowClear = true, allowCreate = null } = {}) {
  const root = h('div', { class: 'bird-picker' });
  const input = h('input', {
    type: 'text', class: 'input', placeholder: placeholder || t('bird.chooseBird'),
    autocomplete: 'off',
  });
  const list = h('div', { class: 'picker-list', hidden: true });
  const clearBtn = allowClear ? h('button', { class: 'btn btn-small', type: 'button' }, t('bird.clearParent')) : null;
  root.value = value;
  // The last CONFIRMED selection. Typing a search clears root.value so the
  // create-guard works, but abandoning the search must not silently detach a
  // parent — only the explicit clear button may do that.
  let committed = value;

  function labelFor(id) {
    const b = allBirds().find((x) => x.id === id);
    return b ? birdLabelText(b) : '';
  }
  if (value) input.value = labelFor(value);

  /** Birds this picker is allowed to offer (sire pickers exclude hens, etc.). */
  const pool = () => (filter ? allBirds().filter(filter) : allBirds());

  function candidates(q) {
    const needle = q.trim().toLowerCase();
    const ringNeedle = ringKey(q);
    let birds = pool();
    if (needle) {
      birds = birds.filter((b) => {
        if ((b.name || '').toLowerCase().includes(needle)) return true;
        if ((b.strain || '').toLowerCase().includes(needle)) return true;
        if (ringNeedle && (b.rings || []).some((r) => ringKey(r).includes(ringNeedle))) return true;
        return false;
      });
    }
    return birds.slice(0, 30);
  }

  function pick(b) {
    root.value = b.id;
    committed = b.id;
    input.value = birdLabelText(b);
    list.hidden = true;
    onPick && onPick(b.id);
  }

  /**
   * Is `q` already an existing bird? Matching on normalised ring, exact name,
   * or the full display label (which is what sits in the input after a pick).
   * Offering "create" for one of those produced duplicate records.
   */
  function exactMatch(q, list) {
    const needle = q.trim().toLowerCase();
    if (!needle) return null;
    const rk = ringKey(q);
    return (list || allBirds()).find((b) => {
      if (rk && (b.rings || []).some((r) => ringKey(r) === rk)) return true;
      if ((b.name || '').trim().toLowerCase() === needle) return true;
      if (birdLabelText(b).trim().toLowerCase() === needle) return true;
      return false;
    }) || null;
  }

  function renderList() {
    clear(list);
    // Re-focusing a filled field: the input still holds the selected bird's
    // label, which matches nothing as a search. Browse the normal list instead.
    const showingLabel = root.value && input.value === labelFor(root.value);
    const cands = candidates(showingLabel ? '' : input.value);
    const q = input.value.trim();
    // Only offer creation for a query that matches NOTHING (anywhere — not
    // just within this picker's filter) and while no bird is selected;
    // otherwise "create" would silently clone an existing record.
    const clash = showingLabel ? null : exactMatch(q, allBirds());
    const canCreate = !!(allowCreate && q && !root.value && !clash);
    // A match this picker can't offer (e.g. a hen in a sire picker) must be
    // explained, never silently swallowed.
    const blocked = clash && !exactMatch(q, pool()) ? clash : null;
    if (!cands.length && !canCreate && !blocked) { list.hidden = true; return; }
    if (blocked) {
      list.append(h('div', { class: 'picker-note' },
        t('picker.existsButFiltered', { name: birdLabelText(blocked), sex: t('sex.' + blocked.sex) })));
    }
    for (const b of cands) {
      list.append(h('button', {
        type: 'button', class: 'picker-item',
        html: `${birdLabelHTML(b)} ${sexChipHTML(b.sex)}`,
        onclick: () => pick(b),
      }));
    }
    // allowCreate: backfilling an existing loft is ancestor-first — let the
    // user create a missing (external) ancestor right here instead of
    // abandoning the form. A query with digits is treated as a ring number.
    if (canCreate) {
      list.append(h('button', {
        type: 'button', class: 'picker-item picker-create',
        html: `+ ${escapeHTML(t('picker.createNew', { q }))}` +
              `<span class="picker-create-hint">${escapeHTML(t('picker.createHint'))}</span>`,
        onclick: async () => {
          // last-line defence: never create a second record for a ring that
          // already exists — select the existing bird instead
          const dupe = exactMatch(q, allBirds());
          if (dupe) { pick(dupe); return; }
          // \d is ASCII-only — in an Arabic-first app a ring may be typed
          // with Eastern Arabic numerals, which are still a ring, not a name.
          const hasDigit = /[0-9\u0660-\u0669]/.test(q);
          const stub = newBird({
            external: true,
            sex: allowCreate.sex || 'unknown',
            name: hasDigit ? '' : q,
            rings: hasDigit ? [parseRing(q)] : [],
          });
          await saveBird(stub);
          pick(stub);
        },
      }));
    }
    list.hidden = false;
  }

  input.addEventListener('input', () => {
    // Symmetrical with the clear button: consumers (e.g. the pair dialog) keep
    // their own copy of the id and must learn the selection was dropped,
    // otherwise they save a bird the field no longer shows.
    const had = root.value;
    root.value = null;
    if (had) onPick && onPick(null);
    renderList();
  });
  // Abandoning an unfinished search reverts to the committed selection, so a
  // field can never LOOK filled while holding null (which used to wipe the
  // parent link on save, with no warning and no undo).
  input.addEventListener('blur', () => {
    setTimeout(() => {
      if (root.contains(document.activeElement)) return;  // a picker item is being clicked
      list.hidden = true;
      if (root.value === committed) return;
      root.value = committed;
      input.value = committed ? labelFor(committed) : '';
      onPick && onPick(committed);
    }, 180);
  });

  input.addEventListener('focus', () => {
    // a filled field holds an existing bird's label — select it so typing
    // replaces rather than appends, and so the list reads as a re-search
    if (root.value) input.select();
    renderList();
  });
  document.addEventListener('click', (e) => { if (!root.contains(e.target)) list.hidden = true; });
  if (clearBtn) clearBtn.addEventListener('click', () => {
    root.value = null; committed = null; input.value = '';
    onPick && onPick(null);
  });

  root.append(input, list);
  if (clearBtn) root.append(clearBtn);
  return root;
}

// ------------------------------------------------------------------- fields

export function field(labelText, inputNode, hint = null) {
  return h('label', { class: 'field' },
    h('span', { class: 'field-label' }, labelText),
    inputNode,
    hint ? h('span', { class: 'field-hint' }, hint) : null);
}

export function select(options, value, attrs = {}) {
  const s = h('select', { class: 'input', ...attrs });
  for (const o of options) {
    s.append(h('option', { value: o.value, selected: o.value === value }, o.label));
  }
  return s;
}

// ----------------------------------------------------------------- download

export function downloadJSON(obj, filename) {
  const blob = new Blob([JSON.stringify(obj, null, 1)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = h('a', { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export function fmtCOIBadge(coi) {
  let cls = 'coi-none';
  if (coi >= 0.25) cls = 'coi-severe';
  else if (coi >= 0.125) cls = 'coi-high';
  else if (coi >= 0.0625) cls = 'coi-moderate';
  else if (coi > 0) cls = 'coi-info';
  return `<span class="coi-badge ${cls}">${fmtPercent(coi, 1)}</span>`;
}
