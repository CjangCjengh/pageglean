"""为日语例句合成全量 ruby：书内注音优先，其余汉字用 unidic 词典读音补全。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline" / "src"))

import yaml  # noqa: E402

from langpipe.config import KB  # noqa: E402
from langpipe.tok.ja import tokenize_para  # noqa: E402

HAN = re.compile(r"[一-鿿㐀-䶿]")


_O_ROW = set("おこそもとのよろをごぞどうぞぼぽょ")
_E_ROW = set("えけせねへめれげぜでべぺぇ")


def kata_to_hira(s: str) -> str:
    """词典读音（片假名表记）转平假名振假名；长音ー按前行假名转 う/い。"""
    out = []
    for c in s:
        o = ord(c)
        if 0x30A1 <= o <= 0x30F6:  # ァ..ヶ
            out.append(chr(o - 0x60))
        else:
            out.append(c)
    # 后处理长音
    for i, c in enumerate(out):
        if c == "ー" and i > 0:
            if out[i - 1] in _O_ROW:
                out[i] = "う"
            elif out[i - 1] in _E_ROW:
                out[i] = "い"
    return "".join(out)


def synthesize(src: str) -> str:
    out: list[str] = []
    for t in tokenize_para(src):
        s, r = t["s"], t.get("r", "")
        if t.get("rs") != "book":
            r = kata_to_hira(r)
        if HAN.search(s) and r and r != s and r != "*":
            out.append(f"{s}[{r}]")
        else:
            out.append(s)
    return "".join(out)


def main() -> None:
    n = 0
    for f in sorted((KB / "grammar" / "ja").glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        changed = False
        for ex in d.get("examples", []):
            src = ex.get("annot") or ex.get("text", "")
            a = synthesize(src)
            if a and a != ex.get("annot"):
                ex["annot"] = a
                changed = True
                n += 1
        if changed:
            tmp = f.with_suffix(".yaml.tmp")
            tmp.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False),
                           encoding="utf-8")
            tmp.replace(f)
    print(f"已为 {n} 条例句合成全量 ruby")


if __name__ == "__main__":
    main()
