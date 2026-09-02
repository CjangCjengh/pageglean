"""全局路径与常量。"""
import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("PAGEGLEAN_ROOT", Path(__file__).resolve().parents[3]))

CORPUS = REPO_ROOT / "corpus"
DATA = REPO_ROOT / "data"
KB = REPO_ROOT / "kb"
PIPELINE_DIR = REPO_ROOT / "pipeline"
PROMPTS_DIR = PIPELINE_DIR / "prompts"
LANGDATA_DIR = PIPELINE_DIR / "langdata"

RAW = DATA / "raw"            # S1 章节产物
TOKENS = DATA / "tokens"      # S2 分词产物
FREQ = DATA / "freq"          # S3 词频表
CANDIDATES = DATA / "candidates"  # S3/S4 候选
CHUNKS = DATA / "chunks"      # S4b 输入块
LEDGER_DB = DATA / "ledger" / "pipeline.db"

LANGS = ("ja", "ko", "th", "vi")

# 版权硬约束（入库处强制执行，与站点侧脱敏双保险）
MAX_EXAMPLES_PER_ENTRY = 2
MAX_EXAMPLE_CHARS = 120


def ensure_dirs() -> None:
    for d in (RAW, TOKENS, FREQ, CANDIDATES, CHUNKS, LEDGER_DB.parent):
        d.mkdir(parents=True, exist_ok=True)
