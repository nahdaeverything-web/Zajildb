// i18n.ext.js — strings the approved specs introduced that the vanilla
// dictionary does not carry. AR and EN both: the vanilla dictionary is
// bilingual and the certificate's AR/EN switch depends on it.
//
// js/i18n.js is copied VERBATIM (src/i18n.js) and does not export its
// dictionary, so this module wraps its t(): a key is looked up here first,
// then delegated. Everything else i18n exports is re-exported unchanged, so
// views import from '@/src/i18n.ext' only.
//
// Curation rule (4.0 ruling 2): every Arabic string in a shipped screen's spec
// must be EITHER a key here (or in the vanilla dictionary) OR on that screen's
// recorded mock-content list in guards/strings.mock.json — the string guard
// fails the build otherwise. Each screen's commit names what it promoted and
// what it judged mock.
import { t as base, getLang } from './i18n.js';
export * from './i18n.js';

export const EXT = {
  // ── shared-states-v1 (4A) ──
  'empty.firstRun.title':     { ar: 'لا طيور بعد', en: 'No birds yet' },
  'empty.firstRun.body':      { ar: 'ابدأ بطائر واحد. الحلقة والاسم يكفيان، والباقي لاحقًا.', en: 'Start with one bird. A ring and a name are enough; the rest can wait.' },
  'empty.filter.title':       { ar: 'لا نتائج لهذا الفلتر', en: 'No results for this filter' },
  'empty.filter.clear':       { ar: 'مسح الفلاتر', en: 'Clear filters' },
  'loading.saving':           { ar: 'جارٍ الحفظ…', en: 'Saving…' },
  'confirm.deleteBird.title': { ar: 'حذف الطائر؟', en: 'Delete this bird?' },
  'confirm.deleteBird.body':  { ar: 'سيُحذف {name} و{n} علاقات مرتبطة: {kinds}', en: '{name} and {n} linked records will be deleted: {kinds}' },
  'confirm.replace.title':    { ar: 'استبدال السجلّ؟', en: 'Replace the records?' },
  'confirm.replace.body':     { ar: 'سيُستبدل السجلّ بالكامل. متابعة؟', en: 'The records will be replaced entirely. Continue?' },
  'confirm.signOut.title':    { ar: 'تسجيل الخروج؟', en: 'Sign out?' },
  'val.cannotSave':           { ar: 'لا يمكن الحفظ', en: 'Cannot save' },
  'val.fieldsNeedFix':        { ar: '{n} حقول تحتاج تصحيحًا:', en: '{n} fields need correcting:' },
  'val.backToForm':           { ar: 'رجوع للنموذج', en: 'Back to the form' },
  'val.saveAnyway':           { ar: 'حفظ رغم ذلك', en: 'Save anyway' },
  'warn.dupRing.title':       { ar: 'رقم حلقة مكرر — يمكنك المتابعة والحفظ', en: 'Duplicate ring number — you can continue and save' },
  'warn.dupRing.body':        { ar: 'الحلقة مسجّلة أيضًا للطائر «{name}».', en: 'This ring is also recorded for “{name}”.' },
  'warn.dupRing.view':        { ar: 'عرض الطائر الآخر', en: 'View the other bird' },
  'notice.importDone':        { ar: 'اكتمل الاستيراد: {birds} طائرًا و {pairs} زوجًا من ملف النسخة الاحتياطية', en: 'Import complete: {birds} birds and {pairs} pairs from the backup file' },
  'notice.viewSummary':       { ar: 'عرض الملخّص', en: 'View summary' },
  'kind.pedigree':            { ar: 'نسب', en: 'pedigree' },
  'kind.races':               { ar: 'سباقات', en: 'races' },
  'kind.health':              { ar: 'صحة', en: 'health' },
  'kind.pairs':               { ar: 'أزواج', en: 'pairs' },
  'kind.media':               { ar: 'صور', en: 'photos' },
  'act.replace':              { ar: 'استبدال', en: 'Replace' },
  'empty.firstRun.cta':       { ar: 'أضف أول طائر', en: 'Add your first bird' },
};

function interpolate(s, params) {
  return params ? s.replace(/\{(\w+)\}/g, (_, k) => (params[k] === undefined ? `{${k}}` : String(params[k]))) : s;
}

/** Ext first, then the vanilla dictionary. Same signature as vanilla t(). */
export function t(key, params) {
  const e = EXT[key];
  if (e) return interpolate(e[getLang() === 'en' ? 'en' : 'ar'] ?? e.ar, params);
  return base(key, params);
}
