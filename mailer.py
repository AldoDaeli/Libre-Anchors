"""Pengiriman email lewat Gmail SMTP (STARTTLS + App Password).

Backend:
  smtp    : kirim sungguhan lewat Gmail (production).
  console : cetak ke log server (HANYA development, kode OTP terlihat di terminal).
  memory  : simpan di daftar `outbox` (untuk tes otomatis).
"""
import html
import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr

log = logging.getLogger("tuxpedia.mail")
outbox = []  # dipakai backend 'memory'


def _smtp_send(cfg, to, subject, text, html_body):
    """Mengembalikan True bila terkirim."""
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((cfg["MAIL_FROM_NAME"], cfg["GMAIL_USER"]))
        msg["To"] = to  # EmailMessage menolak header berisi CR/LF (cegah header injection)
        msg.set_content(text)
        if html_body:
            msg.add_alternative(html_body, subtype="html")
        ctx = ssl.create_default_context()  # verifikasi sertifikat server
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=8) as server:
            server.starttls(context=ctx)
            server.login(cfg["GMAIL_USER"], cfg["GMAIL_APP_PASSWORD"])
            server.send_message(msg)
        return True
    except Exception:
        # Jangan bocorkan isi (OTP/sandi) ke log; cukup catat bahwa pengiriman gagal.
        log.exception("Gagal mengirim email ke tujuan (detail disembunyikan)")
        return False


def send_mail(cfg, to, subject, text, html_body=None):
    backend = cfg["MAIL_BACKEND"]
    if backend == "memory":
        outbox.append({"to": to, "subject": subject, "text": text})
    elif backend == "console":
        log.warning("[EMAIL DEV] ke=%s | %s\n%s", to, subject, text)
    else:
        if cfg.get("MAIL_SYNC"):
            # Serverless (Vercel): proses dibekukan begitu respons terkirim, jadi email harus dikirim SEBELUM membalas.
            _smtp_send(dict(cfg), to, subject, text, html_body)
        else:
            # Server biasa: thread terpisah supaya respons tidak menunggu SMTP.
            threading.Thread(target=_smtp_send, args=(dict(cfg), to, subject, text, html_body), daemon=True).start()


# ------------------------------- templat -------------------------------
def _wrap(title, body_html):
    return f"""<!doctype html><html lang="id"><body style="margin:0;background:#f3f1e7;font-family:Arial,Helvetica,sans-serif;color:#242a22">
<div style="max-width:460px;margin:24px auto;background:#fff;border-radius:16px;padding:28px">
<h2 style="margin:0 0 12px;font-size:20px">{html.escape(title)}</h2>{body_html}
<p style="color:#6c7066;font-size:12px;margin-top:24px">Email otomatis dari Tuxpedia. Jangan balas email ini.</p></div></body></html>"""


def otp_email(name, code, purpose, minutes):
    action = "verifikasi akun" if purpose == "register" else "masuk ke akun"
    text = (
        f"Halo {name},\n\nKode untuk {action} Tuxpedia kamu:\n\n    {code}\n\n"
        f"Kode berlaku {minutes} menit dan hanya bisa dipakai sekali.\n"
        "Jangan bagikan kode ini kepada siapa pun, termasuk yang mengaku dari Tuxpedia.\n"
        "Jika kamu tidak merasa memintanya, abaikan email ini dan pertimbangkan mengganti kata sandimu.\n"
    )
    body = (
        f"<p>Halo {html.escape(name)}, ini kode untuk {action} Tuxpedia kamu:</p>"
        f'<p style="font-size:34px;letter-spacing:8px;font-weight:700;text-align:center;background:#f3f1e7;border-radius:12px;padding:14px 0">{html.escape(code)}</p>'
        f"<p>Kode berlaku <b>{minutes} menit</b> dan hanya bisa dipakai sekali. "
        "Jangan bagikan kode ini kepada siapa pun.</p>"
        "<p>Jika kamu tidak merasa memintanya, abaikan email ini.</p>"
    )
    subject = f"{code} adalah kode Tuxpedia kamu"
    return subject, text, _wrap("Kode verifikasi", body)


def already_registered_email(name):
    text = (
        f"Halo {name},\n\nSeseorang mencoba mendaftar dengan email ini, tetapi akun sudah ada.\n"
        "Jika itu kamu, silakan masuk memakai kata sandimu. Jika bukan, abaikan email ini.\n"
    )
    body = "<p>Seseorang mencoba mendaftar dengan email ini, tetapi akun sudah ada.</p><p>Jika itu kamu, silakan masuk. Jika bukan, abaikan email ini.</p>"
    return "Akun Tuxpedia sudah terdaftar", text, _wrap("Akun sudah ada", body)


def password_changed_email(name):
    text = (
        f"Halo {name},\n\nKata sandi akun Tuxpedia kamu baru saja diubah dan semua perangkat lain dikeluarkan.\n"
        "Jika bukan kamu yang melakukannya, segera hubungi kami.\n"
    )
    body = "<p>Kata sandi akunmu baru saja diubah dan semua perangkat lain dikeluarkan.</p><p>Jika bukan kamu, segera hubungi kami.</p>"
    return "Kata sandi Tuxpedia diubah", text, _wrap("Kata sandi diubah", body)
