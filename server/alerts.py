"""
alerts.py — Alert dispatcher for Agent Pulse.
Sends notifications via Telegram, email (Resend), and webhooks.
"""

import os
import logging
import httpx

log = logging.getLogger("agentpulse.alerts")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
ALERT_FROM_EMAIL = os.environ.get("ALERT_FROM_EMAIL", "alerts@agentpulse.dev")


async def send_telegram(chat_id: str, message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        log.warning("Telegram not configured — skipping alert")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }, timeout=10)
            if resp.status_code == 200:
                log.info(f"Telegram alert sent to {chat_id}")
                return True
            log.error(f"Telegram failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        log.error(f"Telegram error: {e}")
        return False


async def send_email(to_email: str, subject: str, body: str) -> bool:
    if not RESEND_API_KEY or not to_email:
        log.warning("Email not configured — skipping")
        return False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from": ALERT_FROM_EMAIL,
                    "to": [to_email],
                    "subject": subject,
                    "text": body,
                },
                timeout=10,
            )
            return resp.status_code == 200
    except Exception as e:
        log.error(f"Email error: {e}")
        return False


async def send_webhook(url: str, payload: dict) -> bool:
    if not url:
        return False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
            return resp.status_code < 400
    except Exception as e:
        log.error(f"Webhook error: {e}")
        return False


async def fire_alert(agent: dict, owner: dict, alert_type: str = "missed_heartbeat"):
    """Send alert through all configured channels for this owner."""
    from server.db import record_alert

    agent_name = agent["name"]
    last_seen = agent.get("last_ping_at", "never")

    message = (
        f"*Agent Pulse Alert*\n\n"
        f"Agent `{agent_name}` missed its heartbeat.\n"
        f"Last seen: {last_seen}\n"
        f"Expected interval: {agent['interval_seconds']}s\n"
        f"Status: DEAD"
    )

    sent = False

    # Telegram
    if owner.get("telegram_chat_id"):
        ok = await send_telegram(owner["telegram_chat_id"], message)
        if ok:
            record_alert(agent["id"], alert_type, "telegram", message)
            sent = True

    # Email
    if owner.get("email"):
        ok = await send_email(
            owner["email"],
            f"[Agent Pulse] {agent_name} is DOWN",
            message.replace("*", "").replace("`", ""),
        )
        if ok:
            record_alert(agent["id"], alert_type, "email", message)
            sent = True

    # Webhook
    if owner.get("webhook_url"):
        ok = await send_webhook(owner["webhook_url"], {
            "event": alert_type,
            "agent_id": agent["id"],
            "agent_name": agent_name,
            "last_ping_at": last_seen,
            "interval_seconds": agent["interval_seconds"],
            "status": "dead",
        })
        if ok:
            record_alert(agent["id"], alert_type, "webhook", "webhook fired")
            sent = True

    if not sent:
        log.warning(f"No alert channels configured for owner {owner['id']}")
        record_alert(agent["id"], alert_type, "none", "no channels configured")
