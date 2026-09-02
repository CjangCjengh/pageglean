"""日语分词：fugashi + unidic-lite；书内 ruby 读音优先于词典读音。"""
from __future__ import annotations

import re

_tagger = None

POS_JA = {
    "名詞": "noun", "固有名詞": "noun", "代名詞": "noun",
    "動詞": "verb",
    "形容詞": "adj", "形状詞": "adj",
    "副詞": "adv",
    "助詞": "func", "助動詞": "func", "接続詞": "func",
    "接頭辞": "affix", "接尾辞": "affix",
    "記号": "punct", "補助記号": "punct",
    "感動詞": "other", "フィラー": "other", "連体詞": "other", "接頭辞": "affix",
}

_ANNOT_RE = re.compile(r"([^\[\]]+)(?:\[([^\[\]]+)\])?")


def _get_tagger():
    global _tagger
    if _tagger is None:
        import fugashi
        _tagger = fugashi.Tagger()
    return _tagger


def parse_annot(annot: str):
    """'財布[サイフ]を落とす' → [('ruby','財布','サイフ'), ('plain','を落とす','')]"""
    return [
        ("ruby" if read else "plain", txt, read or "")
        for txt, read in _ANNOT_RE.findall(annot)
    ]


def _mk(w, read_override: str | None = None, rs: str | None = None) -> dict:
    f = w.feature
    t = {"s": w.surface, "b": f.lemma or w.surface,
         "r": read_override or (f.pron or ""), "p": POS_JA.get(f.pos1, "other")}
    if rs:
        t["rs"] = rs
    return t


def tokenize_para(annot: str) -> list[dict]:
    tagger = _get_tagger()
    toks: list[dict] = []
    for kind, txt, read in parse_annot(annot):
        ws = list(tagger(txt))
        if kind == "ruby" and len(ws) == 1:
            toks.append(_mk(ws[0], read_override=read, rs="book"))
        else:
            for w in ws:
                toks.append(_mk(w, None, "dict" if kind == "ruby" else None))
    return toks
