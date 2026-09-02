#!/usr/bin/env bash
# 起本地 vLLM 推理服务（供管线批量任务调用）。
# 用法: scripts/serve_qwen.sh [模型] [端口]
#   模型: qwen3-8b (默认) | qwen2.5-14b
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_NAME="${1:-qwen3-8b}"
PORT="${2:-8101}"
HF=~/.cache/huggingface/hub

case "$MODEL_NAME" in
  qwen3-8b)     MODEL="$HF/models--Qwen--Qwen3-8B" ; NEED=20 ;;
  qwen2.5-14b)  MODEL="$HF/models--Qwen--Qwen2.5-14B-Instruct" ; NEED=32 ;;
  *) echo "未知模型: $MODEL_NAME"; exit 1 ;;
esac

SNAP=$(ls -d "$MODEL"/snapshots/*/ 2>/dev/null | head -1)
[[ -n "$SNAP" ]] || { echo "$MODEL 没有本地快照"; exit 1; }

CARD=$(scripts/gpu_lock.sh --need "$NEED")
echo "使用 GPU $CARD 启动 $MODEL_NAME @ :$PORT"

source ~/miniconda3/etc/profile.d/conda.sh
conda activate vllm-deploy
CUDA_VISIBLE_DEVICES="$CARD" HF_HUB_OFFLINE=1 \
  vllm serve "$SNAP" --port "$PORT" --gpu-memory-utilization 0.9 \
  --max-model-len 8192
