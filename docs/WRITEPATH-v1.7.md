# Zajil v1.7 — write path and call-site map

Generated from source with grep, not from memory. Commands and raw output
are shown alongside each section so every line can be re-derived.

Repo: /home/samir/zajil @ `a5e2e79` (branch `hardening/v1.7`)
js/db.js is 562 lines; a verbatim copy is at /tmp/zajil-db-v1.7.js

## 1. Everything js/db.js exports

```
$ grep -nE "^export (async )?(function|const|class)" js/db.js
14:export const STORES = ['birds', 'pairs', 'raceResults', 'healthEvents', 'lofts', 'media', 'settings', 'backups'];
18:export function uuid() {
26:export function nowISO() { return new Date().toISOString(); }
28:export function openDB() {
65:export function idbGet(store, key) {
73:export function idbGetAll(store, indexName, key) {
83:export function idbPut(store, value) { return tx(store, 'readwrite', (s) => s.put(value)); }
84:export function idbDelete(store, key) { return tx(store, 'readwrite', (s) => s.delete(key)); }
85:export function idbClear(store) { return tx(store, 'readwrite', (s) => s.clear()); }
89:export const state = {
101:export function onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }
102:export function emitChange(what) { for (const fn of listeners) fn(what); }
104:export function getBird(id) { return state.birds.get(id) || null; }
105:export function allBirds() { return [...state.birds.values()]; }
112:export const REFERENCE_STATUS = 'reference';
114:export async function initDB() {
138:export function currentLoft() { return state.lofts.get(state.currentLoftId) || null; }
139:export function loftStatuses({ includeReference = false } = {}) {
146:export async function setSetting(key, value) {
170:export function newBird(partial = {}) {
204:export class ValidationError extends Error {
218:export function checkBird(bird, opts = {}) {
231:export async function saveBird(bird, { allowWarnings = false, force = false } = {}) {
251:export async function deleteBird(id) {
306:export async function restoreBird(snapshot) {
327:export function makeGeneric(storeName, stateMap, typeName) {
352:export const Pairs = makeGeneric('pairs', 'pairs', 'pair');
353:export const Races = makeGeneric('raceResults', 'raceResults', 'race');
354:export const Health = makeGeneric('healthEvents', 'healthEvents', 'health');
355:export const Lofts = makeGeneric('lofts', 'lofts', 'loft');
359:export async function addMedia(birdId, kind, subtype, name, blob) {
365:export function mediaForBird(birdId) { return idbGetAll('media', 'birdId', birdId); }
367:export async function restoreMedia(m) {
374:export async function deleteMedia(id) {
392:export async function dataURLToBlob(dataURL) {
398:export async function exportAll({ includeMedia = true } = {}) {
422:export async function importAll(payload, mode = 'merge') {
509:export async function exportBirdWithAncestry(birdId, { includeRaces = true, includeHealth = false, includeMedia = true } = {}) {
545:export async function autoBackup() {
562:export function listBackups() { return idbGetAll('backups'); }
```

## 2. Call sites, per export

Command used for each symbol:
```
$ grep -rn "\b<SYMBOL>\b" js/ tests/ tools/ --include=*.js | grep -v "^js/db.js:"
```

