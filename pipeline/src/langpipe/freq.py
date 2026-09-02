"""S3：词频统计 → 词汇候选。

键规则：
  ja: (lemma, 读音)   书内 ruby 读音优先
  ko: (lemma,)
  th/vi: (surface,) / (surface.lower(),)
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .config import CANDIDATES, FREQ, LANGDATA_DIR, ensure_dirs
from .ingest.epub import load_books
from .tok.common import iter_book_tokens

# 候选门槛（先验值，试点后调）
MIN_COUNT = 30
MIN_DOC = 3
MAX_CANDIDATES = 20000


def load_stopwords(lang: str) -> set[str]:
    p = LANGDATA_DIR / "stopwords" / f"{lang}.txt"
    if not p.exists():
        return set()
    return {ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")}


def build_freq(lang: str) -> dict:
    ensure_dirs()
    books = [b for b in load_books()
             if b["language"] == lang and b.get("status") == "unpacked"]
    counts: Counter = Counter()
    docs: dict = defaultdict(set)
    pos: dict = defaultdict(Counter)
    readings: dict = defaultdict(Counter)

    for b in books:
        for t in iter_book_tokens(b["book_id"]):
            s, base = t["s"], t.get("b") or t["s"]
            if lang == "ja":
                key = (base, t.get("r", ""))
            elif lang == "ko":
                key = (base,)
            else:
                key = (base,)
            counts[key] += 1
            docs[key].add(b["book_id"])
            p = t.get("p", "")
            if p:
                pos[key][p] += 1

    rows = []
    for rank, (key, cnt) in enumerate(counts.most_common(), 1):
        rows.append({
            "rank": rank,
            "key": key[0],
            "reading": key[1] if lang == "ja" else "",
            "pos": pos[key].most_common(1)[0][0] if pos[key] else "",
            "count": cnt,
            "doc_count": len(docs[key]),
        })

    FREQ.mkdir(parents=True, exist_ok=True)
    out = FREQ / f"{lang}.tsv"
    with open(out, "w", encoding="utf-8") as f:
        f.write("rank\tkey\treading\tpos\tcount\tdoc_count\n")
        for r in rows:
            f.write(f"{r['rank']}\t{r['key']}\t{r['reading']}\t{r['pos']}\t"
                    f"{r['count']}\t{r['doc_count']}\n")

    stops = load_stopwords(lang)
    cands = [
        r for r in rows
        if r["key"] not in stops
        and (r["count"] >= MIN_COUNT or r["doc_count"] >= MIN_DOC)
        and len(r["key"]) >= 2
    ][:MAX_CANDIDATES]
    cdir = CANDIDATES / lang
    cdir.mkdir(parents=True, exist_ok=True)
    cout = cdir / "vocab_candidates.tsv"
    with open(cout, "w", encoding="utf-8") as f:
        f.write("rank\tkey\treading\tpos\tcount\tdoc_count\n")
        for r in cands:
            f.write(f"{r['rank']}\t{r['key']}\t{r['reading']}\t{r['pos']}\t"
                    f"{r['count']}\t{r['doc_count']}\n")

    return {"lang": lang, "types": len(rows), "candidates": len(cands),
            "freq_file": str(out), "candidates_file": str(cout)}
