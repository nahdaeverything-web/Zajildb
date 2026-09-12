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
  'form.external.body':       { ar: 'سجل مرجعي للنسب فقط — لا يظهر في قائمة الطيور ولا في السباقات.', en: 'A pedigree-only reference record — not listed among the birds and never in races.' },
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

  // ── rulings at 4A acceptance ──
  // nav.breeding: a DELIBERATE RENAME from vanilla's «التربية». Every approved
  // spec and the kit NAVIGATION NOTE say «التزاوج»; ruled at 4A acceptance.
  // EXT wins over the vanilla dictionary, so every t('nav.breeding') follows.
  'nav.breeding':             { ar: 'التزاوج', en: 'Breeding' },
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
