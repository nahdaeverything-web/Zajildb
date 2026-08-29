// i18n.js — Arabic-first internationalisation.
// Arabic (Jordanian conventions) and English. Full RTL is handled by CSS
// logical properties + document dir; THIS module owns strings, numerals,
// and dates. Ring numbers always render Western digits, LTR-isolated.

import { parseLocalDate } from './dates.js';

export const LANGS = ['ar', 'en'];

const dict = {
  // ---- app chrome
  'app.name': { ar: 'زاجل', en: 'Zajil' },
  'app.tagline': { ar: 'إدارة اللوفت وأنساب الحمام الزاجل', en: 'Racing pigeon pedigree & loft management' },
  'nav.birds': { ar: 'الطيور', en: 'Birds' },
  'nav.breeding': { ar: 'التربية', en: 'Breeding' },
  'nav.races': { ar: 'السباقات', en: 'Races' },
  'nav.health': { ar: 'الصحة', en: 'Health' },
  'nav.stats': { ar: 'الإحصائيات', en: 'Statistics' },
  'nav.tools': { ar: 'الأدوات', en: 'Tools' },

  // ---- common actions
  'act.save': { ar: 'حفظ', en: 'Save' },
  'act.cancel': { ar: 'إلغاء', en: 'Cancel' },
  'act.delete': { ar: 'حذف', en: 'Delete' },
  'act.edit': { ar: 'تعديل', en: 'Edit' },
  'act.add': { ar: 'إضافة', en: 'Add' },
  'act.close': { ar: 'إغلاق', en: 'Close' },
  'act.confirm': { ar: 'تأكيد', en: 'Confirm' },
  'act.undo': { ar: 'تراجع', en: 'Undo' },
  'act.back': { ar: 'رجوع', en: 'Back' },
  'act.print': { ar: 'طباعة', en: 'Print' },
  'act.export': { ar: 'تصدير', en: 'Export' },
  'act.import': { ar: 'استيراد', en: 'Import' },
  'act.share': { ar: 'مشاركة', en: 'Share' },
  'act.search': { ar: 'بحث', en: 'Search' },
  'act.saveAnyway': { ar: 'حفظ رغم التحذير', en: 'Save anyway' },
  'act.saveAndNew': { ar: 'حفظ وإضافة آخر', en: 'Save & add another' },
  'picker.createNew': { ar: 'إنشاء سجل جديد لـ «{q}»', en: 'Create a NEW record for “{q}”' },
  'picker.existsButFiltered': { ar: 'يوجد طير بهذا الرقم/الاسم ({name}) لكنه مسجَّل {sex} — لا يصلح هنا. صحّح جنسه من صفحته إن كان خطأ.', en: 'A bird with this ring/name exists ({name}) but is recorded as {sex}, so it cannot be chosen here. Fix its sex on its page if that is the error.' },
  'picker.createHint': { ar: 'يظهر هذا الخيار فقط عندما لا يوجد طير مطابق — لتسجيل سلف غير موجود في اللوفت.', en: 'Shown only when nothing matches — for an ancestor not yet in your loft.' },
  'dup.title': { ar: 'طيور مكررة (نفس رقم الحلقة)', en: 'Duplicate birds (same ring number)' },
  'dup.none': { ar: 'لا توجد أرقام حلقات مكررة. ✓', en: 'No duplicate ring numbers. ✓' },
  'dup.found': { ar: 'وُجد {n} رقم حلقة مكرر. راجع كل مجموعة واحذف النسخ الزائدة (يمكن التراجع).', en: '{n} duplicated ring number(s). Review each group and delete the extra copies (undoable).' },
  'dup.keepThis': { ar: 'هذا السجل مرتبط بـ {n} علاقة (أبناء/أزواج/سباقات) — احذف النسخة الفارغة بدلًا منه.', en: 'This record has {n} link(s) (offspring/pairs/races) — delete the empty copy instead.' },
  'dup.noLinks': { ar: 'بدون روابط معروفة', en: 'No known links' },
  'bird.useRingYear': { ar: 'استخدام سنة الحلقة: {year}', en: 'Use ring year: {year}' },
  'bird.approxFromRing': { ar: 'تاريخ تقريبي — أول السنة من سنة الحلقة', en: 'Approximate — Jan 1 of the ring year' },
  'toast.savedNext': { ar: 'حُفظ {name} — أدخل التالي', en: 'Saved {name} — enter the next one' },
  'act.newBird': { ar: 'طير جديد', en: 'New bird' },
  'act.viewPedigree': { ar: 'شجرة النسب', en: 'Pedigree' },
  'act.certificate': { ar: 'شهادة النسب', en: 'Certificate' },
  'common.all': { ar: 'الكل', en: 'All' },
  'common.none': { ar: 'لا يوجد', en: 'None' },
  'common.unknown': { ar: 'غير معروف', en: 'Unknown' },
  'common.loading': { ar: 'جارٍ التحميل…', en: 'Loading…' },
  'common.results': { ar: '{n} نتيجة', en: '{n} results' },
  'common.yes': { ar: 'نعم', en: 'Yes' },
  'common.no': { ar: 'لا', en: 'No' },
  'common.date': { ar: 'التاريخ', en: 'Date' },
  'common.notes': { ar: 'ملاحظات', en: 'Notes' },
  'common.actions': { ar: 'إجراءات', en: 'Actions' },
  'common.total': { ar: 'المجموع', en: 'Total' },
  'common.offline': { ar: 'يعمل دون اتصال', en: 'Works offline' },

  // ---- bird fields
  'bird.one': { ar: 'طير', en: 'Bird' },
  'bird.name': { ar: 'الاسم', en: 'Name' },
  'bird.sex': { ar: 'الجنس', en: 'Sex' },
  'sex.cock': { ar: 'ذكر', en: 'Cock' },
  'sex.hen': { ar: 'أنثى', en: 'Hen' },
  'sex.unknown': { ar: 'غير معروف', en: 'Unknown' },
  'bird.hatchDate': { ar: 'تاريخ الفقس', en: 'Hatch date' },
  'bird.colour': { ar: 'اللون', en: 'Colour' },
  'bird.strain': { ar: 'السلالة', en: 'Strain' },
  'bird.eyeSign': { ar: 'علامة العين', en: 'Eye sign' },
  'bird.status': { ar: 'الحالة', en: 'Status' },
  'bird.sire': { ar: 'الأب', en: 'Sire' },
  'bird.dam': { ar: 'الأم', en: 'Dam' },
  'bird.breeder': { ar: 'المربّي', en: 'Breeder' },
  'bird.owner': { ar: 'المالك', en: 'Owner' },
  'bird.acquiredFrom': { ar: 'مصدر الاقتناء', en: 'Acquired from' },
  'bird.acquiredDate': { ar: 'تاريخ الاقتناء', en: 'Acquired date' },
  'bird.rings': { ar: 'الحلقات', en: 'Rings' },
  'bird.ring': { ar: 'رقم الحلقة', en: 'Ring number' },
  'bird.ringType': { ar: 'نوع الحلقة', en: 'Ring type' },
  'bird.external': { ar: 'طير خارجي (من نسب غير مملوك)', en: 'External bird (ancestor never owned)' },
  'bird.ownership': { ar: 'ملكية الطير', en: 'Ownership' },
  'bird.owned': { ar: 'في لوفتي', en: 'In my loft' },
  'bird.ownedHint': { ar: 'طير تملكه أو ملكته — يُحتسب في إحصائيات اللوفت.', en: 'A bird you own or owned — counted in loft statistics.' },
  'bird.referenceOnly': { ar: 'خارجي — للنسب فقط', en: 'External — pedigree only' },
  'bird.referenceHint': { ar: 'سلف لم تملكه قط (من شهادة نسب البائع مثلًا). يُسجَّل كطير كامل ليعمل حساب القرابة، لكنه لا يُحتسب ضمن طيور لوفتك ولا في الإحصائيات.', en: 'An ancestor you never owned (e.g. from the seller’s pedigree). Recorded as a full bird so relatedness maths works, but not counted among your loft’s birds or in its statistics.' },
  'filter.ownership': { ar: 'الملكية', en: 'Ownership' },
  'filter.ownedOnly': { ar: 'طيوري فقط', en: 'My birds only' },
  'filter.externalOnly': { ar: 'الخارجية فقط', en: 'External only' },
  'bird.externalShort': { ar: 'خارجي', en: 'External' },
  'bird.photos': { ar: 'الصور', en: 'Photos' },
  'bird.documents': { ar: 'الوثائق', en: 'Documents' },
  // §7: media METADATA syncs, blobs do not. A row whose bytes live on another
  // device is a real record with its content elsewhere — said plainly, rather
  // than shown as a broken image.
  'media.elsewhere': { ar: 'الصورة على جهاز آخر', en: 'Photo is on another device' },
  // Shown ONCE, after the first sync on a device that had local data. Two
  // devices that never synced generated different ids for the same physical
  // bird, so both records now exist. Only the fancier can say whether two
  // records are one bird — so they are told, and the tool is already there.
  // ── §10 sync status. Five states, and offline is deliberately NOT one of the
  // alarming ones: it is the normal condition this product was built for.
  'sync.synced':   { ar: 'متزامن', en: 'Synced' },
  'sync.syncing':  { ar: 'جارٍ المزامنة…', en: 'Syncing…' },
  'sync.pending':  { ar: '{n} تغييرًا بانتظار المزامنة', en: '{n} change(s) waiting to sync' },
  'sync.offline':  { ar: 'دون اتصال — يعمل محليًا', en: 'Offline — working locally' },
  'sync.error':    { ar: 'تعذّرت المزامنة', en: 'Sync failed' },
  'sync.off':      { ar: 'المزامنة متوقفة', en: 'Sync is off' },
  'sync.details':  { ar: 'التفاصيل', en: 'Details' },

  // الأدوات card
  'sync.card':       { ar: 'المزامنة', en: 'Sync' },
  'sync.account':    { ar: 'الحساب', en: 'Account' },
  'sync.lastSync':   { ar: 'آخر مزامنة', en: 'Last sync' },
  'sync.never':      { ar: 'لم تتم بعد', en: 'Not yet' },
  'sync.pendingN':   { ar: 'بانتظار المزامنة', en: 'Waiting to sync' },
  'sync.now':        { ar: 'مزامنة الآن', en: 'Sync now' },
  'sync.toggleOn':   { ar: 'تشغيل المزامنة', en: 'Turn sync on' },
  'sync.toggleOff':  { ar: 'إيقاف المزامنة', en: 'Turn sync off' },
  'sync.lastError':  { ar: 'آخر خطأ', en: 'Last error' },
  'sync.signedOut':  { ar: 'غير مسجّل الدخول', en: 'Not signed in' },
  'sync.notSetUp':   { ar: 'المزامنة غير مهيأة على هذا الجهاز', en: 'Sync is not set up on this device' },
  'sync.anomalies':  { ar: 'سجلات لم يقبلها الخادم: {n}', en: 'Records the server refused: {n}' },

  // the two things that interrupt, and nothing else
  'sync.err.session':  { ar: 'انتهت الجلسة — سجّل الدخول من جديد', en: 'Session expired — please sign in again' },
  'sync.err.rejected': { ar: 'رفض الخادم المزامنة — تحقق من الأدوات', en: 'The server refused the sync — see Tools' },
  'sync.err.short':    { ar: 'لم تُقبل بعض السجلات — تحقق من الأدوات', en: 'Some records were not accepted — see Tools' },
  'sync.err.network':  { ar: 'تعذّر الاتصال — سنحاول تلقائيًا', en: 'Could not connect — we will retry automatically' },
  'sync.err.config':   { ar: 'المزامنة غير مهيأة', en: 'Sync is not configured' },

  'sync.duplicates': {
    ar: 'تمت المزامنة. وُجدت {n} حلقة مكررة — راجعها.',
    en: 'Sync complete. Found {n} duplicate ring(s) — please review.',
  },
  'media.elsewhereFile': { ar: 'الملف على جهاز آخر', en: 'File is on another device' },
  'bird.addNote': { ar: 'إضافة ملاحظة', en: 'Add note' },
  'bird.addPhoto': { ar: 'إضافة صورة', en: 'Add photo' },
  'bird.addDocument': { ar: 'إضافة وثيقة', en: 'Add document' },
  'bird.age': { ar: 'العمر', en: 'Age' },
  'bird.ageYears': { ar: '{n} سنة', en: '{n} yr' },
  'bird.noBirds': { ar: 'لا توجد طيور بعد. أضف أول طير أو استورد بياناتك.', en: 'No birds yet. Add your first bird or import your data.' },
  'bird.chooseBird': { ar: 'اختر طيرًا…', en: 'Choose a bird…' },
  'bird.clearParent': { ar: 'إزالة', en: 'Clear' },
  'bird.progeny': { ar: 'النسل', en: 'Progeny' },
  'bird.addSibling': { ar: 'إضافة شقيق/شقيقة', en: 'Add sibling' },
  'bird.siblingHint': { ar: 'الأشقاء يُسجَّلون بإعطائهم نفس الأب والأم — لا يوجد ربط مباشر بين الأشقاء، فالقرابة تُشتق من الأبوين.', en: 'Siblings are recorded by giving them the same sire and dam — there is no direct sibling link; kinship derives from the parents.' },
  'bird.siblingNoParents': { ar: 'هذا الطير بلا أبوين مسجلين. لتسجيل شقيق، سيُنشئ زاجل سجلّين للأبوين «غير معروفين» ويربطهما بالطيرين معًا — يمكنك تعبئة بياناتهما لاحقًا.', en: 'This bird has no recorded parents. To record a sibling, Zajil will create two placeholder “unknown” parent records and link them to both birds — you can fill in their details later.' },
  'bird.siblingOfNotice': { ar: 'سيُسجَّل هذا الطير شقيقًا لـ «{name}». عند الحفظ سيُنشأ أبوان «غير معروفان» ويُربطان بالطيرين معًا — ولن يُكتب شيء إن ألغيت.', en: 'This bird will be recorded as a sibling of “{name}”. On save, two “unknown” parents are created and linked to both birds — nothing is written if you cancel.' },
  'bird.createPlaceholders': { ar: 'إنشاء الأبوين والمتابعة', en: 'Create parents & continue' },
  'bird.unknownSire': { ar: 'أب غير معروف', en: 'Unknown sire' },
  'bird.unknownDam': { ar: 'أم غير معروفة', en: 'Unknown dam' },
  'bird.loadExample': { ar: 'تحميل بيانات تجريبية للتعلّم', en: 'Load example data to explore' },
  'bird.exampleSmall': { ar: 'مثال صغير — ٢٠ طيرًا', en: 'Small example — 20 birds' },
  'bird.exampleLarge': { ar: 'لوفت تعليمي كامل — ٣٨ طيرًا، ٦ أجيال', en: 'Full teaching loft — 38 birds, 6 generations' },
  'bird.exampleHint': { ar: 'بيانات للتعلّم فقط. تُدمج مع بياناتك دون حذف شيء — ولإزالتها لاحقًا استورد ملفك مع «استبدال كامل».', en: 'Learning data only. It merges alongside your own records without deleting anything — to remove it later, import your own file with “Replace everything”.' },
  'bird.exampleLoaded': { ar: 'حُمّلت البيانات التجريبية — تصفح لوفت الزرقاء: {n} طيرًا عبر خمسة أجيال. احذفها لاحقًا من الأدوات (استبدال كامل بملفك).', en: 'Example data loaded — explore the Zarqa loft: {n} birds across five generations. Remove later via Tools (replace-import your own file).' },
  'bird.raceRecord': { ar: 'سجل السباقات', en: 'Race record' },
  'bird.healthLog': { ar: 'السجل الصحي', en: 'Health log' },

  'photo.body': { ar: 'الجسم', en: 'Body' },
  'photo.eye': { ar: 'العين', en: 'Eye' },
  'photo.wing': { ar: 'الجناح', en: 'Wing' },
  'photo.other': { ar: 'أخرى', en: 'Other' },

  // ---- statuses (defaults; loft can customise)
  'status.breeder': { ar: 'تربية', en: 'Breeder' },
  'status.race team': { ar: 'فريق السباق', en: 'Race team' },
  'status.young bird': { ar: 'فرخ', en: 'Young bird' },
  'status.stock': { ar: 'احتياط', en: 'Stock' },
  'status.sold': { ar: 'مباع', en: 'Sold' },
  'status.lost': { ar: 'مفقود', en: 'Lost' },
  'status.dead': { ar: 'نافق', en: 'Dead' },
  'status.reference': { ar: 'مرجع نسب', en: 'Pedigree reference' },

  // ---- ring types
  'ringType.national': { ar: 'اتحاد وطني', en: 'National' },
  'ringType.FCI': { ar: 'FCI دولي', en: 'FCI' },
  'ringType.club': { ar: 'نادي', en: 'Club' },
  'ringType.private': { ar: 'خاص', en: 'Private' },

  // ---- race types
  'raceType.training': { ar: 'تدريب', en: 'Training' },
  'raceType.club': { ar: 'نادي', en: 'Club' },
  'raceType.federation': { ar: 'اتحاد', en: 'Federation' },
  'raceType.national': { ar: 'وطني', en: 'National' },
  'raceType.one-loft': { ar: 'لوفت واحد', en: 'One-loft' },
  'raceType.international': { ar: 'دولي', en: 'International' },

  // ---- pedigree / genetics
  'ped.title': { ar: 'شجرة النسب', en: 'Pedigree' },
  'ped.generations': { ar: 'الأجيال', en: 'Generations' },
  'ped.coi': { ar: 'معامل التربية الداخلية (COI)', en: 'Inbreeding coefficient (COI)' },
  'ped.coiAtN': { ar: 'معامل التربية الداخلية حتى {n} أجيال', en: 'Pedigree COI at {n} generations' },
  'ped.coiCaveat': {
    ar: 'هذه نسبة محسوبة من شجرة النسب المسجلة، وليست فحصًا جينيًا. الشجرة الناقصة تُظهر نسبة أقل من الحقيقة.',
    en: 'This is a statistic computed from the recorded pedigree, not a genetic test. A shallow or incomplete pedigree understates it.',
  },
  'ped.breakdown': { ar: 'تفصيل المساهمات', en: 'Contribution breakdown' },
  'ped.commonAncestor': { ar: 'السلف المشترك', en: 'Common ancestor' },
  'ped.contribution': { ar: 'المساهمة', en: 'Contribution' },
  'ped.pathPairs': { ar: 'عدد المسارات', en: 'Path pairs' },
  'ped.ancestorF': { ar: 'تربية داخلية للسلف', en: 'Ancestor’s own F' },
  'ped.noCommonAncestors': { ar: 'لا أسلاف مشتركة ضمن العمق المحدد.', en: 'No common ancestors within the chosen depth.' },
  'ped.avk': { ar: 'معامل فقدان الأسلاف (AVK)', en: 'Ancestor loss (AVK)' },
  'ped.avkHint': {
    ar: 'نسبة الأسلاف المميزين إلى خانات الشجرة المعروفة. قد يكون COI منخفضًا بينما التنوع ضيق — AVK يكشف ذلك.',
    en: 'Distinct ancestors as a share of known pedigree slots. COI can read low while the gene pool is already narrow — AVK catches it.',
  },
  'ped.completeness': { ar: 'اكتمال الشجرة', en: 'Pedigree completeness' },
  'ped.subject': { ar: 'الطير', en: 'Subject' },
  'ped.unknownAncestor': { ar: 'غير معروف', en: 'Unknown' },
  'ped.breakdownTruncated': { ar: 'الشجرة كثيفة جدًا؛ عُرض تفصيل جزئي والنتيجة الكلية دقيقة.', en: 'Pedigree too dense; breakdown shown partially — the total remains exact.' },

  // ---- relationships
  'rel.title': { ar: 'صلة القرابة', en: 'Relationship' },
  'rel.finder': { ar: 'فاحص القرابة', en: 'Relationship finder' },
  'rel.sameBird': { ar: 'نفس الطير', en: 'Same bird' },
  'rel.unrelated': { ar: 'لا قرابة ضمن العمق المحدد', en: 'Unrelated within the chosen depth' },
  'rel.related': { ar: 'قرابة بعيدة', en: 'Distantly related' },
  'rel.unknown': { ar: 'غير معروف', en: 'Unknown' },
  'rel.fullSiblings': { ar: 'أشقاء (نفس الأب والأم)', en: 'Full siblings' },
  'rel.halfSiblings': { ar: 'إخوة من طرف واحد', en: 'Half siblings' },
  'rel.avuncular': { ar: 'عم/عمة أو خال/خالة مع ابن/بنت الأخ', en: 'Uncle/aunt ↔ nephew/niece' },
  'rel.firstCousins': { ar: 'أولاد عم/خال (درجة أولى)', en: 'First cousins' },
  'rel.firstCousinsOnceRemoved': { ar: 'أولاد عم مع فارق جيل', en: 'First cousins once removed' },
  'rel.secondCousins': { ar: 'أولاد عم (درجة ثانية)', en: 'Second cousins' },
  'rel.commonAncestors': { ar: 'قرابة عبر {n} سلف مشترك', en: 'Related via {n} common ancestors' },
  'rel.ancestor.parent': { ar: 'الطير الثاني هو أحد الوالدين', en: 'The second bird is a parent' },
  'rel.ancestor.grandparent': { ar: 'الطير الثاني جدّ/جدّة', en: 'The second bird is a grandparent' },
  'rel.ancestor.great': { ar: 'الطير الثاني سلف بدرجة {n} فوق الجدّ', en: 'The second bird is a great({n})-grandparent' },
  'rel.descendant.offspring': { ar: 'الطير الثاني من الأبناء', en: 'The second bird is an offspring' },
  'rel.descendant.grandchild': { ar: 'الطير الثاني حفيد', en: 'The second bird is a grandchild' },
  'rel.descendant.great': { ar: 'الطير الثاني من الأحفاد بدرجة {n}', en: 'The second bird is a great({n})-grandchild' },
  'rel.hypCOI': { ar: 'COI المتوقع لنسل هذا التزاوج', en: 'Hypothetical COI of this pairing' },
  'rel.warn.severe': { ar: 'تحذير شديد: تزاوج أقارب من الدرجة الأولى ({coi}). راجع القرار قبل المتابعة.', en: 'Severe: first-degree inbreeding ({coi}). Review before proceeding.' },
  'rel.warn.high': { ar: 'تحذير: نسبة قرابة مرتفعة ({coi}).', en: 'Warning: high inbreeding ({coi}).' },
  'rel.warn.moderate': { ar: 'تنبيه: نسبة قرابة متوسطة ({coi}).', en: 'Note: moderate inbreeding ({coi}).' },
  'rel.warn.info': { ar: 'قرابة منخفضة ({coi}).', en: 'Low inbreeding ({coi}).' },
  'rel.warn.none': { ar: 'لا قرابة مسجلة بين الزوجين.', en: 'No recorded relationship between the pair.' },

  // ---- validation
  'val.selfParent': { ar: 'لا يمكن أن يكون الطير والدًا لنفسه.', en: 'A bird cannot be its own parent.' },
  'val.cycle': { ar: 'هذا الربط يخلق حلقة نسب مغلقة عبر: {path}. عدّل السلسلة أولًا.', en: 'This link creates a pedigree loop via: {path}. Fix that chain first.' },
  'val.sireIsHen': { ar: 'الأب المحدد مسجل كأنثى.', en: 'The selected sire is recorded as a hen.' },
  'val.damIsCock': { ar: 'الأم المحددة مسجلة كذكر.', en: 'The selected dam is recorded as a cock.' },
  'val.sameSireDam': { ar: 'الأب والأم لا يمكن أن يكونا نفس الطير.', en: 'Sire and dam cannot be the same bird.' },
  'val.parentYounger': { ar: 'تاريخ فقس {role} بعد تاريخ فقس الطير نفسه.', en: 'The {role} hatched after this bird.' },
  'val.parentSameDay': { ar: 'الوالد والطير لهما نفس تاريخ الفقس — تحقق من التواريخ.', en: 'Parent and bird share the same hatch date — check the dates.' },
  'val.dupRing': { ar: 'رقم الحلقة {ring} مستخدم لطير آخر ({otherName}).', en: 'Ring {ring} is already used by another bird ({otherName}).' },
  'val.dupRingSameBird': { ar: 'الحلقة {ring} مكررة على نفس الطير.', en: 'Ring {ring} is listed twice on this bird.' },
  'val.pairSireIsHen': { ar: 'ذكر الزوج مسجل كأنثى.', en: 'The pair’s cock is recorded as a hen.' },
  'val.pairDamIsCock': { ar: 'أنثى الزوج مسجلة كذكر.', en: 'The pair’s hen is recorded as a cock.' },
  'val.pairSameBird': { ar: 'لا يمكن تزويج الطير مع نفسه.', en: 'A bird cannot be paired with itself.' },
  'integrity.birdParent': { ar: 'الطير {birdId}: رابط {role} يشير إلى سجل غير موجود ({missingId}).', en: 'Bird {birdId}: {role} points at a record that does not exist ({missingId}).' },
  'integrity.pairParent': { ar: 'الزوج {pairId}: {role} يشير إلى سجل غير موجود ({missingId}).', en: 'Pair {pairId}: {role} points at a record that does not exist ({missingId}).' },
  'integrity.eggChick': { ar: 'البيضة {eggId} في الزوج {pairId} مرتبطة بفرخ غير موجود ({missingId}).', en: 'Egg {eggId} in pair {pairId} is linked to a chick that does not exist ({missingId}).' },
  'integrity.raceBird': { ar: 'نتيجة السباق {resultId} تخصّ طيرًا غير موجود ({missingId}).', en: 'Race result {resultId} belongs to a bird that does not exist ({missingId}).' },
  'integrity.healthBird': { ar: 'الحدث الصحي {eventId} يخصّ طيرًا غير موجود ({missingId}).', en: 'Health event {eventId} belongs to a bird that does not exist ({missingId}).' },
  'integrity.liveWithTombstone': { ar: 'السجل {recordId} في «{store}» موجود ومحذوف في آن واحد — حذف لم يكتمل أو سجل عاد بالخطأ.', en: 'Record {recordId} in “{store}” exists AND is marked deleted — a half-completed deletion, or a record that came back when it should not have.' },
  'integrity.title': { ar: 'فحص ترابط البيانات', en: 'Data integrity check' },
  'integrity.clean': { ar: 'لا مراجع معلّقة. ✓', en: 'No dangling references. ✓' },
  'integrity.found': { ar: 'وُجدت {n} مرجعًا معلّقًا.', en: '{n} dangling reference(s) found.' },
  'val.fixErrors': { ar: 'لا يمكن الحفظ — صحّح الأخطاء أولًا:', en: 'Cannot save — fix these errors first:' },
  'val.warningsTitle': { ar: 'تحذيرات — راجع قبل الحفظ:', en: 'Warnings — review before saving:' },

  // ---- FCI
  'fci.title': { ar: 'فاحص أهلية FCI', en: 'FCI eligibility checker' },
  'fci.hasRing': { ar: 'يحمل حلقة FCI', en: 'Carries an FCI ring' },
  'fci.noRing': { ar: 'لا يحمل حلقة FCI', en: 'No FCI ring' },
  'fci.qualifying': { ar: 'نتائج مؤهلة', en: 'Qualifying results' },
  'fci.nonQualifying': { ar: 'نتائج غير مؤهلة', en: 'Non-qualifying results' },
  'fci.rule': { ar: 'الحد الأدنى للتأهيل: {f} مربّيًا و{b} طيرًا في السباق، وحلقة FCI على الطير.', en: 'Qualifying minimum: {f} fanciers and {b} pigeons entered, and an FCI ring on the bird.' },
  'fci.tooFewFanciers': { ar: 'أقل من 20 مربّيًا', en: 'Fewer than 20 fanciers' },
  'fci.tooFewBirds': { ar: 'أقل من 150 طيرًا', en: 'Fewer than 150 pigeons' },
  'fci.trainingNotEligible': { ar: 'التدريب غير مؤهل', en: 'Training flights not eligible' },
  'fci.noResult': { ar: 'لا نتيجة', en: 'No result' },
  'fci.eligibleBirds': { ar: 'طيور مؤهلة', en: 'Eligible birds' },

  // ---- breeding
  'br.title': { ar: 'إدارة موسم التربية', en: 'Breeding season' },
  'br.pair': { ar: 'زوج', en: 'Pair' },
  'br.newPair': { ar: 'زوج جديد', en: 'New pair' },
  'br.season': { ar: 'الموسم', en: 'Season' },
  'br.nestBox': { ar: 'العش', en: 'Nest box' },
  'br.round': { ar: 'البطن', en: 'Round' },
  'br.addRound': { ar: 'بطن جديد', en: 'New round' },
  'br.eggs': { ar: 'البيض', en: 'Eggs' },
  'br.addEgg': { ar: 'إضافة بيضة', en: 'Add egg' },
  'br.laidDate': { ar: 'تاريخ الوضع', en: 'Laid' },
  'br.egg.laid': { ar: 'بيضة', en: 'Egg' },
  'br.egg.hatched': { ar: 'فقست', en: 'Hatched' },
  'br.egg.failed': { ar: 'لم تفقس', en: 'Failed' },
  'br.hatch': { ar: 'فقس', en: 'Hatch' },
  'br.markHatched': { ar: 'تسجيل الفقس', en: 'Mark hatched' },
  'br.markFailed': { ar: 'لم تفقس', en: 'Mark failed' },
  'br.ringChick': { ar: 'تركيب الحلقة', en: 'Ring chick' },
  'br.wean': { ar: 'فطام', en: 'Wean' },
  'br.weaned': { ar: 'مفطوم', en: 'Weaned' },
  'br.chick': { ar: 'فرخ', en: 'Chick' },
  'br.chickCreated': { ar: 'أُنشئ سجل الفرخ وربُط بالأبوين تلقائيًا.', en: 'Chick record created and auto-linked to its parents.' },
  'br.active': { ar: 'نشط', en: 'Active' },
  'br.separated': { ar: 'مفصول', en: 'Separated' },
  'br.pairCOIWarning': { ar: 'تنبيه قرابة عند إنشاء الزوج', en: 'Pairing relationship check' },
  'br.noPairs': { ar: 'لا أزواج في هذا الموسم بعد.', en: 'No pairs this season yet.' },
  'br.offspringOf': { ar: 'نسل هذا الزوج', en: 'Offspring of this pair' },
  'br.startDate': { ar: 'تاريخ التزويج', en: 'Pairing date' },
  'br.acquiredFrom': { ar: 'مصدر الزوج (إن كان مشترى)', en: 'Acquired from (if bought)' },
  'br.acquiredDate': { ar: 'تاريخ الشراء', en: 'Acquired on' },
  'br.boughtHint': { ar: 'اشتريت زوجًا مع بيض أو فراخ؟ سجّل الزوج، ثم أضف البيض وصحّح تواريخه — أو اربط فرخًا مسجَّلًا مسبقًا بالبيضة.', en: 'Bought a pair with eggs or chicks? Record the pair, add the eggs and correct their dates — or link an already-recorded chick to an egg.' },
  'br.bought': { ar: 'مشترى', en: 'Bought' },
  'br.linkExisting': { ar: 'ربط طير مسجَّل', en: 'Link an existing bird' },
  'br.linkExistingHint': { ar: 'اختر طيرًا مسجَّلًا بالفعل ليصبح فرخ هذه البيضة. سيُضبط أبواه على هذا الزوج.', en: 'Choose a bird already in your records as this egg’s chick. Its parents will be set to this pair.' },
  'br.linked': { ar: 'تم الربط — وضُبط الأبوان على هذا الزوج.', en: 'Linked — parents set to this pair.' },
  'br.unlink': { ar: 'إلغاء الربط', en: 'Unlink' },
  'br.linkBlocked': { ar: 'لا يمكن الربط: {reason}', en: 'Cannot link: {reason}' },

  // ---- races
  'race.title': { ar: 'سجل السباقات والتدريب', en: 'Race & training log' },
  'race.new': { ar: 'نتيجة جديدة', en: 'New result' },
  'race.name': { ar: 'اسم السباق', en: 'Race name' },
  'race.type': { ar: 'نوع السباق', en: 'Race type' },
  'race.org': { ar: 'الجهة المنظمة', en: 'Organisation' },
  'race.country': { ar: 'الدولة', en: 'Country' },
  'race.releasePoint': { ar: 'نقطة الإطلاق', en: 'Release point' },
  'race.releaseTime': { ar: 'وقت الإطلاق', en: 'Release time' },
  'race.arrivalTime': { ar: 'وقت الوصول', en: 'Arrival time' },
  'race.distance': { ar: 'المسافة', en: 'Distance' },
  'race.velocity': { ar: 'السرعة', en: 'Velocity' },
  'race.mpm': { ar: 'م/د', en: 'm/min' },
  'race.km': { ar: 'كم', en: 'km' },
  'race.position': { ar: 'المركز', en: 'Position' },
  'race.fanciers': { ar: 'عدد المربّين', en: 'Fanciers entered' },
  'race.birdsEntered': { ar: 'عدد الطيور', en: 'Birds entered' },
  'race.coords': { ar: 'الإحداثيات (خط العرض، خط الطول)', en: 'Coordinates (lat, lon)' },
  'race.loftCoords': { ar: 'إحداثيات اللوفت', en: 'Loft coordinates' },
  'race.calcVelocity': { ar: 'حساب السرعة من الإحداثيات', en: 'Compute velocity from GPS' },
  'race.noRaces': { ar: 'لا نتائج مسجلة.', en: 'No results recorded.' },
  'race.bird': { ar: 'الطير', en: 'Bird' },

  // ---- progeny analysis
  'prog.title': { ar: 'تحليل النسل', en: 'Progeny analysis' },
  'prog.offspringCount': { ar: 'عدد الأبناء المباشرين', en: 'Direct offspring' },
  'prog.descendants': { ar: 'إجمالي النسل', en: 'Total descendants' },
  'prog.raced': { ar: 'خاض سباقات', en: 'Raced' },
  'prog.totalResults': { ar: 'مجموع النتائج', en: 'Combined results' },
  'prog.bestPerformers': { ar: 'أفضل النسل أداءً', en: 'Best performers' },
  'prog.wins': { ar: 'مراكز أولى', en: 'Wins' },
  'prog.top10': { ar: 'ضمن العشرة الأوائل', en: 'Top-10 finishes' },
  'prog.avgVelocity': { ar: 'متوسط السرعة', en: 'Average velocity' },
  'prog.noProgeny': { ar: 'لا نسل مسجل لهذا الطير.', en: 'No recorded progeny for this bird.' },

  // ---- health
  'health.title': { ar: 'السجل الصحي والعلاجات', en: 'Health & treatment log' },
  'health.new': { ar: 'حدث جديد', en: 'New event' },
  'health.type': { ar: 'النوع', en: 'Type' },
  'health.vaccination': { ar: 'تطعيم', en: 'Vaccination' },
  'health.treatment': { ar: 'علاج', en: 'Treatment' },
  'health.illness': { ar: 'مرض', en: 'Illness' },
  'health.check': { ar: 'فحص', en: 'Check-up' },
  'health.medication': { ar: 'الدواء/اللقاح', en: 'Medication/vaccine' },
  'health.wholeLoft': { ar: 'اللوفت كامل', en: 'Whole loft' },
  'health.scope': { ar: 'النطاق', en: 'Scope' },
  'health.singleBird': { ar: 'طير واحد', en: 'Single bird' },
  'health.noEvents': { ar: 'لا أحداث صحية مسجلة.', en: 'No health events recorded.' },

  // ---- stats
  'stats.title': { ar: 'إحصائيات اللوفت', en: 'Loft statistics' },
  'stats.totalBirds': { ar: 'عدد الطيور', en: 'Total birds' },
  'stats.bySex': { ar: 'حسب الجنس', en: 'By sex' },
  'stats.byStatus': { ar: 'حسب الحالة', en: 'By status' },
  'stats.byStrain': { ar: 'حسب السلالة', en: 'By strain' },
  'stats.coiDistribution': { ar: 'توزيع معامل التربية الداخلية', en: 'COI distribution' },
  'stats.coiBand.zero': { ar: 'صفر', en: 'Zero' },
  'stats.avgCOI': { ar: 'متوسط COI', en: 'Average COI' },
  'stats.maxCOI': { ar: 'أعلى COI', en: 'Highest COI' },
  'stats.birdsWithFCI': { ar: 'طيور بحلقة FCI', en: 'Birds with FCI ring' },

  // ---- tools / settings
  'tools.title': { ar: 'الأدوات والإعدادات', en: 'Tools & settings' },
  'set.language': { ar: 'اللغة', en: 'Language' },
  'set.numerals': { ar: 'الأرقام', en: 'Numerals' },
  'set.numerals.western': { ar: 'غربية (0123456789)', en: 'Western (0123456789)' },
  'set.numerals.eastern': { ar: 'مشرقية (٠١٢٣٤٥٦٧٨٩)', en: 'Eastern Arabic (٠١٢٣٤٥٦٧٨٩)' },
  'set.numeralsHint': { ar: 'أرقام الحلقات تُعرض دائمًا بالأرقام الغربية.', en: 'Ring numbers always render in Western digits.' },
  'set.dates': { ar: 'عرض التاريخ', en: 'Date display' },
  'set.dates.gregorian': { ar: 'ميلادي', en: 'Gregorian' },
  'set.dates.hijri': { ar: 'هجري', en: 'Hijri' },
  'set.dates.both': { ar: 'ميلادي + هجري', en: 'Gregorian + Hijri' },
  'set.highContrast': { ar: 'وضع التباين العالي (ضوء الشمس)', en: 'High contrast (sunlight) mode' },
  'set.loft': { ar: 'اللوفت', en: 'Loft' },
  'set.loftName': { ar: 'اسم اللوفت', en: 'Loft name' },
  'set.loftLocation': { ar: 'الموقع', en: 'Location' },
  'set.coiDepth': { ar: 'عمق حساب COI (أجيال)', en: 'COI depth (generations)' },
  'backup.title': { ar: 'النسخ الاحتياطي والتصدير', en: 'Backup & export' },
  'backup.exportAll': { ar: 'تصدير كل البيانات (JSON)', en: 'Export everything (JSON)' },
  'backup.import': { ar: 'استيراد ملف JSON', en: 'Import JSON file' },
  'backup.importMode.merge': { ar: 'دمج (الأحدث يبقى)', en: 'Merge (newest wins)' },
  'backup.importMode.replace': { ar: 'استبدال كامل', en: 'Replace everything' },
  'backup.lastExport': { ar: 'آخر تصدير: {d}', en: 'Last export: {d}' },
  'backup.never': { ar: 'لم يتم التصدير بعد', en: 'Never exported' },
  'backup.warn30': { ar: 'مرّ أكثر من ٣٠ يومًا على آخر تصدير. صدّر نسخة الآن.', en: 'More than 30 days since your last export. Export a copy now.' },
  'backup.auto': { ar: 'نسخ تلقائي داخلي كل {h} ساعة (آخر {n} نسخ)', en: 'Automatic internal snapshot every {h}h (last {n} kept)' },
  'backup.restoreAuto': { ar: 'استرجاع نسخة تلقائية', en: 'Restore an automatic snapshot' },
  'backup.confirmSnapshot': { ar: 'سيُستبدل السجلّ بمحتوى النسخة المحفوظة بتاريخ {d}. الصور والوثائق تبقى كما هي. متابعة؟', en: 'Records will be replaced with the snapshot from {d}. Photos and documents are kept as they are. Continue?' },
  'backup.imported': { ar: 'تم الاستيراد: {birds} طير، {pairs} زوج، {races} نتيجة.', en: 'Imported: {birds} birds, {pairs} pairs, {races} results.' },
  'share.title': { ar: 'مشاركة طير', en: 'Share a bird' },
  'share.hint': { ar: 'يصدّر الطير مع كامل نسبه كملف يستورده أي مستخدم زاجل — دون حساب.', en: 'Exports the bird with its full ancestry as a file any Zajil user can import — no account needed.' },
  'share.includeRaces': { ar: 'تضمين نتائج السباقات', en: 'Include race results' },
  'share.includeMedia': { ar: 'تضمين الصور والوثائق', en: 'Include photos & documents' },
  'about.title': { ar: 'حول التطبيق', en: 'About' },
  'about.version': { ar: 'الإصدار {v}', en: 'Version {v}' },
  'about.unknown': { ar: 'غير معروف', en: 'Unknown' },
  'about.hint': { ar: 'الإصدار المثبَّت فعليًا على هذا الجهاز، كما يبلّغ عنه عامل الخدمة. يظهر «غير معروف» عند التشغيل دون HTTPS، حيث لا يعمل عامل الخدمة.', en: 'The version actually installed on this device, as reported by the service worker. Shows “Unknown” when running without HTTPS, where the service worker does not run.' },
  'dev.title': { ar: 'لوحة المطوّر — فحوصات المحرّك', en: 'Dev panel — engine tests' },
  'dev.run': { ar: 'تشغيل الفحوصات', en: 'Run tests' },
  'dev.passed': { ar: '{p} نجح، {f} فشل', en: '{p} passed, {f} failed' },
  'dev.roundtrip': { ar: 'فحص التصدير والاستيراد (ذهاب وإياب)', en: 'Export/import round-trip test' },
  'dev.roundtripOK': { ar: 'نجح فحص الذهاب والإياب — البيانات متطابقة.', en: 'Round-trip passed — data identical.' },
  'dev.roundtripFail': { ar: 'فشل فحص الذهاب والإياب: {msg}', en: 'Round-trip FAILED: {msg}' },
  'scan.title': { ar: 'ماسح شهادات النسب الورقية', en: 'Pedigree document scanner' },
  'scan.hint': { ar: 'ميزة اختيارية تتطلب خادم رؤية حاسوبية (يدعم خط اليد العربي). التطبيق يعمل كاملًا دونها. اضبط عنوان الخادم لتفعيلها.', en: 'Optional feature requiring a server-side vision model (Arabic handwriting capable). The app is fully functional without it. Set a server URL to enable.' },
  'scan.serverUrl': { ar: 'عنوان خادم الرؤية (اختياري)', en: 'Vision server URL (optional)' },
  'scan.notConfigured': { ar: 'غير مفعّل — التطبيق يعمل دون اتصال بشكل كامل.', en: 'Not configured — the app remains fully offline-capable.' },

  // ---- certificates
  'cert.title': { ar: 'شهادة نسب', en: 'Pedigree certificate' },
  'cert.issuedBy': { ar: 'صادرة عن', en: 'Issued by' },
  'cert.date': { ar: 'تاريخ الإصدار', en: 'Issued on' },
  'cert.signature': { ar: 'التوقيع', en: 'Signature' },
  'cert.language': { ar: 'لغة الشهادة', en: 'Certificate language' },

  // ---- confirmations & toasts
  'confirm.deleteBird': { ar: 'حذف الطير «{name}»؟ سيُفصل عن أبنائه وتُحذف صوره.', en: 'Delete “{name}”? It will be detached from its offspring and its media removed.' },
  'confirm.deleteGeneric': { ar: 'تأكيد الحذف؟', en: 'Delete this record?' },
  'confirm.replaceAll': { ar: 'سيُستبدل كل شيء في قاعدة البيانات بمحتوى الملف. متابعة؟', en: 'Everything in the database will be replaced by the file contents. Continue?' },
  'toast.saved': { ar: 'تم الحفظ', en: 'Saved' },
  'toast.saveFailed': { ar: 'تعذّر الحفظ — راجع البيانات', en: 'Could not save — check the record' },
  'toast.deleted': { ar: 'تم الحذف', en: 'Deleted' },
  'toast.undone': { ar: 'تم التراجع', en: 'Undone' },
  'toast.exported': { ar: 'تم التصدير', en: 'Exported' },
  'toast.copied': { ar: 'تم النسخ', en: 'Copied' },
  'toast.installed': { ar: 'التطبيق جاهز للعمل دون اتصال', en: 'App ready for offline use' },
  'toast.updated': { ar: 'يتوفر تحديث — أعد فتح التطبيق', en: 'Update available — reopen the app' },
};

