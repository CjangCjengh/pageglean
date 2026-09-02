"""S4b 输入准备：章节 → 提取块（~2000 字，跨块一段重叠）。"""
from __future__ import annotations

import orjson

from ..config import CHUNKS, RAW, ensure_dirs


def chunk_book(book_id: str, target: int = 2000, overlap_paras: int = 1) -> list[dict]:
    ch_dir = RAW / book_id / "chapters"
    if not ch_dir.exists():
        raise FileNotFoundError(f"先跑 unpack: {book_id}")
    ensure_dirs()
    chunks: list[dict] = []
    cur: list[str] = []
    cur_len = 0
    from_ch = to_ch = None

    def flush():
        nonlocal cur, cur_len, from_ch, to_ch
        if not cur:
            return
        idx = len(chunks)
        payload = {
            "book_id": book_id,
            "chunk_idx": idx,
            "from_chapter": from_ch,
            "to_chapter": to_ch,
            "char_count": cur_len,
            "text": "\n".join(cur),
        }
        out = CHUNKS / book_id / f"k{idx:04d}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".json.tmp")
        tmp.write_bytes(orjson.dumps(payload))
        tmp.replace(out)
        chunks.append(payload)
        tail = cur[-overlap_paras:] if overlap_paras > 0 else []
        cur = tail
        cur_len = sum(len(x) for x in cur)

    for f in sorted(ch_dir.glob("ch*.json")):
        ch = orjson.loads(f.read_bytes())
        for para in ch["paras"]:
            line = para.get("annot") or para["text"]
            if cur and cur_len + len(line) > target:
                flush()
                if from_ch is not None:
                    from_ch = to_ch
            if from_ch is None:
                from_ch = ch["chapter_idx"]
            to_ch = ch["chapter_idx"]
            cur.append(line)
            cur_len += len(line)
    flush()
    return chunks
