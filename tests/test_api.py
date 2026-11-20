"""Tes otomatis alur & keamanan.  Jalankan:  python -m unittest discover -s tests -v"""
import re
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mailer  # noqa: E402
from app import create_app  # noqa: E402

PW = "Kopi-Hitam-Pagi-9"
ORIGIN = {"Origin": "http://localhost"}


class Base(unittest.TestCase):
    overrides = {}

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        mailer.outbox.clear()
        cfg = {
            "MAIL_BACKEND": "memory", "DATABASE": f"{self.tmp}/t.db", "INSTANCE_DIR": Path(self.tmp),
            "SECRET_KEY": "k" * 48, "OTP_RESEND_COOLDOWN": 0, "COOKIE_SECURE": False,
        }
        cfg.update(self.overrides)
        self.app = create_app(cfg)
        self.c = self.app.test_client()
        self.token = self.c.get("/api/csrf").get_json()["token"]

    # ---- helpers
    def post(self, path, data=None, token="__default__", headers=None, client=None):
        h = dict(ORIGIN)
        h["X-CSRF-Token"] = self.token if token == "__default__" else token
        h.update(headers or {})
        return (client or self.c).post(path, json=data if data is not None else {}, headers=h)

    def patch(self, path, data):
        return self.c.patch(path, json=data, headers={**ORIGIN, "X-CSRF-Token": self.token})

    def last_code(self):
        m = re.search(r"\b(\d{6})\b", mailer.outbox[-1]["text"])
        return m.group(1)

    def register(self, email="budi@example.com", name="Budi Santoso", pw=PW, client=None):
        return self.post("/api/auth/register", {"name": name, "email": email, "password": pw}, client=client)

    def verify(self, challenge, code, client=None):
        return self.post("/api/auth/verify", {"challenge": challenge, "code": code}, client=client)

    def make_user(self, email="budi@example.com"):
        """Daftar + verifikasi; sesi langsung aktif di self.c."""
        r = self.register(email)
        self.assertEqual(r.status_code, 202)
        v = self.verify(r.get_json()["challenge"], self.last_code())
        self.assertEqual(v.status_code, 200, v.get_json())
        return v

    def db(self):
        conn = sqlite3.connect(self.app.config["DATABASE"])
        conn.row_factory = sqlite3.Row
        return conn