| Export | Signature | Called from |
|---|---|---|
| `STORES` | `const` | _(not referenced outside db.js)_ |
| `uuid` | `()` | `js/views/breeding.js:8`<br>`js/views/breeding.js:98`<br>`js/views/breeding.js:150`<br>`js/views/breeding.js:176`<br>`js/views/races.js:4`<br>`js/views/races.js:117`<br>`js/views/bird-form.js:5`<br>`js/views/health.js:3`<br>`js/views/health.js:88`<br>`js/views/bird-detail.js:7`<br>`js/views/bird-detail.js:194` |
| `nowISO` | `()` | `js/views/breeding.js:8`<br>`js/views/bird-form.js:5`<br>`js/views/bird-detail.js:7`<br>`js/views/bird-detail.js:194`<br>`tests/guards.test.js:49` |
| `openDB` | `()` | _(not referenced outside db.js)_ |
| `idbGet` | `(store, key)` | `tests/guards.test.js:56` |
| `idbGetAll` | `(store, indexName, key)` | `js/views/tools.js:7`<br>`js/views/tools.js:163`<br>`tests/guards.test.js:56` |
| `idbPut` | `(store, value)` | _(not referenced outside db.js)_ |
| `idbDelete` | `(store, key)` | _(not referenced outside db.js)_ |
| `idbClear` | `(store)` | _(not referenced outside db.js)_ |
| `state` | `const` | `js/app.js:4`<br>`js/app.js:49`<br>`js/app.js:50`<br>`js/app.js:51`<br>`js/app.js:53`<br>`js/app.js:90`<br>`js/app.js:92`<br>`js/app.js:129`<br>`js/app.js:192`<br>`js/app.js:194`<br>`js/app.js:198`<br>`js/app.js:209`<br>`js/i18n.js:403`<br>`js/views/tools.js:6`<br>`js/views/tools.js:30`<br>`js/views/tools.js:34`<br>`js/views/tools.js:39`<br>`js/views/tools.js:40`<br>`js/views/tools.js:41`<br>`js/views/tools.js:86`<br>`js/views/tools.js:187`<br>`js/views/tools.js:188`<br>`js/views/tools.js:189`<br>`js/views/tools.js:234`<br>`js/views/tools.js:241`<br>`js/views/tools.js:294`<br>`js/views/tools.js:295`<br>`js/views/pedigree.js:9`<br>`js/views/pedigree.js:23`<br>`js/views/breeding.js:8`<br>`js/views/breeding.js:24`<br>`js/views/breeding.js:34`<br>`js/views/breeding.js:37`<br>`js/views/breeding.js:178`<br>`js/views/breeding.js:187`<br>`js/views/breeding.js:192`<br>`js/views/breeding.js:209`<br>`js/views/breeding.js:213`<br>`js/views/breeding.js:220`<br>`js/views/breeding.js:226`<br>`js/views/races.js:4`<br>`js/views/races.js:48`<br>`js/views/races.js:50`<br>`js/views/races.js:90`<br>`js/views/races.js:98`<br>`js/views/races.js:129`<br>`js/views/stats.js:4`<br>`js/views/stats.js:13`<br>`js/views/cert.js:6`<br>`js/views/cert.js:52`<br>`js/views/health.js:3`<br>`js/views/health.js:20`<br>`js/views/health.js:22`<br>`js/views/bird-detail.js:6`<br>`js/views/bird-detail.js:23`<br>`js/views/bird-detail.js:130`<br>`js/views/bird-detail.js:162`<br>`js/views/bird-detail.js:255`<br>`js/views/birds.js:4`<br>`js/views/birds.js:23`<br>`js/views/birds.js:114`<br>`js/views/birds.js:115`<br>`tools/gen-sample.js:138`<br>`tools/gen-sample.js:139`<br>`tools/gen-sample.js:145`<br>`tools/gen-sample.js:146`<br>`tools/gen-sample.js:158`<br>`tools/gen-sample.js:159`<br>`tools/gen-sample.js:172`<br>`tools/gen-sample.js:173`<br>`tools/gen-sample.js:183`<br>`tools/gen-sample.js:184`<br>`tools/gen-example-large.js:167`<br>`tools/gen-example-large.js:168`<br>`tools/gen-example-large.js:172`<br>`tools/gen-example-large.js:173`<br>`tools/gen-example-large.js:181`<br>`tools/gen-example-large.js:182`<br>`tools/gen-example-large.js:189`<br>`tools/gen-example-large.js:191`<br>`tools/gen-example-large.js:198`<br>`tools/gen-example-large.js:205` |
| `onChange` | `(fn)` | `js/app.js:4`<br>`js/app.js:159` |
| `emitChange` | `(what)` | _(not referenced outside db.js)_ |
| `getBird` | `(id)` | `js/engine/pedigree.js:3`<br>`js/engine/pedigree.js:11`<br>`js/engine/pedigree.js:20`<br>`js/engine/pedigree.js:35`<br>`js/engine/pedigree.js:44`<br>`js/engine/pedigree.js:62`<br>`js/engine/pedigree.js:72`<br>`js/engine/pedigree.js:91`<br>`js/engine/pedigree.js:93`<br>`js/engine/pedigree.js:101`<br>`js/engine/pedigree.js:102`<br>`js/engine/validate.js:8`<br>`js/engine/validate.js:13`<br>`js/engine/validate.js:24`<br>`js/engine/validate.js:31`<br>`js/engine/validate.js:32`<br>`js/engine/validate.js:101`<br>`js/engine/validate.js:103`<br>`js/engine/relationship.js:17`<br>`js/engine/relationship.js:18`<br>`js/engine/relationship.js:26`<br>`js/engine/relationship.js:27`<br>`js/engine/relationship.js:48`<br>`js/engine/coi.js:68`<br>`js/engine/coi.js:69`<br>`js/engine/coi.js:71`<br>`js/engine/coi.js:78`<br>`js/engine/coi.js:80`<br>`js/engine/coi.js:121`<br>`js/engine/coi.js:126`<br>`js/engine/coi.js:188`<br>`js/engine/coi.js:196`<br>`js/views/pedigree.js:9`<br>`js/views/pedigree.js:20`<br>`js/views/pedigree.js:58`<br>`js/views/pedigree.js:97`<br>`js/views/pedigree.js:98`<br>`js/views/pedigree.js:118`<br>`js/views/pedigree.js:150`<br>`js/views/breeding.js:8`<br>`js/views/breeding.js:91`<br>`js/views/breeding.js:114`<br>`js/views/breeding.js:201`<br>`js/views/breeding.js:237`<br>`js/views/breeding.js:285`<br>`js/views/breeding.js:345`<br>`js/views/races.js:4`<br>`js/views/races.js:59`<br>`js/views/bird-form.js:5`<br>`js/views/bird-form.js:13`<br>`js/views/bird-form.js:18`<br>`js/views/bird-form.js:19`<br>`js/views/bird-form.js:25`<br>`js/views/bird-form.js:167`<br>`js/views/bird-form.js:172`<br>`js/views/stats.js:4`<br>`js/views/stats.js:34`<br>`js/views/cert.js:6`<br>`js/views/cert.js:17`<br>`js/views/cert.js:53`<br>`js/views/health.js:3`<br>`js/views/health.js:31`<br>`js/views/bird-detail.js:6`<br>`js/views/bird-detail.js:20`<br>`js/views/bird-detail.js:24`<br>`js/views/bird-detail.js:25`<br>`js/views/bird-detail.js:27`<br>`js/views/bird-detail.js:28`<br>`js/views/bird-detail.js:288`<br>`tests/sample.test.js:17`<br>`tests/sample.test.js:20`<br>`tests/sample.test.js:21`<br>`tests/sample.test.js:26`<br>`tests/sample.test.js:31`<br>`tests/sample.test.js:34`<br>`tests/example-large.test.js:17`<br>`tests/example-large.test.js:23`<br>`tests/example-large.test.js:28`<br>`tests/example-large.test.js:33`<br>`tests/example-large.test.js:38`<br>`tests/example-large.test.js:39`<br>`tests/example-large.test.js:40`<br>`tests/example-large.test.js:41`<br>`tests/example-large.test.js:42`<br>`tests/example-large.test.js:47`<br>`tests/example-large.test.js:50`<br>`tests/example-large.test.js:58`<br>`tests/example-large.test.js:73`<br>`tests/example-large.test.js:75`<br>`tests/writeboundary.test.js:14`<br>`tests/writeboundary.test.js:23`<br>`tests/writeboundary.test.js:29`<br>`tests/writeboundary.test.js:36`<br>`tests/writeboundary.test.js:40`<br>`tests/writeboundary.test.js:46`<br>`tests/writeboundary.test.js:52`<br>`tests/writeboundary.test.js:63`<br>`tests/writeboundary.test.js:70`<br>`tests/writeboundary.test.js:77`<br>`tests/engine.test.js:16`<br>`tests/engine.test.js:24`<br>`tests/engine.test.js:33`<br>`tests/engine.test.js:38`<br>`tests/engine.test.js:39`<br>`tests/engine.test.js:48`<br>`tests/engine.test.js:53`<br>`tests/engine.test.js:54`<br>`tests/engine.test.js:61`<br>`tests/engine.test.js:67`<br>`tests/engine.test.js:68`<br>`tests/engine.test.js:74`<br>`tests/engine.test.js:78`<br>`tests/engine.test.js:79`<br>`tests/engine.test.js:87`<br>`tests/engine.test.js:92`<br>`tests/engine.test.js:99`<br>`tests/engine.test.js:107`<br>`tests/engine.test.js:117`<br>`tests/engine.test.js:125`<br>`tests/engine.test.js:139`<br>`tests/engine.test.js:144`<br>`tests/engine.test.js:146`<br>`tests/engine.test.js:153`<br>`tests/engine.test.js:157`<br>`tests/engine.test.js:160`<br>`tests/engine.test.js:161`<br>`tests/engine.test.js:163`<br>`tests/engine.test.js:165`<br>`tests/engine.test.js:169`<br>`tests/engine.test.js:173`<br>`tests/engine.test.js:179`<br>`tests/engine.test.js:196`<br>`tests/engine.test.js:200`<br>`tests/engine.test.js:209`<br>`tests/engine.test.js:214`<br>`tests/engine.test.js:215`<br>`tests/engine.test.js:224`<br>`tests/engine.test.js:231`<br>`tests/engine.test.js:235`<br>`tests/engine.test.js:236`<br>`tests/engine.test.js:237`<br>`tests/engine.test.js:238`<br>`tests/engine.test.js:239`<br>`tests/engine.test.js:240`<br>`tests/engine.test.js:243`<br>`tests/engine.test.js:320`<br>`tests/engine.test.js:323`<br>`tests/engine.test.js:326`<br>`tests/engine.test.js:331`<br>`tests/engine.test.js:335`<br>`tests/engine.test.js:338`<br>`tests/engine.test.js:347`<br>`tests/engine.test.js:353` |
| `allBirds` | `()` | `js/engine/validate.js:9`<br>`js/engine/validate.js:13`<br>`js/engine/validate.js:62`<br>`js/engine/validate.js:101`<br>`js/engine/validate.js:103`<br>`js/ui.js:4`<br>`js/ui.js:220`<br>`js/ui.js:226`<br>`js/ui.js:260`<br>`js/ui.js:278`<br>`js/ui.js:306`<br>`js/views/tools.js:7`<br>`js/views/tools.js:167`<br>`js/views/tools.js:186`<br>`js/views/breeding.js:8`<br>`js/views/breeding.js:117`<br>`js/views/races.js:4`<br>`js/views/races.js:89`<br>`js/views/bird-form.js:5`<br>`js/views/bird-form.js:264`<br>`js/views/stats.js:4`<br>`js/views/stats.js:12`<br>`js/views/bird-detail.js:6`<br>`js/views/bird-detail.js:248`<br>`js/views/birds.js:4`<br>`js/views/birds.js:35` |
| `REFERENCE_STATUS` | `const` | `js/views/bird-form.js:6`<br>`js/views/bird-form.js:39`<br>`js/views/bird-form.js:155`<br>`tests/guards.test.js:20`<br>`tests/guards.test.js:133`<br>`tests/guards.test.js:138`<br>`tests/guards.test.js:147`<br>`tests/factory.test.js:5`<br>`tests/factory.test.js:11`<br>`tests/factory.test.js:13`<br>`tests/factory.test.js:14`<br>`tests/factory.test.js:19`<br>`tests/factory.test.js:20`<br>`tests/factory.test.js:30`<br>`tests/factory.test.js:31`<br>`tests/factory.test.js:33` |
| `initDB` | `()` | `js/app.js:4`<br>`js/app.js:184` |
| `currentLoft` | `()` | `js/views/tools.js:6`<br>`js/views/tools.js:64`<br>`js/views/cert.js:6`<br>`js/views/cert.js:51` |
| `loftStatuses` | `({ includeReference = false } = {})` | `js/views/bird-form.js:6`<br>`js/views/bird-form.js:38`<br>`js/views/birds.js:8`<br>`js/views/birds.js:65` |
| `setSetting` | `(key, value)` | `js/app.js:4`<br>`js/views/tools.js:6`<br>`js/views/tools.js:43`<br>`js/views/tools.js:44`<br>`js/views/tools.js:45`<br>`js/views/tools.js:46`<br>`js/views/tools.js:49`<br>`js/views/tools.js:94`<br>`js/views/tools.js:236`<br>`js/views/races.js:182` |
| `newBird` | `(partial = {})` | `js/i18n.js:49`<br>`js/ui.js:4`<br>`js/ui.js:311`<br>`js/views/breeding.js:8`<br>`js/views/breeding.js:336`<br>`js/views/bird-form.js:5`<br>`js/views/bird-form.js:14`<br>`js/views/bird-form.js:182`<br>`js/views/bird-form.js:183`<br>`js/views/bird-form.js:312`<br>`js/views/birds.js:118`<br>`js/views/birds.js:148`<br>`tests/guards.test.js:13`<br>`tests/guards.test.js:20`<br>`tests/guards.test.js:130`<br>`tests/guards.test.js:131`<br>`tests/guards.test.js:132`<br>`tests/guards.test.js:133`<br>`tests/guards.test.js:134`<br>`tests/guards.test.js:135`<br>`tests/factory.test.js:7`<br>`tests/factory.test.js:11`<br>`tests/factory.test.js:13`<br>`tests/factory.test.js:14`<br>`tests/factory.test.js:17`<br>`tests/factory.test.js:19`<br>`tests/factory.test.js:20`<br>`tests/factory.test.js:23`<br>`tests/factory.test.js:24`<br>`tests/factory.test.js:25`<br>`tests/factory.test.js:26`<br>`tests/factory.test.js:27`<br>`tests/factory.test.js:30`<br>`tests/factory.test.js:31`<br>`tests/factory.test.js:36`<br>`tests/factory.test.js:37`<br>`tests/factory.test.js:46`<br>`tests/factory.test.js:47`<br>`tools/gen-sample.js:22`<br>`tools/gen-example-large.js:32` |
| `ValidationError` | `—` | `js/views/breeding.js:8`<br>`js/views/breeding.js:370` |
| `checkBird` | `(bird, opts = {})` | `js/views/breeding.js:8`<br>`js/views/breeding.js:292`<br>`js/views/breeding.js:350`<br>`js/views/bird-form.js:5`<br>`js/views/bird-form.js:226`<br>`tests/guards.test.js:65`<br>`tests/guards.test.js:68` |
| `saveBird` | `(bird, { allowWarnings = false, force = false } = {})` | `js/engine/validate.js:88`<br>`js/ui.js:4`<br>`js/ui.js:317`<br>`js/views/breeding.js:8`<br>`js/views/breeding.js:202`<br>`js/views/breeding.js:299`<br>`js/views/breeding.js:349`<br>`js/views/breeding.js:361`<br>`js/views/bird-form.js:5`<br>`js/views/bird-form.js:182`<br>`js/views/bird-form.js:183`<br>`js/views/bird-form.js:186`<br>`js/views/bird-form.js:188`<br>`js/views/bird-detail.js:6`<br>`js/views/bird-detail.js:195`<br>`tests/guards.test.js:61`<br>`tests/guards.test.js:68`<br>`tests/writeboundary.test.js:4`<br>`tests/writeboundary.test.js:5` |
| `deleteBird` | `(id)` | `js/engine/integrity.js:13`<br>`js/app.js:132`<br>`js/i18n.js:390`<br>`js/views/tools.js:7`<br>`js/views/tools.js:160`<br>`js/views/tools.js:199`<br>`js/views/tools.js:200`<br>`js/views/bird-detail.js:6`<br>`js/views/bird-detail.js:73`<br>`js/views/bird-detail.js:75` |
| `restoreBird` | `(snapshot)` | `js/views/tools.js:7`<br>`js/views/tools.js:202`<br>`js/views/bird-detail.js:6`<br>`js/views/bird-detail.js:78` |
| `makeGeneric` | `(storeName, stateMap, typeName)` | _(not referenced outside db.js)_ |
| `Pairs` | `const` | `js/views/breeding.js:2`<br>`js/views/breeding.js:8`<br>`js/views/breeding.js:97`<br>`js/views/breeding.js:131`<br>`js/views/breeding.js:137`<br>`js/views/breeding.js:139`<br>`js/views/breeding.js:151`<br>`js/views/breeding.js:180`<br>`js/views/breeding.js:199`<br>`js/views/breeding.js:215`<br>`js/views/breeding.js:221`<br>`js/views/breeding.js:244`<br>`js/views/breeding.js:251`<br>`js/views/breeding.js:302`<br>`js/views/breeding.js:364`<br>`tests/guards.test.js:61` |
| `Races` | `const` | `js/i18n.js:16`<br>`js/views/races.js:4`<br>`js/views/races.js:75`<br>`js/views/races.js:77`<br>`js/views/races.js:184` |
| `Health` | `const` | `js/i18n.js:17`<br>`js/i18n.js:120`<br>`js/i18n.js:220`<br>`js/i18n.js:314`<br>`js/views/health.js:3`<br>`js/views/health.js:42`<br>`js/views/health.js:44`<br>`js/views/health.js:87` |
| `Lofts` | `const` | `js/views/tools.js:6`<br>`js/views/tools.js:72` |
| `addMedia` | `(birdId, kind, subtype, name, blob)` | `js/views/bird-form.js:5`<br>`js/views/bird-form.js:190` |
| `mediaForBird` | `(birdId)` | `js/views/bird-detail.js:7`<br>`js/views/bird-detail.js:206` |
| `restoreMedia` | `(m)` | `js/views/bird-detail.js:7`<br>`js/views/bird-detail.js:230`<br>`tests/guards.test.js:61` |
| `deleteMedia` | `(id)` | `js/views/bird-detail.js:7`<br>`js/views/bird-detail.js:226` |
| `dataURLToBlob` | `(dataURL)` | _(not referenced outside db.js)_ |
| `exportAll` | `({ includeMedia = true } = {})` | `js/i18n.js:356`<br>`js/views/tools.js:6`<br>`js/views/tools.js:92`<br>`js/views/tools.js:98`<br>`js/views/tools.js:270` |
| `importAll` | `(payload, mode = 'merge')` | `js/engine/validate.js:96`<br>`js/views/tools.js:6`<br>`js/views/tools.js:111`<br>`js/views/tools.js:132`<br>`js/views/birds.js:17`<br>`js/views/birds.js:19` |
| `exportBirdWithAncestry` | `(birdId, { includeRaces = true, includeHealth = false, includeMedia = ` | `js/views/bird-detail.js:7`<br>`js/views/bird-detail.js:95` |
| `autoBackup` | `()` | `js/app.js:4`<br>`js/app.js:195`<br>`js/app.js:198`<br>`js/views/tools.js:7` |
| `listBackups` | `()` | `js/views/tools.js:7`<br>`js/views/tools.js:120` |

