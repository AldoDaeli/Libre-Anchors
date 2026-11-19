"""Primitif keamanan: hashing sandi, OTP, token, CSRF, rate limit, validasi input."""
import base64
import hashlib
import hmac
import re
import secrets
import time
import unicodedata

from werkzeug.security import check_password_hash, generate_password_hash


# ---------------------------------------------------------------------------
# Kata sandi  (OWASP A02 / A07)
# ---------------------------------------------------------------------------
# scrypt (memory-hard) dari Werkzeug, garam acak per pengguna otomatis.
_HASH_METHOD = "scrypt"
# Hash palsu: dipakai agar waktu respons sama untuk email yang tidak terdaftar (cegah user enumeration).
DUMMY_HASH = generate_password_hash("dummy-password-for-timing-equalization", method=_HASH_METHOD)

COMMON_PASSWORDS = {
    "password", "password1", "password123", "passw0rd123", "1234567890", "12345678910", "0123456789",
    "qwertyuiop", "qwerty12345", "qwerty123456", "1q2w3e4r5t", "iloveyou123", "letmein1234", "welcome123",
    "admin12345", "administrator", "abc1234567", "abcd123456", "123456789a", "a123456789", "11111111111",
    "indonesia123", "indonesia2024", "bismillah123", "rahasia1234", "katasandi123", "sayangku123",
    "passwordpassword", "linuxlinux", "ubuntu12345", "tuxpedia123",
}


def hash_password(password: str) -> str:
    return generate_password_hash(password, method=_HASH_METHOD)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return check_password_hash(stored_hash, password)
    except ValueError:
        return False


def validate_password(password, email="", name="", min_len=10):
    """Kembalikan pesan error (str) atau None bila sandi memenuhi syarat. Mengikuti NIST 800-63B:
    panjang > aturan komposisi, tolak sandi umum/mudah ditebak."""
    if not isinstance(password, str):
        return "Kata sandi tidak valid."
    if len(password) < min_len:
        return f"Kata sandi minimal {min_len} karakter."
    if len(password) > 128:
        return "Kata sandi maksimal 128 karakter."
    low = password.lower()
    if low in COMMON_PASSWORDS or len(set(low)) <= 3:
        return "Kata sandi terlalu mudah ditebak. Gunakan kombinasi yang lebih unik."
    if re.fullmatch(r"(?:0123456789|1234567890|abcdefghij)+\d*", low):
        return "Kata sandi tidak boleh berupa urutan angka atau huruf."
    local = email.split("@")[0].lower() if email else ""
    if len(local) >= 4 and local in low:
        return "Kata sandi tidak boleh mengandung bagian dari email."
    if name and len(name) >= 4 and name.lower() in low:
        return "Kata sandi tidak boleh mengandung nama."
    return None


# ---------------------------------------------------------------------------
# Validasi input  (OWASP A03)
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)+$")


def normalize_email(value):
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    if len(v) > 254 or not _EMAIL_RE.match(v):
        return None
    return v


def clean_text(value, max_len, allow_newlines=False):
    """Normalisasi Unicode, buang karakter kontrol, potong spasi, batasi panjang. None bila bukan str."""
    if not isinstance(value, str):
        return None
    v = unicodedata.normalize("NFKC", value)
    allowed = {"\n"} if allow_newlines else set()
    v = "".join(ch for ch in v if ch in allowed or (unicodedata.category(ch)[0] != "C"))
    v = v.strip()
    return v if len(v) <= max_len else None


def email_key(email: str) -> str:
    """Kunci anonim untuk rate limit (tidak menyimpan email asli di tabel)."""
    return hashlib.sha256(email.encode()).hexdigest()[:32]


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "?"
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


# ---------------------------------------------------------------------------
# Token & OTP  (OWASP A02 / A07)
# ---------------------------------------------------------------------------
def _subkey(secret: str, label: str) -> bytes:
    return hashlib.sha256(f"{label}|{secret}".encode()).digest()


def new_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bit


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def generate_otp() -> str:
    return f"{secrets.randbelow(10**6):06d}"  # CSPRNG, bukan random.randint


def otp_hash(secret: str, user_id: int, purpose: str, code: str) -> str:
    return hmac.new(_subkey(secret, "otp"), f"{user_id}|{purpose}|{code}".encode(), hashlib.sha256).hexdigest()


def make_challenge(secret: str, user_id: int, purpose: str, ttl: int) -> str:
    """Token bertanda tangan yang membuktikan langkah pertama (sandi) sudah lolos.
    OTP tidak bisa diminta/diverifikasi tanpa token ini, jadi OTP bukan jalan pintas tanpa sandi."""
    payload = f"{user_id}.{purpose}.{int(time.time()) + ttl}"
    sig = hmac.new(_subkey(secret, "challenge"), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}.{sig}".encode()).decode().rstrip("=")


def read_challenge(secret: str, token):
    """Kembalikan (user_id, purpose) bila valid, selain itu None."""
    if not isinstance(token, str) or len(token) > 200:
        return None
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        uid, purpose, exp, sig = raw.split(".")
        payload = f"{uid}.{purpose}.{exp}"
        good = hmac.new(_subkey(secret, "challenge"), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good) or int(exp) < time.time():
            return None
        return int(uid), purpose
    except Exception:
        return None


# ---------------------------------------------------------------------------
# CSRF  (double-submit cookie bertanda tangan)
# ---------------------------------------------------------------------------
def make_csrf(secret: str) -> str:
    raw = secrets.token_urlsafe(24)
    sig = hmac.new(_subkey(secret, "csrf"), raw.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{raw}.{sig}"


def csrf_valid(secret: str, cookie_value, header_value) -> bool:
    if not cookie_value or not header_value or len(header_value) > 120:
        return False
    if not hmac.compare_digest(cookie_value, header_value):
        return False
    try:
        raw, sig = header_value.rsplit(".", 1)
    except ValueError:
        return False
    good = hmac.new(_subkey(secret, "csrf"), raw.encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(sig, good)


# ---------------------------------------------------------------------------
# Rate limiting (jendela tetap, disimpan di database)  (OWASP A04 / A07)
# ---------------------------------------------------------------------------
def rl_status(db, key, window):
    """(jumlah saat ini, sisa detik jendela)."""
    now = int(time.time())
    row = db.execute("SELECT window_start, count FROM rate_limits WHERE key = ?", (key,)).fetchone()
    if row is None or now - row["window_start"] >= window:
        return 0, 0
    return row["count"], window - (now - row["window_start"])


def rl_incr(db, key, window):
    now = int(time.time())
    # Satu statement atomik (aman dari race condition di SQLite maupun Postgres, tanpa lock tambahan).
    db.execute(
        "INSERT INTO rate_limits(key, window_start, count) VALUES (?, ?, 1) "
        "ON CONFLICT(key) DO UPDATE SET "
        "count = CASE WHEN ? - rate_limits.window_start >= ? THEN 1 ELSE rate_limits.count + 1 END, "
        "window_start = CASE WHEN ? - rate_limits.window_start >= ? THEN ? ELSE rate_limits.window_start END",
        (key, now, now, window, now, window, now),
    )


def rl_hit(db, key, limit_window):
    """Catat satu permintaan. Kembalikan (diizinkan, retry_after_detik)."""
    limit, window = limit_window
    count, retry = rl_status(db, key, window)
    if count >= limit:
        return False, max(retry, 1)
    rl_incr(db, key, window)
    return True, 0


def rl_reset(db, key):
    db.execute("DELETE FROM rate_limits WHERE key = ?", (key,))
