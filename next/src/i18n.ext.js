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
  // val.saveAnyway «حفظ رغم ذلك» was retired at 4A acceptance (ruling 14: vanilla act.saveAnyway has the same meaning)
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
  // act.addBird «إضافة طائر» was retired at 4A acceptance (ruling 14: vanilla act.newBird «طير جديد» has the same meaning)
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
  // Ruling D (4B addendum): a tile label is an invariant noun under the number —
  // never the accusative tamyīz the spec drew («سباقًا»), which is wrong at 0 and 1.
  'tile.races':               { ar: 'سباق', en: 'races' },
  'tile.hatch':               { ar: 'الفقس', en: 'Hatched' },
  'profile.verified.title':   { ar: 'سجل موثق', en: 'Verified record' },
  'profile.verified.body':    { ar: 'في زاجل منذ {since}. كل تعديل محفوظ بتاريخه وجهازه، والشهادة تُبنى من السجل نفسه.', en: 'In Zajil since {since}. Every edit is kept with its date and device, and the certificate is built from this very record.' },
  'profile.basics':           { ar: 'البيانات الأساسية', en: 'Basic details' },
  'profile.added':            { ar: 'أُضيف', en: 'Added' },
  // Ruling 7 (4C acceptance): phrased as the vanilla dictionary phrases COI elsewhere —
  // ped.coiAtN «معامل التربية الداخلية حتى {n} أجيال» and ped.completeness «اكتمال الشجرة».
  'profile.coiLine':          { ar: 'معامل التربية الداخلية حتى {n} أجيال: {pct} · اكتمال الشجرة {c}', en: 'Pedigree COI at {n} generations: {pct} · pedigree {c} complete' },
  'profile.fullTree':         { ar: 'شجرة النسب الكاملة', en: 'Full pedigree tree' },
  'race.best':                { ar: 'أفضل نتيجة', en: 'Best result' },
  'race.kmMpm':               { ar: '{km} km · {mpm} m/min', en: '{km} km · {mpm} m/min' },
  'col.release':              { ar: 'الإطلاق', en: 'Release' },
  // Ruling 7 (4C acceptance): the app's own word for a single photo — the gallery's heading
  // stays vanilla's bird.photos «الصور», and each tile is labelled with this.
  'media.photo':              { ar: 'صورة', en: 'Photo' },
  // Ruling 7 (4C acceptance): the app's own word for a single photo — the gallery's heading
  // stays vanilla's bird.photos «الصور», and each tile is labelled with this.
  'media.photo':              { ar: 'صورة', en: 'Photo' },
  'health.next':              { ar: 'التطعيم القادم', en: 'Next vaccination' },
  'health.next.estimate':     { ar: 'تقديري — سنة من آخر تطعيم', en: 'Estimate — one year after the last vaccination' },

  // ── add-edit-bird-v2 (4B) ──
  // Vanilla wins for the title (act.newBird), the save button (act.save), the colour label (bird.colour),
  // the hatch label (bird.hatchDate), the status words (status.*) and the duplicate-ring warning
  // (shared-states' warn.dupRing.*); the spec's variants are on strings.ruled.json (ruling 14).
  'form.sec.basics':          { ar: 'الأساسيات', en: 'Basics' },
  'form.photo.hint':          { ar: 'تُحفظ الصورة على هذا الجهاز.', en: 'The photo is kept on this device.' },
  'form.name.placeholder':    { ar: 'مثال: رعد', en: 'e.g. Thunder' },
  'form.colour.placeholder':  { ar: 'مثال: أزرق مخطط', en: 'e.g. blue bar' },
  'form.parent.none':         { ar: 'لم تُحدَّد', en: 'Not set' },
  'form.parent.pick':         { ar: 'اختيار من اللوفت', en: 'Choose from the loft' },
  'form.parent.quick':        { ar: 'إنشاء سريع', en: 'Quick create' },
  'form.external.title':      { ar: 'سلف خارج اللوفت', en: 'Ancestor outside the loft' },
  // RULED 2026-10-03: the BEHAVIOUR is right and this COPY was wrong. It said an external
  // bird «لا يظهر في قائمة الطيور» — measured, all 8 external birds in the teaching loft DO
  // appear in the register, tagged «خارجي», and the «الخارجية فقط» filter isolates them. They
  // must: a fancier has to be able to find a bird he marked as a reference, and hiding it
  // would make the feature feel like deletion under another name.
  // ── the three-way delete, RULED 2026-10-03 ──
  // A fancier who sells or loses a bird reaches for delete, because it is the only visible
  // control meaning "not mine any more". Deleting one with descendants empties its slot in
  // THEIR pedigrees and changes THEIR computed COI — measured: 12.5% -> 10.5%, three nodes
  // lost, on a bird the fancier was not even looking at. These offer the non-destructive
  // answer at the moment the destructive one is reached for.
  'act.makeReference':        { ar: 'أصبح مرجع نسب', en: 'Make it a pedigree reference' },
  'act.deletePermanently':    { ar: 'حذف نهائيًا', en: 'Delete permanently' },
  // the CONSEQUENCE, not a count: the old body said "N linked records will be deleted",
  // which never mentioned that another bird's pedigree and COI change.
  'confirm.deleteBird.descendants': {
    ar: 'لهذا الطائر {n} من النسل. الحذف سيُفرغ موضعه في شجراتهم ويغيّر معامل التآلف المحسوب لهم.',
    en: 'This bird has {n} descendant(s). Deleting it empties its place in their pedigrees and changes their computed COI.' },
  'toast.madeReference':      { ar: 'تم تحويله إلى مرجع نسب', en: 'Converted to a pedigree reference' },
  'form.external.body':       { ar: 'سجل مرجعي للنسب — يبقى في القائمة بوسم «خارجي» ويحافظ على شجرات نسله، ولا يُحتسب في السباقات.', en: 'A pedigree reference — stays in the register tagged «external» and keeps its descendants\' trees intact; not counted in races.' },
  'act.change':               { ar: 'تغيير', en: 'Change' },
  'form.notes.placeholder':   { ar: 'سلالة، مصدر الطائر، ملاحظات التدريب…', en: 'Strain, where the bird came from, training notes…' },

  // ── pedigree-tree-v1 (4B) ──
  // Ruling D: invariant noun, as tile.races. «أجيال مكتملة» is already invariant (a plural
  // noun phrase, not an inflection of the count) and stays as the spec drew it.
  'ped.tile.ancestors':       { ar: 'سلف من {total}', en: 'ancestors of {total}' },
  'ped.tile.complete':        { ar: 'أجيال مكتملة', en: 'complete generations' },
  'ped.legend.order':         { ar: 'الأب أعلى · الأم أسفل', en: 'Sire above · dam below' },
  'ped.legend.common':        { ar: 'سلف مشترك', en: 'Common ancestor' },
  'ped.legend.unknown':       { ar: 'غير مسجل', en: 'Not recorded' },
  'ped.hint.scroll':          { ar: 'اسحب لرؤية الأجيال الأقدم', en: 'Drag to see the older generations' },
  'ped.gen.parents':          { ar: 'الوالدان', en: 'Parents' },
  'ped.gen.grand':            { ar: 'الأجداد', en: 'Grandparents' },
  'ped.gen.great':            { ar: 'الأجداد الكبار', en: 'Great-grandparents' },
  'ped.gen.fifth':            { ar: 'الجيل الخامس', en: 'Fifth generation' },
  'ped.gen.nth':              { ar: 'الجيل {n}', en: 'Generation {n}' },
  'ped.unknown.add':          { ar: 'سلف غير مسجل — إضافة', en: 'Ancestor not recorded — add' },

  // ── certificate-v1 (4D) ──
  // Vanilla wins where it already says the same thing: cert.title «شهادة نسب» (the spec's
  // «شهادة النسب» is the same sentence), cert.date, act.print, act.share, act.change,
  // ped.generations, ped.gen.* for the ruler, bird.sex / bird.hatchDate / bird.colour /
  // bird.strain for the facts, common.unknown for an unrecorded ancestor.
  'ped.gen.subject':          { ar: 'الطائر', en: 'Subject' },
  'cert.sub':                 { ar: 'زاجل · سجل اللوفت الموثق', en: 'Zajil · verified loft record' },
  'cert.format':              { ar: 'التنسيق', en: 'Format' },
  'cert.format.a4':           { ar: 'A4 عرضي', en: 'A4 landscape' },
  'cert.format.story':        { ar: 'صورة للهاتف', en: 'Phone image' },
  'cert.contentLang':         { ar: 'لغة المحتوى', en: 'Content language' },
  'cert.contentLangHint':     { ar: 'مستقلة عن لغة التطبيق', en: 'Independent of the app language' },
  'cert.photosHint':          { ar: 'تبقى الملفات على جهازك', en: 'Files stay on your device' },
  'cert.loftData':            { ar: 'بيانات اللوفت', en: 'Loft details' },
  'cert.loftDataHint':        { ar: 'من إعدادات اللوفت · تُعدَّل قبل الطباعة', en: 'From the loft settings · editable before printing' },
  'cert.showLoft':            { ar: 'إظهار بيانات اللوفت على الشهادة', en: 'Show the loft details on the certificate' },
  'cert.showLoftHint':        { ar: 'بطاقة المربّي على الطائر المباع', en: 'The breeder card on a bird that is sold' },
  'cert.noPhoto':             { ar: 'لا صورة بعد', en: 'No photo yet' },
  'cert.fromBird':            { ar: 'من ملف الطائر', en: 'From the bird record' },
  'cert.pickPhoto':           { ar: 'اختيار صورة', en: 'Choose a photo' },
  'cert.pickHere':            { ar: 'اختيار هنا', en: 'Choose one here' },
  'cert.photoAway':           { ar: 'الصورة على جهاز آخر', en: 'Photo is on another device' },
  'cert.preview':             { ar: 'المعاينة', en: 'Preview' },
  'cert.size.a4':             { ar: '297×210 مم', en: '297×210 mm' },
  'cert.size.story':          { ar: '9:16 · 1080×1920', en: '9:16 · 1080×1920' },
  'cert.gensN':               { ar: '{n} أجيال', en: '{n} generations' },
  'cert.depth':               { ar: 'عمق الشجرة', en: 'Depth' },
  'act.zoom':                 { ar: 'تكبير', en: 'Zoom' },
  'cert.zoomTitle':           { ar: 'معاينة مكبرة', en: 'Enlarged preview' },
  'cert.zoomHint':            { ar: 'اسحب للتنقل · قرّب بإصبعين', en: 'Drag to pan · pinch to zoom' },
  'cert.zoomFit':             { ar: 'ملاءمة', en: 'Fit' },
  // the COI block: ped.coi already names the coefficient, and the sub-line states what it
  // was computed over — the CERTIFICATE'S OWN depth, which is what the sentence claims.
  'cert.coiLabel':            { ar: 'معامل التربية الداخلية', en: 'Inbreeding coefficient' },
  'cert.coiOver':             { ar: 'محسوب على {n} أجيال · {f} من {tot} سلفًا', en: 'Over {n} generations · {f} of {tot} ancestors' },
  'cert.verifiedSince':       { ar: 'سجل موثق في زاجل منذ {d}', en: 'Verified Zajil record since {d}' },
  'cert.issuedFrom':          { ar: 'صدرت من سجل اللوفت في {d}', en: 'Issued from the loft record on {d}' },
  'cert.note':                { ar: 'الأسماء والحلقات كما هي مسجلة في اللوفت. الحلقة: الدولة · السنة · الرقم.', en: 'Names and rings as recorded in the loft. Ring: country · year · number.' },
  'cert.breederLine':         { ar: 'المربّي: {n}', en: 'Breeder: {n}' },
  'cert.qrTitle':             { ar: 'الصفحة العامة للطائر', en: 'Public bird page' },
  'cert.qrSoon':              { ar: 'قريبًا', en: 'Coming soon' },
  'cert.logoAlt':             { ar: 'شعار اللوفت', en: 'Loft logo' },
  'cert.photoOf':             { ar: 'صورة {n}', en: 'Photo of {n}' },
  'err.exportFailed':         { ar: 'تعذّر تجهيز الملف للمشاركة.', en: 'The file could not be prepared for sharing.' },

  // ── breeding-v1 (4B) ──
  // Vanilla wins for the save buttons (act.save / act.saveAnyway), «الطير» (bird.one), the delete toasts (toast.deleted)
  // and the split «مصدر الزوج» label (br.acquiredFrom whole); the spec variants are on strings.ruled.json (ruling 14).
  'br.countLine':             { ar: '{n} أزواج · {m} نشط', en: '{n} pairs · {m} active' },
  'br.progress':              { ar: 'التقدم', en: 'Progress' },
  'br.empty.body':            { ar: 'أنشئ أول زوج من «زوج جديد».', en: 'Create the first pair from “New pair”.' },
  'br.pairs':                 { ar: 'الأزواج', en: 'Pairs' },
  'br.pairsSeason':           { ar: 'الأزواج · موسم {y}', en: 'Pairs · season {y}' },
  'br.notSaved':              { ar: 'لم يُحفظ الزوج. صحّح ما يلي:', en: 'The pair was not saved. Fix the following:' },
  'br.pickSire':              { ar: 'اختر ذكرًا', en: 'Choose a cock' },
  'br.pickDam':               { ar: 'اختر أنثى', en: 'Choose a hen' },
  'pick.fromLoft':            { ar: 'اختر طيرًا من اللوفت', en: 'Choose a bird from the loft' },   // breeding's link sheet and the race sheet draw the same field
  'br.nest.placeholder':      { ar: '4', en: '4' },
  'br.source.placeholder':    { ar: 'مثل: لوفت أبو خالد — الزرقاء', en: 'e.g. Abu Khalid loft — Zarqa' },
  'br.name.placeholder':      { ar: 'مثل: برق', en: 'e.g. Lightning' },
  'common.optional':          { ar: '(اختياري)', en: '(optional)' },
  'br.saveAndLink':           { ar: 'حفظ وربط بالبيضة', en: 'Save and link to the egg' },
  'br.kinWait':               { ar: 'تنبيه القرابة يظهر بعد اختيار الأب والأم', en: 'The relationship check appears once both parents are chosen' },
  'br.err.sire':              { ar: 'اختر الأب.', en: 'Choose the sire.' },
  'br.err.dam':               { ar: 'اختر الأم.', en: 'Choose the dam.' },
  'br.err.nest':              { ar: 'رقم العش مطلوب.', en: 'The nest box number is required.' },
  'br.err.nestBusy':          { ar: 'العش {n} مشغول بزوج نشط في هذا الموسم.', en: 'Nest box {n} is taken by an active pair this season.' },
  'br.blk.parent':            { ar: 'الطير أحد أبوي هذا الزوج.', en: 'The bird is one of this pair’s parents.' },
  'br.blk.linked':            { ar: 'الطير مرتبط ببيضة أخرى في هذا الموسم.', en: 'The bird is already linked to another egg this season.' },
  'br.ringCtx':               { ar: 'فرخ {s} × {d} · البطن {n} · فقس {date}', en: 'Chick of {s} × {d} · round {n} · hatched {date}' },
  'br.warn.ringYear':         { ar: 'سنة الحلقة {y} تختلف عن موسم الفقس {h}.', en: 'The ring year {y} differs from the hatch year {h}.' },
  'br.hatchedOf':             { ar: '{h} من {n} فقست', en: '{h} of {n} hatched' },
  'br.separate':              { ar: 'فصل الزوج', en: 'Separate the pair' },
  'br.reactivate':            { ar: 'إعادة تنشيط الزوج', en: 'Reactivate the pair' },
  'br.eggsCount':             { ar: '{n} بيض', en: '{n} eggs' },
  'br.roundsCount':           { ar: '{n} بطون', en: '{n} rounds' },
  'br.noEggs':                { ar: 'بلا بيض', en: 'No eggs' },
  'br.noRounds':              { ar: 'لا بطون بعد', en: 'No rounds yet' },
  'br.deleteRound':           { ar: 'حذف البطن', en: 'Delete the round' },
  'br.deleteEgg':             { ar: 'حذف البيضة', en: 'Delete the egg' },
  'br.weanDate':              { ar: 'تاريخ الفطام', en: 'Wean date' },
  'act.more':                 { ar: 'المزيد', en: 'More' },

  // ── races-v1 (4C) ──
  // Vanilla carries the field labels, the race types, the FCI rule and every FCI reason;
  // these are the strings races-v1 introduces. The spec's inline errors are ruled in by
  // design/README.md (it fixes two silent failures: the required bird and unparseable coordinates).
  'race.countLine':           { ar: '{n} نتائج · {b} طيور', en: '{n} results · {b} birds' },
  'race.noneThisSeason':      { ar: 'لا نتائج هذا الموسم', en: 'No results this season' },
  // Ruling 3 (4C acceptance): the log is filtered to the season the header states; this is the way out of that filter.
  'race.allSeasons':          { ar: 'كل المواسم', en: 'All seasons' },
  'race.empty.body':          { ar: 'سجّل أول نتيجة لهذا الموسم من «نتيجة جديدة».', en: 'Record the first result of the season from “New result”.' },
  'race.velocity.sub':        { ar: 'أدخل الوقت والمسافة، أو احسب المسافة والسرعة من الإحداثيات.', en: 'Enter the time and distance, or compute both from the coordinates.' },
  'race.calcDone':            { ar: 'حُسبت المسافة {km} والسرعة {mpm} من الإحداثيات ووقتَي الإطلاق والوصول.', en: 'Distance {km} and velocity {mpm} computed from the coordinates and the release and arrival times.' },
  'val.notSaved':             { ar: 'لم تُحفظ النتيجة. راجع الحقول المحددة بالأحمر.', en: 'The result was not saved. Check the fields marked in red.' },
  'val.birdRequired':         { ar: 'الطير مطلوب — اختر طيرًا قبل الحفظ.', en: 'The bird is required — choose one before saving.' },
  'val.coords':               { ar: 'تعذّر قراءة الإحداثيات. اكتبها بالصيغة: خط العرض، فاصلة، خط الطول — مثل 29.5321, 35.0063', en: 'The coordinates could not be read. Write them as latitude, comma, longitude — e.g. 29.5321, 35.0063' },
  'val.loftCoords':           { ar: 'تعذّر قراءة إحداثيات اللوفت. الصيغة: 31.9539, 35.9106', en: 'The loft coordinates could not be read. The format is 31.9539, 35.9106' },
  'fci.ringShort':            { ar: 'حلقة FCI', en: 'FCI ring' },
  'fci.nonQualifyingShort':   { ar: 'غير مؤهلة', en: 'Non-qualifying' },
  'fci.empty.body':           { ar: 'تظهر الطيور هنا بعد تسجيل أول نتيجة.', en: 'Birds appear here once the first result is recorded.' },

  // ── health-v1 (4C) ──
  // Vanilla carries the four event types, the scope words, the field labels and the empty line.
  // design/README.md rules two deliberate departures in: an EDIT path (vanilla's dialog can only
  // create) and visible inline errors (vanilla's save returns false in silence). The third — the
  // next-vaccination block — is ruling 4 (4.0): last vaccination + 365 days, labelled an estimate.
  'health.countLine':         { ar: '{n} أحداث · آخرها {d}', en: '{n} events · latest {d}' },
  'health.noneYet':           { ar: 'لا أحداث بعد', en: 'No events yet' },
  'health.empty.body':        { ar: 'سجّل أول تطعيم أو علاج من «حدث جديد».', en: 'Record the first vaccination or treatment from “New event”.' },
  'health.noMatch':           { ar: 'لا أحداث تطابق التصفية.', en: 'No events match this filter.' },
  'health.doseLine':          { ar: 'آخر جرعة {last} · يُستحق {due}', en: 'Last dose {last} · due {due}' },
  'health.daysUntil':         { ar: 'يومًا حتى الموعد', en: 'days until it is due' },
  'health.med.placeholder':   { ar: 'مثل: أمبروليوم — كوكسيديا', en: 'e.g. amprolium — coccidiosis' },
  'health.notes.placeholder': { ar: 'الجرعة، المدة، ما لاحظته…', en: 'Dose, duration, what you observed…' },
  'act.filter':               { ar: 'تصفية', en: 'Filter' },
  'val.notSavedEvent':        { ar: 'لم يُحفظ الحدث. راجع الحقل المحدد بالأحمر.', en: 'The event was not saved. Check the field marked in red.' },
  'val.birdRequiredScope':    { ar: 'الطير مطلوب — اختر طيرًا أو غيّر النطاق إلى «اللوفت كامل».', en: 'The bird is required — choose one, or change the scope to “Whole loft”.' },

  // ── stats-v1 (4C) ──
  // design/README.md rules FIVE deliberate departures here, and every one is a
  // string too: the COI honesty band and its note, the «غير محددة» strain row,
  // the fifth sex tile, the whole-view empty state, and the two season cards.
  // Vanilla keeps the titles it already has (stats.title, stats.byStatus,
  // stats.byStrain, stats.avgCOI, stats.maxCOI, stats.totalBirds,
  // stats.birdsWithFCI, stats.coiBand.zero) and the shared race/breeding words.
  'stats.countLine':          { ar: '{n} طيرًا · محدّثة {d}', en: '{n} birds · updated {d}' },
  'stats.coiHead':            { ar: 'توزيع معامل التربية الداخلية — حتى {n} أجيال', en: 'Inbreeding distribution — to {n} generations' },
  'stats.coiScope':           { ar: 'محسوب لـ {n} طيرًا بنسب مسجل من أصل {total}', en: 'Computed for {n} birds with a recorded pedigree of {total}' },
  'stats.coiBand.unknown':    { ar: 'نسب غير معروف', en: 'Pedigree unknown' },
  'stats.coiNote':            { ar: '{n} طيور بلا نسب مسجل (أحد الأبوين مجهول) — غير محتسبة في المتوسط ولا في التوزيع.', en: '{n} birds have no recorded pedigree (a parent is unknown) — excluded from both the average and the distribution.' },
  'stats.total':              { ar: 'المجموع', en: 'Total' },
  'stats.strain.unset':       { ar: 'غير محددة', en: 'Unspecified' },
  'stats.raceCard':           { ar: 'أداء السباقات — الموسم', en: 'Race performance — this season' },
  'stats.raceCount':          { ar: '{n} سباقات', en: '{n} races' },
  'stats.entries':            { ar: 'عدد المشاركات', en: 'Entries' },
  'stats.avgVelocity':        { ar: 'متوسط السرعة', en: 'Average velocity' },
  'stats.bestPosition':       { ar: 'أفضل مركز', en: 'Best position' },
  'stats.top10':              { ar: 'المراكز العشرة الأولى', en: 'Top-ten finishes' },
  'stats.noTraining':         { ar: 'لا تُحتسب نتائج التدريب.', en: 'Training results are not counted.' },
  'stats.breedingCard':       { ar: 'التربية — الموسم', en: 'Breeding — this season' },
  'stats.activePairs':        { ar: 'أزواج نشطة', en: 'Active pairs' },
  'stats.hatched':            { ar: 'فقس', en: 'Hatched' },
  'stats.weanedChicks':       { ar: 'فراخ مفطومة', en: 'Weaned chicks' },
  'stats.hatchRate':          { ar: 'نسبة الفقس', en: 'Hatch rate' },
  'stats.empty.title':        { ar: 'لا توجد بيانات كافية بعد', en: 'Not enough data yet' },
  'stats.empty.body':         { ar: 'تظهر الإحصائيات بعد إضافة أول طيورك. يمكنك أيضًا تحميل اللوفت التعليمي لتجربة الشاشة ببيانات حقيقية.', en: 'The statistics appear once you add your first birds. You can also load the teaching loft to try the screen on real data.' },

  // ── sign-in-v1 (4D) ──
  // RULING 1 (Phase 4 order): the standalone screen is canonical and is never a launch
  // wall. Vanilla carries the field labels and the button (sync.email / sync.password /
  // sync.signIn / sync.signingIn), the not-configured line (sync.notSetUp) and the
  // signed-in line; these are the strings the screen introduces.
  'signin.tagline':           { ar: 'سجل لوفتك. من أي جهاز. حتى بلا إنترنت.', en: 'Your loft’s record. On any device. Even offline.' },
  'signin.badCredentials':    { ar: 'البريد الإلكتروني أو كلمة المرور غير صحيحة', en: 'That email or password is not right' },
  'signin.offline':           { ar: 'لا يوجد اتصال — تحقّق من الشبكة', en: 'No connection — check the network' },
  'signin.offlineBody':       { ar: 'بياناتك محفوظة على الجهاز. أعد المحاولة عند توفر الاتصال.', en: 'Your records are saved on this device. Try again when you are back online.' },
  'signin.notConfiguredBody': { ar: 'تواصل مع إدارة زاجل لإعداد الجهاز.', en: 'Contact the Zajil team to set this device up.' },
  'signin.retry':             { ar: 'إعادة المحاولة', en: 'Try again' },
  'signin.noAccount':         { ar: 'ليس لديك حساب؟', en: 'No account?' },
  'signin.earlyAccess':       { ar: 'سجّل للوصول المبكر', en: 'Request early access' },
  'signin.forgot':            { ar: 'هل نسيت كلمة المرور؟', en: 'Forgot your password?' },
  'signin.forgotHelp':        { ar: 'للمساعدة، تواصل مع إدارة زاجل', en: 'For help, contact the Zajil team' },
  'signin.inviteOnly':        { ar: 'الحسابات بدعوة من إدارة زاجل', en: 'Accounts are by invitation from the Zajil team' },
  'signin.alreadyBody':       { ar: 'يمكنك إدارة الجلسة من بطاقة المزامنة في الأدوات.', en: 'You can manage the session from the sync card in Tools.' },
  'signin.early.title':       { ar: 'سجّل اهتمامك بزاجل', en: 'Register your interest in Zajil' },
  'signin.early.lead':        { ar: 'التسجيل في زاجل مفتوح بدعوة فقط حاليًا. اترك بياناتك وسنتواصل معك عند فتح باب التسجيل.', en: 'Zajil is invitation-only for now. Leave your details and we will be in touch when registration opens.' },
  'signin.early.namePlaceholder': { ar: 'مثال: أبو النشمي', en: 'e.g. Abu Al-Nashmi' },
  'signin.early.chooseCountry':   { ar: 'اختر الدولة', en: 'Choose a country' },
  'signin.early.region':      { ar: 'المنطقة', en: 'The region' },
  'signin.early.allCountries': { ar: 'كل الدول', en: 'All countries' },
  'signin.early.city':        { ar: 'المدينة', en: 'City' },
  'signin.early.cityPlaceholder': { ar: 'مثال: الفحيص', en: 'e.g. Fuheis' },
  'signin.early.loftPlaceholder': { ar: 'مثال: لوفت الفحيص', en: 'e.g. Fuheis Loft' },
  'signin.early.notePlaceholder': { ar: 'كم طائرًا لديك؟ هل تسابق؟', en: 'How many birds do you keep? Do you race?' },
  'signin.early.send':        { ar: 'أرسل الطلب', en: 'Send the request' },
  'signin.early.fine':        { ar: 'سيتم التواصل معك من إدارة زاجل', en: 'The Zajil team will be in touch' },
  'signin.early.doneTitle':   { ar: 'وصلنا طلبك.', en: 'We have your request.' },
  'signin.early.doneBody':    { ar: 'سنتواصل قريبًا.', en: 'We will be in touch soon.' },
  'signin.early.back':        { ar: 'العودة إلى تسجيل الدخول', en: 'Back to sign in' },

  // ── tools-v1 (4D) ──
  // Vanilla carries nearly every label here (tools.title, set.*, sync.*, backup.*, dup.*,
  // scan.*, about.*, dev.*, integrity.*); these are the strings tools-v1 introduces —
  // its three groups and index, the shorter card-level wordings, and RULING 2's loft
  // branding fields.
  // ── the sign-in gate (RULED 2026-10-07) — the loft, never the account ──
  'gate.holds':                { ar: 'هذا الجهاز يحمل {loft}', en: 'This device holds {loft}' },
  'gate.signInToReach':        { ar: 'سجّل الدخول بالحساب الذي استخدمته على هذا الجهاز للوصول إليه.', en: 'Sign in with the account you used on this device to reach it.' },
  // ── the account collision (RULED 2026-10-05; ROOT-FINDINGS RF-13) ──
  // No spec draws this: it is the decision the ruling orders, built from the shared dialog.
  'signin.owner.title':        { ar: 'هذا الجهاز يحمل بيانات حساب آخر', en: 'This device holds another account\'s data' },
  'signin.owner.who':          { ar: 'الحساب السابق: {hint}', en: 'Previous account: {hint}' },
  'signin.owner.whoUnknown':   { ar: 'حساب آخر سبق استخدامه على هذا الجهاز', en: 'Another account used on this device before' },
  'signin.owner.body':         { ar: 'لن تُدمج تلك البيانات مع حسابك ولن تُرفع إليه. صدّرها أولًا إن أردت الاحتفاظ بها، أو امسحها من هذا الجهاز وادخل بحسابك.', en: 'That data will not be merged into your account or uploaded to it. Export it first if you want to keep it, or clear it from this device and sign in as yourself.' },
  'signin.owner.export':       { ar: 'تصدير البيانات', en: 'Export the data' },
  'signin.owner.clear':        { ar: 'مسح والدخول', en: 'Clear and sign in' },
  'signin.owner.confirmTitle': { ar: 'مسح بيانات هذا الجهاز نهائيًا؟', en: 'Clear this device for good?' },
  'signin.owner.confirmBody':  { ar: 'سيُحذف من هذا الجهاز {n} طيرًا وكل ما يتبعها من أزواج ونتائج وسجلات صحية وصور ونسخ تلقائية. لا يمكن التراجع. لا يُحذف شيء من الخادم.', en: '{n} birds will be deleted from this device, with every pair, result, health record, photo and automatic snapshot that goes with them. This cannot be undone. Nothing is deleted from the server.' },
  'signin.owner.confirmGo':    { ar: 'مسح نهائيًا والدخول', en: 'Clear for good and sign in' },
  'signin.owner.inline':       { ar: 'لم يتم تسجيل الدخول: هذا الجهاز يحمل بيانات حساب آخر.', en: 'Not signed in: this device holds another account\'s data.' },
  'signin.owner.inlineBody':   { ar: 'اضغط «تسجيل الدخول» مجددًا لتصديرها أو مسحها. لم يُرفع شيء ولم يُحذف شيء.', en: 'Press “Sign in” again to export it or clear it. Nothing was uploaded and nothing was deleted.' },
  // ── tools-v2: the grouped settings list (RULED 2026-10-03) ──
  // Every string below is one the v2 spec draws and the port RENDERS. Spec strings that are
  // synonyms of an existing vanilla key are NOT duplicated here — per 4A acceptance item 14
  // the existing key wins and the variant is registered in guards/strings.ruled.json. Spec
  // strings the port does not render (the three NOT-YET-BUILT rows, the inline sign-in form
  // superseded by /sign-in, the review switcher) are ruled or mock there too.
  'tools.sub':                { ar: 'الحساب، بيانات المربط، النسخ، الفحوصات وإعدادات التطبيق', en: 'Account, loft details, backups, checks and app settings' },
  'tools.sec.account':        { ar: 'حسابي', en: 'My account' },
  'tools.sec.data':           { ar: 'البيانات', en: 'Data' },
  'tools.sec.checks':         { ar: 'الفحوصات', en: 'Checks' },
  'tools.sec.advancedNote':   { ar: 'يُستخدم نادرًا', en: 'Rarely used' },
  // account row
  'tools.account.helpIn':     { ar: 'الحساب المستخدم للمزامنة', en: 'The account used for sync' },
  'tools.account.helpOut':    { ar: 'لا يوجد حساب مسجل على هذا الجهاز', en: 'No account on this device' },
  'tools.account.helpOff':    { ar: 'إعداد الخادم غير موجود في هذه النسخة', en: 'No server configuration in this build' },
  'tools.account.off':        { ar: 'غير مهيأ', en: 'Not configured' },
  'tools.account.offNote':    { ar: 'إعداد الخادم غير موجود في هذه النسخة، لذلك لا يظهر نموذج تسجيل الدخول.', en: 'This build has no server configuration, so there is no sign-in form.' },
  // sync row + sub-screen
  'tools.sync.helpOut':       { ar: 'سجّل الدخول لتشغيل المزامنة', en: 'Sign in to turn sync on' },
  'tools.sync.helpOff':       { ar: 'إعداد الخادم غير موجود', en: 'No server configuration' },
  'tools.sync.helpOffline':   { ar: 'يعمل محليًا', en: 'Working locally' },
  'tools.sync.helpSyncing':   { ar: 'جارٍ رفع وتنزيل التغييرات', en: 'Uploading and downloading changes' },
  'tools.sync.helpPending':   { ar: 'محفوظة محليًا بانتظار الاتصال', en: 'Saved locally, waiting for a connection' },
  'tools.sync.helpRejected':  { ar: 'لم يقبلها الخادم', en: 'Not accepted by the server' },
  'tools.sync.stopped':       { ar: 'متوقفة', en: 'Stopped' },
  'tools.sync.notSetUpShort': { ar: 'غير مهيأة', en: 'Not configured' },
  'tools.sync.offlineShort':  { ar: 'دون اتصال', en: 'Offline' },
  'tools.sync.syncingShort':  { ar: 'جارٍ…', en: 'Syncing…' },
  'tools.sync.pendingShort':  { ar: '{n} معلّقًا', en: '{n} pending' },
  'tools.sync.errorShort':    { ar: 'خطأ أخير', en: 'Last error' },
  'tools.sync.rejectedShort': { ar: '{n} مرفوضة', en: '{n} rejected' },
  'tools.sync.st.synced':     { ar: 'تمت المزامنة', en: 'Synced' },
  'tools.sync.st.syncedText': { ar: 'لا توجد تغييرات بانتظار الرفع.', en: 'Nothing is waiting to upload.' },
  'tools.sync.st.offlineText':{ ar: 'أي تغييرات جديدة ستبقى على هذا الجهاز حتى يعود الاتصال.', en: 'New changes stay on this device until the connection returns.' },
  'tools.sync.st.syncingText':{ ar: 'يتم رفع أحدث التغييرات وتنزيل ما تغيّر على الأجهزة الأخرى.', en: 'Uploading the latest changes and downloading what changed elsewhere.' },
  'tools.sync.st.pendingText':{ ar: 'التغييرات محفوظة محليًا وستُرسل عند توفر الاتصال.', en: 'Changes are saved locally and will be sent when a connection is available.' },
  'tools.sync.errorHint':     { ar: 'أعد تسجيل الدخول لاستكمال المزامنة.', en: 'Sign in again to continue syncing.' },
  'tools.sync.rejectedText':  { ar: 'بياناتك الأصلية ما زالت على الجهاز. راجع السجلات أدناه.', en: 'Your original data is still on this device. Review the records below.' },
  'tools.sync.outNote':       { ar: 'سجّل الدخول أولًا لتشغيل المزامنة بين الأجهزة.', en: 'Sign in first to sync between devices.' },
  // loft / logo
  'tools.logo.present':       { ar: 'موجود', en: 'Set' },
  'tools.logo.current':       { ar: 'الشعار الحالي: {name}', en: 'Current logo: {name}' },
  'tools.logo.pick':          { ar: 'اختيار شعار', en: 'Choose a logo' },
  'tools.logo.types':         { ar: 'PNG أو JPG', en: 'PNG or JPG' },
  'tools.logo.remove':        { ar: 'إزالة الشعار', en: 'Remove the logo' },
  // data
  'tools.row.export':         { ar: 'تصدير كل البيانات', en: 'Export all data' },
  'tools.export.help':        { ar: 'ملف JSON كامل', en: 'A complete JSON file' },
  'tools.import.help':        { ar: 'دمج أو استبدال كامل', en: 'Merge, or replace everything' },
  'tools.restore.help':       { ar: 'نسخة داخلية محفوظة على هذا الجهاز', en: 'An internal copy kept on this device' },
  'tools.restore.available':  { ar: '{n} متاحة', en: '{n} available' },
  'tools.restore.btn':        { ar: 'استرجاع', en: 'Restore' },
  'tools.restore.last':       { ar: 'آخر نسخة تلقائية: {d}', en: 'Last automatic snapshot: {d}' },
  // checks
  'tools.row.dup':            { ar: 'البحث عن تكرار أرقام الحلقات', en: 'Find duplicate ring numbers' },
  'tools.dup.helpClean':      { ar: 'آخر فحص: لا يوجد تكرار', en: 'Last check: no duplicates' },
  'tools.dup.helpFound':      { ar: 'تحتاج مراجعة قبل الحذف أو الدمج', en: 'Needs review before deleting or merging' },
  'tools.dup.clean':          { ar: 'نظيف', en: 'Clean' },
  'tools.dup.foundN':         { ar: '{n} مكرر', en: '{n} duplicate' },
  'tools.dup.scanned':        { ar: 'تم فحص سجلات الطيور في هذا اللوفت.', en: 'The bird records in this loft were checked.' },
  'tools.integrity.help':     { ar: 'العلاقات، السجلات اليتيمة، والتواريخ', en: 'Links, orphaned records, and dates' },
  'tools.integrity.ok':       { ar: 'سليم', en: 'Sound' },
  'tools.integrity.run':      { ar: 'تشغيل الفحص', en: 'Run the check' },
  'tools.integrity.never':    { ar: 'لم يُشغَّل بعد', en: 'Not run yet' },
  'tools.lastCheck':          { ar: 'آخر فحص: {d}', en: 'Last check: {d}' },
  // settings
  'tools.numerals.help':      { ar: 'أرقام الحلقات تبقى غربية دائمًا', en: 'Ring numbers always stay Western' },
  'tools.coi.help':           { ar: 'من 3 إلى 15 جيلًا', en: '3 to 15 generations' },
  'tools.coi.valueMany':      { ar: '{n} جيلًا', en: '{n} generations' },
  'tools.coi.value':          { ar: '{n} أجيال', en: '{n} generations' },
  'tools.hc.help':            { ar: 'للعمل تحت ضوء الشمس', en: 'For working in sunlight' },
  'tools.hc.off':             { ar: 'موقوف', en: 'Off' },
  'tools.hc.on':              { ar: 'مفعّل', en: 'On' },
  'tools.hc.text':            { ar: 'يزيد الفرق بين النص والخلفية في ظروف الإضاءة القوية.', en: 'Increases the difference between text and background in strong light.' },
  'tools.hc.aria':            { ar: 'تفعيل وضع التباين العالي', en: 'Turn on high contrast' },
  // advanced
  'tools.scan.help':          { ar: 'عنوان خادم الرؤية', en: 'Vision server address' },
  'tools.scan.offShort':      { ar: 'غير مفعّل', en: 'Off' },
  'tools.dev.collapsed':      { ar: 'مطوي', en: 'Collapsed' },
  'tools.about.note':         { ar: 'قد يختلف عن آخر إصدار منشور حتى تُحدَّث الصفحة.', en: 'May differ from the latest published version until the page is refreshed.' },
  'tools.index':              { ar: 'فهرس الصفحة', en: 'Page index' },
  'tools.settings':           { ar: 'الإعدادات', en: 'Settings' },
  'tools.group.settings':     { ar: 'إعدادات', en: 'Settings' },
  'tools.group.settingsSub':  { ar: 'اللغة والعرض · الحساب · اللوفت', en: 'Language and display · account · loft' },
  'tools.group.data':         { ar: 'بيانات', en: 'Data' },
  'tools.group.dataSub':      { ar: 'فحص · تعلّم · نسخ احتياطي', en: 'Checks · learning · backup' },
  'tools.group.advanced':     { ar: 'متقدّم', en: 'Advanced' },
  'tools.group.advancedSub':  { ar: 'ميزات اختيارية · المطوّر · حول', en: 'Optional features · developer · about' },
  'lang.ar':                  { ar: 'العربية', en: 'Arabic' },
  'lang.en':                  { ar: 'English', en: 'English' },
  'set.numerals.westernShort': { ar: 'غربية', en: 'Western' },
  'set.numerals.easternShort': { ar: 'مشرقية', en: 'Eastern' },
  // RULING 2 (Phase 4 order): the loft's branding, which the certificate reads.
  'set.breederName':          { ar: 'اسم المربّي', en: 'Breeder name' },
  'set.phone':                { ar: 'الهاتف', en: 'Phone' },
  'set.website':              { ar: 'الموقع الإلكتروني', en: 'Website' },
  'set.logo':                 { ar: 'شعار اللوفت', en: 'Loft logo' },
  'set.logoSet':              { ar: 'شعار محفوظ على هذا الجهاز', en: 'A logo is saved on this device' },
  'set.logoNone':             { ar: 'لا شعار', en: 'No logo' },
  'set.logoHint':             { ar: 'يُحفظ الشعار على هذا الجهاز كالصور — يظهر في الشهادة ولا يُرفع إلى الخادم.', en: 'The logo is kept on this device like a photo — it appears on the certificate and is never uploaded.' },
  'sync.signInToSync':        { ar: 'سجّل الدخول لمزامنة بياناتك بين أجهزتك.', en: 'Sign in to sync your records across your devices.' },
  'dup.noneShort':            { ar: 'لا توجد أرقام حلقات مكررة.', en: 'No duplicate ring numbers.' },
  'dup.foundShort':           { ar: 'وُجد {n} رقم حلقة مكرر. احتفظ بالسجل المرتبط واحذف النسخة الزائدة.', en: '{n} duplicate ring number(s). Keep the linked record and delete the surplus copy.' },
  // [ruling D] the spec prints «نسختان» — its MOCK's own two-copy group. Kept as a
  // literal it lies at every other count, so it becomes the number plus the invariant
  // noun, which is the grammar ruling D already fixed for the tiles.
  'dup.copies':               { ar: '{n} نسخة', en: '{n} copies' },
  'dup.linkedTo':             { ar: 'هذا السجل مرتبط بـ {n} علاقات ({kinds})', en: 'This record has {n} links ({kinds})' },
  'example.title':            { ar: 'تحميل بيانات تجريبية للتعلّم', en: 'Load sample data for learning' },
  'example.hint':             { ar: 'بيانات للتعلّم فقط. تُدمج مع بياناتك دون حذف شيء — ويمكن حذف طيورها لاحقًا كأي طير.', en: 'Learning data only. It merges with yours and deletes nothing — and its birds can be deleted later like any other.' },
  'example.small':            { ar: 'مثال صغير', en: 'A small example' },
  'example.smallN':           { ar: '{n} طيرًا', en: '{n} birds' },
  'example.large':            { ar: 'لوفت تعليمي كامل', en: 'A full teaching loft' },
  'example.largeN':           { ar: '{n} طيرًا، {g} أجيال', en: '{n} birds, {g} generations' },
  'backup.snapshot':          { ar: 'النسخة', en: 'Snapshot' },
  'backup.noSnapshots':       { ar: 'لا نسخ تلقائية بعد', en: 'No automatic snapshots yet' },
  'backup.importModeLabel':   { ar: 'طريقة الاستيراد', en: 'Import mode' },
  'backup.file':              { ar: 'الملف', en: 'File' },
  'backup.chooseFile':        { ar: 'اختيار ملف', en: 'Choose a file' },
  'backup.noFile':            { ar: 'لم يُختر ملف — .json', en: 'No file chosen — .json' },
  'backup.importBtn':         { ar: 'استيراد', en: 'Import' },
  'about.versionLabel':       { ar: 'الإصدار', en: 'Version' },
  'dev.cardTitle':            { ar: 'أدوات المطوّر', en: 'Developer tools' },
  'dev.cardSub':              { ar: 'فحوصات المحرّك · للمطوّرين فقط', en: 'Engine checks · developers only' },
  'act.less':                 { ar: 'أقل', en: 'Less' },
  // the stepper's «+»: vanilla's act.more is «المزيد» (more ITEMS), which is the wrong word for a stepper
  'act.increase':             { ar: 'أكثر', en: 'More' },
  'backup.lastExportLabel':   { ar: 'آخر تصدير', en: 'Last export' },

  // ── rulings at 4A acceptance ──
  // nav.breeding: a DELIBERATE RENAME from vanilla's «التربية». Every approved
  // spec and the kit NAVIGATION NOTE say «التزاوج»; ruled at 4A acceptance.
  // EXT wins over the vanilla dictionary, so every t('nav.breeding') follows.
  'nav.breeding':             { ar: 'التزاوج', en: 'Breeding' },
  // ── the export's busy state (pre-launch) ──
  // The old export had none: at ~180 photos it threw `Invalid string length` and the fancier
  // saw no file, no toast and an unchanged «آخر تصدير». These three are what it says instead.
  'backup.exporting': { ar: 'جارٍ التصدير…', en: 'Exporting…' },
  'backup.exportProgress': { ar: '{n} من {total} صورة', en: '{n} of {total} photos' },
  'toast.exportFailed': { ar: 'تعذّر التصدير. جرّب مرة أخرى.', en: 'Export failed. Try again.' },

  // ── the import guard (pre-launch) ──
  // File.text() returns "" past 536,870,888 bytes with NO error, so JSON.parse says
  // «Unexpected end of JSON input» — which describes an empty file. These say what is true.
  'backup.importTooLarge': {
    ar: 'الملف أكبر من الحد ({size} م.ب، والحد {limit} م.ب). صدّر لوفتك على دفعتين — احذف بعض الصور مؤقتًا، صدّر، ثم أعدها.',
    en: 'This file is larger than the limit ({size} MB, limit {limit} MB). Export your loft in two passes — remove some photos temporarily, export, then put them back.' },
  'backup.importFailed': {
    ar: 'تعذّر الاستيراد. لم يتغيّر شيء. ({why})',
    en: 'Import failed. Nothing was changed. ({why})' },

  // ── the stats total (pre-launch) ──
  // الطيور counts every record; الإحصائيات excludes reference birds by design
  // (stats.js:12). Both numbers are right and the difference was being asked about —
  // one line under the total answers it without inventing a second tile whose own
  // number would then need explaining.
  'stats.excludesReference': { ar: 'لا تشمل طيور المرجع', en: 'Excludes reference birds' },

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
