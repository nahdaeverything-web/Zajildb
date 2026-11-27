'use client';
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import * as db from '@/src/db.js';
import { useZajilStore, selectBird, useMediaForBird } from '@/src/db/react';
import { t, fmtDate, fmtNum, fmtPercent, getLang, configure } from '@/src/i18n.ext.js';
import { pedigreeGrid } from '@/src/engine/pedigree.js';
import { todayISO } from '@/src/dates.js';
import { inbreeding } from '@/src/engine/coi.js';
import { Loading, toast, downloadJSON, downscaleImage, storedName, storePicked, primaryRing, birdLabelText, placeholderName, initDB } from '@/src/components';
import s from './cert.module.css';

// Certificate — design/approved/certificate-v1.html, wiring from js/views/cert.js.
//
// The spec's own shape: an options panel on the start side and a scaled preview, with
// four controls — A4 / 9:16, three depths, the CONTENT language (independent of the app
// language, as vanilla's cert.js already had it), and per-photo switches — plus the loft
// branding block that RULING 2's new fields feed, a QR slot, and the print rules.
//
// Design-review scaffolding NOT carried: the strip of three photo-state variants (v0/v1/v3)
// and the mock toast; both are how the prototype shows its states side by side.
//
// RULED at 4D acceptance: the spec's head prints a certificate number («ZJ-2026-00417»)
// and the port does not render it. A number implies an authority that can verify it, and
// Zajil has no register, so inventing one would be a claim the record cannot back. The
// cell is out, and the story rule that hid it (`.head .meta > div:first-child`) went with
// it. The number and the QR slot are RESERVED FOR A FUTURE VERIFICATION SURFACE: when a
// public bird page exists, it is the thing a number would point at.
// RULED at 4D acceptance: «مشاركة» keeps the app's ONE share, the profile's export
// (bird-detail.js:83). Real PDF and 9:16 image generation is a post-port feature, and the
// QR / public-page surface is its natural companion — the commit that can render this
// sheet to a file is the one that can give it a URL.

type Bird = {
  id: string; mainPhotoId?: string; name?: string; sex?: string; hatchDate?: string; colour?: string; strain?: string;
  sireId?: string | null; damId?: string | null; createdAt?: string; rings?: Array<{ raw?: string; year?: string | number }>;
};
type Slot = { id: string; bird: Bird | null } | null;
type Loft = { id: string; name?: string; location?: string; breederName?: string; phone?: string; website?: string; logoMediaId?: string | null };
type Media = { id: string; kind?: string; subtype?: string; name?: string; hasBlob?: boolean };
const Lofts = db.Lofts as { save: (l: Loft) => Promise<Loft> };
const SIZE: Record<string, [number, number]> = { a4: [1123, 794], story: [405, 720] };
const GEN_LABEL = ['', 'ped.gen.subject', 'ped.gen.parents', 'ped.gen.grand', 'ped.gen.great', 'ped.gen.fifth'];
const COUNTS: Record<number, number> = { 2: 2, 3: 4, 4: 8, 5: 16 };
// the spec styles only some of the per-generation classes (.g1, .g4, .g5, .r1, .r4, .r5,
// .b2...b5); the rest exist only as hooks, so an absent one must not print as "undefined"
const cx = (...xs: Array<string | undefined | null | false>) => xs.filter(Boolean).join(' ');

/**
 * Render `fn` with the dictionary switched to the certificate's own language, then put the
 * app language back — js/views/cert.js:44. i18n keeps the locale in module state, so this
 * is the only way to say one thing in Arabic while the app is in English. JSX children are
 * built eagerly, so every t() inside has already run by the time this returns.
 */
function withLang<T>(lang: string, fn: () => T): T {
  const ui = getLang();
  if (lang === ui) return fn();
  configure({ lang });
  try { return fn(); } finally { configure({ lang: ui }); }
}

const MARK = (
  <svg viewBox="0 0 100 100" fill="#fff" aria-hidden="true">
    <path d="M18 78c14 4 34 4 46-4 10-7 16-18 17-30 0-4-2-6-5-6-2 0-4 1-5 3l-4 8c-6 10-16 16-28 18-8 1-15 5-21 11z" />
    <path d="M62 34c3-6 9-9 15-8 3 0 5 2 5 5 0 2-1 3-3 4l-6 2c-4 2-8 1-11-3z" />
    <path d="M80 36l8 2-8 2z" />
  </svg>
);
const AWAY_ICON = (
  <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M12 17h.01" /></svg>
);

export default function CertView() {
  const params = useSearchParams();
  const router = useRouter();
  const id = params.get('id') || '';
  const [booted, setBooted] = useState(false);
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  const bird = useZajilStore(selectBird(id)) as Bird | null;
  const st = useZajilStore((x) => x);
  const loft = db.currentLoft() as Loft | null;

  // the spec's own default: a phone opens on the 9:16 sheet, anything wider on A4. The
  // query is READ IN THE INITIALISER, not assigned from a mount effect: an effect that only
  // seeds state from the environment buys a second render and a visible A4-then-story flip
  // for nothing (and trips react-hooks/set-state-in-effect). `typeof window` is the guard
  // Preview's `phone` already uses — this subtree only ever renders in the browser, because
  // useSearchParams() bails the static export out to the page's Suspense boundary, but the
  // build must not reach for matchMedia even so.
  const [format, setFormat] = useState<'a4' | 'story'>(() =>
    typeof window !== 'undefined' && matchMedia('(max-width:700px)').matches ? 'story' : 'a4');
  const [depth, setDepth] = useState(5);
  // vanilla: the certificate starts in the app's language and can then be switched. The
  // start value is READ below the boot guard rather than seeded by an effect — getLang()
  // only says anything once initDB has configured i18n, and everything past that guard is
  // after it. So the state here is the PICK: empty means «no explicit choice yet», which
  // reads as the app language, not as «no language».
  const [langPick, setLangPick] = useState<string>('');
  const [photos, setPhotos] = useState({ bird: false, sire: false, dam: false });
  const [brand, setBrand] = useState(true);
  const [zoom, setZoom] = useState<number | 'fit' | null>(null);

  useEffect(() => { if (booted && id && !bird) router.replace('/birds'); }, [booted, id, bird, router]);
  if (!booted || !bird) return <section className={s.screen}><Loading /></section>;

  const lang = langPick || getLang();

  return (
    <CertScreen
      bird={bird} loft={loft} st={st} lang={lang || 'ar'}
      format={format} setFormat={setFormat} depth={depth} setDepth={setDepth} setLang={setLangPick}
      photos={photos} setPhotos={setPhotos} brand={brand} setBrand={setBrand}
      zoom={zoom} setZoom={setZoom} router={router}
    />
  );
}

