# BACKLOG — outstanding findings

Everything here came from an adversarially-verified audit: each item was
claimed by one agent reading the source, then a second agent tried to refute it
against the actual code. 32 further claims were refuted and are not listed. A
further ~30 claims were never verified (the run hit a limit) — so this list is
thorough but not exhaustive.

Nothing here is a crash or a blocker. The four data-loss defects found in the
same audit are already fixed (see the git history for v1.6.0).

Severity is the auditor's, and reflects user impact, not effort.


## Medium (20)

### Re-picking files in the photo/document inputs accumulates instead of replacing — wrong photos get attached

**Where:** `js/views/bird-form.js`  
**Trigger:** On the bird form, tap "Add photo", select two photos, notice one is wrong, tap the input again and select only the correct photo. Save.  
**Effect:** Both `change` handlers do `for (const f of photoIn.files) pendingMedia.push(...)` and never clear `pendingMedia` for that input. The second selection replaces `photoIn.files` in the UI but the first batch is still queued, so `doSave` attaches all three files (and two copies of any file selected twice). There is no list of pending attachments and no way to remove one, so the user cannot see or undo it before saving.  
**Suggested fix:** Key pending media per input and rebuild on each change (e.g. `pendingPhotos = [...photoIn.files].map(...)` instead of pushing), then concatenate at save time; and render a small removable chip list of queued files.

### Edit URL for a missing bird renders a blank "New bird" form instead of redirecting

**Where:** `js/views/bird-form.js`  
**Trigger:** Open any `#/bird/<id>/edit` URL whose record is not present — a bookmarked/shared edit link on a device that never had that bird, a link kept after a Tools "Replace everything" import, or browser-Back onto the edit URL of a bird deleted in this session.  
**Effect:** `const existing = birdId ? getBird(birdId) : null;` has no guard, so `existing` is null, `isNew` becomes true and the user gets an empty create form titled "New bird" for a URL that says /edit. Saving creates a brand-new record under a freshly generated uuid rather than the one in the URL. Every other id-driven view (bird-detail.js:21, pedigree.js:21) guards this with `if (!bird) { navigateReplace('#/birds'); return null; }`.  
**Suggested fix:** Mirror the other views: `if (birdId && !existing) { navigateReplace('#/birds'); return null; }`.

### Ancestors created inline from a parent picker get status 'stock', so the register mislabels and misfilters them

**Where:** `js/ui.js (birdPicker allowCreate, used by `js/views/bird-form.js) — visible in `js/views/birds.js`  
**Trigger:** In the bird form's Sire field type an unknown ring number and tap "+ Create a NEW record for …". Then go to the register and set the Status filter to "Stock".  
**Effect:** The stub is built with `newBird({ external: true, sex, name, rings })`, so `status` takes the default `'stock'` instead of `REFERENCE_STATUS`. In the register that bird renders a "Stock" status chip next to its "External" chip and is returned by the Status = Stock filter, mixed in with real loft birds — while an identically-external bird saved through the form's ownership selector gets `status: 'reference'` and renders "Pedigree reference". The same inconsistency is produced by the placeholder parents in bird-detail.js:65-66.  
**Suggested fix:** Pass `status: REFERENCE_STATUS` wherever `external: true` records are created (ui.js inline create and bird-detail.js placeholder parents), or have `newBird()` derive `status` from `external`.

### Undo of a bird deletion restores the record but never refreshes the visible bird register

**Where:** `js/views/bird-detail.js`  
**Trigger:** Open a bird → Delete → confirm. You land on #/birds and the bird is gone from the list. Within the 8-second window click Undo on the toast.  
**Effect:** `del()` calls `restoreBird(snapshot)` and shows `toast(t('toast.undone'))`, and the record really is put back into IndexedDB and into `state.birds`. But nothing re-renders: `js/app.js:133` subscribes with `onChange((ev) => { if (ev && ev.type === 'import') rerender(); })` and `restoreBird` emits `{type:'bird'}`; `js/views/birds.js` has no `onChange` subscription at all (the only two `onChange` references in the whole tree are app.js:133 and the definition in db.js:99). So the user sees a success toast on a list that still shows the bird missing. Since the register is the app's home screen, the  
**Suggested fix:** Either broaden the app.js subscriber to `rerender()` (or at least re-run `route()`) for `bird`/`media` change events, or have `del()`'s undo callback explicitly re-route after `restoreBird` (e.g. `navigateReplace('#/bird/' + id)` so the user lands back on the restored bird).

