-- Skema Supabase (Postgres). Tempel di Supabase > SQL Editor > Run, ATAU jalankan:  python init_db.py
-- Aman dijalankan berulang kali.

CREATE TABLE IF NOT EXISTS users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    verified      INTEGER NOT NULL DEFAULT 0,
    city          TEXT    NOT NULL DEFAULT '',
    address       TEXT    NOT NULL DEFAULT '',
    created_at    BIGINT  NOT NULL,
    updated_at    BIGINT  NOT NULL
);

-- Kode OTP disimpan sebagai HMAC (bukan plaintext), satu kode aktif per (user, tujuan).
CREATE TABLE IF NOT EXISTS otps (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose    TEXT    NOT NULL CHECK (purpose IN ('register', 'login')),
    code_hash  TEXT    NOT NULL,
    expires_at BIGINT  NOT NULL,
    attempts   INTEGER NOT NULL DEFAULT 0,
    created_at BIGINT  NOT NULL,
    UNIQUE (user_id, purpose)
);

-- Token sesi tidak disimpan; hanya hash SHA-256-nya.
CREATE TABLE IF NOT EXISTS sessions (
    id_hash    TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at BIGINT NOT NULL,
    last_seen  BIGINT NOT NULL,
    expires_at BIGINT NOT NULL,
    ip         TEXT,
    user_agent TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS rate_limits (
    key          TEXT PRIMARY KEY,
    window_start BIGINT  NOT NULL,
    count        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       TEXT   NOT NULL,
    email      TEXT   NOT NULL,
    body       TEXT   NOT NULL,
    created_at BIGINT NOT NULL
);

-- PENTING (OWASP A01/A05): Supabase membuka semua tabel di schema "public" lewat REST API publik
-- (anon key). Aktifkan Row Level Security TANPA policy => anon/authenticated tidak bisa membaca/menulis
-- apa pun lewat API itu. Backend Flask tetap bisa karena memakai koneksi Postgres langsung (role postgres,
-- yang melewati RLS).
ALTER TABLE users       ENABLE ROW LEVEL SECURITY;
ALTER TABLE otps        ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages    ENABLE ROW LEVEL SECURITY;
