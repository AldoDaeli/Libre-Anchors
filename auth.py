"""API: registrasi, login (+OTP Gmail), sesi, profil, kontak, materi distro (butuh login)."""
import hmac
import logging
import re
import time
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request

import mailer
from db import INTEGRITY_ERRORS, get_db, tx
from security import (
    DUMMY_HASH, clean_text, email_key, generate_otp, hash_password, make_challenge, make_csrf,
    mask_email, new_token, normalize_email, otp_hash, read_challenge, rl_hit, rl_incr, rl_reset,
    rl_status, sha256_hex, validate_password, verify_password,
)

bp = Blueprint("api", __name__, url_prefix="/api")
audit_log = logging.getLogger("tuxpedia.security")


# ----------------------------------------------------------------- util
def cfg(key):
    return current_app.config[key]


def client_ip():
    return request.remote_addr or "unknown"


def _safe(v):
    return str(v).replace("\n", " ").replace("\r", " ")[:120]  # cegah log injection


def audit(event, **kv):
    """Log keamanan (OWASP A09). Tidak pernah mencatat sandi, OTP, atau token."""
    kv.setdefault("ip", client_ip())
    audit_log.info("%s %s", event, " ".join(f"{k}={_safe(v)}" for k, v in kv.items()))


def err(code, message, status=400, retry_after=None, **extra):
    resp = jsonify({"error": code, "message": message, **extra})
    resp.status_code = status
    if retry_after:
        resp.headers["Retry-After"] = str(int(retry_after))
    return resp


def limited(retry):
    return err("rate_limited", f"Terlalu banyak permintaan. Coba lagi dalam {int(retry)} detik.", 429, retry)


def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def user_json(row):
    return {"name": row["name"], "email": row["email"], "city": row["city"], "address": row["address"]}


def cookie_names():
    secure = cfg("COOKIE_SECURE")
    # Awalan __Host- : browser menolak cookie ini kecuali Secure, Path=/, tanpa Domain (cegah cookie tossing)
    return ("__Host-sid", "__Host-csrf") if secure else ("sid", "csrf")


# ----------------------------------------------------------------- sesi (server-side, bisa dicabut)
def load_session():
    g.user = None
    g.session_hash = None
    token = request.cookies.get(cookie_names()[0])
    if not token or len(token) > 100:
        return
    db = get_db()
    now = int(time.time())
    h = sha256_hex(token)
    row = db.execute(
        "SELECT s.last_seen, s.expires_at, u.id, u.name, u.email, u.city, u.address, u.verified "
        "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.id_hash = ?", (h,)
    ).fetchone()
    if row is None:
        return
    if row["expires_at"] < now or now - row["last_seen"] > cfg("SESSION_IDLE_SECONDS") or not row["verified"]:
        db.execute("DELETE FROM sessions WHERE id_hash = ?", (h,))
        return
    g.user, g.session_hash = row, h
    if now - row["last_seen"] >= 60:
        db.execute("UPDATE sessions SET last_seen = ? WHERE id_hash = ?", (now, h))


def start_session(user_id):
    """Buat sesi baru (token baru setiap login = tidak ada session fixation)."""
    db = get_db()
    now = int(time.time())
    if g.get("session_hash"):
        db.execute("DELETE FROM sessions WHERE id_hash = ?", (g.session_hash,))
    token = new_token()
    ttl = cfg("SESSION_ABSOLUTE_SECONDS")
    db.execute(
        "INSERT INTO sessions(id_hash, user_id, created_at, last_seen, expires_at, ip, user_agent) VALUES (?,?,?,?,?,?,?)",
        (sha256_hex(token), user_id, now, now, now + ttl, client_ip(), (request.headers.get("User-Agent") or "")[:200]),
    )
    db.execute(
        "DELETE FROM sessions WHERE user_id = ? AND id_hash NOT IN "
        "(SELECT id_hash FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?)",
        (user_id, user_id, cfg("MAX_SESSIONS_PER_USER")),
    )
    g.new_session_cookie = (token, ttl)


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not g.user:
            return err("unauthorized", "Silakan masuk terlebih dahulu.", 401)
        return fn(*a, **kw)
    return wrapper