### Undo of a media deletion silently does nothing visible, and throws if the item is already gone

**Where:** `js/views/bird-detail.js`  
**Trigger:** On a bird page, click ✕ on a photo in the gallery, confirm the delete, then click Undo on the toast. Separately: double-click ✕ so two confirm dialogs stack, confirm both.  
**Effect:** Two defects in the same handler (lines ~224-236). (1) The undo does `const { idbPut } = await import('../db.js'); await idbPut('media', snap);` — a raw `idbPut` that emits no change event — while `fig.remove()` has already permanently detached the figure from the gallery. The record comes back in IndexedDB but the page still shows it as deleted and there is no re-render path (app.js only rerenders on `type === 'import'`), so the 'Undone' toast is contradicted by the UI; the photo only reappears after a manual navigation. (2) `deleteMedia(id)` returns `await idbGet('media', id)`, which is `null  
**Suggested fix:** Guard with `if (!snap) return;` before offering undo; re-insert the figure node (or re-run the gallery fetch) inside the undo callback; and route the restore through a db.js helper that calls `emitChange({type:'media', ...})` instead of importing `idbPut` directly.

### Add-sibling placeholder flow rewrites the bird's parents before the sibling exists, with no undo

**Where:** `js/views/bird-detail.js`  
**Trigger:** Open a bird that has no sire and no dam → click '👥 Add sibling' → click 'Create parents & continue' in the modal → then hit browser Back, or navigate to any other tab, without saving the new sibling.  
**Effect:** The modal's primary action (lines ~63-79) creates two external placeholder birds, then does `bird.sireId = sire.id; bird.damId = dam.id; await saveBird(bird);` and only afterwards navigates to `#/bird/new?sire=…&dam=…`. The parent write is committed unconditionally and up front, so abandoning the new-bird form leaves the loft with two junk 'Unknown sire'/'Unknown dam' records that appear in the bird register (newBird gives them `status: 'stock'`, not REFERENCE_STATUS) and permanently re-parents the original bird to fabricated ancestors. That silently changes its pedigree everywhere downstream:  
**Suggested fix:** Defer the writes: pass a pending intent to the new-bird form (e.g. `#/bird/new?siblingOf=<id>`) and create the two placeholders plus the parent link only inside the form's successful save. If the eager write is kept, wrap it in `undoToast` that deletes the two placeholders and restores the original `sireId`/`damId`.

### Pair saved into a different season vanishes: the season <select> is built once and never rebuilt

**Where:** `js/views/breeding.js`  
**Trigger:** Open Breeding (selector defaults to the current year, e.g. 2026). Click "+ New pair", fill sire/dam, change the Season field to 2027 (or 2025, or any season with no pairs yet), Save.  
**Effect:** `seasons` and `seasonSel` are computed once in renderBreeding() (lines 23-27); `refresh()` (line 31) only clears `listWrap` and re-filters by `p.season === vs.season`. The saved pair belongs to 2027, so it is filtered out of the list, and 2027 was never added as an <option> — so the user sees the "No pairs this season yet" empty state, a "Saved" toast, and no way to reach the pair they just created. app.js only re-runs route() on hashchange, so the pair stays unreachable until the user leaves the Breeding tab and comes back.  
**Suggested fix:** Move the seasons/option build into refresh() (rebuild the <select> options from state.pairs each time), and after Pairs.save set `vs.season = savedPair.season` before calling refresh() so the new pair is what the user is looking at.

### The same bird can be linked as the chick of two different eggs

