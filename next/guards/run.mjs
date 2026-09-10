#!/usr/bin/env node
// Phase 0.5 guards. Each is a source scan over next/ that fails the build on a
// violation. They exist so the rules the specs impose are enforced by a
// process, not remembered by a person. `npm run build` runs them first
// (prebuild); `node guards/run.mjs --only <name>` runs one.
//
// A guard that has never been seen to fail is not evidence of anything, so
// every guard here was proved to fire by reintroducing its violation — see
// the Phase 0.5 commit.
import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs';
import { join, relative, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(fileURLToPath(import.meta.url), '..', '..');
const SKIP = new Set(['node_modules', '.next', 'out', '.git']);

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (SKIP.has(name)) continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p); else yield p;
  }
}
const files = (...exts) => [...walk(ROOT)].filter((f) => exts.includes(extname(f)));
const rel = (f) => relative(ROOT, f);
const lines = (f) => readFileSync(f, 'utf8').split('\n');

// ─── the sanctioned palette (tokens.css is the source of truth; this list
//     mirrors its comments and must be edited together with it) ───
const CORE = ['#128C6E', '#0E6F57', '#E3F4EE', '#101820', '#4A5560', '#8C97A2',
              '#F5F7F8', '#FFFFFF', '#E4E9ED', '#C9971F', '#FBF3DF', '#C43D2B'];
const EXT  = ['#8A6410', '#7A5A0E', '#F8E6E3', '#2FBF95', '#A83223'];
const DEV  = ['#5CD6A8', '#FF8A78', '#E6B84A', '#D8DEE3'];
const SEX  = ['#E4EDF6', '#0A4D8C', '#F6E4EE', '#8C0A57'];   // ruled in: sex chips
const SANCTIONED = new Set([...CORE, ...EXT, ...DEV, ...SEX].map((h) => h.toUpperCase()));
const expand = (h) => (h.length === 4 ? '#' + [...h.slice(1)].map((c) => c + c).join('') : h).toUpperCase();

const guards = {
  // 1. Any hex colour in .css/.ts/.tsx outside the sanctioned set fails.
  //    rgba()/rgb() are allowed (focus rings, hairline insets).
  palette() {
    const bad = [];
    for (const f of files('.css', '.tsx', '.ts')) {
      lines(f).forEach((l, i) => {
        for (const m of l.matchAll(/#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b/g)) {
          if (!SANCTIONED.has(expand(m[0]))) bad.push(`${rel(f)}:${i + 1}  ${m[0]}`);
        }
      });
    }
    return bad;
  },
  // 2. next/ never reaches into the root at all: no import/url of ../js, ../css or ../tools.
  'no-root-imports'() {
    const bad = [];
    for (const f of files('.ts', '.tsx', '.js', '.mjs', '.css')) {
      lines(f).forEach((l, i) => {
        if (/['"(](\.\.\/)+(js|css|tools)\//.test(l)) bad.push(`${rel(f)}:${i + 1}  ${l.trim()}`);
      });
    }
    return bad;
  },
  // 3. The document is Arabic and RTL, in source and — when built — in every page.
  'html-rtl'() {
    const bad = [];
    const layout = readFileSync(join(ROOT, 'app', 'layout.tsx'), 'utf8');
    const tag = layout.match(/<html[^>]*>/)?.[0] ?? '';
    if (!/\blang="ar"/.test(tag)) bad.push(`app/layout.tsx  <html> lacks lang="ar": ${tag}`);
    if (!/\bdir="rtl"/.test(tag)) bad.push(`app/layout.tsx  <html> lacks dir="rtl": ${tag}`);
    const out = join(ROOT, 'out');
    if (existsSync(out)) {
      for (const name of readdirSync(out).filter((n) => n.endsWith('.html'))) {
        const h = readFileSync(join(out, name), 'utf8').match(/<html[^>]*>/)?.[0] ?? '';
        if (!/\blang="ar"/.test(h) || !/\bdir="rtl"/.test(h)) bad.push(`out/${name}  ${h.slice(0, 60)}`);
      }
    }
    return bad;
  },
  // 4. No gradients. No blurred box-shadow: a shadow is allowed only if it is
  //    `inset` (hairline) or its blur radius — the third length — is 0
  //    (focus ring `0 0 0 Npx`). Applies to CSS and to inline styles in TSX.
  'no-gradient-no-blur'() {
    const bad = [];
    for (const f of files('.css', '.tsx')) {
      lines(f).forEach((l, i) => {
        if (/gradient/i.test(l)) bad.push(`${rel(f)}:${i + 1}  gradient: ${l.trim()}`);
        for (const m of l.matchAll(/box-?[sS]hadow\s*:\s*['"]?([^;'"}]+)/g)) {
          for (const shadow of m[1].split(/,(?![^()]*\))/)) {
            const s = shadow.trim();
            if (!s || s === 'none') continue;
            if (/^inset\b/.test(s)) continue;
            const lens = s.match(/-?\d*\.?\d+(px|em|rem)?/g) ?? [];
            const blur = lens[2] ?? '0';
            if (parseFloat(blur) !== 0) bad.push(`${rel(f)}:${i + 1}  blurred shadow: ${s}`);
          }
        }
      });
    }
    return bad;
  },
  // 6. The test harness route must not exist unless this is a harness build.
  //    app/test-harness/ is created by scripts/build-harness.mjs for one build and
  //    removed after; its presence during a normal build is a defect.
  'no-harness-route'() {
    if (process.env.NEXT_PUBLIC_HARNESS === '1') return [];
    return existsSync(join(ROOT, 'app', 'test-harness')) ? ['app/test-harness/  exists in a NORMAL build'] : [];
  },
  // 7. A secret key never appears under next/ — not in source, tests, docs or
  //    config. The secret key grants everything; the publishable one grants
  //    nothing on its own (js/sync-config.js). Needle assembled from parts so
  //    this file cannot match itself.
  'no-secret-key'() {
    const needle = 'sb_' + 'secret_';
    const bad = [];
    for (const f of files('.js', '.mjs', '.ts', '.tsx', '.css', '.json', '.md', '.py', '.txt', '.env', '.html')) {
      lines(f).forEach((l, i) => { if (l.includes(needle)) bad.push(`${rel(f)}:${i + 1}`); });
    }
    return bad;
  },
  // 5. No dynamic route segments: user data cannot be enumerated at build time,
  //    so [id] cannot be statically exported. Record views use ?id=.
  'no-dynamic-segments'() {
    const bad = [];
    for (const f of walk(join(ROOT, 'app'))) {
      const seg = rel(f).split('/').find((p) => /^\[.*\]$/.test(p));
      if (seg) bad.push(`${rel(f)}  segment ${seg}`);
    }
    return [...new Set(bad.map((b) => b.split('/page')[0].split('/layout')[0]))];
  },
};

const only = process.argv.includes('--only') ? process.argv[process.argv.indexOf('--only') + 1] : null;
let failed = 0;
for (const [name, fn] of Object.entries(guards)) {
  if (only && name !== only) continue;
  const bad = fn();
  if (bad.length) {
    failed++;
    console.log(`✗ ${name}  (${bad.length})`);
    for (const b of bad) console.log(`    ${b}`);
  } else {
    console.log(`✓ ${name}`);
  }
}
console.log(failed ? `\n${failed} guard(s) FAILED` : '\nall guards pass');
process.exit(failed ? 1 : 0);
