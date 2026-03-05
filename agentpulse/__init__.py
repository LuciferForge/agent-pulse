"""
Agent Pulse — Dead man's switch for AI agents.

Usage:
    import agentpulse

    agentpulse.init(token="ap_xxx", agent_id="my-bot", interval=300)
    # That's it. SDK pings in a background thread automatically.

    # Or manual ping:
    client = agentpulse.Client(token="ap_xxx", base_url="https://agentpulse.dev")
    agent = client.register("my-bot", interval=300)
    client.ping(agent["agent_id"])
"""

from agentpulse.client import Client, init, ping

__version__ = "0.1.0"
__all__ = ["Client", "init", "ping"]