**Where:** `js/views/breeding.js`  
**Trigger:** Link bird X to egg 1 of round 1. Add a second egg, mark it hatched, press "Link an existing bird" and pick bird X again (or do it from an egg of a completely different pair).  
**Effect:** The picker filter (line 270) only excludes `pair.sireId` and `pair.damId` — nothing excludes birds that already carry a `chickId` reference from another egg. Both eggs end up with `chickId === X`: the loft shows two chicks that are one bird, wean/ring flags are tracked twice for one record, and if the second link came from another pair, X's sireId/damId are silently rewritten to that pair while the first egg's row still displays X as its chick under the wrong parents. Unlinking one egg leaves the other dangling on the same bird.  
**Suggested fix:** Build a Set of every chickId already referenced by any egg in state.pairs and exclude those birds in the picker's filter (or block them in the onClick with a t('br.linkBlocked', …) message).

### "Ring chick" creates a bird bypassing validateBird entirely

**Where:** `js/views/breeding.js`  
**Trigger:** Press "Ring chick" on a hatched egg and type a ring number that already exists on another bird — or ring a chick of a pair whose sire was later corrected to sex "hen" (or whose sire's hatchDate is after the egg's hatch date).  
**Effect:** ringChickDialog (lines 326-343) calls newBird()/saveBird() with no validation at all, while the sibling link path calls validateBird and the bird form blocks on errors and confirms on warnings (bird-form.js:209-228). Result: duplicate ring numbers are created with no warning (they only surface later in Tools' duplicate finder), and records the bird form would refuse as hard errors — sire recorded as a hen, parent hatched after the chick — are written silently.  
**Suggested fix:** Run `validateBird(chick, getBird, allBirds())` before saving; render errors in the dialog and `return false` to keep it open, and surface warnings (duplicate ring) for confirmation as the bird form does.

### "Mark failed" / "Mark hatched" are one-way with no confirm, no undo, and no way to delete an egg

**Where:** `js/views/breeding.js`  
**Trigger:** Mis-tap "Mark failed" on the wrong egg row (the buttons sit next to each other on a phone).  
**Effect:** The handler sets `egg.state = 'failed'` and saves (lines 217-222). A failed egg row renders only its label and laid date — no state buttons — and there is no remove-egg or remove-round control anywhere in roundBlock/eggRow, so the false record is permanent for that season. The same applies to "Mark hatched": once hatched, "Mark failed" disappears. Neither transition passes through confirmDialog or undoToast, contrary to the destructive-action invariant.  
**Suggested fix:** Offer undoToast after a state change (restoring the previous state/hatchDate), and add a small delete control for an egg and a round, also with undo.

### egg.chickId is left dangling when the chick bird is deleted, stranding the egg

**Where:** `js/views/breeding.js`  
**Trigger:** Ring a chick from an egg, then open that bird's page and delete it (or delete it from Tools' duplicate cleanup). Return to Breeding.  
**Effect:** db.deleteBird (db.js:189) detaches the bird only from other birds' sireId/damId — it never scans pair.rounds[].eggs[].chickId. eggRow (line 236) then does `getBird(egg.chickId)` → null, so the row renders a link labelled "Unknown" pointing at `#/bird/<deleted-id>`, which bounces to #/birds via renderBirdDetail's guard. Because `egg.chickId` is still truthy, both "Ring chick" and "Link an existing bird" stay hidden, so the egg cannot be re-ringed until the user notices the ⛓ button and unlinks.  
**Suggested fix:** In eggRow treat a missing getBird(egg.chickId) as unlinked (show the ring/link buttons plus a 'missing record' note); better, have deleteBird clear matching egg.chickId in state.pairs and include those pair snapshots in the undo payload.

### Race log's FCI column marks results as qualifying for birds with no FCI ring

**Where:** `js/views/races.js`  
**Trigger:** Open Races → race log with the shipped sample-data.json loaded. Race r-5 ("بطولة الاتحاد — العقبة", 27 fanciers / 214 birds, type federation) belongs to bird فجر, which carries no FCI ring.  
**Effect:** The FCI column (line 69) is computed from `resultQualifies(r)` alone, which only checks fanciers >= 20, birds >= 150 and raceType !== 'training'. ENGINE.md §6 and the FCI tab in the same view both state a result counts only if the bird also carries an FCI ring. So the log shows ✓ for فجر's result while the FCI tab in the adjacent tab shows ✗ (no ring) for the same bird — the two tabs of one view contradict each other, and the user is told a result counts toward FCI awards when it does not. Note `hasFCIRing` is already imported at the top of races.js and never used.  
**Suggested fix:** In logTab, compute `const q = resultQualifies(r); const ok = q.qualifies && hasFCIRing(getBird(r.birdId));` and render ✓ only for `ok` (or render a third state for 'race qualifies but bird has no FCI ring').

