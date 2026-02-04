
import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate


def send_email(subject: str, body_text: str):
    host = (os.environ.get("SMTP_HOST") or "").strip()
    port_str = (os.environ.get("SMTP_PORT") or "").strip()
    user = (os.environ.get("SMTP_USER") or "").strip()
    pwd = (os.environ.get("SMTP_PASS") or "").strip()
    to_raw = (os.environ.get("MAIL_TO") or "").strip()

    if not host:
        raise ValueError("SMTP_HOST boş. GitHub Secrets/Vars kontrol et.")
    if not user:
        raise ValueError("SMTP_USER boş. GitHub Secrets/Vars kontrol et.")
    if not pwd:
        raise ValueError("SMTP_PASS boş. GitHub Secrets/Vars kontrol et.")
    if not to_raw:
        raise ValueError("MAIL_TO boş. GitHub Secrets/Vars kontrol et.")

    port = int(port_str) if port_str else 587
    to = [x.strip() for x in to_raw.split(",") if x.strip()]

    msg = MIMEText(body_text, "plain", "utf-8")
    msg["From"] = user
    msg["To"] = ", ".join(to)
    msg["Date"] = formatdate(localtime=False)
    msg["Subject"] = subject

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as s:
            s.ehlo()
            s.login(user, pwd)
            s.sendmail(user, to, msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.connect(host, port)
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(user, pwd)
            s.sendmail(user, to, msg.as_string())