type ScreenProps = {
  bird: Bird; loft: Loft | null; st: Record<string, unknown>; lang: string;
  format: 'a4' | 'story'; setFormat: (f: 'a4' | 'story') => void;
  depth: number; setDepth: (n: number) => void; setLang: (l: string) => void;
  photos: { bird: boolean; sire: boolean; dam: boolean }; setPhotos: (p: { bird: boolean; sire: boolean; dam: boolean }) => void;
  brand: boolean; setBrand: (b: boolean) => void;
  zoom: number | 'fit' | null; setZoom: (z: number | 'fit' | null) => void;
  router: ReturnType<typeof useRouter>;
};

function CertScreen(p: ScreenProps) {
  const { bird, loft, format, depth, lang, photos, brand } = p;
  const getBird = db.getBird as (id: string) => Bird | null;
  // pedigreeGrid indexes from the SUBJECT: grid[0] is the bird, grid[1] the parents
  // (engine/pedigree.js:91). The certificate counts the subject as generation 1, so the
  // ruler's generation g reads grid[g - 1], and four ancestor rows reach generation 5.
  const grid = pedigreeGrid(getBird, bird.id, 4) as Slot[][];
  const sire = bird.sireId ? getBird(bird.sireId) : null;
  const dam = bird.damId ? getBird(bird.damId) : null;

  // photo state per slot — the metadata says whether the bytes are on THIS device
  const mBird = useMediaForBird(bird.id) as Media[];
  const mSire = useMediaForBird(bird.sireId || null) as Media[];
  const mDam = useMediaForBird(bird.damId || null) as Media[];
  // E5 (RULED 2026-11-24): each box draws THAT BIRD'S MAIN PHOTO — the one its `mainPhotoId` names, else its earliest
  // (the layer's rule, mainPhotoOf). It used to be "the first photo" of a list that came back in the order of a random id.
  const mainPhoto = (rows: Media[], of: Bird | null | undefined) => (of ? (db.mainPhotoOf(rows, of.mainPhotoId) as Media | null) : null);
  const slots = {
    bird: { bird, media: mainPhoto(mBird, bird), label: t('ped.gen.subject') },
    sire: { bird: sire, media: mainPhoto(mSire, sire), label: t('bird.sire') },
    dam: { bird: dam, media: mainPhoto(mDam, dam), label: t('bird.dam') },
  };

  // object URLs for whatever bytes this device actually holds
  const [urls, setUrls] = useState<Record<string, string>>({});
  const logoId = loft?.logoMediaId || '';
  useEffect(() => {
    let live = true; const made: string[] = [];
    const wanted = [mainPhoto(mBird, bird), mainPhoto(mSire, sire), mainPhoto(mDam, dam)]
      .filter((m): m is Media => !!m && !!m.hasBlob).map((m) => m.id);
    if (logoId) wanted.push(logoId);
    Promise.all(wanted.map(async (mid) => {
      const row = (await db.idbGet('media', mid)) as { blob?: Blob } | undefined;
      if (!row || !row.blob) return null;
      const u = URL.createObjectURL(row.blob); made.push(u); return [mid, u] as const;
    })).then((pairs) => {
      if (!live) { made.forEach((u) => URL.revokeObjectURL(u)); return; }
      setUrls(Object.fromEntries(pairs.filter(Boolean) as Array<readonly [string, string]>));
    });
    return () => { live = false; made.forEach((u) => URL.revokeObjectURL(u)); };
  }, [mBird, mSire, mDam, logoId]);

  return (
    <section className={s.screen} data-testid="cert-screen">
      <Panel key={loft?.id || 'none'} {...p} slots={slots} urls={urls} />
      <Preview {...p} grid={grid} slots={slots} urls={urls} />
      {p.zoom !== null && <Zoom {...p} grid={grid} slots={slots} urls={urls} />}
      {/* the spec's own mechanism, restored: a <style> element whose text is the @page rule
          for the format on screen (certificate-v1.html:303, rewritten at :504). A CSS Module
          cannot hold @page, and a page box has nothing to scope to. */}
      <style data-testid="pagesize">{format === 'a4'
        ? '@page{ size:A4 landscape; margin:0; }'
        : '@page{ size:108mm 192mm; margin:0; }'}</style>
      <style data-testid="print-isolation">{PRINT_ISOLATION}</style>
      <span hidden data-testid="state-probe" data-format={format} data-depth={depth} data-lang={lang}
        data-brand={brand ? 'on' : 'off'} data-photos={`${photos.bird ? 1 : 0}${photos.sire ? 1 : 0}${photos.dam ? 1 : 0}`} />
    </section>
  );
}

// ───────────────────────────────────────────────────────── options panel
type SlotMap = Record<'bird' | 'sire' | 'dam', { bird: Bird | null; media: Media | null; label: string }>;

