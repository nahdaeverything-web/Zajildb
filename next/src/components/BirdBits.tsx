import { t, fmtPercent, ringHTML } from '@/src/i18n.ext.js';
import s from './shared.module.css';

// Small pieces every screen reuses, ported from js/ui.js one-to-one.
type Ring = { raw?: string; type?: string; year?: string | number };
type BirdLike = { id: string; name?: string; sex?: string; rings?: Ring[] } | null | undefined;

/** ui.js primaryRing: the FCI ring if there is one, else the first. */
export function primaryRing(b: BirdLike): string {
  if (!b || !Array.isArray(b.rings) || !b.rings.length) return '';
  const fci = b.rings.find((r) => r.type === 'FCI');
  return (fci || b.rings[0]).raw || '';
}
/** ui.js birdLabelText: ring · name, or the first 8 chars of the id. */
export function birdLabelText(b: BirdLike): string {
  if (!b) return t('common.unknown');
  return [primaryRing(b), b.name].filter(Boolean).join(' · ') || b.id.slice(0, 8);
}
/** ui.js birdLabelHTML: ring (mono, ltr) · name (bdi). */
export function BirdLabel({ bird }: { bird: BirdLike }) {
  if (!bird) return <span className={s.muted}>{t('common.unknown')}</span>;
  const ring = primaryRing(bird);
  if (!ring && !bird.name) return <span className={s.muted}>{bird.id.slice(0, 8)}</span>;
  return (<>{ring && <span dangerouslySetInnerHTML={{ __html: ringHTML(ring) }} />}{ring && bird.name ? ' · ' : ''}{bird.name && <bdi>{bird.name}</bdi>}</>);
}
/** ui.js sexIcon. */
export const sexIcon = (sex?: string) => (sex === 'cock' ? '♂' : sex === 'hen' ? '♀' : '?');
/** Sex chip — loft-home-v1's .sx (monochrome: ink / outlined / muted), which supersedes the prototype's tinted chip for bird rows. */
export function SexChip({ sex }: { sex?: string }) {
  const sx = sex || 'unknown'; const k = sx === 'cock' ? 'm' : sx === 'hen' ? 'f' : 'u';
  return <span className={`${s.sx} ${s[k]}`} data-sex={sx} aria-label={t('sex.' + sx)}><span className={s.g}>{sexIcon(sx)}</span>{t('sex.' + sx)}</span>;
}
/** COI value with ui.js's band as DATA (≥25% severe · ≥12.5% high · ≥6.25% moderate · >0 info · 0 none). No approved spec draws a coloured badge; each screen presents the value as its spec does. */
export function COIValue({ coi }: { coi: number }) {
  const band = coi >= 0.25 ? 'severe' : coi >= 0.125 ? 'high' : coi >= 0.0625 ? 'moderate' : coi > 0 ? 'info' : 'none';
  return <span className={s.mono} data-testid="coi-badge" data-band={band}>{fmtPercent(coi, 1)}</span>;
}
/** The ring plate — shared-states `.plate` / `.plate.sm`: a mono ring, optional season. */
export function Plate({ ring, season, small = false }: { ring: string; season?: string; small?: boolean }) {
  return <span className={`${s.plate} ${small ? s.sm : ''}`}><span>{ring}</span>{season && <span className={s.season}>{season}</span>}</span>;
}