### New health event defaults to the wrong day (date computed in UTC, not local time)

**Where:** `js/views/health.js`  
**Trigger:** Tap "+ New event" on the Health view outside the UTC-overlap window — e.g. at 01:00 local in Amman (UTC+3), or at 20:00 local in New York (UTC-4).  
**Effect:** Line 66 prefills the date input with `new Date().toISOString().slice(0,10)`, which is the UTC calendar day. Verified with node: TZ=Asia/Amman at 01:00 on 2026-08-24 yields "2026-08-23" (yesterday); TZ=America/New_York at 20:00 on 2026-08-24 yields "2026-08-25" (tomorrow). The user accepts the default and the vaccination/treatment is logged on the wrong date — and health events cannot be edited afterwards in this view, only deleted and re-entered. (js/views/breeding.js:67 has the identical line for pairing start date.)  
**Suggested fix:** Build the default from local fields, e.g. `const d = new Date(); const local = new Date(d.getTime() - d.getTimezoneOffset()*60000).toISOString().slice(0,10);` — ideally as one shared `todayISO()` helper reused by breeding.js.

### Coordinate parser silently mis-reads DMS/degree-symbol/Arabic-numeral coordinates instead of rejecting them

**Where:** `js/views/races.js`  
**Trigger:** In the race result dialog, paste coordinates in any format other than plain decimal pairs — e.g. "29 32 15 N, 35 0 22 E" (space-separated DMS, a common copy from a GPS/handheld), or "29.5321° N, 35.0063° E" (Google Maps default), or Eastern-Arabic digits, then press "حساب السرعة من الإحداثيات".  
**Effect:** `parseCoords` (line 135) uses an unanchored regex `/(-?\d+(?:\.\d+)?)[\s,;]+(-?\d+(?:\.\d+)?)/`, which matches the first number pair anywhere in the string and ignores the rest. Verified in node: "29 32 15 N, 35 0 22 E" → {lat:29, lon:32}, so the release point is silently placed ~250 km from the real one and the computed distance and velocity written into the form (and then saved) are wrong with no warning. "29.5321° N, 35.0063° E", "N29.53 E35.00" and Eastern-Arabic digits all → null, in which case the calc button returns silently (line 140: `if (!a || !b) return;` with no toast) and on save   
**Suggested fix:** Anchor and validate: require the whole trimmed string to be a coordinate pair, normalise Eastern-Arabic digits first, accept an optional degree symbol / N,S,E,W hemisphere suffix and DMS, and range-check lat ∈ [-90,90], lon ∈ [-180,180]. When parsing fails, show a toast/field error instead of returning silently, and only persist loftCoords once it parses.

### Save button is a silent dead end when the bird field holds text but no selection

**Where:** `js/views/races.js`  
**Trigger:** Edit an existing race result (or open a new one), click into the bird field — the picker selects the prefilled label on focus — type a character, then click Save. Same in the Health event dialog with scope "single bird".  
**Effect:** birdPicker's `input` listener (js/ui.js:301) sets `root.value = null` on any keystroke, so the field still displays text while the selection is gone. races.js:178 (`if (!birdP.value) return false;`) and health.js:84 do keep the modal open but render no message at all, so Save appears to be broken: the user sees a filled bird field and a button that does nothing, with no clue that they must click a row in the dropdown. breeding.js:91-94 handles the same case correctly by appending errors to an errBox before returning false.  
**Suggested fix:** Mirror breeding.js: add an error box to both dialogs and populate it with `t('bird.chooseBird')` (and any other failed validation) before `return false`, or at minimum fire a toast.

