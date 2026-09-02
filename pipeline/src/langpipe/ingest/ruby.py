"""HTML/XHTML → 段落，保留 <ruby> 振假名。

产物格式（每个段落）:
  text  : 纯文本（ruby 仅保留基底字）
  annot : 标注文本，ruby 写作  基底[读音]   如  財布[サイフ]
"""
from __future__ import annotations

import re
from typing import Iterable

from bs4 import BeautifulSoup, NavigableString, Tag

_SKIP_TAGS = {"style", "script", "svg", "head", "title"}
_BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "li"}


def parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _ruby_segment(ruby: Tag) -> dict:
    """把 <ruby> 解析为 {t: ruby, text: 基底, read: 读音}。"""
    base_parts: list[str] = []
    read_parts: list[str] = []
    for child in ruby.children:
        if isinstance(child, Tag):
            if child.name == "rp":
                continue
            if child.name == "rt":
                read_parts.append(child.get_text())
            elif child.name in ("rb", "r"):
                base_parts.append(child.get_text())
            else:  # ruby 内其他标签，按基底处理
                base_parts.append(child.get_text())
        elif isinstance(child, NavigableString):
            s = str(child)
            if s.strip():
                base_parts.append(s)
    return {
        "t": "ruby",
        "text": "".join(base_parts).strip(),
        "read": "".join(read_parts).strip(),
    }


def _walk(el: Tag, segs: list[dict]) -> None:
    for child in el.children:
        if isinstance(child, NavigableString):
            s = str(child)
            if s:
                segs.append({"t": "plain", "text": s})
        elif isinstance(child, Tag):
            if child.name in _SKIP_TAGS:
                continue
            if child.name == "ruby":
                seg = _ruby_segment(child)
                if seg["text"]:
                    segs.append(seg)
            elif child.name == "br":
                segs.append({"t": "plain", "text": "\n"})
            else:
                _walk(child, segs)


def _norm(s: str) -> str:
    s = s.replace("　", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def segments_to_plain(segs: Iterable[dict]) -> str:
    return _norm("".join(s["text"] for s in segs))


def segments_to_annot(segs: Iterable[dict]) -> str:
    out = []
    for s in segs:
        out.append(s["text"])
        if s["t"] == "ruby" and s.get("read"):
            out.append(f"[{s['read']}]")
    return _norm("".join(out))


# Word 转制 epub（越南语）常见的垃圾段落特征
_WORD_JUNK = re.compile(
    r"(FullName|mso-|MsoNormal|st1:|\d{4}-\d{2}-\d{2}T\d{2}:|false false|behavior:url)",
    re.I,
)


def _is_junk(text: str) -> bool:
    if len(text) < 2:
        return True
    if _WORD_JUNK.search(text):
        return True
    # 纯数字/纯符号行
    if not re.search(r"[\w฀-๿぀-ヿ㐀-鿿가-힯]", text):
        return True
    return False


def doc_to_paragraphs(soup: BeautifulSoup) -> list[dict]:
    """返回 [{text, annot}]，按文档顺序。"""
    paras: list[dict] = []
    els = soup.find_all("p")
    if len([e for e in els if e.get_text(strip=True)]) < 3:
        # 无 p 结构时退化为块级标签
        els = [e for e in soup.find_all(_BLOCK_TAGS) if not e.find(_BLOCK_TAGS)]
    for el in els:
        if el.name != "p" and el.find("p"):
            continue  # 避免与内层 p 重复
        segs: list[dict] = []
        _walk(el, segs)
        if not segs:
            continue
        text = segments_to_plain(segs)
        if _is_junk(text):
            continue
        paras.append({"text": text, "annot": segments_to_annot(segs)})
    return paras


def chapter_title(soup: BeautifulSoup) -> str | None:
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        t = tag.get_text(strip=True)
        if t:
            return t[:80]
    return None
