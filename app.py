"""Tuxpedia: aplikasi Flask. Jalankan:  flask --app app run   (atau: python app.py)"""
import json
import logging
import os
import random
import re
import time
from logging.handlers import RotatingFileHandler
from pathlib import PurePosixPath
from urllib.parse import quote

from flask import Flask, abort, g, jsonify, redirect, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

import db as database
from auth import bp as api_bp, cookie_names, err, load_session
from config import load_config
from security import csrf_valid

# Hanya file statis dengan ekstensi ini yang boleh dilayani (kode .py, .db, .env, dll. tidak akan pernah terkirim).
ALLOWED_EXT = {".html", ".css", ".js", ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".ico", ".woff2", ".txt"}
# Halaman yang butuh login: dicek di SERVER, bukan hanya di JavaScript.
PROTECTED_PAGES = {"profil.html", "distro.html"}

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://cdn.jsdelivr.net",          # tanpa 'unsafe-inline': XSS lewat inline script diblokir
    "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com",
    "style-src-attr 'unsafe-inline'",                        # hanya atribut style=""; <style> inline tetap diblokir
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",                                # anti-clickjacking
])


def setup_logging(app):
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handlers = [logging.StreamHandler()]  # stdout/stderr -> Vercel Logs
    if app.config["LOG_TO_FILE"]:
        try:
            handlers.append(RotatingFileHandler(app.config["INSTANCE_DIR"] / "security.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"))
        except OSError:
            pass
    for name in ("tuxpedia.security", "tuxpedia.mail", "tuxpedia.app"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.INFO)
        lg.propagate = False
        if not lg.handlers:
            for h in handlers:
                h.setFormatter(fmt)
                lg.addHandler(h)


def cleanup(conn):
    now = int(time.time())
    conn.execute("DELETE FROM otps WHERE expires_at < ?", (now,))
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    conn.execute("DELETE FROM rate_limits WHERE window_start < ?", (now - 86400,))
    conn.execute("DELETE FROM users WHERE verified = 0 AND created_at < ?", (now - 86400,))  # pendaftaran tak diverifikasi


def create_app(overrides=None):
    cfg = load_config(overrides)
    app = Flask(__name__, static_folder=None)
    app.config.update(cfg)
    app.json.sort_keys = False
    if cfg["TRUSTED_PROXIES"]:
        n = cfg["TRUSTED_PROXIES"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n)
    setup_logging(app)
    log = logging.getLogger("tuxpedia.app")

    with open(cfg["DATA_FILE"], encoding="utf-8") as f:
        app.extensions["distros"] = json.load(f)

    app.teardown_appcontext(database.close_db)
    with app.app_context():
        database.init_db()
    app.register_blueprint(api_bp)

    allowed_hosts = {h.strip().lower() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()}

    # ------------------------------------------------------------------ sebelum tiap request
    @app.before_request
    def guard():
        if allowed_hosts and request.host.lower() not in allowed_hosts:  # cegah Host header attack
            abort(400)
        load_session()
        if random.random() < 0.02:
            cleanup(database.get_db())

        if request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.mimetype != "application/json":
                return err("unsupported_media_type", "Gunakan Content-Type: application/json.", 415)
            origin = request.headers.get("Origin")
            if origin is not None and origin != request.host_url.rstrip("/"):
                return err("forbidden_origin", "Permintaan lintas situs ditolak.", 403)
            site = request.headers.get("Sec-Fetch-Site")
            if site and site not in ("same-origin", "none"):
                return err("forbidden_origin", "Permintaan lintas situs ditolak.", 403)
            if not csrf_valid(cfg["SECRET_KEY"], request.cookies.get(cookie_names()[1]), request.headers.get("X-CSRF-Token")):
                return err("csrf", "Token keamanan tidak valid. Muat ulang halaman lalu coba lagi.", 403)

    # ------------------------------------------------------------------ setelah tiap request
    @app.after_request
    def harden(resp):
        sid_name = cookie_names()[0]
        if g.get("new_session_cookie"):
            token, ttl = g.new_session_cookie
            resp.set_cookie(sid_name, token, max_age=ttl, httponly=True, secure=cfg["COOKIE_SECURE"], samesite="Lax", path="/")
        elif g.get("clear_session_cookie"):
            resp.delete_cookie(sid_name, path="/", httponly=True, secure=cfg["COOKIE_SECURE"], samesite="Lax")

        h = resp.headers
        h["Content-Security-Policy"] = CSP + ("; upgrade-insecure-requests" if cfg["IS_PROD"] else "")
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "strict-origin-when-cross-origin"
        h["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=(), usb=()"
        h["Cross-Origin-Opener-Policy"] = "same-origin"
        h["Cross-Origin-Resource-Policy"] = "same-origin"
        if cfg["COOKIE_SECURE"]:
            h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.path.startswith("/api/"):
            h["Cache-Control"] = "no-store"
        return resp

    # ------------------------------------------------------------------ halaman & file statis
    @app.get("/")
    def index():
        return redirect("/landing.html")

    @app.get("/<path:filename>")
    def static_files(filename):
        p = PurePosixPath(filename)
        if any(part.startswith(".") for part in p.parts) or p.suffix.lower() not in ALLOWED_EXT:
            abort(404)
        if filename in PROTECTED_PAGES and not g.user:
            q = request.query_string.decode("latin-1")
            nxt = filename + (("?" + q) if q else "")
            if not re.fullmatch(r"[a-z0-9_-]+\.html(\?[a-z0-9_=&-]*)?", nxt, re.I):
                nxt = "landing.html"
            return redirect("/login.html?next=" + quote(nxt, safe=""))
        resp = send_from_directory(cfg["STATIC_DIR"], filename, max_age=0)  # send_from_directory menolak path traversal
        if filename in PROTECTED_PAGES:
            resp.headers["Cache-Control"] = "no-store"
        elif p.suffix.lower() in (".html", ".js", ".css"):
            resp.headers["Cache-Control"] = "no-cache"
        else:
            resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp

    # ------------------------------------------------------------------ error: tidak pernah membocorkan detail internal
    @app.errorhandler(HTTPException)
    def http_error(e):
        if request.path.startswith("/api/"):
            code = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 413: "payload_too_large"}.get(e.code, "error")
            msg = {404: "Tidak ditemukan.", 405: "Metode tidak diizinkan.", 413: "Data terlalu besar."}.get(e.code, "Permintaan tidak valid.")
            return err(code, msg, e.code or 400)
        return (f"{e.code} {e.name}", e.code)

    @app.errorhandler(Exception)
    def unhandled(e):
        log.exception("Kesalahan tak terduga")  # detail hanya di log server
        if request.path.startswith("/api/"):
            return err("server_error", "Terjadi kesalahan di server.", 500)
        return ("500 Internal Server Error", 500)

    return app


if __name__ == "__main__":
    # Hanya untuk development. Production: gunicorn di belakang nginx (lihat README). Debug sengaja TIDAK diaktifkan.
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