class TestRegisterAndOtp(Base):
    def test_register_verify_login_flow(self):
        r = self.register()
        self.assertEqual(r.status_code, 202)
        j = r.get_json()
        self.assertTrue(j["otp_required"] and j["purpose"] == "register")
        self.assertEqual(len(mailer.outbox), 1)
        self.assertEqual(mailer.outbox[0]["to"], "budi@example.com")
        self.assertEqual(self.c.get("/api/me").status_code, 401)  # belum login sebelum OTP benar
        v = self.verify(j["challenge"], self.last_code())
        self.assertEqual(v.status_code, 200)
        me = self.c.get("/api/me").get_json()["user"]
        self.assertEqual(me["email"], "budi@example.com")

    def test_otp_is_not_stored_in_plaintext(self):
        self.register()
        code = self.last_code()
        row = self.db().execute("SELECT code_hash FROM otps").fetchone()
        self.assertNotIn(code, row["code_hash"])
        self.assertEqual(len(row["code_hash"]), 64)

    def test_password_not_stored_in_plaintext(self):
        self.register()
        h = self.db().execute("SELECT password_hash FROM users").fetchone()[0]
        self.assertTrue(h.startswith("scrypt:"))
        self.assertNotIn(PW, h)

    def test_wrong_code_locks_after_max_attempts(self):
        j = self.register().get_json()
        good = self.last_code()
        bad = "000000" if good != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.verify(j["challenge"], bad).status_code, 400)
        # kode benar pun ditolak setelah batas percobaan
        self.assertEqual(self.verify(j["challenge"], good).status_code, 400)
        self.assertEqual(self.c.get("/api/me").status_code, 401)

    def test_expired_code_rejected(self):
        j = self.register().get_json()
        conn = self.db()
        conn.execute("UPDATE otps SET expires_at = ?", (int(time.time()) - 1,))
        conn.commit()
        self.assertEqual(self.verify(j["challenge"], self.last_code()).status_code, 400)

    def test_code_is_single_use(self):
        j = self.register().get_json()
        code = self.last_code()
        self.assertEqual(self.verify(j["challenge"], code).status_code, 200)
        other = self.app.test_client()
        tok = other.get("/api/csrf").get_json()["token"]
        replay = other.post("/api/auth/verify", json={"challenge": j["challenge"], "code": code},
                            headers={**ORIGIN, "X-CSRF-Token": tok})
        self.assertEqual(replay.status_code, 400)  # kode yang sama tidak bisa dipakai lagi
        self.assertEqual(other.get("/api/me").status_code, 401)

    def test_forged_or_missing_challenge_rejected(self):
        self.register()
        code = self.last_code()
        self.assertEqual(self.verify("abc", code).status_code, 400)
        self.assertEqual(self.post("/api/auth/verify", {"code": code}).status_code, 400)
        self.assertEqual(self.c.get("/api/me").status_code, 401)

    def test_register_code_cannot_be_used_for_login(self):
        """Challenge terikat pada tujuan; OTP login tidak bisa diganti OTP lain."""
        j = self.register().get_json()
        import security
        forged = security.make_challenge(self.app.config["SECRET_KEY"], 1, "login", 600)
        self.assertEqual(self.verify(forged, self.last_code()).status_code, 400)
        self.assertEqual(self.verify(j["challenge"], self.last_code()).status_code, 200)

    def test_resend_cooldown(self):
        self.app.config["OTP_RESEND_COOLDOWN"] = 60
        j = self.register().get_json()
        r = self.post("/api/auth/resend", {"challenge": j["challenge"]})
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r.headers)
        self.assertEqual(len(mailer.outbox), 1)

    def test_weak_passwords_rejected(self):
        for pw in ["short", "password123", "1234567890", "aaaaaaaaaaaa", "budi@example.com", "budisantoso1"]:
            r = self.register(pw=pw)
            self.assertEqual(r.status_code, 400, pw)
        self.assertEqual(len(mailer.outbox), 0)

    def test_invalid_email_rejected(self):
        for e in ["x", "a@b", "a b@c.com", "a@b.com\r\nBcc: evil@x.com", "<script>@x.com", "a" * 300 + "@x.com"]:
            self.assertEqual(self.register(email=e).status_code, 400, e)

    def test_no_user_enumeration_on_register(self):
        self.make_user()
        other = self.app.test_client()
        tok = other.get("/api/csrf").get_json()["token"]
        mailer.outbox.clear()
        r2 = other.post("/api/auth/register", json={"name": "Orang Lain", "email": "budi@example.com", "password": PW},
                        headers={**ORIGIN, "X-CSRF-Token": tok})
        self.assertEqual(r2.status_code, 202)
        j = r2.get_json()
        self.assertEqual(set(j), {"ok", "otp_required", "purpose", "challenge", "resend_after", "message"})
        self.assertIn("sudah ada", mailer.outbox[-1]["text"])      # pemilik akun diberi tahu lewat email
        self.assertNotRegex(mailer.outbox[-1]["text"], r"\b\d{6}\b")  # tanpa kode OTP
        # penyerang tidak bisa menembus: tidak ada OTP yang berlaku
        self.assertEqual(other.post("/api/auth/verify", json={"challenge": j["challenge"], "code": "123456"},
                                    headers={**ORIGIN, "X-CSRF-Token": tok}).status_code, 400)

    def test_unverified_registration_can_be_retaken_but_not_by_attacker_without_otp(self):
        self.register(name="Penyerang", pw="Penyerang-Kuat-77")
        j = self.register(name="Pemilik Asli", pw=PW).get_json()
        self.assertEqual(self.verify(j["challenge"], self.last_code()).status_code, 200)
        self.c.post("/api/auth/logout", json={}, headers={**ORIGIN, "X-CSRF-Token": self.token})
        r = self.post("/api/auth/login", {"email": "budi@example.com", "password": "Penyerang-Kuat-77"})
        self.assertEqual(r.status_code, 401)  # sandi penyerang sudah tertimpa pemilik asli


