/**
 * kb-sync：kb/ → site/src/content/kb/（同步即脱敏）
 * - 剥离 examples[].pointer（段落级指针不进公开构建）
 * - 每条目强制 ≤2 例句、单句 ≤120 字符
 * - 丢弃 candidate / deprecated 状态条目
 * 公开构建与本地构建的差异只在这里与阅读器数据注入，页面代码不分叉。
 */
import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';

const ROOT = path.resolve(import.meta.dirname, '..', '..');
const KB = path.join(ROOT, 'kb');
const OUT = path.join(import.meta.dirname, '..', 'src', 'content', 'kb');
const LANGS = ['ja', 'ko', 'th', 'vi'];
const MAX_EXAMPLES = 2;
const MAX_CHARS = 120;
const DROP_STATUS = new Set(['candidate', 'deprecated']);

fs.rmSync(OUT, { recursive: true, force: true });

function sanitizeEntry(e) {
  if (DROP_STATUS.has(e.status)) return null;
  const out = { ...e };
  out.examples = (e.examples || []).slice(0, MAX_EXAMPLES).map((ex) => {
    const { pointer, ...rest } = ex;
    if (rest.text && rest.text.length > MAX_CHARS) rest.text = rest.text.slice(0, MAX_CHARS);
    return rest;
  });
  return out;
}

let nGrammar = 0, nVocab = 0, nTut = 0;
for (const sub of ['grammar', 'vocab']) {
  for (const lang of LANGS) {
    const dir = path.join(KB, sub, lang);
    if (!fs.existsSync(dir)) continue;
    for (const f of fs.readdirSync(dir).filter((x) => x.endsWith('.yaml'))) {
      const data = yaml.load(fs.readFileSync(path.join(dir, f), 'utf8'));
      const clean = sanitizeEntry(data);
      if (!clean) continue;
      const odir = path.join(OUT, sub, lang);
      fs.mkdirSync(odir, { recursive: true });
      fs.writeFileSync(path.join(odir, f), yaml.dump(clean, { lineWidth: 120 }), 'utf8');
      if (sub === 'grammar') nGrammar++; else nVocab++;
    }
  }
}

for (const lang of LANGS) {
  const dir = path.join(KB, 'tutorials', lang);
  if (!fs.existsSync(dir)) continue;
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith('.md'))) {
    const odir = path.join(OUT, 'tutorials', lang);
    fs.mkdirSync(odir, { recursive: true });
    fs.copyFileSync(path.join(dir, f), path.join(odir, f));
    nTut++;
  }
}

// 跨语言概念组
const linkDir = path.join(KB, 'links');
if (fs.existsSync(linkDir)) {
  for (const f of fs.readdirSync(linkDir).filter((x) => x.endsWith('.yaml'))) {
    const odir = path.join(OUT, 'links');
    fs.mkdirSync(odir, { recursive: true });
    fs.copyFileSync(path.join(linkDir, f), path.join(odir, f));
  }
}

// books.json（页面直接 import）
const booksYaml = path.join(KB, 'meta', 'books.yaml');
const booksOut = path.join(import.meta.dirname, '..', 'src', 'lib', 'books.json');
if (fs.existsSync(booksYaml)) {
  const books = yaml.load(fs.readFileSync(booksYaml, 'utf8')) || [];
  fs.mkdirSync(path.dirname(booksOut), { recursive: true });
  fs.writeFileSync(booksOut, JSON.stringify(books.map(({ sha256, epub_path, ...rest }) => rest)), 'utf8');
}

console.log(`kb-sync: 语法 ${nGrammar} | 词汇 ${nVocab} | 教程 ${nTut}`);
