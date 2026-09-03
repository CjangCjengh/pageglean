"""试点阶段采纳器：claude 提取候选 → kb/grammar/（status=draft）。

正式 M4 阶段会并入带去重裁决的 merge 流水线；此模块保留为快速通道。
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import orjson
import yaml

from ..config import KB, MAX_EXAMPLE_CHARS, MAX_EXAMPLES_PER_ENTRY
from ..validate.models import (LEVEL_RANK, LEVELS, Example, GrammarEntry,
                               Provenance, next_id)


def norm_level(lang: str, level) -> str | None:
    if not level:
        return None
    s = str(level).strip().upper().replace("급", "")
    m = re.search(r"(\d)", s)
    if lang == "ko":
        return f"TOPIK{m.group(1)}" if m else None
    if lang in ("th", "vi"):
        return f"L{m.group(1)}" if m else None
    if lang == "ja" and s in LEVELS["ja"]:
        return s
    return None


def valid_annot(annot: str, text: str) -> bool:
    """校验注音标注：去标注后与原句一致，且每个标注基底以汉字结尾。"""
    if not annot:
        return False
    if re.sub(r"\[[^\]]*\]", "", annot) != text:
        return False
    for m in re.finditer(r"\[", annot):
        if m.start() == 0 or not re.match(r"[㐀-鿿豈-﫿]", annot[m.start() - 1]):
            return False
    return True


def _norm_for_match(s: str) -> str:
    """归一化用于出处核对：去空白与标点差异。"""
    return re.sub(r"[\s、。，．！？!?…・「」『』()（）\-—]+", "", s)


def _parse_annot(annot: str):
    """'財布[サイフ]を落とす' → [(base, read|None), ...]"""
    return [(m.group(1), m.group(2)) for m in
            re.finditer(r"([^\[\]]+)(?:\[([^\[\]]+)\])?", annot)]


def annot_for_example(text: str, chunk_annot: str) -> str:
    """从源块标注文本中切出例句对应的 ruby 标注版本。"""
    if not chunk_annot or not text:
        return ""
    segs = _parse_annot(chunk_annot)
    plain = "".join(b for b, _ in segs)
    t = text.strip()
    pos = plain.find(t)
    if pos < 0:
        # 退化为前缀匹配（例句可能被模型截短）
        head = t[: max(10, len(t) // 2)]
        pos = plain.find(head)
        if pos < 0:
            return ""
        t = head
    end = pos + len(t)
    out: list[str] = []
    cursor = 0
    for base, read in segs:
        b_start, b_end = cursor, cursor + len(base)
        cursor = b_end
        if b_end <= pos or b_start >= end:
            continue
        piece = base[max(0, pos - b_start): min(len(base), end - b_start)]
        if read and piece == base:
            out.append(f"{piece}[{read}]")
        else:
            out.append(piece)
    return "".join(out)


def adopt_file(path: Path, lang: str, book_id: str = "") -> list[str]:
    payload = orjson.loads(Path(path).read_bytes())
    # 兼容两种格式：{result: ..., chunk_text: ...} 或裸候选
    data = payload.get("result", payload)
    chunk_text = payload.get("chunk_text", "")
    chunk_norm = _norm_for_match(chunk_text)
    written: list[str] = []
    today = dt.date.today().isoformat()
    for gp in data.get("grammar_points", []):
        level = norm_level(lang, gp.get("level"))
        if not level:
            continue
        examples = []
        for ex in (gp.get("examples") or []):
            text = (ex.get("text") or "").strip()
            if not text or len(text) > MAX_EXAMPLE_CHARS:
                continue
            # 反幻觉：例句必须真实出自源块（允许截断，取前 60% 字符核对）
            probe = _norm_for_match(text)[: max(8, int(len(_norm_for_match(text)) * 0.6))]
            if chunk_norm and probe and probe not in chunk_norm:
                continue
            m_annot = (ex.get("annot") or "").strip()
            examples.append(Example(
                text=text,
                reading=(ex.get("reading") or "").strip(),
                annot=m_annot if valid_annot(m_annot, text)
                else annot_for_example(text, chunk_text),
                translation_zh=(ex.get("translation_zh") or "").strip(),
                source_book=book_id,
            ))
            if len(examples) >= MAX_EXAMPLES_PER_ENTRY:
                break
        if not examples:
            continue  # 无合格例句不入库
        entry = GrammarEntry(
            id=next_id(lang, "grm"),
            language=lang,
            level=level,
            level_rank=LEVEL_RANK[level],
            title=(gp.get("title_zh") or "").strip(),
            structure=(gp.get("structure") or "").strip(),
            structure_pattern=(gp.get("structure_pattern") or "").strip(),
            explanation_zh=(gp.get("explanation_zh") or "").strip(),
            examples=examples,
            tags=gp.get("tags") or [],
            provenance=Provenance(
                discovered_in=book_id,
                frequency_hint=gp.get("frequency_hint"),
                extracted_by="claude-code",
                extracted_at=today,
            ),
            status="draft",
        )
        out = KB / "grammar" / lang / f"{entry.id}.yaml"
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".yaml.tmp")
        tmp.write_text(
            yaml.safe_dump(entry.model_dump(mode="json"), allow_unicode=True,
                           sort_keys=False),
            encoding="utf-8")
        tmp.replace(out)
        written.append(entry.id)
    return written