class TestLogin(Base):
    def test_login_requires_otp_second_factor(self):
        self.make_user()
        self.post("/api/auth/logout")
        r = self.post("/api/auth/login", {"email": "budi@example.com", "password": PW})
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j["otp_required"] and j["purpose"] == "login")
        self.assertEqual(self.c.get("/api/me").status_code, 401)  # sandi benar saja belum cukup
        v = self.verify(j["challenge"], self.last_code())
        self.assertEqual(v.status_code, 200)
        self.assertEqual(self.c.get("/api/me").status_code, 200)

    def test_login_without_otp_when_disabled(self):
        self.app.config["LOGIN_OTP"] = False
        self.make_user()
        self.post("/api/auth/logout")
        r = self.post("/api/auth/login", {"email": "budi@example.com", "password": PW})
        self.assertEqual(r.status_code, 200)
        self.assertIn("user", r.get_json())

    def test_login_errors_are_identical_for_unknown_and_wrong_password(self):
        self.make_user()
        self.post("/api/auth/logout")
        a = self.post("/api/auth/login", {"email": "budi@example.com", "password": "salah-salah-1"})
        b = self.post("/api/auth/login", {"email": "tidakada@example.com", "password": "salah-salah-1"})
        self.assertEqual((a.status_code, a.get_json()), (b.status_code, b.get_json()))
        self.assertEqual(a.status_code, 401)

    def test_account_lockout_after_failures(self):
        self.make_user()
        self.post("/api/auth/logout")
        for _ in range(5):
            self.assertEqual(self.post("/api/auth/login", {"email": "budi@example.com", "password": "salah-salah-1"}).status_code, 401)
        r = self.post("/api/auth/login", {"email": "budi@example.com", "password": PW})  # sandi benar pun diblok
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r.headers)

    def test_sql_injection_attempts(self):
        for payload in ["' OR '1'='1", "admin'--", "x@y.com' OR 1=1--", '"; DROP TABLE users;--']:
            r = self.post("/api/auth/login", {"email": payload, "password": payload})
            self.assertEqual(r.status_code, 401, payload)
        self.make_user()
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)

    def test_non_string_inputs_do_not_crash(self):
        for bad in [None, 123, ["a"], {"a": 1}, True]:
            self.assertIn(self.post("/api/auth/login", {"email": bad, "password": bad}).status_code, (400, 401))
            self.assertIn(self.post("/api/auth/register", {"name": bad, "email": bad, "password": bad}).status_code, (400,))
            self.assertIn(self.post("/api/auth/verify", {"challenge": bad, "code": bad}).status_code, (400,))

    def test_logout_revokes_session_server_side(self):
        self.make_user()
        stolen = self.c.get_cookie("sid").value
        self.assertEqual(self.post("/api/auth/logout").status_code, 200)
        thief = self.app.test_client()
        thief.set_cookie("sid", stolen)
        self.assertEqual(thief.get("/api/me").status_code, 401)  # token lama tidak berlaku lagi

    def test_session_idle_and_absolute_timeout(self):
        self.make_user()
        conn = self.db()
        conn.execute("UPDATE sessions SET last_seen = ?", (int(time.time()) - self.app.config["SESSION_IDLE_SECONDS"] - 5,))
        conn.commit()
        self.assertEqual(self.c.get("/api/me").status_code, 401)

    def test_new_session_token_on_each_login(self):
        self.make_user()
        first = self.c.get_cookie("sid").value
        self.post("/api/auth/logout")
        j = self.post("/api/auth/login", {"email": "budi@example.com", "password": PW}).get_json()
        self.verify(j["challenge"], self.last_code())
        self.assertNotEqual(first, self.c.get_cookie("sid").value)

    def test_session_cookie_flags_and_token_not_stored(self):
        j = self.register().get_json()
        r = self.verify(j["challenge"], self.last_code())
        cookie = next(h for h in r.headers.getlist("Set-Cookie") if h.startswith("sid="))
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        token = self.c.get_cookie("sid").value
        self.assertIsNone(self.db().execute("SELECT 1 FROM sessions WHERE id_hash = ?", (token,)).fetchone())