## 3. Direct IndexedDB access outside js/db.js

```
$ grep -rn "\bidbPut\b|\bidbDelete\b|\bidbClear\b|\bidbGet\b|\bidbGetAll\b|indexedDB" js/ --include=*.js | grep -v "^js/db.js:"
js/views/tools.js:7:  listBackups, autoBackup, allBirds, deleteBird, restoreBird, idbGetAll,
js/views/tools.js:163:    for (const m of await idbGetAll('media')) {
```

WRITES (`idbPut` / `idbDelete` / `idbClear`) outside `js/db.js`: **none**.
Enforced by `tests/guards.test.js` — "guard: no view writes to IndexedDB directly".

The only survivors are READS, which are deliberately allowed:

| File:line | Call | Why it is allowed |
|---|---|---|
| `js/views/tools.js:163` | `idbGetAll(\"media\")` | counts media per bird in the duplicate finder; a read, so it cannot desync the mirror or skip a change event |

## 4. Change events

```
$ grep -n "emitChange" js/db.js
102:export function emitChange(what) { for (const fn of listeners) fn(what); }
237:  emitChange({ type: 'bird', id: bird.id });
301:  emitChange({ type: 'bird', id });
324:  emitChange({ type: 'bird', id: bird.id });
334:      emitChange({ type: typeName, id: rec.id });
341:      emitChange({ type: typeName, id });
347:      emitChange({ type: typeName, id: rec.id });
362:  emitChange({ type: 'media', id: m.id, birdId });
370:  emitChange({ type: 'media', id: m.id, birdId: m.birdId });
377:  emitChange({ type: 'media', id, birdId: m && m.birdId });
500:  emitChange({ type: 'import' });

$ grep -rn "onChange" js/ --include=*.js
js/db.js:101:export function onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }
js/app.js:4:import { initDB, state, setSetting, onChange, autoBackup } from './db.js';
js/app.js:159:  onChange((ev) => {
```

