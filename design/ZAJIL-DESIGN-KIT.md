# ZAJIL (زاجل) — DESIGN KIT v3
## Part 1: The Brief · Part 2: The Screen Inventory · Part 3: Desktop & Responsive

Give Claude Design TWO files at the start of every session: this file, and
`zajil-prototype.html` (the approved design system as living code — sign-in, loft home,
bird profile). Then name ONE screen from the inventory and design it.

Zajil ships for BOTH phone and desktop from one codebase. Design mobile-first at 430px;
desktop follows Part 3's adaptation rules, except the three screens Part 3 names for
dedicated desktop layouts.

---

# PART 1 — THE BRIEF

Arabic-first, RTL, mobile app (design at 430px width) for pigeon fanciers in Jordan and
the Gulf. The design language is SET and lives in the attached prototype. Your job is to
extend it to more screens, never to reinvent it.

## Direction (fixed)
Bold, flat, modern — the register of current Gulf government apps (TAMM, UAE Pass, the
new Absher): huge heavy Arabic type, oversized numbers, chunky components, generous
whitespace, one confident color. No gradients. No drop shadows. Hierarchy comes from
size, weight, color and 1px borders. Never playful, never startup-generic, never ornate.

## Tokens (fixed — do not restyle)
```
--brand:#128C6E   --brand-deep:#0E6F57   --brand-tint:#E3F4EE
--ink:#101820     --ink-2:#4A5560        --ink-3:#8C97A2
--page:#F5F7F8    --surface:#FFFFFF      --line:#E4E9ED
--gold:#C9971F    --gold-tint:#FBF3DF    --danger:#C43D2B
radius: cards 20px · buttons 16px · row-cards 18px · chips/pills 999px
```

## Type (fixed)
- Family: **Alexandria** (weights 400–900). One family for everything Arabic and Latin.
- Screen titles / bird names: 34–52px, weight 900.
- Card titles: 19px / 800. Body: 15px / 500–600. Labels: 12–13.5px / 700–800.
- Big numbers ARE the design: stats 34px/900 in brand color; a rank can be a bare 44px numeral.
- Ring numbers, dates, speeds: **IBM Plex Mono**, always `direction:ltr`.
- Latin digits for data values; Arabic for all labels and prose.

## Signature components (fixed — reuse from the prototype)
- **The ring plate**: dark ink block, white mono number, small gold season segment.
  Full size on profiles, compact (`plate sm`) in lists.
- **Solid color blocks** for key moments: the verified notice (brand), best result (gold).
- **Pill segmented control**, active state solid ink (black), not brand.
- **Bottom tab bar**: الرئيسية · الطيور · الأنساب · السباقات · المزيد — 26px line icons,
  active in brand color.

## RTL rules (fixed)
Everything right-to-left. Data values (rings, dates, speeds) are LTR islands. Back arrows
point RIGHT. Borders/insets use inline-start. Never mirror numerals.

## Sync & accounts realities (design for them; the machinery exists)
- Sync is INVISIBLE when healthy. A slim status row above content exists only for:
  offline (calm, never error-styled: «دون اتصال — يعمل محليًا»), brief syncing, pending
  count, and rare amber errors. Design all states when a screen includes the row.
- Sign-in is invite-only: NO create-account link, NO social buttons, ever.
- A photo whose file lives on another device shows «الصورة على جهاز آخر» — calm
  information, not a broken state.

## Session rules
- ONE screen per session until approved, then the next.
- Anything that fights the tokens is wrong by definition — the screen changes, not the tokens.
- Realistic Jordanian data always: bird names برق، الصاعقة، غيمة، النشمي، شقراء؛ rings
  like JOR 24 17352 with occasional NL/BE imports; loft «لوفت الفحيص». No lorem ipsum.
- Every approved screen is downloaded as HTML and archived; it becomes the frozen spec
  the engineers implement.

---

