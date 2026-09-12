'use client';
import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import * as db from '@/src/db.js';
import { useZajilStore, selectBird, useMediaForBird } from '@/src/db/react';
import { t, fmtDate, fmtNum, fmtPercent, statusLabel } from '@/src/i18n.ext.js';
import { inbreeding, ancestorLoss } from '@/src/engine/coi.js';
import { descendantDepths, pedigreeGrid } from '@/src/engine/pedigree.js';
import { birdEligibility } from '@/src/engine/fci.js';
import { SyncRow, Loading, MediaPlaceholder, COIValue, BirdLabel, primaryRing, birdLabelText, toast, undoToast, confirmDialog, seasonStart, downloadJSON, initDB } from '@/src/components';
import sh from '@/src/components/shared.module.css';
import s from './bird.module.css';

// Bird profile — design/approved/bird-profile-v1.html, behaviour from
// js/views/bird-detail.js. Spec wins on presentation: hero + tiles + four
// tabs, the verified-record notice, the gallery grammar, a mini pedigree, one
// table per season, a health timeline. Vanilla wins on wiring: COI/AVK from
// the engine, progeny analysis (bird-detail.js:256-306), delete → undo, the
// two add-sibling paths, whole-loft health events, blobless media rows as
// «الصورة على جهاز آخر». Where the spec is silent (options-menu items, the
// zero-relation delete body, the next-vaccination rule, the season boundary)
// the interim is named in the commit and the 4A report.
type Ring = { raw?: string; type?: string; year?: number | string };
type Note = { id?: string; at?: string; text?: string };
type Bird = { id: string; name?: string; sex?: string; status?: string; hatchDate?: string; colour?: string; strain?: string; eyeSign?: string; breeder?: string; owner?: string; acquiredFrom?: string; acquiredDate?: string; createdAt?: string; external?: boolean; loftId?: string; sireId?: string | null; damId?: string | null; rings?: Ring[]; notes?: Note[] };
type Race = { id: string; birdId: string; date?: string; raceName?: string; raceType?: string; releasePoint?: { name?: string } | null; distanceKm?: number; velocity?: number; position?: number | null; birdsEntered?: number };
type HealthEvent = { id: string; birdId?: string | null; loftId?: string; wholeLoft?: boolean; eventType: string; date?: string; medication?: string; notes?: string };
type Pair = { id: string; sireId?: string; damId?: string };
type Media = { id: string; kind?: string; subtype?: string; name?: string; hasBlob?: boolean };
type Slot = { id: string; bird: Bird | undefined } | null;
type Tab = 'over' | 'ped' | 'race' | 'hlth';
const TABS: Array<[Tab, string]> = [['over', 'tab.overview'], ['ped', 'tab.pedigree'], ['race', 'nav.races'], ['hlth', 'nav.health']];
const getBird = (id: string) => db.getBird(id) as Bird | undefined;
const byDateDesc = <T extends { date?: string }>(a: T, b: T) => (b.date || '').localeCompare(a.date || '');