// Declared at MODULE SCOPE deliberately. A component declared inside another component's
// render body is a brand-new component type on every render, so React unmounts its DOM and
// mounts a fresh subtree each time: a text field inside one loses the caret after a single
// keystroke, and even a subtree without a field is dozens of pointless remounts per render
// (eslint: react-hooks/static-components). Everything it used to close over now arrives as
// a prop — the CSS module `s` is module state already, so it needs no passing.
function Seg({ label, hint, value, options, onPick, testid }: {
  label: string; hint?: string; value: string; options: Array<[string, ReactNode]>;
  onPick: (v: string) => void; testid: string;
}) {
  return (
    <div className={s.sec} data-testid={`sec-${testid}`}>
      <div className={s.lab}>{label}{hint && <span className={s.hint}>{hint}</span>}</div>
      <div className={s.seg} role="group" aria-label={label}>
        {options.map(([v, node]) => (
          <button key={v} type="button" className={value === v ? s.on : undefined} aria-pressed={value === v}
            onClick={() => onPick(v)} data-testid={`${testid}-${v}`}>{node}</button>
        ))}
      </div>
    </div>
  );
}

function Panel(p: ScreenProps & { slots: SlotMap; urls: Record<string, string> }) {
  const { bird, loft, format, depth, lang, photos, brand, slots, urls } = p;
  const [f, setF] = useState({
    name: loft?.name || '', breederName: loft?.breederName || '', phone: loft?.phone || '', website: loft?.website || '',
  });
  const fileIn = useRef<HTMLInputElement>(null);
  const logoIn = useRef<HTMLInputElement>(null);
  const [picking, setPicking] = useState<'bird' | 'sire' | 'dam'>('bird');

  // the panel edits the ONE loft record — «من إعدادات اللوفت · تُعدَّل قبل الطباعة» — so a
  // change here is the same change the الأدوات card makes, through the same Lofts.save
  async function saveLoft(next: Partial<Loft>) {
    if (!loft) return;
    await Lofts.save({ ...loft, ...next });
  }
  async function pickPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = '';
    const target = slots[picking].bird;
    // G1 (RULED 2026-11-25): a placeholder parent takes no photo here — the button is disabled and the slot says why
    if (!file || !target || db.isPlaceholder(target)) return;
    // E5 (RULED 2026-11-24): the photo is stored AND made that bird's main photo, in one transaction — so the box
    // always changes to it. Until then «تغيير» only added a photo, and the box kept drawing whichever had the lowest id.
    await storePicked(target.id, { kind: 'photo', subtype: 'body', file }, { main: true });
    p.setPhotos({ ...photos, [picking]: true });
  }
  async function pickLogo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = '';
    if (!file || !loft) return;
    const out = await downscaleImage(file);
    const m = await db.addMedia(loft.id, 'document', 'logo', storedName(file, out), out) as { id: string };
    await saveLoft({ logoMediaId: m.id });
  }
  function share() {
    // the app's one share — the profile's export (bird-detail.js:83). A PDF or a 9:16 image
    // is what the spec's button implies and what the app cannot make yet; raised.
    //
    // The catch is not decoration. LAYER DEFECT, raised in the 4D report: with
    // includeMedia, exportBirdWithAncestry reads every media row through
    // blobToDataURL (db/io.js:237), and a row whose bytes are on ANOTHER device has no
    // blob — which is the ordinary state after a sync (SYNC-DESIGN §7: metadata syncs,
    // blobs do not). readAsDataURL(undefined) throws, so the whole share rejects. The fix
    // belongs in js/db/io.js, outside next/; until then a share that cannot be made says
    // so instead of doing nothing at all.
    // RF-4 (RULED 2026-11-16): the share now carries what this device has and says how many photos it does not
    let missing = 0;
    db.exportBirdWithAncestry(bird.id, { includeRaces: true, includeMedia: true, onMissing: (n: number) => { missing = n; } }).then((payload: unknown) => {
      downloadJSON(payload, `zajil-cert-${(primaryRing(bird) || bird.id.slice(0, 8)).replace(/[^\w-]+/g, '_')}.json`);
      toast(t('toast.exported') + (missing ? ' ' + t('backup.mediaNotHere', { n: fmtNum(missing) }) : ''), { kind: 'success', timeout: missing ? 7000 : undefined });
    }).catch(() => toast(t('err.exportFailed'), { kind: 'error' }));
  }

  return (
    <aside className={s.panel} data-testid="panel">
      <div className={s.top}>
        <button type="button" className={s['icon-btn']} aria-label={t('act.back')} onClick={() => p.router.push(`/bird?id=${bird.id}`)} data-testid="back">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
        </button>
        <div>
          <div className={s.ttl}>{t('cert.title')}</div>
          <div className={s.crumb} data-testid="crumb"><bdi>{birdLabelText(bird)}</bdi><span className={s.mono}>{primaryRing(bird)}</span></div>
        </div>
      </div>

      <div className={s.opts}>
        <Seg testid="format" label={t('cert.format')} value={format} onPick={(v) => p.setFormat(v as 'a4' | 'story')}
          options={[['a4', t('cert.format.a4')], ['story', <>{t('cert.format.story')}<span className={s.mono}>9:16</span></>]]} />
        <Seg testid="depth" label={t('ped.generations')} value={String(depth)} onPick={(v) => p.setDepth(+v)}
          options={[3, 4, 5].map((g) => [String(g), <span key={g} className={s.mono}>{fmtNum(g)}</span>] as [string, ReactNode])} />
        <Seg testid="lang" label={t('cert.contentLang')} hint={t('cert.contentLangHint')} value={lang} onPick={p.setLang}
          options={[['ar', t('lang.ar')], ['en', t('lang.en')]]} />

        <div className={s.sec} data-testid="sec-photos">
          <div className={s.lab}>{t('bird.photos')}<span className={s.hint}>{t('cert.photosHint')}</span></div>
          <div className={s.card}>
            {(['bird', 'sire', 'dam'] as const).map((who) => {
              const slot = slots[who];
              const away = !!slot.media && !slot.media.hasBlob;
              const on = photos[who];
              const url = slot.media && slot.media.hasBlob ? urls[slot.media.id] : '';
              // G1 (RULED 2026-11-25): a PLACEHOLDER parent's slot accepts no file. Having a photo of the parent means
              // knowing the bird: the way out is to give it a name or a ring first, which makes it an ordinary bird. A
              // placeholder that already holds a photo (made before this rule) keeps it, and its box still draws it.
              const ph = !!slot.bird && db.isPlaceholder(slot.bird);
              return (
                <div key={who} className={`${s.row} ${on ? '' : s.off} ${away ? s['away-row'] : ''}`} data-testid={`row-${who}`}>
                  <button type="button" className={`${s.sw} ${on ? s.on : ''}`} aria-pressed={on}
                    aria-label={t('cert.photoOf', { n: slot.label })} disabled={!slot.bird}
                    onClick={() => p.setPhotos({ ...photos, [who]: !on })} data-testid={`sw-${who}`} />
                  <div className={`${s.thumb} ${slot.media ? '' : s.empty}`} data-testid={`thumb-${who}`}>
                    {url ? <img src={url} alt="" /> : <span>{away ? '' : who}</span>}
                  </div>
                  <div className={s.tx}>
                    <div className={s.t}>{slot.label} · <bdi data-testid={`who-${who}`}>{!slot.bird ? t('common.unknown') : db.isPlaceholder(slot.bird) ? placeholderName(slot.bird, who === 'bird' ? 'text' : 'box') : birdLabelText(slot.bird)}</bdi></div>
                    <div className={s.d} data-testid={`d-${who}`} id={`d-${who}`}>
                      {ph ? t('cert.placeholderPhoto') : away ? <>{AWAY_ICON}{t('cert.photoAway')}</> : slot.media ? t('cert.fromBird') : t('cert.noPhoto')}
                    </div>
                  </div>
                  <button type="button" className={s.pick} disabled={!slot.bird || ph} aria-describedby={ph ? `d-${who}` : undefined}
                    onClick={() => { setPicking(who); fileIn.current?.click(); }} data-testid={`pick-${who}`}>
                    {away ? t('cert.pickHere') : slot.media ? t('act.change') : t('cert.pickPhoto')}
                  </button>
                </div>
              );
            })}
          </div>
          <input ref={fileIn} type="file" accept="image/*" onChange={pickPhoto} data-testid="photo-input" />
        </div>

        <div className={s.sec} data-testid="sec-brand">
          <div className={s.lab}>{t('cert.loftData')}<span className={s.hint}>{t('cert.loftDataHint')}</span></div>
          <div className={s.card}>
            <div className={s.row}>
              <button type="button" className={`${s.sw} ${brand ? s.on : ''}`} aria-pressed={brand}
                aria-label={t('cert.showLoft')} onClick={() => p.setBrand(!brand)} data-testid="sw-brand" />
              <div className={s.tx}>
                <div className={s.t}>{t('cert.showLoft')}</div>
                <div className={s.d}>{t('cert.showLoftHint')}</div>
              </div>
            </div>
            {brand && (
              <div className={s.fields} data-testid="fields">
                <label><span>{t('set.loftName')}</span>
                  <input type="text" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })}
                    onBlur={() => saveLoft({ name: f.name.trim() })} data-testid="f-loft" /></label>
                <label><span>{t('set.breederName')}</span>
                  <input type="text" value={f.breederName} onChange={(e) => setF({ ...f, breederName: e.target.value })}
                    onBlur={() => saveLoft({ breederName: f.breederName.trim() })} data-testid="f-breeder" /></label>
                <label><span>{t('set.phone')}</span>
                  <input type="text" dir="ltr" className={s.mono} value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })}
                    onBlur={() => saveLoft({ phone: f.phone.trim() })} data-testid="f-phone" /></label>
                <label><span>{t('set.website')}</span>
                  <input type="text" dir="ltr" className={s.mono} value={f.website} onChange={(e) => setF({ ...f, website: e.target.value })}
                    onBlur={() => saveLoft({ website: f.website.trim() })} data-testid="f-site" /></label>
                <label className={s['logo-row']}><span>{t('set.logo')}</span>
                  <div className={s.thumb} data-testid="thumb-logo">
                    {loft?.logoMediaId && urls[loft.logoMediaId] ? <img src={urls[loft.logoMediaId]} alt="" /> : <span>logo</span>}
                  </div>
                  <button type="button" className={s.pick} onClick={() => logoIn.current?.click()} data-testid="pick-logo">{t('act.change')}</button>
                </label>
                <input ref={logoIn} type="file" accept="image/*" onChange={pickLogo} data-testid="logo-input" />
              </div>
            )}
          </div>
        </div>
      </div>

      <div className={s.cta} data-bottom-chrome="cert-cta">
        <button type="button" className={`${s.btn} ${s['btn-outline']}`} onClick={share} data-testid="share">{t('act.share')}</button>
        <button type="button" className={`${s.btn} ${s['btn-primary']}`} onClick={() => window.print()} data-testid="print">{t('act.print')}</button>
      </div>
    </aside>
  );
}

