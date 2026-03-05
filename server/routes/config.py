"""
routes/config.py — Alert configuration endpoints.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from server.auth import require_auth
from server import db

router = APIRouter(prefix="/api/v1/config", tags=["config"])


class TelegramConfig(BaseModel):
    chat_id: str


class WebhookConfig(BaseModel):
    url: str


@router.post("/telegram")
def set_telegram(req: TelegramConfig, owner: dict = Depends(require_auth)):
    db.update_owner_telegram(owner["id"], req.chat_id)
    return {"status": "ok", "telegram_chat_id": req.chat_id}


@router.post("/webhook")
def set_webhook(req: WebhookConfig, owner: dict = Depends(require_auth)):
    db.update_owner_webhook(owner["id"], req.url)
    return {"status": "ok", "webhook_url": req.url}
