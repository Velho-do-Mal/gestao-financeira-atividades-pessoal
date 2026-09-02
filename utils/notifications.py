"""
utils/notifications.py
Envio de e-mail por SMTP — usado pelo digest diário (scripts/send_digest.py).

Migração v3: credenciais vêm de variáveis de ambiente (.env / Railway
Variables), não mais de st.secrets.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def get_recipients() -> list[str]:
    raw = os.getenv("EMAIL_RECIPIENTS", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


def send_email(subject: str, body_html: str, to=None) -> bool:
    """Envia e-mail HTML. `to` pode ser uma string ou lista de e-mails — usado
    pelo digest diário para mandar cada usuário para o seu próprio e-mail.
    Sem `to`, cai no EMAIL_RECIPIENTS (compatibilidade)."""
    try:
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_pass = os.getenv("SMTP_PASSWORD", "")
        if to:
            recipients = [to] if isinstance(to, str) else list(to)
        else:
            recipients = get_recipients()

        if not smtp_user or not smtp_pass:
            logger.warning("SMTP_USER/SMTP_PASSWORD não configurados — e-mail não enviado.")
            return False
        if not recipients:
            logger.warning("EMAIL_RECIPIENTS não configurado — e-mail não enviado.")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipients, msg.as_string())

        logger.info(f"✅ E-mail enviado para {recipients}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Erro ao enviar e-mail: {e}")
        return False