// ───────────────────────────────────────────────────────── preview + zoom
function useScaleToFit(format: 'a4' | 'story', deps: unknown[]) {
  const stage = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = stage.current; if (!el) return;
    const fit = () => {
      const sheet = el.firstElementChild as HTMLElement | null; if (!sheet) return;
      const phone = matchMedia('(max-width:700px)').matches;
      if (format === 'story' && phone) el.style.width = Math.min((el.parentElement?.clientWidth || 405) - 32, 405) + 'px';
      else el.style.width = '';
      const [w, h] = SIZE[format];
      const k = Math.min(1, el.clientWidth / w);
      el.style.height = h * k + 'px';
      sheet.style.transform = `scale(${k})`;
    };
    fit();
    addEventListener('resize', fit);
    return () => removeEventListener('resize', fit);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [format, ...deps]);
  return stage;
}

function Preview(p: ScreenProps & { grid: Slot[][]; slots: SlotMap; urls: Record<string, string> }) {
  const { format, depth, lang, photos, brand } = p;
  const stage = useScaleToFit(format, [depth, lang, photos, brand, p.urls]);
  const phone = typeof window !== 'undefined' && matchMedia('(max-width:700px)').matches;
  return (
    <main className={s.preview}>
      <div className={s.cap} data-testid="cap">
        <span>
          <b>{t('cert.preview')}</b>{' '}
          {format === 'a4' ? `${t('cert.format.a4')} · ${t('cert.size.a4')}` : `${t('cert.format.story')} · ${t('cert.size.story')}`}
          {' · '}<span className={s.mono}>{fmtNum(depth)}</span>{' '}{t('cert.gensN', { n: '' }).replace('{n}', '').trim()}
        </span>
        {format === 'a4' && (
          <button type="button" className={s['zoom-btn']} onClick={() => p.setZoom(0.7)} data-testid="zoom-open">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.5-4.5M11 8v6M8 11h6" /></svg>
            {t('act.zoom')}
          </button>
        )}
      </div>
      <div className={`${s.stage} ${format === 'a4' && phone ? s.tappable : ''}`} ref={stage} data-testid="stage" data-format={format}
        onClick={() => { if (format === 'a4' && phone) p.setZoom(0.7); }}>
        <Sheet {...p} />
      </div>
    </main>
  );
}