### Emitted types

| Type | Emitted by (db.js line) | Trigger |
|---|---|---|
| `bird` | 220, 244, 257 | `saveBird`, `deleteBird`, `restoreBird` |
| `media` | 295, 302, 367 | `addMedia`, `deleteMedia`, `restoreMedia` |
| `pair` / `race` / `health` / `loft` | 267, 274, 280 (via `makeGeneric`) | `Pairs`/`Races`/`Health`/`Lofts` `.save`, `.remove`, `.restore` |
| `import` | 389 | `importAll` |

### Subscribers

There is exactly one subscriber, registered in `js/app.js` `wireAutoRefresh()`:

| Event | Behaviour |
|---|---|
| `import` | full `rerender()` — the shell itself may need rebuilding |
| any other | refresh the current route, **deferred while a dialog is open**, **skipped on a form route**, coalesced, and scroll-preserving |

The deferral is deliberate: re-rendering under an open dialog is how the
v1.5 "page jumps to the top" bug returns. `tests/e2e/change_events.py`
guards it.

## 5. The write path, end to end

```
view                     db.js boundary                     storage
────                     ──────────────                     ───────
checkBird(bird)  ──────► classifySave()  (pure, engine)
   │                        │
   │  show errors /         └─► {ok, errors, warnings}
   │  confirm warnings
   ▼
saveBird(bird, {allowWarnings})
                         ├─► classifySave()  ── !ok ──► throw ValidationError
                         ├─► stamp()          (loftId + updatedAt)
                         ├─► idbPut()         (the ONLY write site)
                         ├─► state.birds.set() (mirror stays in sync)
                         └─► emitChange({type:"bird"})
                                   │
                                   ▼
                          app.js wireAutoRefresh()
                          └─► refresh current route (deferred/coalesced)
```

The same shape holds for pairs, races, health events and lofts via
`makeGeneric`, and for media via `addMedia` / `deleteMedia` / `restoreMedia`.
`importAll` is the one deliberate bypass: it decodes and validates the whole
payload, snapshots to `backups`, then writes with raw `idbPut` — records in
an export are historical facts, not new edits to re-judge.