// ------------------------------------------------------------------ state

let lang = 'ar';
let numerals = 'western'; // 'western' | 'eastern'
let dateMode = 'both';    // 'gregorian' | 'hijri' | 'both'

export function getLang() { return lang; }
export function isRTL() { return lang === 'ar'; }

export function configure({ lang: l, numerals: n, dates: d } = {}) {
  if (l && LANGS.includes(l)) lang = l;
  if (n) numerals = n;
  if (d) dateMode = d;
  if (typeof document !== 'undefined') {
    document.documentElement.lang = lang;
    document.documentElement.dir = isRTL() ? 'rtl' : 'ltr';
  }
}

/** Translate. Missing keys return the key itself (visible in dev, harmless). */
export function t(key, params = {}) {
  const entry = dict[key];
  let s = entry ? (entry[lang] ?? entry.en) : key;
  for (const [k, v] of Object.entries(params)) {
    s = s.split('{' + k + '}').join(typeof v === 'number' ? fmtNum(v) : String(v ?? ''));
  }
  return s;
}

// ------------------------------------------------------------------ numerals

const EASTERN = '٠١٢٣٤٥٦٧٨٩';

/** Format a number in the user's preferred numeral system. */
export function fmtNum(n, opts = {}) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  let s = typeof n === 'number'
    ? n.toLocaleString('en-US', { maximumFractionDigits: opts.dp ?? 2, minimumFractionDigits: opts.dp !== undefined && opts.fixed ? opts.dp : 0, useGrouping: opts.group !== false })
    : String(n);
  if (numerals === 'eastern' && !opts.forceWestern) {
    s = s.replace(/\d/g, (d) => EASTERN[+d]).replace(/,/g, '٬').replace(/\./g, '٫');
  }
  return s;
}