### Date-only values render one day early for users at negative UTC offsets

**Where:** `js/i18n.js`  
**Trigger:** Set the device timezone to any negative offset (e.g. America/New_York) and open the race log or health log containing a record dated "2025-04-12".  
**Effect:** fmtGregorian (line 444) and fmtHijri (line 454) do `new Date(iso)`; a bare "YYYY-MM-DD" is parsed as UTC midnight per spec, then formatted in local time. Verified in node with TZ=America/New_York: `new Date('2025-04-12').toLocaleDateString('en-GB',{year:'numeric',month:'short',day:'numeric'})` → "11 Apr 2025". Every stored date-only field (race date, health event date, hatch date, etc.) displays one day earlier than what was entered and saved, and the Hijri rendering shifts with it. Users at positive offsets (the Arabic-first target, UTC+2/+3) are unaffected, which is why it hides.  
**Suggested fix:** For date-only strings, parse the parts explicitly into a local Date (`new Date(y, m-1, d)`) rather than letting Date parse them as UTC; keep the current behaviour only for full datetime strings.

### Every automatic snapshot base64-encodes all photos and then throws them away

**Where:** `js/db.js`  
**Trigger:** Happens on boot when a snapshot is due and every 12 h thereafter (`autoBackup()` from app.js), for any loft with photos/documents attached.  
**Effect:** `autoBackup()` calls the full `exportAll()`, which reads every media record and awaits `blobToDataURL(m.blob)` for each one — building base64 strings ~1.33× the size of all stored photos — and the very next line discards them (`payload.media = []`). A loft with 200 photos at 2 MB each churns ~400 MB of blob reads and ~530 MB of transient strings on the main thread just to store a media-free snapshot; on a phone this stalls the app or crashes the tab, twice a day.  
**Suggested fix:** Give `exportAll` an `{ includeMedia = true }` option and call `exportAll({ includeMedia: false })` from `autoBackup`, so media blobs are never read or encoded for snapshots.

### Statistics view recomputes COI per bird from scratch and freezes the UI for seconds on a real loft

**Where:** `js/views/stats.js`  
**Trigger:** Open the Statistics tab on a loft of a few hundred birds or more (especially a line-bred one) at the default COI depth of 10.  
**Effect:** `birds.map((b) => ({ b, coi: inbreeding(getBird, b.id, depth).coi }))` runs synchronously inside `renderStats`, and each `inbreeding` call rebuilds its own `truncatedGraph` and a fresh `makeKinship` memo — nothing is shared between birds, so the pair-memo work is repeated N times. Measured in node with the real engine (browsers, and phones especially, are slower): 512-bird selectively-bred loft = 334 ms, ~970-bird line-bred loft = 3.1 s at depth 10 and 3.9 s at depth 15. `route()` has already called `clear(main)`, so the user stares at an empty page with no spinner while the main thread is blo  
**Suggested fix:** Render the page shell first and fill the histogram asynchronously in chunks (or in a worker), and share one `makeKinship` memo across the whole collection instead of allocating one graph+memo per bird; cache results keyed by bird id + updatedAt + depth.

### Date-display setting is unreachable for English users: the dropdown shows "Gregorian + Hijri" while dates render Gregorian-only, and re-picking it fires no change event

**Where:** `js/views/tools.js`  
**Trigger:** Fresh install → Tools → set Language to English (never touching Date display) → look at the Date display dropdown, then try to enable Hijri by selecting "Gregorian + Hijri".  
**Effect:** The control is built as `select([...], state.settings.dates || 'both')` while app.js resolves the effective value as `state.settings.dates || (state.settings.lang === 'en' ? 'gregorian' : 'both')`. With `settings.dates` unset and lang='en', the dropdown displays "Gregorian + Hijri" but dates everywhere render Gregorian only — the displayed setting contradicts the app's behaviour. Worse, because the select's value already *is* `both`, choosing "Gregorian + Hijri" changes nothing and the `change` listener never fires, so nothing is persisted: the user can only reach the both-mode by selecting a   
**Suggested fix:** Use the same resolution in both places — export the default from a single helper (`effectiveDateMode()`) and seed the select with it, or write the resolved default into settings on first `applySettings()`.

