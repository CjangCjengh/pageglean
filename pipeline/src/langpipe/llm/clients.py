"""LLM HTTP 客户端：本地 vLLM 与阿里云 MaaS（均为 OpenAI 兼容）。

并发控制：
  - vLLM 信号量 48（单实例吞吐型）
  - MaaS 信号量 3（配额仅 3-5），tenacity 退避 + 连续失败熔断 5 分钟
密钥读取顺序：环境变量 → 仓库根 .env（gitignore）
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from openai import APIStatusError, AsyncOpenAI
from tenacity import (retry, retry_if_exception, stop_after_attempt,
                      wait_exponential)


def _retryable(e: BaseException) -> bool:
    if isinstance(e, (asyncio.TimeoutError, ConnectionError)):
        return True
    if isinstance(e, APIStatusError):
        return e.status_code in (408, 409, 429, 500, 502, 503, 504)
    return False

from ..config import REPO_ROOT

MAAS_BASE = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"


def load_env_file() -> None:
    envf = REPO_ROOT / ".env"
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def get_maas_key() -> str:
    load_env_file()
    key = os.environ.get("MAAS_API_KEY", "")
    if not key:
        raise RuntimeError("缺少 MAAS_API_KEY（环境变量或仓库根 .env）")
    return key


class VLLMClient:
    """本地 vLLM 批量客户端。"""

    def __init__(self, base_url: str = "http://127.0.0.1:8101/v1",
                 model: str = "qwen", concurrency: int = 48):
        self.client = AsyncOpenAI(base_url=base_url, api_key="EMPTY")
        self.model = model
        self.sem = asyncio.Semaphore(concurrency)

    async def chat(self, messages: list[dict], temperature: float = 0.2,
                   max_tokens: int = 1024) -> str:
        async with self.sem:
            r = await self.client.chat.completions.create(
                model=self.model, messages=messages,
                temperature=temperature, max_tokens=max_tokens)
            return r.choices[0].message.content or ""


class CircuitOpen(Exception):
    pass


class MaasClient:
    """阿里云 MaaS 客户端：低并发 + 退避重试 + 熔断。"""

    def __init__(self, model: str = "qwen3.7-plus", concurrency: int = 3,
                 fail_threshold: int = 10, cooldown: int = 300):
        self.client = AsyncOpenAI(base_url=MAAS_BASE, api_key=get_maas_key())
        self.model = model
        self.sem = asyncio.Semaphore(concurrency)
        self._fails = 0
        self._open_until = 0.0
        self._fail_threshold = fail_threshold
        self._cooldown = cooldown

    def _trip_check(self) -> None:
        if time.time() < self._open_until:
            raise CircuitOpen(f"熔断中，{int(self._open_until - time.time())}s 后恢复")

    @retry(
        retry=retry_if_exception(_retryable),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(4),
    )
    async def chat(self, messages: list[dict], temperature: float = 0.3,
                   max_tokens: int = 2048, timeout: float = 90.0) -> str:
        self._trip_check()
        async with self.sem:
            try:
                r = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model, messages=messages,
                        temperature=temperature, max_tokens=max_tokens),
                    timeout=timeout)
                self._fails = 0
                return r.choices[0].message.content or ""
            except Exception:
                self._fails += 1
                if self._fails >= self._fail_threshold:
                    self._open_until = time.time() + self._cooldown
                    self._fails = 0
                raise
