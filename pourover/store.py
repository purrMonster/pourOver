"""SQLite (WAL): command log, pending confirms, queue. Nothing else is stored;
Vikunja holds the tasks."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS command (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL,
  sender TEXT NOT NULL,
  channel TEXT NOT NULL,
  text TEXT NOT NULL,
  path TEXT,
  plan TEXT,
  outcome TEXT,
  reply TEXT,
  created_task_ids TEXT,
  latency_ms INTEGER
);
CREATE TABLE IF NOT EXISTS pending (
  sender TEXT PRIMARY KEY,
  plan TEXT NOT NULL,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS queue (
  id INTEGER PRIMARY KEY,
  sender TEXT NOT NULL,
  channel TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'waiting'
);
"""


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript(SCHEMA)

    def _exec(self, sql: str, args=()):
        with self.lock:
            return self.db.execute(sql, args)

    def ping(self) -> bool:
        return self._exec("SELECT 1").fetchone()[0] == 1

    # ---- command log -------------------------------------------------
    def log(self, *, now: datetime, sender: str, channel: str, text: str, path: str | None, plan: str | None,
            outcome: str, reply: str, created_task_ids: list[int] | None = None, latency_ms: int = 0) -> int:
        cur = self._exec(
            "INSERT INTO command (created_at, sender, channel, text, path, plan, outcome, reply, created_task_ids, latency_ms)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (now.isoformat(), sender, channel, text, path, plan, outcome, reply,
             json.dumps(created_task_ids or []), latency_ms),
        )
        return cur.lastrowid

    def last_created(self, sender: str) -> list[int]:
        row = self._exec(
            "SELECT created_task_ids FROM command WHERE sender=? AND created_task_ids != '[]' ORDER BY id DESC LIMIT 1",
            (sender,),
        ).fetchone()
        return json.loads(row[0]) if row else []

    def commands(self) -> list[sqlite3.Row]:
        return self._exec("SELECT * FROM command ORDER BY id").fetchall()

    # ---- pending confirms -------------------------------------------
    def set_pending(self, sender: str, plan_json: str, summary: str, now: datetime) -> None:
        self._exec("INSERT OR REPLACE INTO pending VALUES (?,?,?,?)", (sender, plan_json, summary, now.isoformat()))

    def pop_pending(self, sender: str) -> Optional[sqlite3.Row]:
        row = self._exec("SELECT * FROM pending WHERE sender=?", (sender,)).fetchone()
        if row:
            self._exec("DELETE FROM pending WHERE sender=?", (sender,))
        return row

    def has_pending(self, sender: str) -> bool:
        return self._exec("SELECT 1 FROM pending WHERE sender=?", (sender,)).fetchone() is not None

    # ---- queue -------------------------------------------------------
    def enqueue(self, sender: str, channel: str, text: str, now: datetime) -> int:
        return self._exec("INSERT INTO queue (sender, channel, text, created_at) VALUES (?,?,?,?)",
                          (sender, channel, text, now.isoformat())).lastrowid

    def waiting(self) -> list[sqlite3.Row]:
        return self._exec("SELECT * FROM queue WHERE status='waiting' ORDER BY id").fetchall()

    def set_status(self, queue_id: int, status: str) -> None:
        self._exec("UPDATE queue SET status=? WHERE id=?", (status, queue_id))
