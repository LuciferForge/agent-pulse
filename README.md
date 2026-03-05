# Agent Pulse

Dead man's switch for AI agents. Miss a heartbeat, get an alert.

[![PyPI](https://img.shields.io/pypi/v/agent-pulse)](https://pypi.org/project/agent-pulse/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## The Problem

Your AI agent silently dies at 2am. OOM, uncaught exception, network drop. You find out 6 hours later when a customer complains. Healthchecks.io works for cron jobs — but it doesn't understand agent-specific failures like token budget exhaustion or decision trace anomalies.

## The Solution

Agent Pulse monitors your agents with heartbeats. If a heartbeat is missed, you get a Telegram alert (email and webhook coming). One line of Python to integrate.

## Quick Start

```bash
pip install agent-pulse
```

```python
import agentpulse

# One line. Background thread pings automatically.
agentpulse.init(
    token="ap_your_token_here",
    agent_id="my-scraper",
    interval=300,  # ping every 5 min
)

# Your agent code runs normally...
```

Or use the client directly:

```python
from agentpulse import Client

client = Client(token="ap_your_token_here")

# Register a new agent
agent = client.register("my-trading-bot", interval=300)

# Send heartbeats
client.ping(agent["agent_id"])

# Check status
status = client.status(agent["agent_id"])
print(status)  # {'status': 'alive', 'last_ping_at': '...'}
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/register` | POST | Create owner account, get API token |
| `/api/v1/agents` | POST | Register a new agent |
| `/api/v1/agents/{id}/ping` | POST | Send heartbeat |
| `/api/v1/agents/{id}` | GET | Check agent status |
| `/api/v1/agents` | GET | List all agents |
| `/api/v1/agents/{id}` | DELETE | Remove agent |
| `/api/v1/config/telegram` | POST | Set Telegram alert channel |
| `/api/v1/config/webhook` | POST | Set webhook alert channel |

## Self-Hosting

```bash
pip install agent-pulse[server]
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Requires: Python 3.9+, SQLite (included). No external databases needed.

## Pricing

| Plan | Agents | Min Interval | Channels | Price |
|------|--------|-------------|----------|-------|
| Free | 3 | 5 min | Telegram | $0 |
| Indie | 20 | 1 min | Telegram + Email + Webhook | $9/mo |
| Team | Unlimited | 30 sec | All | $19/mo |

## Built by LuciferForge

Part of the AI agent safety ecosystem:
- [mcp-security-audit](https://pypi.org/project/mcp-security-audit/) — MCP server security auditor
- [agentcred](https://pypi.org/project/agentcred/) — Agent trust scoring
- [kya-agent](https://pypi.org/project/kya-agent/) — Agent identity standard

Contact: LuciferForge@proton.me
