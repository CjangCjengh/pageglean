"""韩语分词：kiwipiepy（Kiwi）。"""
from __future__ import annotations

_kiwi = None

_POS_KO_PREFIX = {
    "NN": "noun", "NP": "noun",
    "VV": "verb", "VA": "adj", "VX": "verb", "VCP": "func", "VCN": "func",
    "MM": "other", "MAG": "adv", "MAJ": "adv",
    "IC": "other",
    "JK": "func", "EC": "func", "EF": "func", "EP": "func", "ET": "func",
    "XS": "affix",
    "SF": "punct", "SE": "punct", "SS": "punct", "SP": "punct", "SO": "punct",
    "SL": "other", "SN": "other", "SW": "other", "NF": "other", "NV": "other",
    "NA": "other",
}


def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return _kiwi


def _pos_class(tag: str) -> str:
    if tag in _POS_KO_PREFIX:
        return _POS_KO_PREFIX[tag]
    return _POS_KO_PREFIX.get(tag[:2], "other")


def tokenize_para(text: str) -> list[dict]:
    kiwi = _get_kiwi()
    toks = []
    for t in kiwi.tokenize(text):
        form = t.form.strip()
        if not form:
            continue
        toks.append({"s": form, "b": t.lemma or form, "p": _pos_class(t.tag)})
    return toks
