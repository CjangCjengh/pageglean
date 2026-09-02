"""检查目标目录（如 site/dist）是否泄露金丝雀片段。命中即退出码 1。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

KB_INTERNAL = Path(__file__).resolve().parents[2] / "kb" / "internal"


def main(target: str) -> int:
    canary_file = KB_INTERNAL / "canary.json"
    if not canary_file.exists():
        print("先生成金丝雀: python scripts/canary/gen_canary.py")
        return 2
    rows = json.loads(canary_file.read_text(encoding="utf-8"))
    hits = 0
    for row in rows:
        # 金丝雀本体与其 20 字子串都要查（防截断绕过）
        probes = {row["canary"], row["canary"][:20], row["canary"][10:30]}
        for probe in probes:
            r = subprocess.run(
                ["grep", "-rqF", probe, target],
                capture_output=True,
            )
            if r.returncode == 0:
                print(f"✗ 泄露! {row['book_id']} 片段命中: {probe[:24]}…")
                hits += 1
                break
    if hits:
        print(f"共 {hits} 处泄露")
        return 1
    print(f"✓ {len(rows)} 条金丝雀检查通过: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "site/dist"))