class TestProduction(Base):
    overrides = {"COOKIE_SECURE": True}

    def test_secure_cookie_prefix_and_hsts(self):
        self.assertIsNotNone(self.c.get_cookie("__Host-csrf"))
        r = self.c.get("/api/csrf", base_url="https://localhost")
        self.assertIn("Strict-Transport-Security", r.headers)
        sc = r.headers.getlist("Set-Cookie")[0]
        self.assertIn("Secure", sc)
        self.assertIn("HttpOnly", sc)

    def test_config_refuses_insecure_production(self):
        import os
        old = dict(os.environ)
        try:
            os.environ.update({"APP_ENV": "production", "SECRET_KEY": "pendek", "MAIL_BACKEND": "console"})
            with self.assertRaises(RuntimeError):
                create_app({"DATABASE": f"{self.tmp}/p.db", "INSTANCE_DIR": Path(self.tmp)})
        finally:
            os.environ.clear()
            os.environ.update(old)


class TestCsrfAndRequestChecks(Base):
    def test_post_without_csrf_token_rejected(self):
        r = self.c.post("/api/auth/login", json={"email": "a@b.com", "password": "x"}, headers=ORIGIN)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["error"], "csrf")

    def test_wrong_or_forged_csrf_token_rejected(self):
        self.assertEqual(self.post("/api/auth/login", {"email": "a@b.com", "password": "x"}, token="forged.token").status_code, 403)
        self.assertEqual(self.post("/api/auth/login", {"email": "a@b.com", "password": "x"}, token="").status_code, 403)

    def test_cookie_tossing_with_unsigned_token(self):
        evil = "attacker-chosen.value"
        self.c.set_cookie("csrf", evil)
        self.assertEqual(self.post("/api/auth/login", {"email": "a@b.com", "password": "x"}, token=evil).status_code, 403)

    def test_cross_origin_rejected(self):
        r = self.post("/api/auth/login", {"email": "a@b.com", "password": "x"}, headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)
        r = self.post("/api/auth/login", {"email": "a@b.com", "password": "x"}, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(r.status_code, 403)

    def test_form_content_type_rejected(self):
        r = self.c.post("/api/auth/login", data={"email": "a@b.com"}, headers={**ORIGIN, "X-CSRF-Token": self.token})
        self.assertEqual(r.status_code, 415)

    def test_oversized_body_rejected(self):
        r = self.post("/api/contact", {"name": "a", "email": "a@b.com", "message": "x" * 100_000})
        self.assertEqual(r.status_code, 413)

    def test_security_headers(self):
        r = self.c.get("/")
        for h in ["Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy",
                  "Permissions-Policy", "Cross-Origin-Opener-Policy"]:
            self.assertIn(h, r.headers, h)
        csp = r.headers["Content-Security-Policy"]
        self.assertIn("frame-ancestors 'none'", csp)
        script_src = re.search(r"script-src ([^;]+)", csp).group(1)
        self.assertNotIn("unsafe-inline", script_src)
        self.assertNotIn("unsafe-eval", script_src)
        self.assertEqual(self.c.get("/api/me").headers["Cache-Control"], "no-store")


class TestAccessControl(Base):
    def test_api_requires_login(self):
        self.assertEqual(self.c.get("/api/me").status_code, 401)
        self.assertEqual(self.c.get("/api/distro/ubuntu").status_code, 401)
        self.assertEqual(self.patch("/api/me", {"name": "x"}).status_code, 401)
        self.assertEqual(self.post("/api/me/password", {"current_password": "a", "new_password": "b"}).status_code, 401)

    def test_protected_pages_redirect_to_login(self):
        r = self.c.get("/distro/arch")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], "/login")          # URL bersih, tanpa ?next=
        self.assertIn("nx=/distro/arch", r.headers["Set-Cookie"])   # tujuan diingat server lewat cookie
        self.assertEqual(self.c.get("/profil").status_code, 302)
        self.make_user()
        self.assertEqual(self.c.get("/distro/arch").status_code, 200)
        self.assertEqual(self.c.get("/profil").status_code, 200)

    def test_clean_urls_and_legacy_redirects(self):
        for path in ("/", "/login", "/register", "/login/"):
            self.assertEqual(self.c.get(path).status_code, 200, path)
        for old, new in (("/landing.html", "/"), ("/login.html", "/login"), ("/profil.html", "/profil"),
                         ("/distro.html?d=ubuntu", "/distro/ubuntu"), ("/distro.html?d=../x", "/#about")):
            r = self.c.get(old)
            self.assertEqual((r.status_code, r.headers["Location"]), (302, new), old)
        self.assertEqual(self.c.get("/app.py").status_code, 404)
        self.assertEqual(self.c.get("/distro/ubuntu%20x").status_code, 404)

    def test_go_returns_to_saved_page(self):
        self.c.get("/distro/arch")                                  # tamu -> cookie nx
        r = self.c.get("/go")
        self.assertEqual(r.headers["Location"], "/distro/arch")
        self.assertIn("nx=;", r.headers["Set-Cookie"])              # cookie dihapus (sekali pakai)
        self.assertEqual(self.c.get("/go").headers["Location"], "/")

    def test_open_redirect_not_possible(self):
        # Cookie "nx" yang dipalsukan tidak pernah diikuti kecuali cocok dengan daftar ketat.
        for evil in ("//evil.com", "https://evil.com", "/\\evil.com", "/profil/../x", "/api/me", "javascript:alert(1)"):
            self.c.set_cookie("nx", evil)
            self.assertEqual(self.c.get("/go").headers["Location"], "/", evil)

    def test_distro_content_only_via_api_after_login(self):
        self.assertEqual(self.c.get("/distro-data.js").status_code, 404)   # data tidak lagi file publik
        self.assertEqual(self.c.get("/data/distros.json").status_code, 404)
        self.make_user()
        r = self.c.get("/api/distro/ubuntu")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["distro"]["name"], "Ubuntu")
        self.assertEqual(self.c.get("/api/distro/../../etc/passwd").status_code, 404)
        self.assertEqual(self.c.get("/api/distro/nope").status_code, 404)
        self.assertEqual(self.c.get("/api/distro/__class__").status_code, 404)

    def test_sensitive_files_not_served(self):
        for path in ["/app.py", "/config.py", "/.env", "/instance/tuxpedia.db", "/../config.py", "/%2e%2e/config.py",
                     "/static/../app.py", "/requirements.txt", "/security.log", "/.git/config", "/tests/test_api.py"]:
            self.assertEqual(self.c.get(path).status_code, 404, path)

    def test_profile_is_own_only_and_mass_assignment_blocked(self):
        self.make_user("a@example.com")
        self.post("/api/auth/logout")
        other = self.app.test_client()
        tok = other.get("/api/csrf").get_json()["token"]
        mailer.outbox.clear()
        r = other.post("/api/auth/register", json={"name": "B", "email": "b@example.com", "password": PW},
                       headers={**ORIGIN, "X-CSRF-Token": tok})
        other.post("/api/auth/verify", json={"challenge": r.get_json()["challenge"], "code": self.last_code()},
                   headers={**ORIGIN, "X-CSRF-Token": tok})
        r = other.patch("/api/me", json={"name": "Baru", "city": "Batam", "address": "Jl. X", "email": "a@example.com",
                                         "verified": 0, "id": 1, "password_hash": "x"},
                        headers={**ORIGIN, "X-CSRF-Token": tok})
        self.assertEqual(r.status_code, 200)
        row = self.db().execute("SELECT name, email, verified, id FROM users WHERE email = 'b@example.com'").fetchone()
        self.assertEqual((row["name"], row["verified"]), ("Baru", 1))
        self.assertEqual(self.db().execute("SELECT name FROM users WHERE email = 'a@example.com'").fetchone()[0], "Budi Santoso")

    def test_profile_update_validation(self):
        self.make_user()
        self.assertEqual(self.patch("/api/me", {"name": "", "city": "", "address": ""}).status_code, 400)
        self.assertEqual(self.patch("/api/me", {"name": "A", "city": "x" * 500}).status_code, 400)
        ok = self.patch("/api/me", {"name": "<img src=x onerror=alert(1)>", "city": "Batam", "address": "Jl. A"})
        self.assertEqual(ok.status_code, 200)  # disimpan apa adanya; encoding dilakukan saat tampil (textContent / esc)

    def test_password_change_revokes_other_sessions(self):
        self.make_user()
        other = self.app.test_client()
        tok = other.get("/api/csrf").get_json()["token"]
        j = other.post("/api/auth/login", json={"email": "budi@example.com", "password": PW}, headers={**ORIGIN, "X-CSRF-Token": tok}).get_json()
        other.post("/api/auth/verify", json={"challenge": j["challenge"], "code": self.last_code()}, headers={**ORIGIN, "X-CSRF-Token": tok})
        self.assertEqual(other.get("/api/me").status_code, 200)
        self.assertEqual(self.post("/api/me/password", {"current_password": "salah-salah-1", "new_password": "Sandi-Baru-Kuat-55"}).status_code, 400)
        self.assertEqual(self.post("/api/me/password", {"current_password": PW, "new_password": "pendek"}).status_code, 400)
        r = self.post("/api/me/password", {"current_password": PW, "new_password": "Sandi-Baru-Kuat-55"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self.c.get("/api/me").status_code, 200)       # sesi ini tetap
        self.assertEqual(other.get("/api/me").status_code, 401)        # perangkat lain dikeluarkan
        self.assertIn("diubah", mailer.outbox[-1]["subject"])


class TestRateLimitsAndContact(Base):
    def test_register_ip_rate_limit(self):
        codes = [self.register(email=f"u{i}@example.com").status_code for i in range(12)]
        self.assertEqual(codes[:10], [202] * 10)
        self.assertEqual(codes[10], 429)

    def test_contact_validation_and_rate_limit(self):
        good = {"name": "Ani", "email": "ani@example.com", "message": "Halo\nini pesan"}
        self.assertEqual(self.post("/api/contact", {**good, "email": "salah"}).status_code, 400)
        self.assertEqual(self.post("/api/contact", {**good, "message": ""}).status_code, 400)
        for _ in range(5):
            self.assertEqual(self.post("/api/contact", good).status_code, 201)
        self.assertEqual(self.post("/api/contact", good).status_code, 429)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM messages").fetchone()[0], 5)

    def test_unknown_api_route_returns_json_404(self):
        r = self.c.get("/api/nothing")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json()["error"], "not_found")

    def test_errors_do_not_leak_internals(self):
        r = self.c.post("/api/auth/login", data="{bad json", headers={**ORIGIN, "X-CSRF-Token": self.token, "Content-Type": "application/json"})
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("Traceback", r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()