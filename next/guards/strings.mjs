#!/usr/bin/env node
// The string guard (4.0 ruling 2). For every SHIPPED screen, every Arabic
// string its approved spec renders must resolve to an i18n key (vanilla
// dictionary or i18n.ext), match a {param} template, or be on that screen's
// recorded mock-content list. Anything else fails the build.
//
//   node guards/strings.mjs                 check every shipped screen
//   node guards/strings.mjs --only <spec>   check one
//   node guards/strings.mjs --emit-mock <spec>  print the unresolved set (to seed the mock list)
//
// Extraction rules match the 4.0 report's script: element-level text with
// inline elements folded into their parent, plus placeholder/aria-label/title/
// alt/value attributes; script, style and svg skipped; option text kept.
import { readFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SPECS = join(ROOT, '..', 'design', 'approved');

// ── shipped screens: added as each screen lands ──
export const SHIPPED = ['shared-states-v1.html', 'loft-home-v1.html', 'bird-profile-v1.html', 'add-edit-bird-v2.html', 'pedigree-tree-v1.html', 'breeding-v1.html', 'races-v1.html', 'health-v1.html', 'stats-v1.html'];

const AR = /[؀-ۿ]/;
// FORMAT tags fold into their parent (they never carry a standalone UI string);
// so does any child with no Arabic (a count in <b>3</b> or <span class="n">, so
// {n} templates still match). Spans, links and leaf-text elements (p, h*,
// button, li, td…) are strings in their own right and are NOT folded upward —
// otherwise block containers emit concatenations nobody renders.
const FORMAT = new Set(['b','i','em','strong','bdi','small','u','kbd','code','sup','sub']);
const SKIP = new Set(['script','style','svg']);
const ATTRS = ['placeholder','aria-label','title','alt','value','data-label'];
const norm = (v) => { v = v.replace(/\s+/g, ' ').trim().replace(/^[·|—–:؛، ]+|[·|—–:؛، ]+$/g, '').trim(); return v.replace(/^[\d٠-٩]+(?=[؀-ۿ])/, '').replace(/(?<=[؀-ۿ])\s*[\d٠-٩]+$/, ''); };   // a folded count either side of a label («الصور 3») is not part of the string

/** Element-level Arabic strings of a spec (Set). */
export function extract(html) {
  const out = new Set(); const stack = []; let skip = 0;
  const add = (v) => { v = norm(v); if (v && AR.test(v) && v.length > 1) out.add(v); };
  const re = /<!--[\s\S]*?-->|<\/([a-zA-Z0-9]+)\s*>|<([a-zA-Z0-9]+)((?:\s+[^\s=>]+(?:=(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>|([^<]+)/g;
  let m;
  while ((m = re.exec(html))) {
    if (m[0].startsWith('<!--')) continue;
    if (m[1]) { const tag = m[1].toLowerCase(); if (SKIP.has(tag)) skip--; const top = stack.pop(); if (!top || skip > 0) continue; const text = top.text; const fold = FORMAT.has(tag) || !AR.test(text); if (AR.test(text) && !FORMAT.has(tag)) add(text); if (stack.length && fold) stack[stack.length - 1].text += ' ' + text + ' '; continue; }
    if (m[2]) { const tag = m[2].toLowerCase(); if (SKIP.has(tag)) skip++; if (skip === 0) for (const a of ATTRS) { const am = new RegExp('\\s' + a + '=(?:"([^"]*)"|\'([^\']*)\')').exec(m[3] || ''); if (am) add(am[1] ?? am[2]); } if (m[4]) { if (SKIP.has(tag)) skip--; continue; } stack.push({ tag, text: '' }); continue; }
    if (m[5] && skip === 0 && stack.length) stack[stack.length - 1].text += m[5];
  }
  return out;
}
/** Brace-aware dictionary parse: 'key': { ar: '…', en: '…' } */
export function parseDict(src) {
  const out = {}; const re = /'([A-Za-z0-9_.\- ]+)':\s*\{/g; let m;
  while ((m = re.exec(src))) {
    let i = m.index + m[0].length, depth = 1, q = null, buf = '';
    while (i < src.length && depth) { const c = src[i]; if (q) { buf += c; if (c === '\\') { buf += src[i + 1]; i += 2; continue; } if (c === q) q = null; } else { if (c === "'" || c === '"' || c === '`') { q = c; buf += c; } else if (c === '{') { depth++; buf += c; } else if (c === '}') { depth--; if (depth) buf += c; } else buf += c; } i++; }
    const ar = /\bar\s*:\s*'((?:[^'\\]|\\.)*)'/.exec(buf); if (ar) out[m[1]] = ar[1].replace(/\\'/g, "'");
  }
  return out;
}
const dict = { ...parseDict(readFileSync(join(ROOT, 'src', 'i18n.js'), 'utf8')), ...parseDict(readFileSync(join(ROOT, 'src', 'i18n.ext.js'), 'utf8')) };
// dictionary values go through the same norm() as spec text, so a trailing colon
// or separator on either side cannot make a real key look like a miss
const values = new Map(Object.entries(dict).map(([k, v]) => [norm(v), k]));
// a template whose LAST token is a param («سلفًا من {total}») still matches a spec string whose trailing count
// norm() stripped («سلفًا من 30» → «سلفًا من»): that final param is optional
const templates = Object.entries(dict).filter(([, v]) => v.includes('{')).map(([k, v]) => [new RegExp('^' + norm(v).replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/ \\\{[a-zA-Z]+\\\}$/, '( .+?)?').replace(/\\\{[a-zA-Z]+\\\}/g, '.+?') + '$'), k]);
const mockFile = join(ROOT, 'guards', 'strings.mock.json');
const mock = existsSync(mockFile) ? JSON.parse(readFileSync(mockFile, 'utf8')) : {};
// PENDING: real UI strings whose wording conflicts with the vanilla voice or with
// another spec and awaits a ruling. Accepted by the guard so the build stays
// green, reported as ⚠ so they are never silently dropped. { spec: { string: reason } }
const pendingFile = join(ROOT, 'guards', 'strings.pending.json');
const pending = existsSync(pendingFile) ? JSON.parse(readFileSync(pendingFile, 'utf8')) : {};
// RULED: spec variants settled by an acceptance ruling — the vanilla key wins,
// or the element is not rendered. Accepted silently; the ruling named in the
// entry is the record. { spec: { string: ruling } }
const ruledFile = join(ROOT, 'guards', 'strings.ruled.json');
const ruled = existsSync(ruledFile) ? JSON.parse(readFileSync(ruledFile, 'utf8')) : {};
// A label the spec writes as one string but the app builds from TWO dictionary keys —
// «المسافة كم» is race.distance + race.km, «السرعة (م/د)» is race.velocity + race.mpm.
// Both halves must themselves resolve to a key, so this accepts no new wording.
function isComposite(v) {
  if (/[—·|]/.test(v)) return false;   // a separator means a title or a summary line, not a two-key label
  const clean = (x) => norm(x.replace(/^[(\u061B]+|[)]+$/g, '').replace(/^\(|\)$/g, ''));
  const parts = v.split(/\s+/);
  for (let i = 1; i < parts.length; i++) {
    const a = clean(parts.slice(0, i).join(' ')), b = clean(parts.slice(i).join(' '));
    if (a && b && values.has(a) && values.has(b)) return true;
  }
  return false;
}
export function resolve(v, spec) {
  if (values.has(v)) return 'key';
  if (templates.some(([rx]) => rx.test(v))) return 'template';
  if (isComposite(v)) return 'composite';
  if ((mock[spec] || []).includes(v)) return 'mock';
  if (ruled[spec] && v in ruled[spec]) return 'ruled';
  if (pending[spec] && v in pending[spec]) return 'pending';
  return null;
}
const argv = process.argv.slice(2);
const only = argv.includes('--only') ? argv[argv.indexOf('--only') + 1] : null;
const emit = argv.includes('--emit-mock') ? argv[argv.indexOf('--emit-mock') + 1] : null;
if (emit) { const strs = extract(readFileSync(join(SPECS, emit), 'utf8')); const un = [...strs].filter((v) => !values.has(v) && !templates.some(([rx]) => rx.test(v)) && !isComposite(v) && !(pending[emit] && v in pending[emit]) && !(ruled[emit] && v in ruled[emit])); console.log(JSON.stringify(un, null, 0)); process.exit(0); }
let failed = 0;
for (const spec of SHIPPED) {
  if (only && spec !== only) continue;
  const strs = extract(readFileSync(join(SPECS, spec), 'utf8'));
  const miss = [...strs].filter((v) => !resolve(v, spec));
  const n = { key: 0, template: 0, composite: 0, mock: 0, ruled: 0, pending: 0 }; for (const v of strs) { const r = resolve(v, spec); if (r) n[r]++; }
  if (miss.length) { failed++; console.log(`✗ strings:${spec}  ${miss.length} unresolved of ${strs.size}`); for (const v of miss) console.log('    ' + v); }
  else console.log(`${n.pending ? '⚠' : '✓'} strings:${spec}  ${strs.size} strings — ${n.key} keys · ${n.template} templates${n.composite ? ` · ${n.composite} composites` : ''} · ${n.mock} mock${n.ruled ? ` · ${n.ruled} ruled` : ''}${n.pending ? ` · ${n.pending} PENDING a ruling` : ''}`);
  for (const v of strs) if (resolve(v, spec) === 'pending') console.log(`    ⚠ pending: ${v}  — ${pending[spec][v]}`);
}
console.log(failed ? `\n${failed} screen(s) FAILED the string guard` : '\nstring guard passes');
process.exit(failed ? 1 : 0);