# ----------------------------------------------------------------- OTP
def issue_otp(user, purpose):
    """Buat & kirim OTP baru. Mengembalikan (terkirim, sisa_detik_cooldown)."""
    db = get_db()
    now = int(time.time())
    row = db.execute("SELECT created_at FROM otps WHERE user_id = ? AND purpose = ?", (user["id"], purpose)).fetchone()
    cooldown = cfg("OTP_RESEND_COOLDOWN")
    if row and now - row["created_at"] < cooldown:
        return False, cooldown - (now - row["created_at"])
    code = generate_otp()
    with tx(db):
        db.execute(
            "INSERT INTO otps(user_id, purpose, code_hash, expires_at, attempts, created_at) VALUES (?,?,?,?,0,?) "
            "ON CONFLICT(user_id, purpose) DO UPDATE SET code_hash = excluded.code_hash, "
            "expires_at = excluded.expires_at, attempts = 0, created_at = excluded.created_at",
            (user["id"], purpose, otp_hash(cfg("SECRET_KEY"), user["id"], purpose, code), now + cfg("OTP_TTL_SECONDS"), now),
        )
    subject, text, html = mailer.otp_email(user["name"], code, purpose, cfg("OTP_TTL_SECONDS") // 60)
    mailer.send_mail(current_app.config, user["email"], subject, text, html)
    audit("otp_sent", purpose=purpose, user=user["id"], email=mask_email(user["email"]))
    return True, 0


def challenge_for(user_id, purpose):
    return make_challenge(cfg("SECRET_KEY"), user_id, purpose, cfg("CHALLENGE_TTL_SECONDS"))


def otp_response(user_id, purpose, message):
    return jsonify(ok=True, otp_required=True, purpose=purpose, challenge=challenge_for(user_id, purpose),
                   resend_after=cfg("OTP_RESEND_COOLDOWN"), message=message)


# ----------------------------------------------------------------- CSRF
@bp.get("/csrf")
def csrf():
    token = make_csrf(cfg("SECRET_KEY"))
    resp = jsonify(token=token)
    resp.set_cookie(cookie_names()[1], token, max_age=12 * 3600, httponly=True, secure=cfg("COOKIE_SECURE"),
                    samesite="Strict", path="/")
    return resp


# ----------------------------------------------------------------- registrasi
@bp.post("/auth/register")
def register():
    d, db, ip = body(), get_db(), client_ip()
    name = clean_text(d.get("name"), 80)
    email = normalize_email(d.get("email"))
    password = d.get("password")
    if not name or not email:
        return err("validation", "Nama dan email yang valid wajib diisi.")
    problem = validate_password(password, email, name, cfg("PASSWORD_MIN_LENGTH"))
    if problem:
        return err("validation", problem)

    for key, rule in ((f"reg:ip:{ip}", "RL_REGISTER_IP"), (f"reg:em:{email_key(email)}", "RL_REGISTER_EMAIL")):
        ok, retry = rl_hit(db, key, cfg(rule))
        if not ok:
            audit("register_rate_limited", email=mask_email(email))
            return limited(retry)

    pw_hash = hash_password(password)  # selalu dihitung: waktu respons seragam
    now = int(time.time())
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    existed = user is not None
    if user is None:
        try:
            user = db.execute(
                "INSERT INTO users(name, email, password_hash, verified, created_at, updated_at) VALUES (?,?,?,0,?,?) RETURNING *",
                (name, email, pw_hash, now, now),
            ).fetchone()
        except INTEGRITY_ERRORS:  # balapan: sudah dibuat request lain
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            existed = True

    if user["verified"]:
        # Respons ke klien identik (tidak membocorkan apakah email terdaftar); pemilik akun diberi tahu lewat email.
        subject, text, html = mailer.already_registered_email(user["name"])
        mailer.send_mail(current_app.config, user["email"], subject, text, html)
    else:
        if existed:
            db.execute("UPDATE users SET name = ?, password_hash = ?, updated_at = ? WHERE id = ?", (name, pw_hash, now, user["id"]))
            user = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        issue_otp(user, "register")
    audit("register", email=mask_email(email))
    resp = otp_response(user["id"], "register", "Kami mengirim kode verifikasi ke emailmu (jika alamat valid).")
    resp.status_code = 202
    return resp


# ----------------------------------------------------------------- login
@bp.post("/auth/login")
def login():
    d, db, ip = body(), get_db(), client_ip()
    email = normalize_email(d.get("email"))
    password = d.get("password")
    bad = err("invalid_credentials", "Email atau kata sandi salah.", 401)
    if not email or not isinstance(password, str) or not password or len(password) > 128:
        return bad

    ok, retry = rl_hit(db, f"login:ip:{ip}", cfg("RL_LOGIN_IP"))
    if not ok:
        return limited(retry)
    ek = email_key(email)
    em_limit, em_window = cfg("RL_LOGIN_FAIL_EMAIL")
    count, retry = rl_status(db, f"loginfail:em:{ek}", em_window)
    ip_limit, ip_window = cfg("RL_LOGIN_FAIL_IP")
    ip_count, ip_retry = rl_status(db, f"loginfail:ip:{ip}", ip_window)
    if count >= em_limit or ip_count >= ip_limit:
        audit("login_locked", email=mask_email(email))
        return limited(max(retry, ip_retry, 1))

    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    # Verifikasi selalu dijalankan (hash palsu bila akun tidak ada) agar waktu respons tidak membocorkan keberadaan akun.
    valid = verify_password(user["password_hash"] if user else DUMMY_HASH, password) and user is not None
    if not valid:
        rl_incr(db, f"loginfail:em:{ek}", em_window)
        rl_incr(db, f"loginfail:ip:{ip}", ip_window)
        audit("login_failed", email=mask_email(email))
        return bad

    rl_reset(db, f"loginfail:em:{ek}")
    if not user["verified"]:
        issue_otp(user, "register")
        return otp_response(user["id"], "register", "Email belum diverifikasi. Kami mengirim kode ke emailmu.")
    if cfg("LOGIN_OTP"):
        issue_otp(user, "login")
        return otp_response(user["id"], "login", "Masukkan kode yang kami kirim ke emailmu.")
    start_session(user["id"])
    audit("login_ok", user=user["id"])
    return jsonify(ok=True, user=user_json(user))


# ----------------------------------------------------------------- verifikasi OTP
@bp.post("/auth/verify")
def verify():
    d, db, ip = body(), get_db(), client_ip()
    ok, retry = rl_hit(db, f"verify:ip:{ip}", cfg("RL_VERIFY_IP"))
    if not ok:
        return limited(retry)

    generic = lambda: err("invalid_code", "Kode salah atau sudah kedaluwarsa.", 400)  # noqa: E731
    parsed = read_challenge(cfg("SECRET_KEY"), d.get("challenge"))
    if not parsed:
        return err("session_expired", "Sesi verifikasi berakhir. Silakan ulangi dari awal.", 400)
    code = d.get("code")
    code = code.strip() if isinstance(code, str) else ""
    if not re.fullmatch(r"\d{6}", code):
        return generic()

    uid, purpose = parsed
    now = int(time.time())
    user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    row = db.execute("SELECT * FROM otps WHERE user_id = ? AND purpose = ?", (uid, purpose)).fetchone()
    if user is None or row is None or row["expires_at"] < now:
        return generic()
    max_attempts = cfg("OTP_MAX_ATTEMPTS")
    if row["attempts"] >= max_attempts:
        db.execute("DELETE FROM otps WHERE id = ?", (row["id"],))
        return generic()

    given = otp_hash(cfg("SECRET_KEY"), uid, purpose, code)
    if not hmac.compare_digest(row["code_hash"], given):  # perbandingan waktu-konstan
        with tx(db):
            db.execute("UPDATE otps SET attempts = attempts + 1 WHERE id = ?", (row["id"],))
            if row["attempts"] + 1 >= max_attempts:
                db.execute("DELETE FROM otps WHERE id = ?", (row["id"],))
        audit("otp_failed", user=uid, purpose=purpose)
        return generic()

    if purpose == "register" and user["verified"]:
        return generic()  # akun sudah terverifikasi: kode pendaftaran tidak berlaku
    if purpose == "login" and not user["verified"]:
        return generic()

    with tx(db):
        used = db.execute("DELETE FROM otps WHERE id = ? AND code_hash = ?", (row["id"], row["code_hash"])).rowcount
        if used != 1:  # kode sudah dipakai request lain (sekali pakai)
            return generic()
        if purpose == "register":
            db.execute("UPDATE users SET verified = 1, updated_at = ? WHERE id = ?", (now, uid))

    start_session(uid)
    audit("otp_verified", user=uid, purpose=purpose)
    fresh = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    return jsonify(ok=True, user=user_json(fresh))


@bp.post("/auth/resend")
def resend():
    d, db, ip = body(), get_db(), client_ip()
    ok, retry = rl_hit(db, f"resend:ip:{ip}", cfg("RL_RESEND_IP"))
    if not ok:
        return limited(retry)
    parsed = read_challenge(cfg("SECRET_KEY"), d.get("challenge"))
    if not parsed:
        return err("session_expired", "Sesi verifikasi berakhir. Silakan ulangi dari awal.", 400)
    uid, purpose = parsed
    user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    eligible = user is not None and ((purpose == "register" and not user["verified"]) or (purpose == "login" and user["verified"]))
    if eligible:
        sent, wait = issue_otp(user, purpose)
        if not sent:
            return err("cooldown", f"Tunggu {wait} detik sebelum meminta kode baru.", 429, wait)
    return jsonify(ok=True, resend_after=cfg("OTP_RESEND_COOLDOWN"), message="Jika permintaan valid, kode baru dikirim ke emailmu.")


@bp.post("/auth/logout")
def logout():
    if g.get("session_hash"):
        get_db().execute("DELETE FROM sessions WHERE id_hash = ?", (g.session_hash,))
        audit("logout", user=g.user["id"])
    g.clear_session_cookie = True
    return jsonify(ok=True)


# ----------------------------------------------------------------- profil (hanya milik sendiri: tidak ada parameter id)
@bp.get("/me")
@login_required
def me():
    return jsonify(user=user_json(g.user))


@bp.patch("/me")
@login_required
def update_me():
    d = body()
    name = clean_text(d.get("name"), 80)
    city = clean_text(d.get("city", ""), 80)
    address = clean_text(d.get("address", ""), 200)
    if not name:
        return err("validation", "Nama wajib diisi (maksimal 80 karakter).")
    if city is None or address is None:
        return err("validation", "Kota atau alamat terlalu panjang atau tidak valid.")
    # Whitelist kolom: email, verified, dll. tidak bisa diubah lewat endpoint ini (cegah mass assignment).
    get_db().execute("UPDATE users SET name = ?, city = ?, address = ?, updated_at = ? WHERE id = ?",
                     (name, city, address, int(time.time()), g.user["id"]))
    fresh = get_db().execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    return jsonify(ok=True, user=user_json(fresh))


@bp.post("/me/password")
@login_required
def change_password():
    d, db = body(), get_db()
    ok, retry = rl_hit(db, f"pwchange:{g.user['id']}", cfg("RL_PASSWORD_CHANGE"))
    if not ok:
        return limited(retry)
    current, new = d.get("current_password"), d.get("new_password")
    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    if not isinstance(current, str) or not verify_password(row["password_hash"], current):
        audit("password_change_failed", user=g.user["id"])
        return err("invalid_credentials", "Kata sandi saat ini salah.", 400)
    problem = validate_password(new, g.user["email"], g.user["name"], cfg("PASSWORD_MIN_LENGTH"))
    if problem:
        return err("validation", problem)
    if current == new:
        return err("validation", "Kata sandi baru harus berbeda dari yang lama.")
    db.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?", (hash_password(new), int(time.time()), g.user["id"]))
    db.execute("DELETE FROM sessions WHERE user_id = ? AND id_hash <> ?", (g.user["id"], g.session_hash))  # keluarkan perangkat lain
    subject, text, html = mailer.password_changed_email(g.user["name"])
    mailer.send_mail(current_app.config, g.user["email"], subject, text, html)
    audit("password_changed", user=g.user["id"])
    return jsonify(ok=True, message="Kata sandi diperbarui. Perangkat lain telah dikeluarkan.")


# ----------------------------------------------------------------- kontak (publik, dibatasi)
@bp.post("/contact")
def contact():
    d, db = body(), get_db()
    name = clean_text(d.get("name"), 80)
    email = normalize_email(d.get("email"))
    message = clean_text(d.get("message"), 2000, allow_newlines=True)
    if not name or not email or not message:
        return err("validation", "Lengkapi nama, email yang valid, dan pesan (maks. 2000 karakter).")
    ok, retry = rl_hit(db, f"contact:ip:{client_ip()}", cfg("RL_CONTACT_IP"))
    if not ok:
        return limited(retry)
    db.execute("INSERT INTO messages(name, email, body, created_at) VALUES (?,?,?,?)", (name, email, message, int(time.time())))
    return jsonify(ok=True, message="Terima kasih! Pesanmu sudah kami terima."), 201


# ----------------------------------------------------------------- materi distro: hanya untuk yang sudah login
@bp.get("/distro/<key>")
@login_required
def distro(key):
    data = current_app.extensions["distros"]
    item = data["distros"].get(key)  # key hanya dipakai sebagai kunci dict (whitelist), bukan path/query
    if item is None:
        return err("not_found", "Distro tidak ditemukan.", 404)
    others = [{"key": k, "name": data["distros"][k]["name"], "tag": data["distros"][k]["tag"]} for k in data["order"] if k != key]
    return jsonify(key=key, distro=item, compare=data["compare"], others=others)
