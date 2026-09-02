"""S2 分词公共层。

产物：data/tokens/{book_id}/ch{NNN}.jsonl，每行一个 token（短键）：
  s=surface  b=lemma  r=读音(仅日语)  p=词类  c=章号  a=段号  rs=ruby来源(book|dict)
"""
from __future__ import annotations

import re
from pathlib import Path

import orjson

from ..config import RAW, TOKENS, ensure_dirs

# 零宽字符（泰语 epub 常见）
_ZW = re.compile("[\u200b\u200c\u200d\ufeff\u2060]")

# 统一词类（供词频/词汇候选/站点筛选）
POS_CLASSES = ("noun", "verb", "adj", "adv", "func", "affix", "punct", "other")


def _load_chapters(book_id: str):
    ch_dir = RAW / book_id / "chapters"
    for f in sorted(ch_dir.glob("ch*.json")):
        yield orjson.loads(f.read_bytes())


def tokenize_book(book_id: str, lang: str, tok_para) -> dict:
    """对一本书分词，写 token jsonl。返回统计。"""
    ensure_dirs()
    out_dir = TOKENS / book_id
    out_dir.mkdir(parents=True, exist_ok=True)
    n_tokens = 0
    for ch in _load_chapters(book_id):
        lines = []
        for a, para in enumerate(ch["paras"]):
            src = para["annot"] if lang == "ja" and para.get("annot") else para["text"]
            try:
                toks = tok_para(src)
            except Exception:  # noqa: BLE001  单段失败不中断整书
                continue
            for t in toks:
                s = _ZW.sub("", t.get("s", "")).strip()
                if not s:
                    continue
                t["s"] = s
                if t.get("b"):
                    t["b"] = _ZW.sub("", t["b"]).strip()
                t["c"] = ch["chapter_idx"]
                t["a"] = a
                lines.append(orjson.dumps(t))
                n_tokens += 1
        tmp = out_dir / f"ch{ch['chapter_idx']:03d}.jsonl.tmp"
        with open(tmp, "wb") as f:
            f.write(b"\n".join(lines))
        tmp.replace(tmp.with_suffix(""))
    return {"book_id": book_id, "tokens": n_tokens}


def iter_book_tokens(book_id: str):
    d = TOKENS / book_id
    if not d.exists():
        return
    for f in sorted(d.glob("ch*.jsonl")):
        for line in f.read_bytes().splitlines():
            if line:
                yield orjson.loads(line)