# PART 2 — THE SCREEN INVENTORY

The complete surface of the real app. Design ONLY screens from this list. Items marked
⚙ are functional requirements the design must include; nothing here is optional
decoration. Order below = recommended design order.

### Status legend
✅ already designed in the prototype · 🎨 to design

---

## 1. ✅ Sign-in (تسجيل الدخول)
In prototype. States still to design in a future pass: loading on the button; three
distinct error messages (wrong credentials / no connection / app not configured);
signed-out-after-session-expiry variant.

## 2. ✅ Loft home — the bird list (الطيور) · 🖥 desktop layout too (Part 3)
In prototype. Additional states to design later: EMPTY loft (first run — welcoming, with
«أضف أول طائر» and an offer to load a teaching example loft); search-no-results; the
sync status row variants sitting above the list.

## 3. ✅ Bird profile (ملف الطائر)
In prototype (tabs: عام / النسب / السباقات / الصحة). Later states: bird with photo
gallery (multiple photos + the «الصورة على جهاز آخر» placeholder); dead/sold/lost status
styling; a bird with no races yet.

## 4. 🎨 Add / edit bird (إضافة أو تعديل طائر)
⚙ Fields: name (Arabic) · ring number · sex (ذكر/أنثى/غير معروف) · status
(نشط/تربية/فريق السباق/ميت/مباع/مفقود) · color/description · hatch date · sire
(select existing bird or quick-create) · dam (same) · external-to-loft toggle
(reference-only ancestor) · notes · photo add.
⚙ Behaviors to show: duplicate-ring warning (non-blocking, amber); validation errors
inline per field; save + cancel; the same form reused for "add sibling" (parents
pre-filled).
Design note: forms are where bold design usually dies — keep the big-type confidence:
oversized section labels, generous field height (56px+), one column.

## 5. 🎨 Full pedigree tree (شجرة النسب) — 5 generations · 🖥 desktop layout too (Part 3)
⚙ RTL tree, subject on the right, generations flowing left; each node: name + ring
(mono); tap a node → that bird. COI value displayed prominently (brand, big).
⚙ Handle unknown ancestors (empty slots) gracefully.
This is the screen fanciers will screenshot and share — it must look magnificent on a
phone. Horizontal scroll is acceptable; a print/share action belongs here.

## 6. 🎨 Pairs & breeding (الأزواج والتفقيس)
⚙ List of pairs: sire × dam (both tappable), season, status.
⚙ Pair detail: rounds (الأعشاش), eggs per round (laid date, expected/actual hatch),
chicks linked to their bird records; add round / add egg / mark hatched (creates a
chick) / egg failed.
The genealogy engine hangs off this screen — it deserves clarity over density.

## 7. 🎨 Races (السباقات)
⚙ Season view: list of race events (release point, date, distance km); per event the
loft's entered birds with speed (م/د) and rank; best-result highlight (gold block).
⚙ Add race event + add result per bird.

## 8. 🎨 Health (الصحة)
⚙ Loft-wide health timeline (all birds) and per-bird already exists in profile;
⚙ add event: type (تطعيم/علاج/فيتامينات/ملاحظة), date, description, which birds
(one/many/all).

## 9. 🎨 Tools & settings (الأدوات)
The app's utility hub. ⚙ Cards, in order:
- **Loft (اللوفت)**: name, location, season; placeholder «لوفت بلا اسم» when unnamed.
- **Sync (المزامنة)**: signed-out → email + password + «تسجيل الدخول» (the R1 form);
  signed-in → account email, last sync time, «بانتظار المزامنة: N», «مزامنة الآن»,
  «تسجيل الخروج», last-error line when present, sync on/off toggle.
- **Data (البيانات)**: export JSON backup · import (merge/replace choice) · load
  example datasets (سرب تعليمي صغير / لوفت كبير).
