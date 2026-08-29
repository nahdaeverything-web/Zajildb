// db.js — THE FACADE. Every importer in the app depends on this file and
// nothing else in js/db/. Split across four modules in v1.9 because a sync
// layer was about to land on an 866-line file; the invocation contract did
// not change, and no view changed a single import.
//
//   db/storage.js   IndexedDB access, the in-memory mirror, change events
//   db/oplog.js     the op log and tombstones
//   db/records.js   the write boundary: birds, generic stores, media
//   db/io.js        export, import, sharing, backups
//   db/sync.js      accounts and the Supabase session
//
// This file adds NOTHING. It re-exports, and that is all it may ever do —
// logic here would be logic outside the boundary the guards police.
//
// IndexedDB layer. IndexedDB is the source of truth; the app never
// blocks on the network. An in-memory Map of birds is kept in sync so the
// pure engine (which needs a synchronous getBird) stays fast with 1000+ birds.
//
// Sync-readiness (club mode hook): every record carries `loftId`, `updatedAt`
// (device clock, ISO) and `deviceId`. If sync is added later it must be
// per-field last-write-wins — never whole-record overwrite.
//
// CONFLICT ORDER COMES FROM THE OP LOG, NOT FROM `updatedAt`.
// This supersedes the earlier note that said updatedAt keys LWW. The reason is
// concrete: restoreBird deliberately reinstates a record's ORIGINAL timestamps
// (an undo restores what was there; it is not a new edit). So after any
// delete+undo the surviving record carries an old updatedAt, and any
// updatedAt-keyed resolution would let a stale remote copy win. Order comes
// instead from the op log's per-device monotonic `seq`, which only ever
// increases and is unaffected by restores.
//
// PROVENANCE vs deviceId — two different questions, do not confuse them:
//
//   record.deviceId    the LAST device to write this record. stamp() sets it on
//                      every write, so it changes as the record moves between
//                      devices. It answers "who touched this most recently".
//   record.provenance  an append-only history, [{ event, at, deviceId }].
//                      provenance[0] is the 'created' event, so THAT is the
//                      creating device — never read record.deviceId for that.
//
// newBird() seeds provenance with a single 'created' event; promote-to-loft and
// ownership transfers will append to it later. The op log is a third thing
// again: it records what THIS DEVICE DID, not what happened to a record.
//
// Records created before v1.8 have NO provenance field and nothing backfills
// one. Absence is legal permanently: stamp() and saveBird() must never invent
// provenance for a record that lacks it, because a fabricated 'created' event
// would assert a history that did not happen. Asserted in
// tests/e2e/provenance.py.
//
// ACCEPTED LIMITATION (v1.8): an op and the record it describes are written in
// SEPARATE transactions, so a crash between them can drop an op. This is
// tolerated deliberately: ops carry the full record, so server reconciliation
// is self-healing, and multi-store transactions would mean restructuring every
// write path. Revisit only if a real inconsistency is observed.
//
// OUT OF SYNC SCOPE (no ops, no tombstones): the `settings` store, which is
// per-device preference rather than loft data; and the `backups` store, whose
// snapshots are local safety nets. See setSetting() and autoBackup().

export {
  REFERENCE_STATUS,
  STORES,
  allBirds,
  currentLoft,
  emitChange,
  getBird,
  idbClear,
  idbDelete,
  idbGet,
  idbGetAll,
  idbPut,
  initDB,
  loftStatuses,
  nowISO,
  onChange,
  openDB,
  setSetting,
  state,
  uuid,
} from './db/storage.js';

export {
  diffFields,
  getOpsSinceSeq,
  listOps,
  listTombstones,
  opRecord,
} from './db/oplog.js';

export {
  Health,
  Lofts,
  Pairs,
  Races,
  ValidationError,
  addMedia,
  checkBird,
  deleteBird,
  deleteMedia,
  makeGeneric,
  mediaForBird,
  newBird,
  restoreBird,
  restoreMedia,
  saveBird,
} from './db/records.js';

export {
  SENSITIVE_SETTING_PREFIXES,
  autoBackup,
  dataURLToBlob,
  exportAll,
  exportBirdWithAncestry,
  exportableSettings,
  importAll,
  listBackups,
} from './db/io.js';

export {
  AUTH_SETTING_KEYS,
  AuthError,
  authHeaders,
  authState,
  ensureAccessToken,
  isSignedIn,
  refreshSession,
  signIn,
  signOut,
  syncConfig,
} from './db/sync.js';
