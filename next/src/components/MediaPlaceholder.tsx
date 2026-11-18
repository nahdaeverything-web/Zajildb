import { t } from '@/src/i18n.ext.js';
import s from './shared.module.css';
// «الصورة على جهاز آخر» — §08. A media row whose bytes live on another device
// (SYNC-DESIGN §7): the record is real and its content is elsewhere. Quiet
// information, not an error. `hero` is the cover slot (filename in mono when
// known); the tile is the gallery cell.
const Cloud = () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 18a4 4 0 0 1-.5-8A6 6 0 0 1 18 9a4 4 0 0 1 0 9H7z"/></svg>;
// PHOTO SYNC, STAGE 1 (RULED 2026-11-18): the tile says which of four things is true. `elsewhere` — the bytes are on
// another device (a device with no account: nothing more can be said). `pending` — on another device and not uploaded
// yet. `fetching` — on the server, coming down now. `failed` — the download did not work; opening again retries.
type Where = 'elsewhere' | 'pending' | 'fetching' | 'failed';
const KEY: Record<Where, [string, string]> = {
  elsewhere: ['media.elsewhere', 'media.elsewhereFile'], pending: ['media.notUploadedYet', 'media.notUploadedYetFile'],
  fetching: ['media.fetching', 'media.fetchingFile'], failed: ['media.fetchFailed', 'media.fetchFailedFile'],
};
export default function MediaPlaceholder({ hero = false, filename, meta, kind = 'photo', where = 'elsewhere' }:
  { hero?: boolean; filename?: string; meta?: string; kind?: 'photo' | 'file'; where?: Where }) {
  const label = t(KEY[where][kind === 'photo' ? 0 : 1]);
  if (hero) return (
    <div className={s.hero} data-testid="media-elsewhere-hero" data-where={where}><Cloud /><span>{label}</span>{(filename || meta) && <small>{[filename, meta].filter(Boolean).join(' · ')}</small>}</div>
  );
  return <div className={`${s.ph} ${s.remote}`} data-testid="media-elsewhere" data-where={where} title={filename}><Cloud /><span>{label}</span></div>;
}