function Zoom(p: ScreenProps & { grid: Slot[][]; slots: SlotMap; urls: Record<string, string> }) {
  const { format, lang, zoom } = p;
  const scroll = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const sc = scroll.current; if (!sc) return;
    const sheet = sc.firstElementChild as HTMLElement | null; if (!sheet) return;
    const [w, h] = SIZE[format];
    const k = zoom === 'fit' ? Math.min(1, (sc.clientWidth - 32) / w) : (zoom as number);
    sheet.style.transform = `scale(${k})`;
    sheet.style.marginBottom = h * k - h + 'px';
    sheet.style.marginInlineEnd = w * k - w + 'px';
  }, [format, zoom, lang]);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') p.setZoom(null); };
    addEventListener('keydown', esc);
    document.body.style.overflow = 'hidden';
    return () => { removeEventListener('keydown', esc); document.body.style.overflow = ''; };
  }, [p]);
  return (
    <div className={`${s.zoom} ${s.open}`} role="dialog" aria-label={t('cert.zoomTitle')} aria-modal="true" data-testid="zoom">
      <div className={s.zbar}>
        <button type="button" className={s['icon-btn']} aria-label={t('act.close')} onClick={() => p.setZoom(null)} data-testid="zoom-close">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
        </button>
        <div>
          <div className={s.zt}>{t('cert.zoomTitle')}</div>
          <div className={s.zh}>{t('cert.zoomHint')}</div>
        </div>
        <div className={s.zlvl}>
          {([1, 0.7, 'fit'] as const).map((z) => (
            <button key={String(z)} type="button" className={zoom === z ? s.on : undefined} onClick={() => p.setZoom(z)}
              data-testid={`zoom-${z}`}>{z === 'fit' ? t('cert.zoomFit') : `${z * 100}%`}</button>
          ))}
        </div>
      </div>
      <div className={`${s.zscroll} ${lang === 'en' ? s.en : ''}`} ref={scroll} data-testid="zscroll">
        <Sheet {...p} />
      </div>
    </div>
  );
}

// ───────────────────────────────────────────────────────── the sheet
/**
 * H3 (RULED 2026-11-27): what a box of the certificate prints for a bird — the title is its name when it has one,
 * otherwise its ring (otherwise the first 8 characters of its id, as birdLabelText); `ring` is the ring line, and it is
 * there only when the title is a name. A placeholder parent is printed by placeholderName() and never reaches this.
 */
function boxTitle(b: Bird): { title: string; ring: string } {
  const ring = primaryRing(b); const name = (b.name || '').trim();
  return name ? { title: name, ring } : { title: ring || b.id.slice(0, 8), ring: '' };
}
/**
 * H1 (RULED 2026-11-27): the sheet is the only thing on the printed page, at the page's origin. Measured before: the
 * shell's own layout reached the print — at a page width of 1123 px (A4 landscape) the ≥1100 px rule gives <main> the
 * rail's margin and its children a 960 px cap, so the 297 mm sheet started where the rail ends and its far side ran off
 * the page (fault a), and the sheet's bottom edge fell onto a second page (fault b). Global, because <main> and <body>
 * are not this module's; and in this <style> element, which exists only while the certificate is on screen.
 */
const PRINT_ISOLATION = '@media print{ html, body{ margin:0 !important; padding:0 !important; background:#fff !important; }'
  + ' main:has([data-testid=cert-screen]){ margin:0 !important; padding:0 !important; max-width:none !important; min-height:0 !important; border:none !important; }'
  + ' main:has([data-testid=cert-screen]) > *{ max-width:none !important; margin:0 !important; } }';

/**
 * H2 (RULED 2026-11-27): NO TEXT OVER OTHER TEXT, whatever the names. The sheet has a fixed size (297 × 210 mm, or
 * 405 × 720 px) and so a fixed room for each box; a long name, at five generations, needs more than its box has, and the
 * box grew over its neighbours (measured). So, after every layout: a box whose text does not fit has that text set
 * smaller, step by step, down to FIT_FLOOR of its size; past that the text is cut with «…» rather than drawn over the
 * next box. The subject's title the same, against the column it stands in. A name that fits is untouched. Layout only:
 * the sizes are those of the sheet itself, so the screen, the zoom and the printed page get the same result (H4).
 */
