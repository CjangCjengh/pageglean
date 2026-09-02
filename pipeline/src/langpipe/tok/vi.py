"""越南语分词：underthesea（词级切分，保留声调）。"""
from __future__ import annotations


def tokenize_para(text: str) -> list[dict]:
    from underthesea import word_tokenize
    res = word_tokenize(text)
    if isinstance(res, str):
        res = res.split()
    toks = []
    for t in res:
        t = t.strip()
        if t:
            toks.append({"s": t, "b": t.lower(), "p": ""})
    return toks
