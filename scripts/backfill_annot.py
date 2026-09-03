"""一次性脚本：从提取候选的源块标注文本回填已有条目的例句 ruby annot。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline" / "src"))

import yaml  # noqa: E402

from langpipe.config import CANDIDATES, KB  # noqa: E402
from langpipe.merge.adopt import annot_for_example  # noqa: E402


def main() -> None:
    chunks: list[str] = []
    for f in sorted(CANDIDATES.rglob("*.json")):
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
            ct = payload.get("chunk_text", "")
            if ct:
                chunks.append(ct)
        except Exception:  # noqa: BLE001
            continue
    print(f"源块 {len(chunks)} 个")

    n_fill = n_miss = 0
    for f in sorted((KB / "grammar").rglob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        changed = False
        for ex in d.get("examples", []):
            # 强制从源块还原书内注音版本（覆盖旧 annot，保证幂等链）
            for ct in chunks:
                a = annot_for_example(ex.get("text", ""), ct)
                if a:
                    ex["annot"] = a
                    changed = True
                    n_fill += 1
                    break
            else:
                n_miss += 1
        if changed:
            tmp = f.with_suffix(".yaml.tmp")
            tmp.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False),
                           encoding="utf-8")
            tmp.replace(f)
    print(f"回填 {n_fill} 条例句，未匹配 {n_miss} 条")


if __name__ == "__main__":
    main()
