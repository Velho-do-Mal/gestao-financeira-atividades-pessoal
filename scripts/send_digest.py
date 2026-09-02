"""
scripts/send_digest.py
Digest diário por e-mail: contas vencidas, contas que vencem hoje e
atividades do dia.

MULTIUSUÁRIO: cada usuário ativo com e-mail cadastrado recebe o SEU PRÓPRIO
digest, montado só com os próprios dados — nunca um resumo combinado de
todo mundo. A origem/provisionamento das contas continua manual (só o
admin cria usuários em /admin/usuarios), mas o digest, uma vez a conta
criada, é 100% independente por usuário — é o que permite vender o acesso
sem misturar dados entre clientes.

- send_digest(app, force=False): monta e envia um e-mail por usuário ativo
  com e-mail cadastrado. Idempotente por usuário via notification_log
  (não reenvia se aquele usuário já recebeu hoje), a menos que force=True
  (usado pelo comando manual de teste).
- start_scheduler(app): agenda o envio diário (APScheduler) no horário
  configurado por DIGEST_HOUR/DIGEST_MINUTE/DIGEST_TIMEZONE.

O agendador roda dentro do próprio processo web (BackgroundScheduler) —
não é necessário um serviço de cron separado no Railway. A idempotência
via notification_log (agora por (user_id, sent_date)) protege contra
duplicidade caso existam múltiplos workers/processos.
"""

import logging
import os

from flask import render_template

logger = logging.getLogger(__name__)

_scheduler = None


def _send_digest_for_user(user: dict, force: bool) -> dict:
    """Monta e envia o digest de UM usuário, só com os dados dele."""
    from database.queries_digest import (
        get_overdue_transactions,
        get_due_today_transactions,
        get_today_activities,
        was_digest_sent_today,
        register_digest_sent,
    )
    from utils.notifications import send_email
    from datetime import date

    user_id = user["id"]
    email = (user.get("email") or "").strip()
    if not email:
        return {"sent": False, "reason": "no_email", "user_id": user_id}

    if not force and was_digest_sent_today(user_id):
        return {"sent": False, "reason": "already_sent_today", "user_id": user_id}

    overdue = get_overdue_transactions(user_id)
    due_today = get_due_today_transactions(user_id)
    activities = get_today_activities(user_id)

    total = len(overdue) + len(due_today) + len(activities)

    body_html = render_template(
        "email/digest.html",
        today=date.today(),
        overdue=overdue,
        due_today=due_today,
        activities=activities,
        user=user,
    )

    subject = (
        f"BK Gestão Pessoal — Resumo do dia "
        f"({len(overdue)} vencida(s), {len(due_today)} vence(m) hoje, {len(activities)} atividade(s))"
    )

    ok = send_email(subject, body_html, to=email)
    if ok:
        register_digest_sent(user_id, len(overdue), len(due_today), len(activities))
        logger.info(f"✅ Digest enviado para {email} (user_id={user_id}, {total} itens).")
    else:
        logger.warning(f"❌ Falha ao enviar o digest para {email} (user_id={user_id}).")

    return {
        "sent": ok,
        "user_id": user_id,
        "email": email,
        "overdue_count": len(overdue),
        "due_today_count": len(due_today),
        "activities_count": len(activities),
    }


def send_digest(app, force: bool = False) -> dict:
    """Monta e envia o digest diário — um e-mail por usuário ativo com
    e-mail cadastrado, cada um só com os próprios dados. Retorna um resumo
    agregado de todos os envios."""
    from database.queries_users import get_all_users

    with app.app_context():
        users = [u for u in get_all_users() if u.get("active")]
        results = [_send_digest_for_user(u, force) for u in users]

        sent_count = sum(1 for r in results if r.get("sent"))
        return {
            "sent": sent_count > 0,
            "users_total": len(users),
            "users_sent": sent_count,
            "results": results,
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
