"""
main.py — Agent Pulse FastAPI application.
Dead man's switch for AI agents.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from server import db
from server.scheduler import start_scheduler, stop_scheduler
from server.routes import agents, config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PULSE] %(levelname)s %(message)s",
)
log = logging.getLogger("agentpulse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    start_scheduler()
    log.info("Agent Pulse started")
    yield
    stop_scheduler()
    log.info("Agent Pulse stopped")


app = FastAPI(
    title="Agent Pulse",
    description="Dead man's switch for AI agents. Miss a heartbeat, get an alert.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(agents.router)
app.include_router(config.router)


@app.get("/")
def root():
    return {
        "service": "Agent Pulse",
        "version": "0.1.0",
        "docs": "/docs",
        "description": "Dead man's switch for AI agents",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/register")
def register_owner(email: str = None):
    """Create a new owner account. Returns API token."""
    owner = db.create_owner(email=email)
    return {
        "owner_id": owner["id"],
        "token": owner["token"],
        "plan": "free",
        "message": "Save your token — it's your API key. Use X-API-Token header for all requests.",
    }
