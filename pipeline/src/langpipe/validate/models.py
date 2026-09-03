"""KB 数据模型（pydantic 为唯一事实源）+ 入库校验。

版权硬约束在此强制：每条目 ≤2 例句、单句 ≤120 字符。
"""
from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from ..config import KB, MAX_EXAMPLE_CHARS, MAX_EXAMPLES_PER_ENTRY, PIPELINE_DIR

ID_RE = re.compile(r"^(ja|ko|th|vi)-(grm|voc)-\d{5,}$")

LEVELS = {
    "ja": ["N5", "N4", "N3", "N2", "N1"],
    "ko": [f"TOPIK{i}" for i in range(1, 7)],
    "th": [f"L{i}" for i in range(1, 7)],
    "vi": [f"L{i}" for i in range(1, 7)],
}
LEVEL_RANK = {lv: i + 1 for lst in LEVELS.values() for i, lv in enumerate(lst)}


class Status(str, Enum):
    candidate = "candidate"
    draft = "draft"
    review = "review"
    published = "published"
    deprecated = "deprecated"


class Example(BaseModel):
    text: str
    reading: str = ""
    annot: str = ""  # ruby 标注文本 基底[读音]…，站点按开关注入 <ruby>
    translation_zh: str = ""
    source_book: str = ""
    source_chapter: int | None = None
    pointer: dict | None = None  # 仅内部副本保留，kb-sync 剥离

    @field_validator("text")
    @classmethod
    def _len(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("例句为空")
        if len(v) > MAX_EXAMPLE_CHARS:
            raise ValueError(f"例句超过{MAX_EXAMPLE_CHARS}字符上限")
        return v


class SameLangRef(BaseModel):
    id: str
    relation: Literal["contrast", "base", "derivative", "synonym", "other"] = "other"


class Related(BaseModel):
    cross_lang: list[str] = Field(default_factory=list)
    same_lang: list[SameLangRef] = Field(default_factory=list)


class Provenance(BaseModel):
    discovered_in: str | list[str] = ""
    first_seen_chapter: int | None = None
    frequency_hint: int | None = None
    extracted_by: str = ""
    extracted_at: str = ""


class GrammarEntry(BaseModel):
    id: str
    language: Literal["ja", "ko", "th", "vi"]
    type: Literal["grammar", "particle", "conjugation", "expression", "honorific"] = "grammar"
    level: str
    level_rank: int
    title: str
    structure: str = ""
    structure_pattern: str = ""
    explanation_zh: str = ""
    examples: list[Example] = Field(default_factory=list)
    related: Related = Field(default_factory=Related)
    tags: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    status: Status = Status.draft
    review_note: str = ""

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not ID_RE.match(v):
            raise ValueError(f"id 格式错误: {v}")
        return v

    @field_validator("examples")
    @classmethod
    def _examples(cls, v: list[Example]) -> list[Example]:
        if len(v) > MAX_EXAMPLES_PER_ENTRY:
            raise ValueError(f"例句数超过上限 {MAX_EXAMPLES_PER_ENTRY}")
        return v

    @model_validator(mode="after")
    def _level(self):
        if self.level not in LEVELS[self.language]:
            raise ValueError(f"{self.language} 非法级别: {self.level}")
        if self.level_rank != LEVEL_RANK[self.level]:
            raise ValueError("level_rank 与 level 不一致")
        return self


class Frequency(BaseModel):
    rank: int | None = None
    count: int | None = None
    doc_count: int | None = None


class VocabEntry(BaseModel):
    id: str
    language: Literal["ja", "ko", "th", "vi"]
    type: Literal["vocab"] = "vocab"
    word: str
    reading: str = ""
    pos: str = ""
    gloss_zh: str = ""
    gloss_detail_zh: str = ""
    level: str = ""
    level_rank: int = 0
    frequency: Frequency = Field(default_factory=Frequency)
    examples: list[Example] = Field(default_factory=list)
    related: Related = Field(default_factory=Related)
    tags: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    status: Status = Status.draft

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not ID_RE.match(v):
            raise ValueError(f"id 格式错误: {v}")
        return v

    @field_validator("examples")
    @classmethod
    def _examples(cls, v: list[Example]) -> list[Example]:
        if len(v) > MAX_EXAMPLES_PER_ENTRY:
            raise ValueError(f"例句数超过上限 {MAX_EXAMPLES_PER_ENTRY}")
        return v


class XlangGroup(BaseModel):
    group_id: str
    concept_zh: str
    members: dict[str, list[str]] = Field(default_factory=dict)
    note_zh: str = ""
    status: Status = Status.draft


def next_id(lang: str, kind: str) -> str:
    """扫描 kb/ 生成下一个可用 id。kind: grm|voc"""
    sub = "grammar" if kind == "grm" else "vocab"
    mx = 0
    d = KB / sub / lang
    if d.exists():
        for f in d.glob(f"{lang}-{kind}-*.yaml"):
            m = re.search(r"(\d+)", f.stem)
            if m:
                mx = max(mx, int(m.group(1)))
    return f"{lang}-{kind}-{mx + 1:05d}"


def load_entry(path: Path):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    kind = "grammar" if "/grammar/" in str(path) else "vocab"
    model = GrammarEntry if kind == "grammar" else VocabEntry
    return model.model_validate(data)


def validate_kb(kb_root: Path | None = None) -> list[str]:
    """校验 kb/ 全库，返回错误列表（空=通过）。"""
    kb_root = kb_root or KB
    errors: list[str] = []
    all_ids: set[str] = set()
    entries = []
    for sub, pat in (("grammar", "*-grm-*.yaml"), ("vocab", "*-voc-*.yaml")):
        for f in sorted((kb_root / sub).rglob(pat)):
            try:
                e = load_entry(f)
                if e.id in all_ids:
                    errors.append(f"{f}: id 重复 {e.id}")
                all_ids.add(e.id)
                entries.append(e)
            except Exception as ex:  # noqa: BLE001
                errors.append(f"{f}: {ex}")
    # 内部引用完整性
    for e in entries:
        for ref in e.related.cross_lang + [r.id for r in e.related.same_lang]:
            if ref not in all_ids:
                errors.append(f"{e.id}: 悬空引用 {ref}")
    # 跨语言组一致性
    for f in sorted((kb_root / "links").glob("xlang-*.yaml")):
        try:
            g = XlangGroup.model_validate(yaml.safe_load(f.read_text(encoding="utf-8")))
            for lang, ids in g.members.items():
                for i in ids:
                    if i not in all_ids:
                        errors.append(f"{f.name}: 成员 {i} 不存在")
        except Exception as ex:  # noqa: BLE001
            errors.append(f"{f}: {ex}")
    return errors


def export_schemas() -> None:
    out = PIPELINE_DIR / "schemas"
    out.mkdir(parents=True, exist_ok=True)
    import json
    (out / "grammar_entry.json").write_text(
        json.dumps(GrammarEntry.model_json_schema(), ensure_ascii=False, indent=2),
        encoding="utf-8")
    (out / "vocab_entry.json").write_text(
        json.dumps(VocabEntry.model_json_schema(), ensure_ascii=False, indent=2),
        encoding="utf-8")
