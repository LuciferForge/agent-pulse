"""
client.py — Agent Pulse Python SDK.

One-liner setup:
    import agentpulse
    agentpulse.init(token="ap_xxx", agent_id="my-bot", interval=300)

Or manual:
    client = agentpulse.Client(token="ap_xxx")
    client.ping("agent_id_here")
"""

import threading
import time
import logging
import requests

log = logging.getLogger("agentpulse")

DEFAULT_BASE_URL = "https://agentpulse.dev"

# Global client for one-liner usage
_global_client = None
_ping_thread = None
_running = False


class Client:
    def __init__(self, token: str, base_url: str = DEFAULT_BASE_URL):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers["X-API-Token"] = token

    def register(self, name: str, interval: int = 300, grace: int = None) -> dict:
        """Register a new agent. Returns agent details including agent_id."""
        payload = {"name": name, "interval_seconds": interval}
        if grace is not None:
            payload["grace_seconds"] = grace
        resp = self.session.post(f"{self.base_url}/api/v1/agents", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def ping(self, agent_id: str, metadata: str = None) -> dict:
        """Send a heartbeat ping for an agent."""
        payload = {}
        if metadata:
            payload["metadata"] = metadata
        resp = self.session.post(
            f"{self.base_url}/api/v1/agents/{agent_id}/ping",
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def status(self, agent_id: str) -> dict:
        """Get agent status."""
        resp = self.session.get(f"{self.base_url}/api/v1/agents/{agent_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def list_agents(self) -> dict:
        """List all agents for this owner."""
        resp = self.session.get(f"{self.base_url}/api/v1/agents", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def delete(self, agent_id: str) -> dict:
        """Delete an agent."""
        resp = self.session.delete(f"{self.base_url}/api/v1/agents/{agent_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def configure_telegram(self, chat_id: str) -> dict:
        resp = self.session.post(
            f"{self.base_url}/api/v1/config/telegram",
            json={"chat_id": chat_id},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def configure_webhook(self, url: str) -> dict:
        resp = self.session.post(
            f"{self.base_url}/api/v1/config/webhook",
            json={"url": url},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


def init(token: str, agent_id: str, interval: int = 300,
         base_url: str = DEFAULT_BASE_URL, metadata_fn=None):
    """
    One-liner initialization. Starts a background thread that pings automatically.

    Args:
        token: Your API token (from /api/v1/register)
        agent_id: The agent ID to ping
        interval: Ping interval in seconds (default 300 = 5 min)
        base_url: API base URL
        metadata_fn: Optional callable that returns metadata string per ping
    """
    global _global_client, _ping_thread, _running

    _global_client = Client(token=token, base_url=base_url)
    _running = True

    def _ping_loop():
        while _running:
            try:
                meta = metadata_fn() if metadata_fn else None
                _global_client.ping(agent_id, metadata=meta)
                log.debug(f"Heartbeat sent for {agent_id}")
            except Exception as e:
                log.warning(f"Heartbeat failed: {e}")
            time.sleep(interval)

    _ping_thread = threading.Thread(target=_ping_loop, daemon=True, name="agentpulse-heartbeat")
    _ping_thread.start()
    log.info(f"Agent Pulse initialized: agent={agent_id}, interval={interval}s")


def ping(metadata: str = None):
    """Manual ping using the global client. Requires init() first."""
    if _global_client is None:
        raise RuntimeError("Call agentpulse.init() first")
    # Extract agent_id from init — store it
    raise RuntimeError("Use agentpulse.init() for automatic pinging, or Client.ping() for manual")


def stop():
    """Stop the background ping thread."""
    global _running
    _running = False
    log.info("Agent Pulse stopped")
