"""
scripts/send_digest.py
Digest diário por e-mail: contas vencidas, contas que vencem hoje e
atividades do dia.

- send_digest(app, force=False): monta e envia o e-mail. Idempotente via
  tabela notification_log (não reenvia se já foi enviado hoje), a menos
  que force=True (usado pelo comando manual de teste).
- start_scheduler(app): agenda o envio diário (APScheduler) no horário
  configurado por DIGEST_HOUR/DIGEST_MINUTE/DIGEST_TIMEZONE.

O agendador roda dentro do próprio processo web (BackgroundScheduler) —
não é necessário um serviço de cron separado no Railway. A idempotência
via notification_log protege contra duplicidade caso existam múltiplos
workers/processos.
"""

import logging
import os

from flask import render_template

logger = logging.getLogger(__name__)

_scheduler = None


def send_digest(app, force: bool = False) -> dict:
    """Monta os 3 blocos do digest e envia por e-mail. Retorna um resumo."""
    from database.queries_digest import (
        get_overdue_transactions,
        get_due_today_transactions,
        get_today_activities,
        was_digest_sent_today,
        register_digest_sent,
    )
    from utils.notifications import send_email
    from datetime import date

    with app.app_context():
        if not force and was_digest_sent_today():
            logger.info("Digest já enviado hoje — pulando.")
            return {"sent": False, "reason": "already_sent_today"}

        overdue = get_overdue_transactions()
        due_today = get_due_today_transactions()
        activities = get_today_activities()

        total = len(overdue) + len(due_today) + len(activities)

        body_html = render_template(
            "email/digest.html",
            today=date.today(),
            overdue=overdue,
            due_today=due_today,
            activities=activities,
        )

        subject = f"BK Gestão Pessoal — Resumo do dia ({len(overdue)} vencida(s), {len(due_today)} vence(m) hoje, {len(activities)} atividade(s))"

        ok = send_email(subject, body_html)
        if ok:
            register_digest_sent(len(overdue), len(due_today), len(activities))
            logger.info(f"✅ Digest diário enviado ({total} itens no total).")
        else:
            logger.warning("❌ Falha ao enviar o digest diário.")

        return {
            "sent": ok,
            "overdue_count": len(overdue),
            "due_today_count": len(due_today),
            "activities_count": len(activities),
        }


def start_scheduler(app):
    """Inicia o BackgroundScheduler com o disparo diário do digest."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    import pytz

    hour = int(os.getenv("DIGEST_HOUR", "7"))
    minute = int(os.getenv("DIGEST_MINUTE", "0"))
    tz_name = os.getenv("DIGEST_TIMEZONE", "America/Sao_Paulo")
    tz = pytz.timezone(tz_name)

    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(
        lambda: send_digest(app),
        trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
        id="daily_digest",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(f"📬 Agendador do digest diário iniciado — {hour:02d}:{minute:02d} ({tz_name})")
    return scheduler
