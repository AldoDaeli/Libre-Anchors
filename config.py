"""Konfigurasi aplikasi. Semua rahasia dibaca dari environment / file .env (jangan di-commit)."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(name, default):
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        raise RuntimeError(f"Nilai {name} harus berupa angka.")


def _dev_secret(instance_dir: Path) -> str:
    """Kunci acak khusus development, disimpan agar OTP/sesi tidak rusak tiap restart."""
    path = instance_dir / "dev_secret.key"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_urlsafe(48)
    path.write_text(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def load_config(overrides=None):
    env = os.getenv("APP_ENV", "development").lower()
    prod = env == "production"
    on_vercel = bool(os.getenv("VERCEL"))
    # Vercel: filesystem read-only kecuali /tmp (sementara). Tidak ada yang penting disimpan di sana.
    instance_dir = Path(os.getenv("INSTANCE_DIR", "/tmp/tuxpedia" if on_vercel else BASE_DIR / "instance"))
    instance_dir.mkdir(parents=True, exist_ok=True)

    cfg = {
        "ENV": env,
        "IS_PROD": prod,
        "BASE_DIR": BASE_DIR,
        "INSTANCE_DIR": instance_dir,
        "STATIC_DIR": BASE_DIR / "static",
        "DATA_FILE": BASE_DIR / "data" / "distros.json",
        "DATABASE": os.getenv("DATABASE_PATH", str(instance_dir / "tuxpedia.db")),  # SQLite (dev/tes)
        "DATABASE_URL": os.getenv("DATABASE_URL", "").strip(),                       # Postgres/Supabase
        "AUTO_INIT_DB": _bool("AUTO_INIT_DB", False),
        "ON_VERCEL": on_vercel,
        "LOG_TO_FILE": _bool("LOG_TO_FILE", not on_vercel),
        "SECRET_KEY": os.getenv("SECRET_KEY") or (None if prod else _dev_secret(instance_dir)),
        # Cookie
        "COOKIE_SECURE": _bool("COOKIE_SECURE", prod),
        # Sesi
        "SESSION_IDLE_SECONDS": _int("SESSION_IDLE_MINUTES", 60) * 60,
        "SESSION_ABSOLUTE_SECONDS": _int("SESSION_ABSOLUTE_HOURS", 12) * 3600,
        "MAX_SESSIONS_PER_USER": _int("MAX_SESSIONS_PER_USER", 5),
        # OTP
        "OTP_TTL_SECONDS": _int("OTP_TTL_MINUTES", 10) * 60,
        "OTP_MAX_ATTEMPTS": _int("OTP_MAX_ATTEMPTS", 5),
        "OTP_RESEND_COOLDOWN": _int("OTP_RESEND_COOLDOWN_SECONDS", 60),
        "CHALLENGE_TTL_SECONDS": 15 * 60,
        "LOGIN_OTP": _bool("LOGIN_OTP", True),  # True = login butuh sandi + OTP (2 langkah)
        # Kata sandi
        "PASSWORD_MIN_LENGTH": _int("PASSWORD_MIN_LENGTH", 10),
        # Email (Gmail SMTP + App Password)
        "MAIL_BACKEND": os.getenv("MAIL_BACKEND", "smtp" if prod else "console").lower(),
        "SMTP_HOST": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "SMTP_PORT": _int("SMTP_PORT", 587),
        "MAIL_SYNC": _bool("MAIL_SYNC", on_vercel),  # serverless: thread latar belakang dimatikan setelah respons
        "GMAIL_USER": os.getenv("GMAIL_USER", ""),
        "GMAIL_APP_PASSWORD": os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", ""),
        "MAIL_FROM_NAME": os.getenv("MAIL_FROM_NAME", "Tuxpedia"),
        # Di belakang reverse proxy (nginx): jumlah proxy tepercaya. 0 = jangan percaya X-Forwarded-*.
        "TRUSTED_PROXIES": _int("TRUSTED_PROXIES", 0),
        # Batas ukuran request (cukup kecil: semua body hanyalah JSON pendek)
        "MAX_CONTENT_LENGTH": 32 * 1024,
        # Batas laju (jumlah, jendela detik)
        "RL_REGISTER_IP": (10, 3600),
        "RL_REGISTER_EMAIL": (5, 3600),
        "RL_LOGIN_IP": (40, 600),
        "RL_LOGIN_FAIL_EMAIL": (5, 900),
        "RL_LOGIN_FAIL_IP": (25, 900),
        "RL_VERIFY_IP": (40, 900),
        "RL_RESEND_IP": (20, 3600),
        "RL_PASSWORD_CHANGE": (5, 900),
        "RL_CONTACT_IP": (5, 3600),
    }
    if overrides:
        cfg.update(overrides)

    # ----- Pemeriksaan wajib: aplikasi menolak jalan dengan konfigurasi tidak aman di production -----
    problems = []
    if cfg["IS_PROD"]:
        if not cfg["SECRET_KEY"] or len(cfg["SECRET_KEY"]) < 32:
            problems.append("SECRET_KEY wajib diisi (minimal 32 karakter acak).")
        if cfg["MAIL_BACKEND"] != "smtp":
            problems.append("MAIL_BACKEND harus 'smtp' di production.")
        if not cfg["COOKIE_SECURE"]:
            problems.append("COOKIE_SECURE harus aktif di production (pakai HTTPS).")
    if cfg["ON_VERCEL"] and not cfg["DATABASE_URL"]:
        problems.append("DATABASE_URL (Supabase) wajib diisi di Vercel: SQLite tidak tersimpan permanen di sana.")
    if cfg["DATABASE_URL"] and not cfg["DATABASE_URL"].startswith(("postgres://", "postgresql://")):
        problems.append("DATABASE_URL harus diawali postgresql://")
    if cfg["MAIL_BACKEND"] == "smtp" and not (cfg["GMAIL_USER"] and cfg["GMAIL_APP_PASSWORD"]):
        problems.append("GMAIL_USER dan GMAIL_APP_PASSWORD wajib diisi untuk MAIL_BACKEND=smtp.")
    if cfg["MAIL_BACKEND"] not in ("smtp", "console", "memory"):
        problems.append("MAIL_BACKEND harus smtp, console, atau memory.")
    if problems:
        raise RuntimeError("Konfigurasi tidak valid:\n - " + "\n - ".join(problems))
    return cfg