const FIT_FLOOR = 0.6;
/** the VISIBLE lines of text in `el`: each line box cut by every ancestor that hides its overflow (a designed «…») */
const rectsOf = (el: Element) => {
  const clips: DOMRect[] = [];
  for (let a: Element | null = el; a && !(a as HTMLElement).dataset?.testid?.startsWith('sheet'); a = a.parentElement) {
    const cs = getComputedStyle(a); if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') clips.push(a.getBoundingClientRect());
  }
  const r = document.createRange(); r.selectNodeContents(el);
  return [...r.getClientRects()].map((x) => clips.reduce((y, c) => new DOMRect(Math.max(y.left, c.left), Math.max(y.top, c.top), Math.min(y.right, c.right) - Math.max(y.left, c.left), Math.min(y.bottom, c.bottom) - Math.max(y.top, c.top)), x))
    .filter((x) => x.width > 0.5 && x.height > 0.5);
};
/** every line of text in `el` lies inside `box` (vertically with the 3 px a font's glyph box can stand past its line box) */
const textInside = (el: Element, box: DOMRect) => rectsOf(el).every((r) => r.left >= box.left - 0.5 && r.right <= box.right + 0.5 && r.top >= box.top - 3 && r.bottom <= box.bottom + 3);
const meets = (a: Element[], b: Element[]) => a.some((x) => rectsOf(x).some((r) => b.some((y) => rectsOf(y).some((q) => Math.min(r.right, q.right) - Math.max(r.left, q.left) > 1 && Math.min(r.bottom, q.bottom) - Math.max(r.top, q.top) > 1))));
function fitSheet(sheet: HTMLElement | null) {
  if (!sheet) return;
  sheet.querySelectorAll<HTMLElement>('[data-fit]').forEach((e) => { e.style.fontSize = ''; e.style.zoom = ''; e.removeAttribute('data-fit'); });
  sheet.querySelectorAll<HTMLElement>('[data-clip]').forEach((e) => e.removeAttribute('data-clip'));
  // each text's size as designed is read once; every step is a share of THAT size, never of a size already made smaller
  const base = new Map<HTMLElement, number>();
  const shrink = (texts: HTMLElement[], fits: () => boolean, floor = FIT_FLOOR) => {
    if (fits() || !texts.length) return true;
    texts.forEach((e) => { if (!base.has(e)) base.set(e, parseFloat(getComputedStyle(e).fontSize)); });
    const now = texts.map((e) => parseFloat(getComputedStyle(e).fontSize));
    for (let k = 0.92; k >= floor - 1e-9; k -= 0.04) {
      texts.forEach((e, i) => { e.style.fontSize = `${Math.min(now[i], base.get(e)! * k).toFixed(2)}px`; e.setAttribute('data-fit', ''); });
      if (fits()) return true;
    }
    return false;
  };
  const q = (root: Element, k: string) => [...root.querySelectorAll<HTMLElement>(`.${k}`)];
  // FIRST, because it changes the room every box below has: the verification line, set on one line in 9:16, and the
  // issue line under it, which the 9:16 design cut with «…» (the date it carries was the part cut) — each wraps onto a
  // second line rather than run out of the frame or lose its date
  for (const v of [...q(sheet, s.vrow), ...q(sheet, s.issued)]) if (v.scrollWidth > v.clientWidth + 0.5 || !textInside(v, sheet.getBoundingClientRect())) v.setAttribute('data-clip', '');
  // the subject's title: the subject stays inside the tree's height (A4), its row inside the sheet's width (9:16)
  const subject = sheet.querySelector<HTMLElement>('[data-testid=subject]');
  const gens = subject && subject.parentElement && subject.parentElement.parentElement;
  if (subject && gens) shrink(q(subject, s.big), () => subject.offsetHeight <= gens.clientHeight + 0.5 && textInside(subject, subject.getBoundingClientRect()), 0.4);
  const subj = sheet.querySelector<HTMLElement>(`.${s.subj}`);
  if (subj) shrink(q(subj, s.big), () => textInside(subj, subj.getBoundingClientRect()) && textInside(subj, sheet.getBoundingClientRect()), 0.4);
  // every box of the tree: inside its slot (A4), its text inside the box, the name and the ring apart
  const nodes = [...sheet.querySelectorAll<HTMLElement>('[data-testid=sheet-node]')].filter((n) => n.getClientRects().length > 0);   // not a hidden generation
  for (const node of nodes) {
    const slot = node.parentElement && node.parentElement.classList.contains(s.slot) ? node.parentElement : null;
    // the slot's whole height: a box may take the 2 px the slot keeps above and below it (boxes then touch, they do not
    // overlap) before its text is made any smaller — at five generations the designed box is ~1 px taller than its slot
    const room = slot ? slot.clientHeight : Infinity;
    const nm = q(node, s.nm), rg = q(node, s.rg);
    const fits = () => node.offsetHeight <= room + 0.5 && textInside(node, node.getBoundingClientRect()) && !meets(nm, rg);
    if (!shrink([...nm, ...rg, ...q(node, s['away-cap'])], fits)) node.setAttribute('data-clip', '');
  }
  // 9:16: the generation bands together stay inside their section — a long name wraps and pushes the bands below off the frame
  const bands = sheet.querySelector<HTMLElement>(`.${s.bands}`);
  if (bands) {
    const inBands = nodes.filter((n) => bands.contains(n));
    const fits = () => bands.scrollHeight <= bands.clientHeight + 0.5 && inBands.every((n) => textInside(n, n.getBoundingClientRect()));
    if (!shrink(inBands.flatMap((n) => [...q(n, s.nm), ...q(n, s.rg)]), fits)) inBands.forEach((n) => n.setAttribute('data-clip', ''));
    // last: the bands, as one, drawn smaller (CSS zoom: text, boxes and gaps alike) until they stand inside the frame
    for (let z = 0.96; z >= 0.6 - 1e-9 && !fits(); z -= 0.04) { bands.style.zoom = z.toFixed(2); bands.setAttribute('data-fit', ''); }
  }
}

