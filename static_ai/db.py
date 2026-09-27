"""Small, durable SQLite store. All mutations are transaction scoped."""

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone


def uid():
    return uuid.uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.RLock()
        with self.tx() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,title TEXT,created TEXT);
            CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,conversation_id TEXT,role TEXT,content TEXT,created TEXT);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,conversation_id TEXT,status TEXT,mode TEXT,budget REAL,state TEXT,error TEXT,created TEXT,updated TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON runs(conversation_id) WHERE status IN ('queued','running','awaiting_approval');
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT,kind TEXT,data TEXT,created TEXT);
            CREATE INDEX IF NOT EXISTS events_run ON events(run_id,id);
            CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,conversation_id TEXT,run_id TEXT,name TEXT,mime TEXT,path TEXT,size INTEGER,created TEXT);
            CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,run_id TEXT,tool TEXT,args TEXT,cost REAL,status TEXT,created TEXT);
            CREATE TABLE IF NOT EXISTS charges(id TEXT PRIMARY KEY,run_id TEXT,amount REAL,kind TEXT,status TEXT,created TEXT);
            CREATE TABLE IF NOT EXISTS media_jobs(id TEXT PRIMARY KEY,run_id TEXT,conversation_id TEXT,prediction_id TEXT,kind TEXT,status TEXT,output TEXT,error TEXT,created TEXT);
            CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY,value TEXT,expires REAL);
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,title TEXT,objective TEXT,category TEXT,status TEXT,steps TEXT,conversation_id TEXT,created TEXT,updated TEXT);
            CREATE INDEX IF NOT EXISTS tasks_conversation ON tasks(conversation_id);
            """)

    @contextmanager
    def tx(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                db.execute("BEGIN IMMEDIATE")
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

    def query(self, sql, args=()):
        with self.tx() as db:
            return [dict(r) for r in db.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        rows = self.query(sql, args)
        return rows[0] if rows else None

    def execute(self, sql, args=()):
        with self.tx() as db:
            return db.execute(sql, args).rowcount

    def event(self, run_id, kind, data):
        self.execute(
            "INSERT INTO events(run_id,kind,data,created) VALUES(?,?,?,?)",
            (run_id, kind, json.dumps(data, ensure_ascii=False), now()),
        )

    def message(self, conversation_id, role, content):
        self.execute(
            "INSERT INTO messages VALUES(?,?,?,?,?)", (uid(), conversation_id, role, content, now())
        )

    def run_state(self, run_id, state, status="running"):
        self.execute(
            "UPDATE runs SET state=?,status=?,updated=? WHERE id=?",
            (json.dumps(state), status, now(), run_id),
        )

    def spending(self, run_id=None):
        where, args = ("run_id=?", (run_id,)) if run_id else ("created>=?", (now()[:10],))
        return self.one(
            f"SELECT COALESCE(SUM(amount),0) AS total FROM charges WHERE {where}", args
        )["total"]

    def reserve(self, run_id, amount, kind, daily_limit):
        # Atomic check and reservation prevents simultaneous model/skill calls overspending.
        with self.tx() as db:
            run = db.execute("SELECT budget FROM runs WHERE id=?", (run_id,)).fetchone()
            if not run:
                raise ValueError("Run does not exist")
            spent = db.execute(
                "SELECT COALESCE(SUM(amount),0) FROM charges WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            daily = db.execute(
                "SELECT COALESCE(SUM(amount),0) FROM charges WHERE created>=?", (now()[:10],)
            ).fetchone()[0]
            if amount + spent > run["budget"] + 1e-9 or amount + daily > daily_limit + 1e-9:
                raise ValueError(
                    "Spending limit reached. Increase the budget in Settings or use a local model."
                )
            charge = uid()
            db.execute(
                "INSERT INTO charges VALUES(?,?,?,?,?,?)",
                (charge, run_id, amount, kind, "reserved", now()),
            )
            return charge

    def settle(self, charge, amount=None):
        if amount is None:
            self.execute("UPDATE charges SET status='estimated' WHERE id=?", (charge,))
        else:
            self.execute(
                "UPDATE charges SET amount=?,status='estimated' WHERE id=?",
                (max(0, amount), charge),
            )