export function fmtPercent(x, dp = 2) {
  if (x === null || x === undefined || Number.isNaN(x)) return '—';
  return fmtNum(x * 100, { dp, fixed: true }) + (numerals === 'eastern' ? '٪' : '%');
}

// --------------------------------------------------------------------- dates

/** Gregorian display in the active locale. Storage is always ISO Gregorian. */
function fmtGregorian(iso, withTime) {
  // parseLocalDate keeps a bare "YYYY-MM-DD" on its own calendar day; using
  // `new Date(iso)` would parse it as UTC midnight and render a day early
  // west of Greenwich.
  const d = parseLocalDate(iso);
  if (isNaN(d)) return iso || '—';
  const opts = withTime
    ? { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }
    : { year: 'numeric', month: 'short', day: 'numeric' };
  const locale = (lang === 'ar' ? 'ar-JO' : 'en-GB') + (numerals === 'eastern' ? '-u-nu-arab' : '-u-nu-latn');
  return d.toLocaleDateString(locale, opts);
}

function fmtHijri(iso) {
  const d = parseLocalDate(iso);
  if (isNaN(d)) return '';
  try {
    const locale = (lang === 'ar' ? 'ar-SA' : 'en') +
      '-u-ca-islamic-umalqura-nu-' + (numerals === 'eastern' ? 'arab' : 'latn');
    return d.toLocaleDateString(locale, { year: 'numeric', month: 'long', day: 'numeric' });
  } catch { return ''; }
}

/** Date for display per the user's date-mode preference. */
export function fmtDate(iso, { withTime = false } = {}) {
  if (!iso) return '—';
  const g = fmtGregorian(iso, withTime);
  if (dateMode === 'gregorian') return g;
  const h = fmtHijri(iso);
  if (!h) return g;
  if (dateMode === 'hijri') return h;
  return `${g} (${h})`;
}

// ----------------------------------------------------------------------- bidi

/**
 * HTML for a ring number inside possibly-Arabic text: Western digits, LTR
 * isolated so mixed strings never scramble.
 */
export function ringHTML(raw) {
  return `<bdi dir="ltr" class="ring">${escapeHTML(String(raw || ''))}</bdi>`;
}

/** Wrap free text so mixed-direction content isolates correctly. */
export function bidiHTML(text) {
  return `<bdi>${escapeHTML(String(text || ''))}</bdi>`;
}

export function escapeHTML(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

/** Status label: translate known defaults, otherwise show the custom text. */
export function statusLabel(status) {
  const key = 'status.' + status;
  return dict[key] ? t(key) : status;
}