function Sheet(p: ScreenProps & { grid: Slot[][]; slots: SlotMap; urls: Record<string, string> }) {
  const { bird, loft, format, depth, lang, photos, brand, grid, slots, urls } = p;
  const settings = p.st.settings as Record<string, unknown>;
  void settings;
  const sheetRef = useRef<HTMLDivElement>(null);
  // after every render — a box's room changes with the depth, the format, the language, the photos and the data. In the
  // frame's own callback, before it is painted, not inside the commit: a store change renders synchronously in the
  // caller's task, and fitting inside that task made the certificate suite's driver lose the evaluation that caused the
  // change («Execution context was destroyed», with no navigation — measured; not with the fit in a frame callback).
  // And once more just before a print, and once the fonts have loaded.
  useLayoutEffect(() => {
    let live = true;
    const fit = () => { if (live) fitSheet(sheetRef.current); };
    const frame = requestAnimationFrame(fit);
    if (typeof document !== 'undefined' && document.fonts) document.fonts.ready.then(fit);
    addEventListener('beforeprint', fit);
    return () => { live = false; cancelAnimationFrame(frame); removeEventListener('beforeprint', fit); };
  });
  return withLang(lang, () => {
    const seen = new Map<string, number>();
    for (let g = 1; g <= depth - 1; g++) for (const x of grid[g]) if (x) seen.set(x.id, (seen.get(x.id) || 0) + 1);
    const common = (bid: string) => (seen.get(bid) || 0) > 1;
    // «{n} أجيال · {f} من {tot} سلفًا» is a claim about THIS sheet, so both numbers are
    // computed over the ancestor rows it prints — depth counts the subject, so depth - 1
    // generations of ancestors (the spec's own 5 generations · 30 ancestors).
    const anc = depth - 1;
    const { coi } = inbreeding(db.getBird, bird.id, anc) as { coi: number };
    // B3 (RULED 2026-11-24) — applied here too, PROPOSED: a placeholder parent is not one of the «{f} من {tot} سلفًا»
    const loss = db.knownAncestors(bird.id, anc) as { filled: number; total: number };
    // the LOCAL calendar date: a certificate printed at 01:00 in Jordan must carry
    // today's date, not yesterday's (src/dates.js, and the no-utc-date guard)
    const today = todayISO();

    const photoBox = (who: 'bird' | 'sire' | 'dam') => {
      if (!photos[who]) return null;
      const slot = slots[who];
      const away = !!slot.media && !slot.media.hasBlob;
      const url = slot.media && slot.media.hasBlob ? urls[slot.media.id] : '';
      return (
        <div className={`${s.photo} ${away ? s.away : ''}`} data-testid={`sheet-photo-${who}`}>
          {url ? <img src={url} alt="" /> : <span>{who}</span>}
          <span className={s.aw}>{AWAY_ICON}</span>
        </div>
      );
    };

    const node = (g: number, slot: Slot, i: number) => {
      if (!slot || !slot.bird) {
        return <div key={`${g}-${i}`} className={cx(s.node, s[`n${g}`], s.unknown)} data-testid="sheet-node" data-recorded="no"><span className={s.nm}>{t('common.unknown')}</span></div>;
      }
      const b = slot.bird;
      // RULED 2026-11-23: a PLACEHOLDER parent prints «غير معروف» in the certificate's language — never its stored name. The
      // common-ancestor dot and a parent's photo box are drawn as for any other bird.
      const ph = db.isPlaceholder(b);
      // H3 (RULED 2026-11-27): a ring is printed ONCE per box — the title is the name when there is one, otherwise the
      // ring; the ring line is printed only under a name (boxTitle). It was «ring · name» over the ring again.
      const ti = boxTitle(b);
      const nm = <span className={s.nm}>{ph ? placeholderName(b, 'box') : <bdi>{ti.title}</bdi>}</span>;
      const name = common(b.id) ? <span className={s.ci}><i className={s.dot} />{nm}</span> : nm;
      if (g === 2) {
        const who = i === 0 ? 'sire' : 'dam';
        const box = photoBox(who);
        const away = !!slots[who].media && !slots[who].media!.hasBlob;
        return (
          <div key={`${g}-${i}`} className={cx(s.node, s.n2, box && s['has-photo'], ph && !box && s.unknown)} data-testid="sheet-node" data-recorded={ph ? 'no' : 'yes'} data-placeholder={ph ? '1' : undefined}>
            {box}
            <div className={s.tx}>{name}{!ph && ti.ring && <span className={s.rg}>{ti.ring}</span>}
              {box && away && <span className={s['away-cap']}>{t('cert.photoAway')}</span>}</div>
          </div>
        );
      }
      return (
        <div key={`${g}-${i}`} className={cx(s.node, s[`n${g}`], ph && s.unknown)} data-testid="sheet-node" data-recorded={ph ? 'no' : 'yes'} data-placeholder={ph ? '1' : undefined}>
          {name}{!ph && ti.ring && <span className={s.rg}>{ti.ring}</span>}
        </div>
      );
    };

    const facts = (
      <div className={s.facts} data-testid="facts">
        <div><div className={s.k}>{t('bird.sex')}</div><div className={s.v}>{t('sex.' + (bird.sex || 'unknown'))}</div></div>
        <div><div className={s.k}>{t('bird.hatchDate')}</div><div className={`${s.v} ${s.mono}`}>{bird.hatchDate ? fmtDate(bird.hatchDate) : '—'}</div></div>
        <div><div className={s.k}>{t('bird.colour')}</div><div className={s.v}>{bird.colour || '—'}</div></div>
        <div><div className={s.k}>{t('bird.strain')}</div><div className={s.v}>{bird.strain || '—'}</div></div>
      </div>
    );
    const subj = boxTitle(bird);
    const plate = (() => {
      const ring = subj.ring;
      if (!ring) return null;                      // H3: no name — the ring IS the title, and is not printed again
      // the ring's year is whatever the record holds — sample data carries it as a number
      const yr = String((bird.rings || []).find((r) => r.raw === ring)?.year ?? '');
      return <span className={s.plate} data-testid="plate">{yr && <span className={s.yr}>{yr.slice(-2)}</span>}<span className={s.no}>{ring}</span></span>;
    })();

    const head = (
      <header className={s.head}>
        <div className={s.id}><div className={s.mark}>{MARK}</div>
          <div><h1>{t('cert.title')}</h1><div className={s.sub}>{t('cert.sub')}</div></div></div>
        <div className={s.meta}>
          <div><div className={s.k}>{t('cert.date')}</div><div className={`${s.v} ${s.mono}`} data-testid="issued">{fmtDate(today)}</div></div>
          <div className={s.depth}><div className={s.k}>{t('cert.depth')}</div>
            <div className={s.v}><span className={s.mono}>{fmtNum(depth)}</span> {t('ped.generations')}</div></div>
        </div>
      </header>
    );
    const coiBlock = (
      <div className={s.coi} data-testid="coi">
        <div className={s.n}>{fmtPercent(coi, 1)}</div>
        <div className={s.l}>{t('cert.coiLabel')}</div>
        <div className={s.s}>{t('cert.coiOver', { n: fmtNum(depth), f: fmtNum(loss.filled), tot: fmtNum(loss.total) })}</div>
      </div>
    );
    const verify = (
      <div className={s.verify}>
        <div className={s.vrow}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12l5 5L20 7" /></svg>
          {t('cert.verifiedSince', { d: fmtDate(bird.createdAt || today) })}
        </div>
        <div className={s.issued}>{t('cert.issuedFrom', { d: fmtDate(today) })}
          {loft && <span className={s.loftname}> · <bdi>{loft.name || t('loft.unnamed')}</bdi></span>}</div>
        <div className={s.note}>{t('cert.note')}</div>
      </div>
    );
    const loftBlock = (
      <div className={s.loft} data-testid="loft-block">
        <div className={s.logo}>{loft?.logoMediaId && urls[loft.logoMediaId]
          ? <img src={urls[loft.logoMediaId]} alt={t('cert.logoAlt')} />
          : <span>logo</span>}</div>
        <div>
          <div className={s.nm}><bdi>{loft?.name || t('loft.unnamed')}</bdi></div>
          {loft?.breederName && <div className={s.br}>{t('cert.breederLine', { n: loft.breederName })}</div>}
          <div className={s.ct}>
            {loft?.phone && <span className={s.mono}>{loft.phone}</span>}
            {loft?.website && <span className={s.mono}>{loft.website}</span>}
          </div>
        </div>
      </div>
    );
    const qr = (
      <div className={s.qr} data-testid="qr">
        <div className={s.box}><span>QR</span></div>
        <div className={s.cap}>{t('cert.qrTitle')}<br />{t('cert.qrSoon')}</div>
      </div>
    );

    const cls = `${s.sheet} ${format === 'a4' ? s.a4 : s.story} ${s[`d${depth}`]} ${lang === 'en' ? s.en : ''} ${brand ? '' : s.nobrand}`;
    if (format === 'a4') {
      return (
        <div ref={sheetRef} className={cls} data-testid="sheet" data-format="a4" data-depth={depth} lang={lang} dir={lang === 'ar' ? 'rtl' : 'ltr'}>
          {head}
          <section className={s.tree}>
            <div className={s.ruler}>{[1, 2, 3, 4, 5].map((g) => <div key={g} className={cx(s[`r${g}`])}>{t(GEN_LABEL[g])}</div>)}</div>
            <div className={s.gens}>
              <div className={cx(s.gen, s.g1)}>
                <div className={cx(s.node, s.n1)} data-testid="subject">
                  {photoBox('bird')}<div className={s.big} data-testid="subject-title"><bdi>{subj.title}</bdi></div>{plate}{facts}
                </div>
              </div>
              {[2, 3, 4, 5].map((g) => (
                <div key={g} className={cx(s.gen, s[`g${g}`])}>
                  {Array.from({ length: 2 ** (g - 2) }, (_, k) => (
                    <div key={k} className={s.pair}>
                      <div className={s.slot}>{node(g, grid[g - 1][2 * k], 2 * k)}</div>
                      <div className={s.slot}>{node(g, grid[g - 1][2 * k + 1], 2 * k + 1)}</div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </section>
          <footer className={s.foot}>{coiBlock}{verify}{loftBlock}{qr}</footer>
        </div>
      );
    }
    return (
      <div ref={sheetRef} className={cls} data-testid="sheet" data-format="story" data-depth={depth} lang={lang} dir={lang === 'ar' ? 'rtl' : 'ltr'}>
        {head}
        <section className={s.subj}>{photoBox('bird')}
          <div><div className={s.big} data-testid="subject-title"><bdi>{subj.title}</bdi></div>{plate}</div></section>
        {facts}
        <section className={s.bands}>
          {[2, 3, 4, 5].map((g) => (
            <div key={g} className={cx(s.band, s[`b${g}`])}>
              <div className={s.bl}>{t(GEN_LABEL[g])}<i className={s.mono}>{fmtNum(COUNTS[g])}</i></div>
              <div className={s.grid}>{grid[g - 1].map((slot, i) => node(g, slot, i))}</div>
            </div>
          ))}
        </section>
        <footer className={s.foot}>{coiBlock}{verify}</footer>
        <div className={s.brandrow}>{loftBlock}{qr}</div>
      </div>
    );
  });
}
