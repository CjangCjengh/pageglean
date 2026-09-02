"""S0 书目登记 + S1 解包切章。"""
from __future__ import annotations

import hashlib
import logging
import re
import warnings
from pathlib import Path

import orjson
import yaml
from charset_normalizer import from_bytes

from ..config import CORPUS, KB, LANGS, RAW, ensure_dirs
from ..ledger import Ledger
from .ruby import chapter_title, doc_to_paragraphs, parse_html

warnings.filterwarnings("ignore")
logging.getLogger("ebooklib").setLevel(logging.ERROR)

import ebooklib  # noqa: E402
from ebooklib import epub  # noqa: E402

BOOKS_YAML = KB / "meta" / "books.yaml"

# 章节正文最少字数（过滤封面/版权页/广告/导航）
MIN_CHAPTER_CHARS = 80


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_corpus_epubs(lang: str | None = None):
    langs = [lang] if lang else list(LANGS)
    for lg in langs:
        d = CORPUS / lg
        if not d.exists():
            continue
        for p in sorted(d.glob("*.epub")):
            yield lg, p


def load_books() -> list[dict]:
    if BOOKS_YAML.exists():
        return yaml.safe_load(BOOKS_YAML.read_text(encoding="utf-8")) or []
    return []


def save_books(books: list[dict]) -> None:
    BOOKS_YAML.parent.mkdir(parents=True, exist_ok=True)
    tmp = BOOKS_YAML.with_suffix(".yaml.tmp")
    tmp.write_text(
        yaml.safe_dump(books, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    tmp.replace(BOOKS_YAML)


def register_books(ledger: Ledger) -> list[dict]:
    """S0：扫描 corpus/，写入/更新 kb/meta/books.yaml。按 sha256 保持 id 稳定。"""
    books = load_books()
    by_sha = {b["sha256"]: b for b in books}
    counters = {lg: 0 for lg in LANGS}
    for b in books:
        m = re.match(r"book-(\w+)-(\d+)", b["book_id"])
        if m:
            counters[m.group(1)] = max(counters.get(m.group(1), 0), int(m.group(2)))

    changed = False
    for lg, path in iter_corpus_epubs():
        sha = sha256_file(path)
        if sha in by_sha:
            entry = by_sha[sha]
            if entry["epub_path"] != str(path.relative_to(CORPUS.parent)):
                entry["epub_path"] = str(path.relative_to(CORPUS.parent))
                changed = True
        else:
            counters[lg] += 1
            entry = {
                "book_id": f"book-{lg}-{counters[lg]:03d}",
                "title_orig": path.stem,
                "language": lg,
                "epub_path": str(path.relative_to(CORPUS.parent)),
                "sha256": sha,
                "chapter_count": 0,
                "total_chars": 0,
                "has_ruby": False,
                "script": "horizontal",
                "status": "registered",
            }
            books.append(entry)
            by_sha[sha] = entry
            changed = True
        ledger.register_book(entry["book_id"], lg, sha, str(path))

    if changed:
        save_books(books)
    return books


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        guess = from_bytes(raw).best()
        return str(guess) if guess else raw.decode("utf-8", "ignore")


def unpack_book(book: dict, corpus_root: Path | None = None) -> dict:
    """S1：一本 epub → data/raw/{book_id}/chapters/ch*.json。返回更新后的 book 字典。"""
    ensure_dirs()
    book_id = book["book_id"]
    path = (corpus_root or CORPUS.parent) / book["epub_path"]
    out_dir = RAW / book_id / "chapters"
    out_dir.mkdir(parents=True, exist_ok=True)

    eb = epub.read_epub(str(path), options={"ignore_ncx": True})
    try:
        title = eb.get_metadata("DC", "title")[0][0] or book["title_orig"]
    except Exception:
        title = book["title_orig"]

    items = {it.get_id(): it for it in eb.get_items_of_type(ebooklib.ITEM_DOCUMENT)}
    spine_ids = [sid for sid, *_ in eb.spine]

    # 竖排检测：样式表里出现 vertical-rl / vertical 写作方向
    vertical = False
    for it in eb.get_items_of_type(ebooklib.ITEM_STYLE):
        try:
            if "vertical" in _decode(it.get_content()).lower():
                vertical = True
                break
        except Exception:
            continue

    chapters, has_ruby, total_chars = [], False, 0
    idx = 0
    for sid in spine_ids:
        it = items.get(sid)
        if it is None:
            continue
        name = (it.get_name() or "").lower()
        if any(k in name for k in ("nav", "toc", "cover", "contents", "ads")):
            continue
        try:
            soup = parse_html(_decode(it.get_content()))
        except Exception:
            continue
        if soup.find("ruby") is not None:
            has_ruby = True
        paras = doc_to_paragraphs(soup)
        chars = sum(len(p["text"]) for p in paras)
        if chars < MIN_CHAPTER_CHARS:
            continue
        idx += 1
        ch = {
            "book_id": book_id,
            "chapter_idx": idx,
            "title": chapter_title(soup),
            "paras": paras,
            "char_count": chars,
        }
        chapters.append(ch)
        total_chars += chars
        tmp = out_dir / f"ch{idx:03d}.json.tmp"
        tmp.write_bytes(orjson.dumps(ch))
        tmp.replace(tmp.with_suffix(""))

    book.update(
        {
            "title_orig": title,
            "chapter_count": len(chapters),
            "total_chars": total_chars,
            "has_ruby": has_ruby,
            "script": "vertical" if vertical else "horizontal",
            "status": "unpacked",
        }
    )
    return book


def unpack_all(lang: str | None = None, book_id: str | None = None,
               ledger: Ledger | None = None) -> None:
    books = load_books()
    targets = [
        b for b in books
        if (lang in (None, "all") or b["language"] == lang)
        and (book_id is None or b["book_id"] == book_id)
    ]
    for b in targets:
        if b.get("status") == "unpacked" and b.get("chapter_count", 0) > 0:
            continue
        try:
            unpack_book(b)
            print(f"[S1] {b['book_id']} ✓ {b['chapter_count']}章 {b['total_chars']}字")
        except Exception as e:  # noqa: BLE001
            b["status"] = "failed_unpack"
            print(f"[S1] {b['book_id']} ✗ {e}")
    save_books(books)
