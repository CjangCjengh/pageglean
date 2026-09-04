"""巡检 M2 释义进度：某语言全部批次完成且未入库时，拷入 kb/enrich/ 供审阅。

只拷贝+打标记，commit/push 由调用方（cron 提示词）执行。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline" / "src"))

from langpipe.config import CANDIDATES, DATA, KB  # noqa: E402
from langpipe.ledger import Ledger  # noqa: E402


def main() -> int:
    led = Ledger()
    newly: list[str] = []
    for lg in ("ja", "ko", "th", "vi"):
        tsv = CANDIDATES / lg / "vocab_candidates.tsv"
        if not tsv.exists():
            continue
        rows = tsv.read_text(encoding="utf-8").strip().splitlines()[1:]
        total = (len(rows) + 19) // 20
        # 只统计当前模型（qwen3.8-max）完成的批次，避免旧模型任务混入
        done = led.conn.execute(
            "SELECT COUNT(*) c FROM tasks WHERE stage='s4a_gloss' AND status='done'"
            " AND executor='maas-qwen3.8-max' AND item_key LIKE ?",
            (f"{lg}#%",)).fetchone()["c"]
        target = KB / "enrich" / lg
        if done >= total and not target.exists():
            src = DATA / "enrich" / lg
            if src.exists():
                shutil.copytree(src, target)
                newly.append(f"{lg}({done}/{total})")
                print(f"NEW {lg} done={done}/{total}")
        elif done < total:
            print(f"RUN {lg} {done}/{total}")
        else:
            print(f"OK  {lg} 已入库待审")
    if not newly:
        print("NO_NEW")
    return 0


if __name__ == "__main__":
    sys.exit(main())