### Replace-import erases the database before decoding the payload, so a mid-import failure destroys the user's data

**Where:** `js/db.js`  
**Trigger:** Tools → Import → mode "Replace everything" with a large export containing photos, on a device near its storage quota (or with any media entry whose data URL cannot be decoded).  
**Effect:** `importAll` clears all six stores up front, then inserts records one by one; media go through `await dataURLToBlob(m.dataURL)` (a `fetch` that rejects on a malformed data URL) and `idbPut` (which aborts with QuotaExceededError when storage runs out). Any such failure rejects out of `importAll` after the wipe, leaving a half-populated database — the original loft is already gone and nothing rolls it back. The caller in tools.js just shows a toast; the only remaining copy is an auto-snapshot, which itself contains no media.  
**Suggested fix:** Decode/validate the entire payload (all media blobs included) before clearing anything, and perform the wipe + writes so a failure can restore the previous contents (snapshot to `backups` first, or stage into temp stores and swap).


## Low (13)

### Enter from a <select> triggers "Save & add another" instead of Save

**Where:** `js/views/bird-form.js`  
**Trigger:** On a new-bird form, tab to the Sex / Status / ring-type / Ownership dropdown, choose a value and press Enter (browsers that perform implicit submission from a closed select, e.g. Chrome on Windows and Firefox).  
**Effect:** The keydown guard whose comment says "Enter must never save a half-entered bird" only tests `e.target instanceof HTMLInputElement`, so selects are unguarded and implicit submission proceeds. Implicit submission fires the form's default button = the first submit button in tree order, which is "Save & add another" (it is appended before the primary Save). The half-entered bird is saved and immediately replaced by a fresh blank form with a "Saved … — enter the next one" toast, instead of landing on the saved bird's page.  
**Suggested fix:** Include selects in the Enter guard (`e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement`), and put the primary Save first in the DOM (reordering visually with CSS) so it is the default button.

### Filtering to zero matches renders a completely blank list — the empty state only appears when the database is empty

**Where:** `js/views/birds.js`  
**Trigger:** With birds in the register, set Ownership = "External only" (or any filter/search combination) that matches nothing. Optionally navigate to another tab and back — `vs` is module-level, so the filter persists.  
**Effect:** `refresh()` gates the empty state on `!state.birds.size`, not on `rows.length`, so with birds present but no matches the list area is rendered completely empty: no "no results" message, no hint that a filter is active, and no way to clear filters other than reopening each dropdown. Because the view state survives navigation, a user who leaves and returns sees a blank register and can reasonably think the data is gone.  
**Suggested fix:** Add a second branch: when `state.birds.size && !rows.length`, render a "no matches" block with a "clear filters" button that resets `vs` and calls `refresh()` (also re-syncing the select values).

### Hatch-from-ring-year hint goes stale after a ring row is deleted

**Where:** `js/views/bird-form.js`  
**Trigger:** Type a ring such as JO-2023-12345, see the "📅 Use ring year: 2023" button appear under Hatch date, then press the ✕ on that ring row (e.g. it was typed into the wrong row).  
**Effect:** `updateHatchHint` is only wired to `ringsWrap`'s `input` event and to `hatchIn`; `del`'s click handler just calls `row.remove()`. Removing a row fires no input event, so the hint keeps offering a year taken from a ring that no longer exists on the form, and clicking it writes 2023-01-01 into Hatch date. Adding a row has the same gap in reverse.  
**Suggested fix:** Call `updateHatchHint()` from the ✕ handler and from `addRing`'s onclick (or listen for a custom event dispatched on ringsWrap).

### Submit buttons are never disabled during save — a double tap duplicates attached media

**Where:** `js/views/bird-form.js`  
**Trigger:** On a phone, double-tap "Save" (or "Save & add another") on a form with photos attached while IndexedDB is writing.  
**Effect:** Nothing guards re-entry of the submit handler: both submissions run `doSave`, so the `pendingMedia` loop runs twice and `addMedia` stores a second copy of every photo/document under new ids. In the add-another case, the second handler's `root.replaceWith(next2)` is a no-op because `root` was already detached by the first, so the second freshly built form (and any focus/prefill work) is silently discarded while two toasts appear.  
**Suggested fix:** Set a `let saving = false` re-entry flag (and disable the submit buttons) for the duration of `doSave`, resetting it in a finally block.

