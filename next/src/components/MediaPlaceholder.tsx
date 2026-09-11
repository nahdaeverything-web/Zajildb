import { t } from '@/src/i18n.ext.js';
import s from './shared.module.css';
// «الصورة على جهاز آخر» — §08. A media row whose bytes live on another device
// (SYNC-DESIGN §7): the record is real and its content is elsewhere. Quiet
// information, not an error. `hero` is the cover slot (filename in mono when
// known); the tile is the gallery cell.
const Cloud = () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 18a4 4 0 0 1-.5-8A6 6 0 0 1 18 9a4 4 0 0 1 0 9H7z"/></svg>;
export default function MediaPlaceholder({ hero = false, filename, meta, kind = 'photo' }:
  { hero?: boolean; filename?: string; meta?: string; kind?: 'photo' | 'file' }) {
  const label = t(kind === 'photo' ? 'media.elsewhere' : 'media.elsewhereFile');
  if (hero) return (
    <div className={s.hero} data-testid="media-elsewhere-hero"><Cloud /><span>{label}</span>{(filename || meta) && <small>{[filename, meta].filter(Boolean).join(' · ')}</small>}</div>
  );
  return <div className={`${s.ph} ${s.remote}`} data-testid="media-elsewhere" title={filename}><Cloud /><span>{label}</span></div>;
}
