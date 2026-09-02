"""泰语分词：pythainlp newmm 引擎。"""
from __future__ import annotations


def tokenize_para(text: str) -> list[dict]:
    from pythainlp.tokenize import word_tokenize
    toks = []
    for t in word_tokenize(text, engine="newmm", keep_whitespace=False):
        t = t.strip()
        if t:
            toks.append({"s": t, "b": t, "p": ""})  # v1 不做泰语词性
    return toks
