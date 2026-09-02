"""claude -p headless 封装：进程调用、JSON 解析、超时。"""
from __future__ import annotations

import json
import re
import subprocess

DEFAULT_TIMEOUT = 900
DEFAULT_MODEL = "sonnet"  # 批量任务默认 sonnet；opus 慢 10 倍以上


def run_claude(prompt: str, timeout: int = DEFAULT_TIMEOUT,
               allowed_tools: str = "", model: str = DEFAULT_MODEL,
               max_turns: int = 1, parse_json: bool = True) -> dict:
    """调用 claude -p，返回 {data, raw, usage}。allowed_tools='' 表示禁用危险工具。"""
    cmd = ["claude", "-p", "--output-format", "json",
           "--model", model, "--max-turns", str(max_turns),
           "--allowedTools", allowed_tools] if allowed_tools else \
          ["claude", "-p", "--output-format", "json",
           "--model", model, "--max-turns", str(max_turns)]
    if not allowed_tools:
        cmd += ["--disallowedTools", "Bash,Write,Edit,NotebookEdit,WebFetch,WebSearch,Agent"]
    p = subprocess.run(cmd, input=prompt.encode("utf-8"),
                       capture_output=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"claude exit={p.returncode}: {p.stderr.decode()[:500]}")
    env = json.loads(p.stdout.decode("utf-8"))
    raw = env.get("result", "")
    usage = env.get("usage") or {}
    data = extract_json(raw) if parse_json else None
    return {"data": data, "raw": raw, "usage": usage}


def extract_json(text: str):
    """从模型输出中稳健地抽出 JSON 对象/数组。"""
    m = re.search(r"```(?:json)?\s*([\{\[].*?[\}\]])\s*```", text, re.S)
    cand = m.group(1) if m else text
    for opener, closer in (("{", "}"), ("[", "]")):
        s = cand.find(opener)
        e = cand.rfind(closer)
        if 0 <= s < e:
            try:
                return json.loads(cand[s:e + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"输出中无有效 JSON: {text[:200]}")