### Save failures are silent — no try/catch around saveBird/addMedia

**Where:** `js/views/bird-form.js`  
**Trigger:** Save a bird with several large photos on a device where the IndexedDB quota is exceeded (or storage is otherwise unavailable).  
**Effect:** `doSave` awaits `saveBird` and `addMedia` with no error handling, and the warnings-modal path calls `doSave(bird, andNew)` without awaiting or catching. A rejection becomes an unhandled promise rejection: no toast, no navigation, no problem list — the form just sits there, so the user cannot tell whether the bird was saved and may re-enter it.  
**Suggested fix:** Wrap `doSave` in try/catch, surface the failure via `toast()`/the `problems` block, and attach a `.catch` to the modal's non-awaited `doSave` call.

### Bird rows carry role="listitem" on the <a>, removing their link semantics

**Where:** `js/views/birds.js`  
**Trigger:** Browse the register with a screen reader (or list the page's links).  
**Effect:** `row()` builds `h('a', { class:'bird-row', role:'listitem', href: '#/bird/'+b.id, ... })`. An explicit `role="listitem"` overrides the anchor's implicit `link` role, so assistive tech announces each row as a plain list item with no indication it is actionable, and rows do not appear in the links rotor. The filter selects (ownership/status/sex/sort) also have no accessible name beyond their first option's text, and the sort select has none at all.  
**Suggested fix:** Wrap each anchor in a `role="listitem"` element (or use ul/li) and leave the anchor's role alone; add `aria-label` to the four filter selects.

### IntersectionObserver and picker document listeners are never torn down — leak grows through the batch-entry loop

**Where:** `js/views/birds.js and `js/ui.js (driven by `js/views/bird-form.js)`  
**Trigger:** Batch-enter records with "Save & add another" for a long session (each iteration builds a new form with two birdPickers), and navigate in and out of the register repeatedly.  
**Effect:** `renderBirds` creates an IntersectionObserver per render and never disconnects it, and every `birdPicker` registers a permanent `document.addEventListener('click', ...)` with no removal path. Each abandoned form's picker closures keep the whole detached form subtree alive — including `pendingMedia`'s File references — so memory grows monotonically during exactly the flow the app optimises for, and every page click runs an ever-growing list of `root.contains(e.target)` checks.  
**Suggested fix:** Disconnect the observer and remove the document listener when the node leaves the document (a shared teardown registry the router calls on `clear(main)`, or a MutationObserver/`AbortController` signal tied to the view's lifetime).

### Deleting a bird orphans its race results, health events and breeding pairs

**Where:** `js/db.js`  
**Trigger:** Give a bird some race results (Races tab) and pair it in the Breeding tab, then open the bird's detail page and Delete → confirm, and let the undo toast expire.  
**Effect:** `deleteBird` (js/db.js:180-200) detaches the bird as a parent and deletes its media, but never touches `state.raceResults`, `state.healthEvents` or `state.pairs`. The rows survive pointing at a nonexistent id. Concretely: the Races tab renders the row forever with '—' in the bird column (js/views/races.js:53 null-checks `getBird`), so the result can no longer be attributed but still occupies the log and is exported by `exportAll`; and js/views/breeding.js:120-121 emits `<a href="#/bird/${pair.sireId}">` unconditionally even when `getBird(pair.sireId)` returned null, so the pair card shows a li  
**Suggested fix:** Either cascade-delete the dependent raceResults/healthEvents/pairs and include them in the snapshot returned to `restoreBird` (so undo stays complete), or leave them but null out `birdId`/`sireId`/`damId` and make consumers render dead references as plain text rather than links (breeding.js:120-121 should not emit an `<a>` when the bird lookup is null).

### Link path applies hatchDate after validation, so an impossible date is saved unvalidated

**Where:** `js/views/breeding.js`  
**Trigger:** Link an existing bird that has no hatchDate recorded to a hatched egg whose hatch date is earlier than the pair's sire or dam hatch date (easy after backdating a bought clutch's dates).  
**Effect:** validateBird is run on `candidate` while `candidate.hatchDate` is still empty (line 287), and validate.js's parent-age block is guarded by `if (bird.hatchDate)` — so it is skipped entirely. The code then saves `{ ...candidate, hatchDate: egg.hatchDate }` (line 298) without re-validating, writing a bird whose parents hatched after it — exactly the `val.parentYounger` hard error the bird form refuses. The `warnings` array returned by validateBird is also discarded, so a duplicate ring introduced by the link is never surfaced.  
**Suggested fix:** Compose the final record (including hatchDate) first, validate that, and show warnings for confirmation before the single saveBird call.

### Pairing date and acquired date are collected but never displayed, and a pair cannot be edited

**Where:** `js/views/breeding.js`  
**Trigger:** Create a pair filling in "Pairing date" and "Acquired on" (the new bought-pair fields), then look at the pair card.  
**Effect:** pairCard renders only nestBox, acquiredFrom and status (lines 122-126); `pair.startDate` and `pair.acquiredDate` are read nowhere in the codebase (fmtDate is imported at line 10 and never used in this file). There is also no edit dialog for a pair, so a wrong nest box, season or date can only be corrected by deleting the pair — which throws away all its rounds and eggs. The user's input is silently swallowed.  
**Suggested fix:** Show the pairing/acquired dates in the pair-meta chips via fmtDate, and add an edit action that reopens the pair dialog on the existing record.

### Auto-filled dates use UTC, so between midnight and 03:00 local they record yesterday

**Where:** `js/views/breeding.js`  
**Trigger:** In Jordan (UTC+3), at 01:00 local, add an egg, press "Mark hatched", or press "Wean".  
**Effect:** All defaults use `nowISO().slice(0, 10)` / `new Date().toISOString().slice(0, 10)` (lines 67, 101, 176, 213, 249), which is the UTC calendar day — three hours behind local in Amman. The egg's laid/hatch/wean dates are stamped with the previous day, and the hatch date is copied straight into the chick's permanent `hatchDate` when the chick is ringed (line 333). Same pattern in health.js:66.  
**Suggested fix:** Add a shared `todayISO()` helper that formats the local date (e.g. via getFullYear/getMonth/getDate padded, or sv-SE toLocaleDateString) and use it for every date-input default.

### Arabic comma hardcoded in the FCI non-qualifying reason list, leaking into English UI

**Where:** `js/views/races.js`  
**Trigger:** Switch the app language to English, open Races → FCI eligibility checker, and look at a bird whose result fails two rules (e.g. too few fanciers and too few pigeons).  
**Effect:** Line 111 joins the reason strings with the literal Arabic comma `'، '`, so the English UI renders "Fewer than 20 fanciers، Fewer than 150 pigeons" — an Arabic punctuation mark inside English text, which also disturbs bidi rendering of the surrounding LTR run. It is the only user-visible string in these two views not routed through t().  
**Suggested fix:** Use a language-dependent separator, e.g. a `list.separator` dictionary key (`{ ar: '، ', en: ', ' }`), or `getLang() === 'ar' ? '، ' : ', '`.

### COI depth field silently clamps out-of-range input and keeps showing the rejected number

**Where:** `js/views/tools.js`  
**Trigger:** Tools → type 30 (or 1, or clear the field) into "COI depth (generations)" and click elsewhere.  
**Effect:** The handler stores `Math.max(3, Math.min(15, +depthIn.value || 10))` but never writes the clamped value back to the input and never rerenders, so the box keeps displaying 30 while the persisted depth is 15 (or displays empty while 10 was stored). The user believes the pedigree/statistics COI is computed at the depth shown; the certificate and Statistics headings (`ped.coiAtN`) will then contradict the field on the settings page.  
**Suggested fix:** Assign the clamped value back: `depthIn.value = v;` after `setSetting`, and toast when the entered value was out of range.
