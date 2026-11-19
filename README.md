# Tuxpedia — Flask + Neon (Postgres) + Vercel

Backend Flask (login, daftar, **OTP email Gmail**, profil, kontak, materi distro) dengan database **Neon (Postgres)**,
siap di-deploy ke **Vercel**. Lokal tanpa database online pun jalan (otomatis memakai SQLite).

```
tuxpedia/
├─ api/index.py          titik masuk Vercel (serverless function)
├─ vercel.json           semua URL -> Flask (supaya cek login & header keamanan selalu berjalan)
├─ app.py                app factory, header keamanan, CSRF/Origin guard, penyajian file statis
├─ auth.py               endpoint /api/* (register, login, verify OTP, resend, logout, me, password, contact, distro)
├─ security.py           hash sandi, OTP, token challenge, CSRF, rate limit
├─ mailer.py             kirim email Gmail SMTP (STARTTLS + App Password)
├─ db.py                 lapisan DB: Postgres/Neon (psycopg) atau SQLite (lokal)
├─ config.py             konfigurasi dari environment; menolak start jika production tidak aman
├─ schema_postgres.sql   skema tabel Postgres
├─ init_db.py            alternatif menjalankan skema dari terminal
├─ data/distros.json     materi distro (hanya dikirim ke pengguna yang login)
├─ static/               HTML/CSS/JS  -> TARUH FOLDER img/ MILIKMU DI static/img/
└─ tests/                47 tes otomatis (python -m pytest tests)
```

## 1. Jalankan lokal (tanpa database online)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # MAIL_BACKEND=console: kode OTP dicetak di terminal
python app.py                                          # http://127.0.0.1:5000
```
Salin folder gambar `img/` ke `static/img/`.

## 2. Neon (database)

1. https://neon.tech → daftar → **Create project** (pilih region terdekat, mis. Singapore).
2. **SQL Editor** → tempel isi `schema_postgres.sql` → **Run**. Di menu **Tables** harus muncul `users`, `otps`,
   `sessions`, `rate_limits`, `messages`. (Atau: set `DATABASE_URL`, lalu `python init_db.py`.)
3. Klik **Connect**, aktifkan **Connection pooling**, salin connection string. Bentuknya:
   `postgresql://user:password@ep-xxxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`
   (host harus mengandung `-pooler`). Itu nilai `DATABASE_URL`. Pooler dipakai karena di Vercel tiap request membuka koneksi baru.
4. Password dengan karakter khusus harus di-URL-encode (`@` → `%40`, `#` → `%23`).

Tes lokal: isi `DATABASE_URL` di `.env`, `pip install -r requirements.txt`, `python app.py`, daftar akun,
lalu cek tabel `users` di Neon.

Catatan: tier gratis Neon menidurkan database saat sepi; request pertama setelahnya ± 1 detik lebih lambat.

Penjelasan tabel:
- `users` — akun (sandi tersimpan sebagai hash scrypt).
- `otps` — kode OTP **aktif** saja, disimpan sebagai hash dan dihapus begitu dipakai/kedaluwarsa (tabel sering kosong).
- `sessions` — sesi login (hanya hash token).
- `rate_limits` — penghitung pembatasan percobaan.
- `messages` — pesan dari form kontak di beranda (dibaca lewat dashboard Neon).

## 3. Gmail App Password (untuk OTP)

1. Akun Google → **Keamanan** → aktifkan **Verifikasi 2 Langkah**.
2. https://myaccount.google.com/apppasswords → buat sandi aplikasi (16 karakter).
3. Isi `GMAIL_USER` (alamat Gmail) dan `GMAIL_APP_PASSWORD` (16 karakter tadi; **bukan** sandi Gmail biasa).

Batas Gmail ± 500 email/hari. Untuk trafik lebih besar, ganti ke layanan email transaksional (Resend, Brevo, dll.) dengan SMTP yang sama (`SMTP_HOST`, `SMTP_PORT`).

## 4. Deploy ke Vercel

1. Push folder ini ke GitHub → https://vercel.com/new → import repo (Framework: *Other*).
2. **Settings → Environment Variables**:

| Nama | Nilai |
|---|---|
| `APP_ENV` | `production` |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL` | connection string Neon (host `-pooler`) |
| `MAIL_BACKEND` | `smtp` |
| `GMAIL_USER`, `GMAIL_APP_PASSWORD` | dari langkah 3 |
| `COOKIE_SECURE` | `true` |
| `TRUSTED_PROXIES` | `1` |
| `ALLOWED_HOSTS` | domainmu, mis. `tuxpedia.vercel.app,www.domainmu.com` |

3. Deploy. Buka `https://<project>.vercel.app`, daftar, cek email OTP.

Catatan serverless: email dikirim **sebelum** respons (thread latar belakang dimatikan Vercel); log keamanan ke stdout
(lihat **Vercel → Logs**); filesystem read-only sehingga semua data di Neon.

## 5. Pemetaan OWASP Top 10 (2021)

| # | Risiko | Penanganan |
|---|---|---|
| A01 | Broken Access Control | Halaman `profil`/`distro` dan `/api/me*`, `/api/distro/*` dicek **di server** (bukan hanya JS). Materi distro tidak ada di file publik. Tidak ada parameter id pengguna (hanya data milik sendiri). Whitelist kolom pada PATCH (anti mass-assignment). |
| A02 | Cryptographic Failures | Sandi: **scrypt** + salt. OTP & token sesi disimpan sebagai hash (HMAC/SHA-256), bukan plaintext. Cookie `Secure` + `__Host-`, HSTS, TLS wajib ke DB (`sslmode=require`) dan SMTP (STARTTLS terverifikasi). Rahasia hanya di environment. |
| A03 | Injection | Semua query berparameter. Output di frontend memakai `textContent`/escape. Email lewat `EmailMessage` (anti header injection). CSP tanpa inline script. |
| A04 | Insecure Design | OTP 6 digit, kedaluwarsa 10 menit, maks 5 percobaan, sekali pakai, cooldown kirim ulang. Login = sandi + OTP; token *challenge* bertanda tangan mencegah login hanya dengan OTP. Rate limit per IP & per email. |
| A05 | Security Misconfiguration | Production menolak start tanpa `SECRET_KEY` kuat, SMTP, cookie aman. Header: CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy, COOP/CORP. Allowlist ekstensi file, dotfile diblokir, cek `Host`. Tanpa debug mode. |
| A06 | Vulnerable Components | Dependensi minimal & dipin. Jalankan `pip-audit -r requirements.txt` secara berkala. |
| A07 | Identification & Auth Failures | Kebijakan sandi (≥10, daftar sandi umum), kunci sementara setelah 5 gagal, respons seragam (tanpa user enumeration, termasuk waktu hash), sesi server-side: idle 60 menit, maks 12 jam, token baru tiap login, ganti sandi mencabut sesi lain. |
| A08 | Software & Data Integrity | CSRF: token bertanda tangan (double-submit) + cek `Origin`/`Sec-Fetch-Site` + wajib `application/json`. Token challenge/CSRF ditandatangani HMAC. |
| A09 | Logging & Monitoring | Log audit (daftar, login gagal/sukses, OTP, kunci akun) dengan email disamarkan, anti log-injection, tanpa sandi/OTP/token. |
| A10 | SSRF | Backend tidak mengambil URL dari input pengguna. |
