"""
auth.py — Token-based authentication for Agent Pulse.
"""

from fastapi import Header, HTTPException
from server.db import get_owner_by_token


def require_auth(authorization: str = Header(..., alias="X-API-Token")) -> dict:
    """FastAPI dependency — extracts and validates owner token."""
    owner = get_owner_by_token(authorization)
    if not owner:
        raise HTTPException(status_code=401, detail="Invalid API token")
    return owner
