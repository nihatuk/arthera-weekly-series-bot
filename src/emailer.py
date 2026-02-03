
import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate

def send_email(subject: str, body: str):
    host = os.environ["SMTP_HOST"]

    # ✅ BOŞ GELİRSE DEFAULT 587
    port_str = (os.environ.get("SMTP_PORT") or "").strip()
    port = int(port_str) if port_str else 587

    user = os.environ["SMTP_USER"]
    pwd  = os.environ["SMTP_PASS"]
    to   = [x.strip() for x in os.environ["MAIL_TO"].split(",") if x.strip()]

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = user
    msg["To"] = ", ".join(to)
    msg["Date"] = formatdate(localtime=False)
    msg["Subject"] = subject

    with smtplib.SMTP(host, port, timeout=30) as s:
        s.ehlo()
        s.starttls()
        s.login(user, pwd)
        s.sendmail(user, to, msg.as_string())