// Season of a race: the one display rule (src/components/season.ts, ruled at 4A acceptance).
// Ruling 4 (4.0): next vaccination = most recent vaccination event + 365 days, labelled an estimate, hidden when none.
const plus365 = (iso: string) => { const d = new Date(iso + 'T00:00:00'); d.setDate(d.getDate() + 365); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
// Plate season badge = the two last digits of the primary ring's year (the spec's «24» beside JOR 24 17352).
const seasonYY = (b: Bird) => { const r = (b.rings || []).find((x) => x.type === 'FCI') || (b.rings || [])[0]; return r && r.year ? String(r.year).slice(-2) : ''; };
const Chev = () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6" /></svg>;

export default function BirdView() {
  const params = useSearchParams(); const router = useRouter();
  const id = params.get('id') || '';
  const want = params.get('tab') as Tab | null;
  const [tab, setTab] = useState<Tab>(want && TABS.some(([k]) => k === want) ? want : 'over');
  const [booted, setBooted] = useState(false);
  const [menu, setMenu] = useState(false);
  const [noteText, setNoteText] = useState('');
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  const bird = useZajilStore(selectBird(id)) as Bird | null;
  const st = useZajilStore((x) => x);
  const media = useMediaForBird(id || null) as Media[];
  // object URLs for the rows whose bytes are on this device; revoked on change and unmount (ui.js onViewTeardown)
  const [urls, setUrls] = useState<Record<string, string>>({});
  useEffect(() => {
    let live = true; const made: string[] = [];
    Promise.all(media.filter((m) => m.hasBlob).map(async (m) => { const row = (await db.idbGet('media', m.id)) as { blob?: Blob } | undefined; return row && row.blob ? ([m.id, URL.createObjectURL(row.blob)] as const) : null; }))
      .then((pairs) => {
        if (!live) { for (const p of pairs) if (p) URL.revokeObjectURL(p[1]); return; }
        const map: Record<string, string> = {}; for (const p of pairs) if (p) { map[p[0]] = p[1]; made.push(p[1]); } setUrls(map);
      });
    return () => { live = false; for (const u of made) URL.revokeObjectURL(u); };
  }, [media]);
  useEffect(() => { if (booted && !bird) router.replace('/birds'); }, [booted, bird, router]);   // bird-detail.js:21

  if (!booted || !bird) return <section className={s.screen}><Loading /></section>;

  const ring = primaryRing(bird); const yy = seasonYY(bird);
  const title = bird.name || ring || id.slice(0, 8);
  const depth = +((st.settings as Record<string, unknown>).coiDepth || 10);
  const coi = (inbreeding(getBird, id, depth) as { coi: number }).coi;
  const avk = ancestorLoss(getBird, id, 5) as { avk: number; completeness: number };
  const sire = bird.sireId ? getBird(bird.sireId) : null; const dam = bird.damId ? getBird(bird.damId) : null;
  const loft = bird.loftId ? (st.lofts.get(bird.loftId) as { name?: string } | undefined) : null;
  const results = ([...st.raceResults.values()] as Race[]).filter((r) => r.birdId === id).sort(byDateDesc);
  const events = ([...st.healthEvents.values()] as HealthEvent[]).filter((e) => e.birdId === id || (e.wholeLoft && e.loftId === bird.loftId)).sort(byDateDesc);
  const offspring = ([...st.birds.values()] as Bird[]).filter((b) => b.sireId === id || b.damId === id).length;
  const pairs = ([...st.pairs.values()] as Pair[]).filter((p) => p.sireId === id || p.damId === id).length;
  const ownHealth = events.filter((e) => e.birdId === id).length;       // deleteBird removes these; whole-loft events stay

  // ── actions (vanilla's, behind the spec's ⋯ button) ──
  async function del() {
    setMenu(false);
    const kinds: string[] = [];
    if (offspring) kinds.push(t('kind.pedigree')); if (pairs) kinds.push(t('kind.pairs')); if (results.length) kinds.push(t('kind.races')); if (ownHealth) kinds.push(t('kind.health')); if (media.length) kinds.push(t('kind.media'));
    const n = offspring + pairs + results.length + ownHealth + media.length;
    const ok = await confirmDialog({ title: t('confirm.deleteBird.title'), who: { label: title, plate: ring || undefined },
      body: n ? t('confirm.deleteBird.body', { name: birdLabelText(bird), n: fmtNum(n), kinds: kinds.join('، ') }) : undefined,
      cancelLabel: t('act.cancel'), confirmLabel: t('act.delete'), confirmKind: 'danger' });
    if (!ok) return;
    const snapshot = await db.deleteBird(id);
    router.replace('/birds');
    undoToast(t('toast.deleted'), t('act.undo'), async () => { await db.restoreBird(snapshot); toast(t('toast.undone'), { kind: 'success' }); });
  }
  async function addSibling() {
    // bird-detail.js:44 — parents exist → prefill them; none → the form gets the INTENT (?siblingOf=) and commits it on save
    setMenu(false);
    if (bird!.sireId || bird!.damId) {
      const q: string[] = []; if (bird!.sireId) q.push('sire=' + bird!.sireId); if (bird!.damId) q.push('dam=' + bird!.damId);
      router.push('/bird/new?' + q.join('&')); return;
    }
    const ok = await confirmDialog({ title: t('bird.addSibling'), body: t('bird.siblingHint') + ' ' + t('bird.siblingNoParents'), cancelLabel: t('act.cancel'), confirmLabel: t('bird.createPlaceholders'), confirmKind: 'primary' });
    if (ok) router.push('/bird/new?siblingOf=' + id);
  }
  function share() {
    // bird-detail.js:83 with its defaults (races and media included); the include options are not designed on this screen — raised
    setMenu(false);
    db.exportBirdWithAncestry(id, { includeRaces: true, includeMedia: true }).then((payload: unknown) => {
      downloadJSON(payload, `zajil-bird-${ring.replace(/[^\w-]+/g, '_') || id.slice(0, 8)}.json`); toast(t('toast.exported'), { kind: 'success' });
      // db/io.js:237 rejects when an ancestor's photo metadata has no bytes on this device —
      // the ordinary state after a sync. Raised in the 4D report; a share that cannot be made
      // must say so rather than doing nothing.
    }).catch(() => toast(t('err.exportFailed'), { kind: 'error' }));
  }
  // bird-detail.js:233 — per-photo delete with undo (ruling 8: a capability the spec's silence does not remove)
  async function delMedia(m: Media) {
    const ok = await confirmDialog({ title: t('confirm.deleteGeneric'), cancelLabel: t('act.cancel'), confirmLabel: t('act.delete'), confirmKind: 'danger' });
    if (!ok) return;
    const snap = await db.deleteMedia(m.id);
    undoToast(t('toast.deleted'), t('act.undo'), async () => { if (!snap) return; await db.restoreMedia(snap); toast(t('toast.undone'), { kind: 'success' }); });
  }
  // bird-detail.js:189 — add a note through the write boundary (ruling 10: data entry must not be lost)
  async function addNote() {
    const text = noteText.trim(); if (!text) return;
    const copy = { ...bird!, notes: [...(bird!.notes || []), { id: db.uuid(), at: db.nowISO(), text }] };
    try { await db.saveBird(copy); setNoteText(''); } catch { toast(t('toast.saveFailed'), { kind: 'error' }); }
  }

  // ── pedigree tab data ──
  const gens = pedigreeGrid(getBird, id, 2) as Slot[][];
  const desc = descendantDepths(() => st.birds.values(), id) as Map<string, number>;
  // bird-detail.js:263-294 progenyAnalysis, verbatim in logic
  const direct = [...desc.entries()].filter(([, d]) => d === 1).length;
  const perBird = new Map<string, { results: number; wins: number; top10: number; velSum: number; velN: number; bestPos: number }>();
  for (const r of st.raceResults.values() as Iterable<Race>) {
    if (!desc.has(r.birdId) || r.raceType === 'training') continue;
    let x = perBird.get(r.birdId);
    if (!x) { x = { results: 0, wins: 0, top10: 0, velSum: 0, velN: 0, bestPos: Infinity }; perBird.set(r.birdId, x); }
    x.results++; const pos = +(r.position || 0);
    if (pos === 1) x.wins++; if (pos >= 1 && pos <= 10) x.top10++; if (pos >= 1 && pos < x.bestPos) x.bestPos = pos;
    if (r.velocity) { x.velSum += +r.velocity; x.velN++; }
  }
  let totResults = 0, totWins = 0, totTop10 = 0, velSum = 0, velN = 0;
  for (const x of perBird.values()) { totResults += x.results; totWins += x.wins; totTop10 += x.top10; velSum += x.velSum; velN += x.velN; }
  const ranked = [...perBird.entries()].sort((a, b) => b[1].wins - a[1].wins || b[1].top10 - a[1].top10 || b[1].results - a[1].results).slice(0, 5);

  // ── races tab data ──
  const best = results.filter((r) => r.position && r.position >= 1).sort((a, b) => (a.position! - b.position!) || byDateDesc(a, b))[0];
  const seasons = new Map<number, Race[]>();
  for (const r of results) { const sy = seasonStart(r.date || ''); (seasons.get(sy) ?? seasons.set(sy, []).get(sy)!).push(r); }
  const elig = birdEligibility(bird, results) as { hasRing: boolean; qualifyingResults: unknown[] };   // bird-detail.js:131 — one row in the races tab (ruling 10)
  const seasonList = [...seasons.entries()].sort((a, b) => b[0] - a[0]);
  const raceLabel = (r: Race) => r.releasePoint?.name || r.raceName || t('raceType.' + (r.raceType || 'training'));

  // ── health tab data ──
  const lastVac = events.filter((e) => e.eventType === 'vaccination' && e.date)[0];
  const evKind = (e: HealthEvent) => (e.eventType === 'treatment' || e.eventType === 'illness') ? s.treat : e.eventType === 'check' ? s.note : '';

  const Row = ({ k, v, data, tid }: { k: string; v: ReactNode; data?: boolean; tid: string }) => (
    <div className={s.row} data-testid={`row-${tid}`}><span className={s.k}>{k}</span><span className={`${s.v} ${data ? s.data : ''}`}>{v}</span></div>
  );
  const ParentRow = ({ k, b, tid }: { k: string; b: Bird | null | undefined; tid: string }) => (
    <div className={s.row} data-testid={`row-${tid}`}><span className={s.k}>{k}</span>
      {b ? <Link className={`${s.v} ${s.link}`} href={`/bird?id=${b.id}`}><bdi>{b.name || primaryRing(b) || b.id.slice(0, 8)}</bdi><Chev /></Link> : <span className={s.v}>—</span>}
    </div>
  );
  const Node = ({ slot, size, role }: { slot: Slot; size: 'n1' | 'n2' | 'n3'; role?: string }) => {
    const b = slot?.bird;
    if (!b) return <span className={`${s.node} ${s[size]}`} data-testid="mini-node">{role && <span className={s.role}>{role}</span>}<span className={`${s.nm} ${sh.muted}`}>{t('common.unknown')}</span></span>;
    const r = primaryRing(b);
    return (
      <Link className={`${s.node} ${s[size]}`} href={`/bird?id=${b.id}`} data-testid="mini-node">
        {role && <span className={s.role}>{role}</span>}<span className={s.nm}><bdi>{b.name || r || b.id.slice(0, 8)}</bdi></span>
        {size === 'n1' ? (r && <span className={`${s.plate} ${s.sm}`}><span className={s.season}>{seasonYY(b)}</span><span className={s.num}>{r}</span></span>) : <span className={s.rg}>{r}</span>}
      </Link>
    );
  };
  const Pill = ({ pos }: { pos: number }) => <span className={`${s.pill} ${pos <= 3 ? s.gold : pos <= 10 ? s.top : ''}`}>{fmtNum(pos, { group: false })}</span>;
  const coiPieces = t('profile.coiLine', { n: fmtNum(depth), c: fmtPercent(avk.completeness / 100, 0) }).split('{pct}');

  return (
    <section className={s.screen} onKeyDown={(e) => { if (e.key === 'Escape') setMenu(false); }}>
      <div className={s.herobg}><div className={s.wrap}>
        <div className={s.top}><div className={s.bar}>
          <Link href="/birds" className={s['icon-btn']} aria-label={t('act.back')} data-testid="back-link"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg></Link>
          <span className={s.crumb}>{t('nav.birds')}</span>
          <div className={s.menuwrap}>
            <button type="button" className={s['icon-btn']} aria-label={t('act.options')} aria-haspopup="menu" aria-expanded={menu} onClick={() => setMenu(!menu)} data-testid="options-menu">
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.3" /><circle cx="12" cy="12" r="1.3" /><circle cx="19" cy="12" r="1.3" /></svg>
            </button>
            {menu && (
              <div className={s.menu} role="menu" data-testid="menu">
                <button type="button" role="menuitem" onClick={() => router.push(`/bird/edit?id=${id}`)} data-testid="menu-edit">{t('act.edit')}</button>
                <button type="button" role="menuitem" onClick={addSibling} data-testid="menu-add-sibling">{t('bird.addSibling')}</button>
                <button type="button" role="menuitem" onClick={share} data-testid="menu-share">{t('act.share')}</button>
                <button type="button" role="menuitem" className={s.danger} onClick={del} data-testid="menu-delete">{t('act.delete')}</button>
              </div>
            )}
          </div>
        </div></div>
        <header className={s.hero} data-testid="profile-hero">
          <div>
            <div className={s['hero-row']}>
              <div className={s.avatar}><svg viewBox="0 0 100 100" fill="#fff" aria-hidden="true"><path d="M18 78c14 4 34 4 46-4 10-7 16-18 17-30 0-4-2-6-5-6-2 0-4 1-5 3l-4 8c-6 10-16 16-28 18-8 1-15 5-21 11z" /><path d="M62 34c3-6 9-9 15-8 3 0 5 2 5 5 0 2-1 3-3 4l-6 2c-4 2-8 1-11-3z" /><path d="M80 36l8 2-8 2z" /></svg></div>
              <div><h1 data-testid="hero-name"><bdi>{title}</bdi></h1>
                <div className={s.meta}>
                  <span className={`${s.tag} ${s.on}`} data-testid="meta-sex" data-sex={bird.sex || 'unknown'}>{t('sex.' + (bird.sex || 'unknown'))}</span>
                  {bird.external && <span className={s.tag}>{t('bird.externalShort')}</span>}
                  <span className={s.tag} data-testid="meta-status">{statusLabel(bird.status || '')}</span>
                </div>
              </div>
            </div>
            {ring && <div className={s.plate} data-testid="plate"><span className={s.season}>{yy}</span><span className={s.num}>{ring}</span></div>}
          </div>
          <div className={s['hero-actions']}>
            <Link href={`/bird/edit?id=${id}`} className={`${s.btn} ${s['btn-outline']}`} data-testid="hero-edit">{t('act.edit')}</Link>
            <Link href={`/cert?id=${id}`} className={`${s.btn} ${s['btn-primary']}`} data-testid="hero-cert">{t('act.certificate')}</Link>
          </div>
        </header>
      </div></div>

      <div className={s.wrap}>
        <SyncRow />
        <section className={s.tiles}>
          <div className={s.tile} data-testid="tile-coi"><div className={s.v}><COIValue coi={coi} mono={false} /></div><div className={s.k}>{t('tile.coi')}</div></div>
          <div className={s.tile} data-testid="tile-races"><div className={s.v}>{fmtNum(results.length)}</div><div className={s.k}>{t('tile.races')}</div></div>
          <div className={s.tile} data-testid="tile-hatch"><div className={s.v}>{bird.hatchDate ? bird.hatchDate.slice(0, 4) : '—'}</div><div className={s.k}>{t('tile.hatch')}</div></div>
        </section>
        <nav className={s.seg} role="tablist">
          {TABS.map(([k, key]) => <button key={k} type="button" role="tab" id={`t-${k}`} aria-selected={tab === k} aria-controls={`p-${k}`} onClick={() => setTab(k)} data-testid={`tab-${k}`}>{t(key)}</button>)}
        </nav>

        <section className={s.panel} id="p-over" role="tabpanel" aria-labelledby="t-over" hidden={tab !== 'over'} data-testid="panel-over">
          <div className={s.notice} data-testid="verified-notice">
            <div className={s.t}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12l4 4L19 7" /></svg>{t('profile.verified.title')}</div>
            <p>{t('profile.verified.body', { since: fmtDate(bird.createdAt) })}</p>
          </div>
          <div className={s.two}>
            <div className={s.card}>
              <h2>{t('bird.photos')} <span className={s.cnt}>{fmtNum(media.length)}</span></h2>
              {media.length === 0 ? <p className={sh.muted}>{t('common.none')}</p> : (
                <div className={s.gal} data-testid="gallery">
                  {media.map((m) => (
                    <div key={m.id} className={s.phwrap} data-testid="media-tile">
                      {!m.hasBlob ? <MediaPlaceholder kind={m.kind === 'photo' ? 'photo' : 'file'} filename={m.name} />
                        : !urls[m.id] ? <div className={s.ph} />
                        : m.kind === 'photo' ? <div className={`${s.ph} ${s.img}`} role="img" aria-label={`${t('media.photo')} — ${t('photo.' + (m.subtype || 'other'))}`} data-testid="media-photo"><img src={urls[m.id]} alt={`${t('media.photo')} — ${t('photo.' + (m.subtype || 'other'))}`} loading="lazy" /><span>{m.name}</span></div>
                        : <a className={`${s.ph} ${s.img}`} href={urls[m.id]} download={m.name || 'document'} data-testid="media-file">📄<span>{m.name || 'document'}</span></a>}
                      <button type="button" className={s.del} aria-label={t('act.delete')} onClick={() => delMedia(m)} data-testid="media-delete">✕</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className={s.card}>
              <h2>{t('profile.basics')}</h2>
              <div className={s.rows} data-testid="basics">
                <Row k={t('set.loft')} v={loft?.name || '—'} tid="loft" />   {/* vanilla's only «اللوفت» label */}
                <Row k={t('bird.colour')} v={bird.colour || '—'} tid="colour" />
                <Row k={t('bird.hatchDate')} v={fmtDate(bird.hatchDate)} data tid="hatch" />
                <ParentRow k={t('bird.sire')} b={sire} tid="sire" />
                <ParentRow k={t('bird.dam')} b={dam} tid="dam" />
                <Row k={t('profile.added')} v={fmtDate(bird.createdAt)} data tid="added" />
                {/* vanilla's remaining facts (bird-detail.js:108) in the spec's row grammar, shown when recorded */}
                {(bird.rings || []).length > 0 && <Row k={t('bird.rings')} v={(bird.rings || []).map((r, i) => <span key={i} style={{ display: 'block' }}><span className={sh.mono}>{r.raw}</span> <span className={s.tag}>{t('ringType.' + r.type)}</span></span>)} tid="rings" />}
                {bird.strain && <Row k={t('bird.strain')} v={<bdi>{bird.strain}</bdi>} tid="strain" />}
                {bird.eyeSign && <Row k={t('bird.eyeSign')} v={<bdi>{bird.eyeSign}</bdi>} tid="eye" />}
                {bird.breeder && <Row k={t('bird.breeder')} v={<bdi>{bird.breeder}</bdi>} tid="breeder" />}
                {bird.owner && <Row k={t('bird.owner')} v={<bdi>{bird.owner}</bdi>} tid="owner" />}
                {bird.acquiredFrom && <Row k={t('bird.acquiredFrom')} v={<><bdi>{bird.acquiredFrom}</bdi>{bird.acquiredDate ? ' · ' + fmtDate(bird.acquiredDate) : ''}</>} tid="acquired" />}
              </div>
            </div>
          </div>
          <div className={s.card} data-testid="notes">
            <h2>{t('common.notes')}</h2>
            {(bird.notes || []).length === 0 ? <p className={sh.muted}>{t('common.none')}</p>
              : [...(bird.notes || [])].sort((a, b) => (b.at || '').localeCompare(a.at || '')).map((n, i) => <p key={n.id || i} className={s.prose} data-testid="note"><span className={sh.muted}>{fmtDate(n.at, { withTime: true })} — </span><bdi>{n.text}</bdi></p>)}
            <div className={s.noteform}>
              <textarea rows={2} value={noteText} onChange={(e) => setNoteText(e.target.value)} aria-label={t('bird.addNote')} data-testid="note-input" />
              <button type="button" className={`${sh.btn} ${sh.save}`} onClick={addNote} disabled={!noteText.trim()} data-testid="note-add">+ {t('bird.addNote')}</button>
            </div>
          </div>
        </section>

        <section className={s.panel} id="p-ped" role="tabpanel" aria-labelledby="t-ped" hidden={tab !== 'ped'} data-testid="panel-ped">
          <p className={s.pnote} data-testid="coi-line">{coiPieces[0]}<strong><COIValue coi={coi} mono={false} /></strong>{coiPieces[1]}</p>
          <p className={s.pnote}>{t('ped.avk')}: <strong>{fmtPercent(avk.avk / 100, 1)}</strong></p>
          <div className={s.card}>
            <div className={s.mini}>
              <div className={s.gen}><Node slot={gens[0][0]} size="n1" /></div>
              <div className={s.gen}><div className={s.pair}>
                <div className={s.slot}><Node slot={gens[1][0]} size="n2" role={t('bird.sire')} /></div>
                <div className={s.slot}><Node slot={gens[1][1]} size="n2" role={t('bird.dam')} /></div>
              </div></div>
              <div className={s.gen}>
                <div className={s.pair}><div className={s.slot}><Node slot={gens[2][0]} size="n3" /></div><div className={s.slot}><Node slot={gens[2][1]} size="n3" /></div></div>
                <div className={s.pair}><div className={s.slot}><Node slot={gens[2][2]} size="n3" /></div><div className={s.slot}><Node slot={gens[2][3]} size="n3" /></div></div>
              </div>
            </div>
            <Link href={`/pedigree?id=${id}`} className={s.pbtn} data-testid="full-tree-link">{t('profile.fullTree')}<Chev /></Link>
          </div>
          <div className={s.card} data-testid="progeny">
            <h2>{t('prog.title')}</h2>
            {!desc.size ? <p className={sh.muted}>{t('prog.noProgeny')}</p> : (
              <>
                <div className={s.rows}>
                  <Row k={t('prog.offspringCount')} v={fmtNum(direct)} data tid="prog-direct-r" />
                  <Row k={t('prog.descendants')} v={fmtNum(desc.size)} data tid="prog-desc" />
                  <Row k={t('prog.raced')} v={fmtNum(perBird.size)} data tid="prog-raced" />
                  <Row k={t('prog.totalResults')} v={fmtNum(totResults)} data tid="prog-results" />
                  <Row k={t('prog.wins')} v={fmtNum(totWins)} data tid="prog-wins" />
                  <Row k={t('prog.top10')} v={fmtNum(totTop10)} data tid="prog-top10" />
                  <Row k={t('prog.avgVelocity')} v={velN ? fmtNum(velSum / velN, { dp: 0 }) + ' ' + t('race.mpm') : '—'} data tid="prog-vel" />
                </div>
                <span hidden data-testid="prog-direct">{fmtNum(direct)}</span>
                {ranked.length > 0 && (
                  <>
                    <p className={s.pnote} style={{ marginTop: 18 }}>{t('prog.bestPerformers')}</p>
                    <div className={s.rows}>
                      {ranked.map(([bid, x]) => (
                        <div key={bid} className={s.row} data-testid="prog-best">
                          <span className={s.k}><Link href={`/bird?id=${bid}`}><BirdLabel bird={getBird(bid)} /></Link></span>
                          <span className={s.v}>{`${t('prog.wins')}: ${fmtNum(x.wins)} · ${t('prog.top10')}: ${fmtNum(x.top10)} · ${t('prog.totalResults')}: ${fmtNum(x.results)}`}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </section>

        <section className={s.panel} id="p-race" role="tabpanel" aria-labelledby="t-race" hidden={tab !== 'race'} data-testid="panel-race">
          <div className={s.card} data-testid="fci-row"><div className={s.rows}>
            <div className={s.row}><span className={s.k}>{t('fci.qualifying')}</span><span className={`${s.v} ${s.data}`}>{fmtNum(elig.qualifyingResults.length)} / {fmtNum(results.length)}</span></div>
          </div></div>
          {results.length === 0 ? <div className={s.card}><p className={sh.muted}>{t('race.noRaces')}</p></div> : (
            <>
              {best && (
                <div className={s.best} data-testid="race-best">
                  <div>
                    <div className={s.t}>{t('race.best')}</div>
                    <div className={s.r}><bdi>{raceLabel(best)}</bdi></div>
                    <div className={s.m}>{t('race.kmMpm', { km: best.distanceKm ? fmtNum(best.distanceKm, { dp: 0 }) : '—', mpm: best.velocity ? fmtNum(best.velocity, { dp: 0 }) : '—' })}</div>
                  </div>
                  <div className={s.rank}>{fmtNum(best.position!, { group: false })}{best.birdsEntered ? <small>/ {fmtNum(best.birdsEntered, { group: false })}</small> : null}</div>
                </div>
              )}
              {seasonList.map(([sy, rs]) => (
                <div key={sy} className={s.card} data-testid="season-card">
                  <h2>{sy ? t('loft.season', { a: sy, b: sy + 1 }) : '—'} <span className={s.cnt}>{fmtNum(rs.length)}</span></h2>
                  <div className={s.table}><table>
                    <thead><tr><th>{t('col.release')}</th><th className={s.num}>{t('race.km')}</th><th className={s.num}>{t('race.mpm')}</th><th className={s.num}>{t('race.position')}</th></tr></thead>
                    <tbody>{rs.map((r) => (
                      <tr key={r.id} data-testid="race-row">
                        <td><bdi>{raceLabel(r)}</bdi><span className={s.d}><bdi>{fmtDate(r.date)}</bdi></span></td>
                        <td className={s.num}>{r.distanceKm ? fmtNum(r.distanceKm, { dp: 0 }) : '—'}</td>
                        <td className={s.num}>{r.velocity ? fmtNum(r.velocity, { dp: 0 }) : '—'}</td>
                        <td className={s.num}>{r.position ? <Pill pos={r.position} /> : '—'}</td>
                      </tr>
                    ))}</tbody>
                  </table></div>
                </div>
              ))}
            </>
          )}
        </section>

        <section className={s.panel} id="p-hlth" role="tabpanel" aria-labelledby="t-hlth" hidden={tab !== 'hlth'} data-testid="panel-hlth">
          {lastVac && (
            <div className={s.nxt} data-testid="health-next">
              <div><div className={s.k}>{t('health.next')}</div><div className={s.t}><bdi>{lastVac.medication || t('health.vaccination')}</bdi></div><div className={s.k}>{t('health.next.estimate')}</div></div>
              <span className={s.d}><bdi>{fmtDate(plus365(lastVac.date!))}</bdi></span>
            </div>
          )}
          <div className={s.card} data-testid="health-log">
            <h2>{t('bird.healthLog')} <span className={s.cnt}>{fmtNum(events.length)}</span></h2>
            {events.length === 0 ? <p className={sh.muted}>{t('health.noEvents')}</p> : (
              <div className={s.tl}>
                {events.map((e) => (
                  <div key={e.id} className={`${s.ev} ${evKind(e)}`} data-testid="health-event" data-type={e.eventType}>
                    {/* dates in <bdi>: the spec's .d is direction:ltr for its numeric mock dates; vanilla fmtDate carries Arabic month names */}
                    <div className={s.h}><div className={s.t}><bdi>{e.medication || t('health.' + e.eventType)}</bdi></div><span className={s.d}><bdi>{fmtDate(e.date)}</bdi></span></div>
                    {e.notes && <div className={s.n}><bdi>{e.notes}</bdi></div>}
                    <span className={`${s.kind} ${evKind(e)}`}>{t('health.' + e.eventType)}</span>
                    {e.wholeLoft && <span className={`${s.kind} ${s.note}`}>{t('health.wholeLoft')}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>

      <div className={s['cta-wrap']} data-bottom-chrome="cta"><Link href={`/cert?id=${id}`} className={s.cta} data-testid="cta-cert">{t('act.certificate')}</Link></div>
    </section>
  );
}
