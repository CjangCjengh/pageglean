"""SQLite ledger —— 管线状态中枢，支持断点续跑。"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path

from .config import LEDGER_DB

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  stage TEXT NOT NULL,
  book_id TEXT,
  item_key TEXT,
  executor TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  enqueue_ts INTEGER, start_ts INTEGER, end_ts INTEGER,
  prompt_tokens INTEGER, completion_tokens INTEGER,
  output_path TEXT,
  error TEXT
);
CREATE TABLE IF NOT EXISTS books (
  book_id TEXT PRIMARY KEY, lang TEXT, sha256 TEXT, path TEXT, registered_ts INTEGER
);
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, stage TEXT, config_json TEXT, started_ts INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tasks_stage_status ON tasks(stage, status);
"""


class Ledger:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path or LEDGER_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=60)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    # ---------- tasks ----------
    def enqueue(self, task_id: str, stage: str, book_id: str | None = None,
                item_key: str | None = None, max_attempts: int = 3) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO tasks(id,stage,book_id,item_key,max_attempts,enqueue_ts)"
            " VALUES(?,?,?,?,?,?)",
            (task_id, stage, book_id, item_key, max_attempts, int(time.time())),
        )
        self.conn.commit()

    def pending(self, stage: str, reset_stale_after: int = 1800) -> list[dict]:
        """返回该阶段所有待办任务（含可重试的失败任务），并重置超时的 running。"""
        now = int(time.time())
        self.conn.execute(
            "UPDATE tasks SET status='queued' WHERE stage=? AND status='running' AND start_ts < ?",
            (stage, now - reset_stale_after),
        )
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE stage=? AND"
            " (status='queued' OR (status='failed' AND attempts<max_attempts))"
            " ORDER BY enqueue_ts",
            (stage,),
        ).fetchall()
        self.conn.commit()
        return [dict(r) for r in rows]

    def claim(self, task_id: str) -> None:
        self.conn.execute(
            "UPDATE tasks SET status='running', attempts=attempts+1, start_ts=? WHERE id=?",
            (int(time.time()), task_id),
        )
        self.conn.commit()

    def complete(self, task_id: str, output_path: str | None = None,
                 prompt_tokens: int | None = None, completion_tokens: int | None = None,
                 executor: str | None = None) -> None:
        self.conn.execute(
            "UPDATE tasks SET status='done', end_ts=?, output_path=?,"
            " prompt_tokens=?, completion_tokens=?, executor=COALESCE(?,executor) WHERE id=?",
            (int(time.time()), output_path, prompt_tokens, completion_tokens, executor, task_id),
        )
        self.conn.commit()

    def fail(self, task_id: str, error: str) -> None:
        self.conn.execute(
            "UPDATE tasks SET status='failed', end_ts=?, error=? WHERE id=?",
            (int(time.time()), str(error)[:2000], task_id),
        )
        self.conn.commit()

    def is_done(self, task_id: str) -> bool:
        r = self.conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        return bool(r and r["status"] == "done")

    def report(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT stage, status, COUNT(*) AS n,"
            " COALESCE(SUM(prompt_tokens),0) AS prompt_tokens,"
            " COALESCE(SUM(completion_tokens),0) AS completion_tokens"
            " FROM tasks GROUP BY stage, status ORDER BY stage, status"
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------- books ----------
    def register_book(self, book_id: str, lang: str, sha256: str, path: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO books(book_id,lang,sha256,path,registered_ts) VALUES(?,?,?,?,?)",
            (book_id, lang, sha256, path, int(time.time())),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


def content_hash(*parts) -> str:
    """内容寻址哈希：幂等键的一部分。"""
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()[:16]
