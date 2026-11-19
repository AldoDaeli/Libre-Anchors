"""Lapisan database. Semua query memakai parameter (?) sehingga kebal terhadap SQL injection.

  - DATABASE_URL terisi  -> Postgres (Supabase) lewat psycopg 3   [production / Vercel]
  - kosong               -> SQLite lokal                          [development & tes]
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    verified      INTEGER NOT NULL DEFAULT 0,
    city          TEXT    NOT NULL DEFAULT '',
    address       TEXT    NOT NULL DEFAULT '',
    created_at    INTEGER NOT NULL,
    updated_at    INTEGER NOT NULL
);

-- Kode OTP disimpan sebagai HMAC (bukan plaintext), satu kode aktif per (user, tujuan).
CREATE TABLE IF NOT EXISTS otps (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose    TEXT    NOT NULL CHECK (purpose IN ('register', 'login')),
    code_hash  TEXT    NOT NULL,
    expires_at INTEGER NOT NULL,
    attempts   INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    UNIQUE (user_id, purpose)
);

-- Token sesi tidak disimpan; hanya hash SHA-256-nya (kebocoran DB tidak membocorkan sesi aktif).
CREATE TABLE IF NOT EXISTS sessions (
    id_hash    TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at INTEGER NOT NULL,
    last_seen  INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    ip         TEXT,
    user_agent TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS rate_limits (
    key          TEXT PRIMARY KEY,
    window_start INTEGER NOT NULL,
    count        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
"""


# Galat "data duplikat" dari kedua mesin database.
INTEGRITY_ERRORS = (sqlite3.IntegrityError,)
try:  # psycopg hanya wajib bila memakai Postgres
    import psycopg
    from psycopg.rows import dict_row
    INTEGRITY_ERRORS += (psycopg.errors.IntegrityError,)
except ImportError:  # pragma: no cover
    psycopg = None


class Database:
    """Pembungkus tipis: execute(sql, params) dengan placeholder '?' untuk SQLite maupun Postgres."""

    def __init__(self, conn, kind):
        self.conn, self.kind = conn, kind

    def execute(self, sql, params=()):
        if self.kind == "pg":
            sql = sql.replace("?", "%s")
        return self.conn.execute(sql, params)

    @contextmanager
    def transaction(self):
        """Transaksi atomik (mencegah race condition pada penghitung dan OTP)."""
        if self.kind == "pg":
            with self.conn.transaction():
                yield
            return
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def close(self):
        self.conn.close()


def _pg_url(url):
    # Supabase mewajibkan TLS; paksa verifikasi enkripsi bila URL tidak menyebutkannya (OWASP A02).
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def connect():
    cfg = current_app.config
    if cfg.get("DATABASE_URL"):
        if psycopg is None:
            raise RuntimeError("Paket psycopg belum terpasang (pip install -r requirements.txt).")
        conn = psycopg.connect(
            _pg_url(cfg["DATABASE_URL"]), autocommit=True, row_factory=dict_row,
            connect_timeout=8,
            prepare_threshold=None,  # wajib untuk Supabase pooler (mode transaction): tanpa prepared statement
        )
        return Database(conn, "pg")
    conn = sqlite3.connect(cfg["DATABASE"], timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return Database(conn, "sqlite")


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def tx(db):
    return db.transaction()


def init_db():
    """SQLite: otomatis. Postgres: lewat schema_postgres.sql / init_db.py (bukan tiap cold start)."""
    db = get_db()
    if db.kind == "sqlite":
        db.conn.executescript(SCHEMA)
    elif current_app.config.get("AUTO_INIT_DB"):
        apply_pg_schema(db)


def apply_pg_schema(db):
    sql = (Path(__file__).resolve().parent / "schema_postgres.sql").read_text(encoding="utf-8")
    for stmt in (s.strip() for s in sql.split(";")):
        if stmt and not all(l.strip().startswith("--") or not l.strip() for l in stmt.splitlines()):
            db.execute(stmt)
