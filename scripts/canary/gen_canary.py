"""生成版权金丝雀：每本书摘一句特征片段（40字），供构建产物泄露检查。

输出写到 kb/internal/canary.json（gitignore，金丝雀本身不进公开仓库）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline" / "src"))

from langpipe.config import KB, RAW  # noqa: E402
from langpipe.ingest.epub import load_books  # noqa: E402

FRAG_LEN = 40


def pick_fragment(book_id: str) -> str | None:
    ch_dir = RAW / book_id / "chapters"
    for name in ("ch003.json", "ch002.json", "ch001.json"):
        f = ch_dir / name
        if not f.exists():
            continue
        import orjson
        ch = orjson.loads(f.read_bytes())
        for p in ch["paras"]:
            t = p["text"].replace(" ", "")
            if 50 <= len(t) <= 200:
                return t[10:10 + FRAG_LEN]
    return None


def main() -> None:
    out = KB / "internal" / "canary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for b in load_books():
        frag = pick_fragment(b["book_id"])
        if frag:
            rows.append({"book_id": b["book_id"], "canary": frag})
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已生成 {len(rows)} 条金丝雀 → {out}")


if __name__ == "__main__":
    main()
