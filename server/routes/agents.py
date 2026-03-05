"""
routes/agents.py — Core API: register, ping, status, list, delete.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from server.auth import require_auth
from server import db

router = APIRouter(prefix="/api/v1", tags=["agents"])


class RegisterRequest(BaseModel):
    name: str
    interval_seconds: int = 300
    grace_seconds: Optional[int] = None


class PingPayload(BaseModel):
    metadata: Optional[str] = None


# ─── Register a new agent ────────────────────────────────────────────────────

@router.post("/agents")
def register_agent(req: RegisterRequest, owner: dict = Depends(require_auth)):
    plan = owner.get("plan", "free")
    limit = db.PLAN_LIMITS.get(plan, 3)
    current = db.count_agents(owner["id"])

    if current >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Agent limit reached ({current}/{limit}). Upgrade at https://agentpulse.dev/pricing",
        )

    # Enforce minimum interval per plan
    min_intervals = {"free": 300, "indie": 60, "team": 30}
    min_interval = min_intervals.get(plan, 300)
    if req.interval_seconds < min_interval:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum interval for {plan} plan is {min_interval}s",
        )

    agent = db.create_agent(
        owner_id=owner["id"],
        name=req.name,
        interval=req.interval_seconds,
        grace=req.grace_seconds,
    )

    return {
        "agent_id": agent["id"],
        "name": agent["name"],
        "interval_seconds": agent["interval_seconds"],
        "grace_seconds": agent["grace_seconds"],
        "status": "new",
        "message": f"Agent registered. Send pings to POST /api/v1/agents/{agent['id']}/ping",
    }


# ─── Ping (heartbeat) ────────────────────────────────────────────────────────

@router.post("/agents/{agent_id}/ping")
def ping_agent(agent_id: str, payload: PingPayload = None, owner: dict = Depends(require_auth)):
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent["owner_id"] != owner["id"]:
        raise HTTPException(status_code=403, detail="Not your agent")

    meta = payload.metadata if payload else None
    db.record_ping(agent_id, meta)

    return {"status": "ok", "agent_id": agent_id, "recorded_at": db.now_iso()}


# ─── Status check ────────────────────────────────────────────────────────────

@router.get("/agents/{agent_id}")
def get_agent_status(agent_id: str, owner: dict = Depends(require_auth)):
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent["owner_id"] != owner["id"]:
        raise HTTPException(status_code=403, detail="Not your agent")

    return {
        "agent_id": agent["id"],
        "name": agent["name"],
        "status": agent["status"],
        "last_ping_at": agent["last_ping_at"],
        "interval_seconds": agent["interval_seconds"],
        "grace_seconds": agent["grace_seconds"],
    }


# ─── List all agents ─────────────────────────────────────────────────────────

@router.get("/agents")
def list_agents(owner: dict = Depends(require_auth)):
    agents = db.list_agents(owner["id"])
    return {
        "agents": [
            {
                "agent_id": a["id"],
                "name": a["name"],
                "status": a["status"],
                "last_ping_at": a["last_ping_at"],
                "interval_seconds": a["interval_seconds"],
            }
            for a in agents
        ],
        "count": len(agents),
        "plan": owner.get("plan", "free"),
        "limit": db.PLAN_LIMITS.get(owner.get("plan", "free"), 3),
    }


# ─── Delete agent ─────────────────────────────────────────────────────────────

@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str, owner: dict = Depends(require_auth)):
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent["owner_id"] != owner["id"]:
        raise HTTPException(status_code=403, detail="Not your agent")

    db.delete_agent(agent_id)
    return {"status": "deleted", "agent_id": agent_id}
