
import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate


def send_email(subject: str, body: str):
    host = (os.environ.get("SMTP_HOST") or "").strip()
    port_str = (os.environ.get("SMTP_PORT") or "").strip()
    user = (os.environ.get("SMTP_USER") or "").strip()
    pwd = (os.environ.get("SMTP_PASS") or "").strip()
    to_raw = (os.environ.get("MAIL_TO") or "").strip()

    # --- Net doğrulamalar (boş gelirse erken ve anlaşılır hata) ---
    if not host:
        raise ValueError("SMTP_HOST boş. GitHub Secrets -> SMTP_HOST değerini kontrol et.")
    if not user:
        raise ValueError("SMTP_USER boş. GitHub Secrets -> SMTP_USER değerini kontrol et.")
    if not pwd:
        raise ValueError("SMTP_PASS boş. GitHub Secrets -> SMTP_PASS değerini kontrol et.")
    if not to_raw:
        raise ValueError("MAIL_TO boş. GitHub Secrets -> MAIL_TO değerini kontrol et.")

    # Port default
    port = int(port_str) if port_str else 587

    to = [x.strip() for x in to_raw.split(",") if x.strip()]

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = user
    msg["To"] = ", ".join(to)
    msg["Date"] = formatdate(localtime=False)
    msg["Subject"] = subject

    try:
        if port == 465:
            # SSL portu
            with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                s.ehlo()
                s.login(user, pwd)
                s.sendmail(user, to, msg.as_string())
        else:
            # STARTTLS portu (genelde 587)
            with smtplib.SMTP(host, port, timeout=30) as s:
                # Bazı sunucularda explicit connect daha stabil
                s.connect(host, port)
                s.ehlo()
                s.starttls()
                s.ehlo()
                s.login(user, pwd)
                s.sendmail(user, to, msg.as_string())

    except smtplib.SMTPServerDisconnected as e:
        raise RuntimeError(
            f"SMTP bağlantısı kurulamadı/kapandı. host={host!r}, port={port}. "
            f"SMTP_HOST/PORT doğru mu? 587 için STARTTLS, 465 için SSL gerekir. Hata: {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Mail gönderilemedi. host={host!r}, port={port}. Hata: {e}"
        ) from e
