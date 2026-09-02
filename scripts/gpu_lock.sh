#!/usr/bin/env bash
# GPU 门控：在共享机器上找一张空闲显存足够的卡，输出卡号。
# 用法: CARD=$(scripts/gpu_lock.sh --need 20) || exit 1
# 参数: --need <GB>  需要的空闲显存（默认 24）
set -euo pipefail
need=24
while [[ $# -gt 0 ]]; do
  case "$1" in
    --need) need="$2"; shift 2 ;;
    *) shift ;;
  esac
done

found=""
while IFS= read -r line; do
  # 形如: [3] NVIDIA RTX A6000 | 47°C,  0 % |   18 / 49140 MB | user(4M)
  idx=$(echo "$line" | sed -n 's/^\[\([0-9]*\)\].*/\1/p') || true
  mem=$(echo "$line" | grep -oE '[0-9]+ / [0-9]+ MB' | head -1) || true
  [[ -z "${mem:-}" || -z "${idx:-}" ]] && continue
  used=${mem%% *}
  total=${mem#* / }; total=${total%% *}
  free_mb=$((total - used))
  if (( free_mb >= need * 1024 )); then
    found=$idx
    break
  fi
done < <(gpustat --no-header 2>/dev/null)

if [[ -n "$found" ]]; then
  echo "$found"
  exit 0
fi
echo "没有找到空闲显存 >= ${need}GB 的卡" >&2
exit 1
