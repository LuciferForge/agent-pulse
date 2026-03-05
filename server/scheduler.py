"""
scheduler.py — Background heartbeat checker.
Runs every 30s, finds overdue agents, fires alerts.
"""

import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from server import db
from server.alerts import fire_alert

log = logging.getLogger("agentpulse.scheduler")

scheduler = AsyncIOScheduler()


async def check_heartbeats():
    """Scan for agents that missed their heartbeat window."""
    overdue = db.get_overdue_agents()
    never_pinged = db.get_never_pinged_agents()

    all_dead = overdue + never_pinged

    if not all_dead:
        return

    log.info(f"Found {len(all_dead)} dead/overdue agents")

    for agent in all_dead:
        owner = db.get_owner_by_token(None)  # Need owner lookup by id
        # Get owner by agent's owner_id
        conn = db.get_conn()
        row = conn.execute("SELECT * FROM owners WHERE id = ?", (agent["owner_id"],)).fetchone()
        conn.close()
        if not row:
            continue
        owner = dict(row)

        log.warning(f"Agent '{agent['name']}' (id={agent['id']}) is DEAD — last ping: {agent.get('last_ping_at', 'never')}")

        db.mark_agent_dead(agent["id"])
        await fire_alert(agent, owner)


def start_scheduler():
    scheduler.add_job(
        check_heartbeats,
        "interval",
        seconds=30,
        id="heartbeat_check",
        replace_existing=True,
    )
    scheduler.start()
    log.info("Heartbeat checker started (30s interval)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
