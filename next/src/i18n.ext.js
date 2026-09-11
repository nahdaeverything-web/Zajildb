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
// what it judged mock. Where vanilla already has the string, vanilla's wording
// is the app's voice and wins; the spec's variant goes to strings.pending.json.
import { t as base, getLang } from './i18n.js';
export * from './i18n.js';

export const EXT = {
  // ── shared-states-v1 (4A) ──
  'empty.firstRun.title':     { ar: 'لا طيور بعد', en: 'No birds yet' },
  'empty.firstRun.body':      { ar: 'ابدأ بطائر واحد. الحلقة والاسم يكفيان، والباقي لاحقًا.', en: 'Start with one bird. A ring and a name are enough; the rest can wait.' },
  'empty.firstRun.cta':       { ar: 'أضف أول طائر', en: 'Add your first bird' },
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

  // ── loft-home-v1 (4A) ──
  'loft.season':              { ar: 'موسم {a} / {b}', en: 'Season {a} / {b}' },
  'loft.countLine':           { ar: '{n} طائرًا · {m} ذكرًا · {f} أنثى', en: '{n} birds · {m} cocks · {f} hens' },
  'loft.search.placeholder':  { ar: 'بحث بالاسم أو رقم الحلقة', en: 'Search by name or ring number' },
  'act.addBird':              { ar: 'إضافة طائر', en: 'Add a bird' },
  'filter.males':             { ar: 'ذكور', en: 'Cocks' },
  'filter.females':           { ar: 'إناث', en: 'Hens' },
  'loft.generation':          { ar: 'جيل {y}', en: 'Generation {y}' },
  'loft.noResults':           { ar: 'لا نتائج', en: 'No results' },
  'col.ring':                 { ar: 'الحلقة', en: 'Ring' },
  'col.generation':           { ar: 'الجيل', en: 'Generation' },
  'col.lastResult':           { ar: 'آخر نتيجة', en: 'Last result' },
  'race.noneShort':           { ar: 'لا سباقات', en: 'No races' },
  'empty.loft.body':          { ar: 'اسم، رقم حلقة، وجنس — وتبدأ شجرة نسب لوفتك من هنا. كل ما تسجّله يُحفظ على جهازك ويُزامَن حين يتوفر اتصال.', en: 'A name, a ring number and a sex — and your loft’s pedigree tree starts here. Everything you record is saved on your device and synced when a connection is available.' },
  'empty.example.cta':        { ar: 'تحميل سرب تعليمي', en: 'Load a teaching flock' },
  'empty.example.hint':       { ar: '{n} طائرًا بأنسابهم ونتائجهم للتجربة — يمكن حذفهم لاحقًا', en: '{n} birds with their pedigrees and results to try out — they can be deleted later' },

  // ── bird-profile-v1 (4A) ──
  // Vanilla already carries «رجوع» (act.back), «الصور» (bird.photos), «السجل الصحي» (bird.healthLog),
  // «المركز» (race.position, the spec's «الترتيب» column) and «الفقس» in «تاريخ الفقس» (bird.hatchDate,
  // the spec's «التفقيس»); vanilla's words are used and the spec variants are on strings.pending.json.
  'act.options':              { ar: 'خيارات', en: 'Options' },
  'tab.overview':             { ar: 'عام', en: 'Overview' },
  'tab.pedigree':             { ar: 'النسب', en: 'Pedigree' },
  'tile.coi':                 { ar: 'التربية الداخلية', en: 'Inbreeding' },
  'tile.races':               { ar: 'سباقًا', en: 'races' },
  'tile.hatch':               { ar: 'الفقس', en: 'Hatched' },
  'profile.verified.title':   { ar: 'سجل موثق', en: 'Verified record' },
  'profile.verified.body':    { ar: 'في زاجل منذ {since}. كل تعديل محفوظ بتاريخه وجهازه، والشهادة تُبنى من السجل نفسه.', en: 'In Zajil since {since}. Every edit is kept with its date and device, and the certificate is built from this very record.' },
  'profile.basics':           { ar: 'البيانات الأساسية', en: 'Basic details' },
  'profile.added':            { ar: 'أُضيف', en: 'Added' },
  'profile.coiLine':          { ar: 'التربية الداخلية {pct} من {n} أجيال · اكتمال الشجرة {c}', en: 'Inbreeding {pct} over {n} generations · pedigree {c} complete' },
  'profile.fullTree':         { ar: 'شجرة النسب الكاملة', en: 'Full pedigree tree' },
  'race.best':                { ar: 'أفضل نتيجة', en: 'Best result' },
  'race.kmMpm':               { ar: '{km} km · {mpm} m/min', en: '{km} km · {mpm} m/min' },
  'col.release':              { ar: 'الإطلاق', en: 'Release' },
  'health.next':              { ar: 'التطعيم القادم', en: 'Next vaccination' },
  'health.next.estimate':     { ar: 'تقديري — سنة من آخر تطعيم', en: 'Estimate — one year after the last vaccination' },
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
