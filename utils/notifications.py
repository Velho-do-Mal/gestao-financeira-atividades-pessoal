"""
utils/notifications.py
Notificações por e-mail e alertas visuais
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date
import streamlit as st

logger = logging.getLogger(__name__)

RECIPIENTS = ["marcio@bk-engenharia.com", "mnknopp@gmail.com"]


def send_email(subject: str, body_html: str):
    """Envia e-mail HTML para os destinatários configurados."""
    try:
        secrets = st.secrets.get("email", {})
        smtp_host = secrets.get("smtp_host", "smtp.gmail.com")
        smtp_port = int(secrets.get("smtp_port", 587))
        smtp_user = secrets.get("smtp_user", "")
        smtp_password = secrets.get("smtp_password", "")

        if not smtp_password:
            logger.warning("Senha SMTP não configurada, e-mail não enviado.")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = ", ".join(RECIPIENTS)
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, RECIPIENTS, msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar e-mail: {e}")
        return False


def notify_due_items(items: list):
    """Gera e envia e-mail com itens próximos ao vencimento."""
    if not items:
        return

    rows_html = ""
    for item in items:
        tipo = item.get('type', '')
        title = item.get('title', '')
        due = item.get('due_date', '')
        extra = item.get('extra', '')
        emoji = "💳" if tipo == "transaction" else "📋"
        rows_html += f"""
        <tr>
            <td>{emoji} {tipo.title()}</td>
            <td><b>{title}</b></td>
            <td>{due}</td>
            <td>{extra}</td>
        </tr>
        """

    body = f"""
    <html><body style="font-family:Arial,sans-serif;background:#0F172A;color:#F1F5F9;padding:20px">
    <div style="max-width:600px;margin:auto;background:#1E293B;border-radius:12px;padding:24px">
        <h2 style="color:#60A5FA">⚠️ BK Finance — Alertas de Vencimento</h2>
        <p>Os seguintes itens vencem nos próximos 3 dias:</p>
        <table style="width:100%;border-collapse:collapse;margin-top:16px">
            <thead>
                <tr style="background:#1E40AF;color:white">
                    <th style="padding:10px">Tipo</th>
                    <th style="padding:10px">Descrição</th>
                    <th style="padding:10px">Vencimento</th>
                    <th style="padding:10px">Info</th>
                </tr>
            </thead>
            <tbody style="background:#1E293B">
                {rows_html}
            </tbody>
        </table>
        <p style="margin-top:20px;color:#94A3B8;font-size:12px">
            BK Finance — Sistema de Gestão Financeira e Atividades<br>
            BK Engenharia e Tecnologia
        </p>
    </div>
    </body></html>
    """
    send_email(f"⚠️ BK Finance — {len(items)} item(s) vencendo em breve", body)