- **Checks (الفحوصات)**: duplicate-ring finder · integrity check · sync anomalies
  list (rare; shows isolated records with reasons).
- **About (حول التطبيق)**: version row (الإصدار zajil-v1.9.1).

## 10. 🎨 Home / dashboard (الرئيسية) · 🖥 desktop layout too (Part 3)
The tab exists; today it's minimal. Design the aspiration: season summary (birds,
pairs, active eggs with days-to-hatch, next race), recent activity. Big numbers, calm.

## 11. 🎨 THE PEDIGREE CERTIFICATE (شهادة النسب) — special deliverable
Not an app screen: a DOCUMENT the app generates. Two formats:
- **A4 landscape** (print/PDF) and **a phone-shareable image** (story ratio 9:16).
⚙ Content: Zajil brand mark + «شهادة نسب» title; the bird: name huge, ring plate,
photo slot, sex, hatch date, color; the loft & breeder; 5-generation tree (names +
rings, mono); COI value; «سجل موثق في زاجل منذ …» verification line; issue date;
a QR-code slot (links to the future public bird page).
Design direction: THE BOLD SYSTEM ON PAPER — this replaces the ornate certificates of
the old world with Gulf-modern confidence. It will be framed on walls and shared in
WhatsApp groups; it is Zajil's single biggest marketing surface. Use the same tokens;
gold is at home here.

## 12. 🎨 Shared states (design once, reuse everywhere)
- Sync status row: offline / syncing / pending / amber error (spec in Part 1).
- One-time notice banner: «تمت المزامنة. وُجدت N حلقة مكررة — راجعها» — dismissible,
  non-alarming.
- Confirm dialogs: delete bird (warns about cascade: races, health, pairings),
  sign-out, replace-import.
- Toast/undo pattern: «تم حذف برق» + «تراجع».

---

# PART 3 — DESKTOP & RESPONSIVE

Zajil ships for BOTH phone and desktop from one codebase. Design mobile-first at 430px
as specified; desktop follows these rules rather than separate designs, EXCEPT the three
screens below. Responsive per this part is a BUILD REQUIREMENT of the React port, not a
later pass.

## Adaptation rules (apply to every screen unless overridden)
- Breakpoints: ≤700px phone (as designed) · 701–1099px content column centered, max
  720px · ≥1100px desktop layout.
- ≥1100px: the bottom tab bar becomes a fixed side rail on the RIGHT (the RTL start
  side) — same five items, icon + label, brand-colored active state. Content sits to
  its left, max 960px, centered in the remaining space.
- Cards may pair two-up on desktop where they are peers (stat tiles row widens to 3–6
  tiles; overview cards two columns). Never three-plus columns of prose.
- Forms stay ONE column, max 560px, centered. The type scale does not shrink on
  desktop — boldness is the identity at every size.
- Hover states exist on desktop: rows shift to --brand-tint background; buttons darken
  to --brand-deep. Focus rings: 3px brand. Touch targets stay ≥44px even with a mouse.

## Desktop-specific designs (each gets its own desktop layout in its session, same tokens)
1. **Pedigree tree** — the flagship desktop screen: all 5 generations visible at once
   without scroll, subject on the right flowing left, connector lines, print-ready.
   This IS the wall chart.
2. **Loft home** — denser, table-like list: columns for ring (mono), name, sex, status,
   year, latest result; sortable headers; the same filter pills above.
3. **Dashboard (الرئيسية)** — desktop may show the season summary and recent activity
   side by side.

The certificate (deliverable 11) is format-fixed (A4 + 9:16) and unaffected by this part.

---

## Verification note (for the record)
Screens 1–9 and 12 are verified against the shipped app (v1.9.1) — every ⚙ item exists
in the codebase today. Screen 10 is aspirational by declared intent. Screen 11 exists
today only as a basic export; the certificate design is its intended replacement. If any
control seems missing or extra during a session, the app is the truth — flag it rather
than invent.
