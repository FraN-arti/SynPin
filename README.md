<div align="center">

# SynPin

**Agent-Driven Organization Platform**

[Docs](wiki/quickstart.md) · [Setup](wiki/quickstart.md#установка) · [License](LICENSE)

</div>

---

## What is SynPin?

SynPin is not just a framework — it's an **organization where every agent can be both a worker and a director**.

Any agent can:
- Execute tasks as a **worker** (search, code, analyze)
- Join the **board of directors** to make strategic decisions
- Lead a team and delegate work
- Learn from experience and improve over time

Think of it as a company that runs itself — where AI agents collaborate, discuss, and execute tasks at any level of complexity.

---

## Quick Start

### Install

```powershell
git clone https://github.com/FraN-arti/SynPin.git
cd SynPin
.\scripts\install.ps1
```

### Run

```powershell
synpin start
```

Open `http://localhost:2088` — your organization is ready.

---

## Commands

| Command | Description |
|---------|-------------|
| `synpin start` | Start the server |
| `synpin stop` | Stop the server |
| `synpin status` | Check server status |
| `synpin update` | Update from GitHub + rebuild |
| `synpin setup` | Initial configuration wizard |
| `synpin version` | Show version |

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Web Dashboard (React)               │
│         Monitor · Chat · Configure              │
└─────────────────────┬───────────────────────────┘
                      │ HTTP / WebSocket
                      ▼
┌─────────────────────────────────────────────────┐
│              Core API (FastAPI)                  │
│         /api/agents · /api/tasks · /api/chat    │
└─────────────────────┬───────────────────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
┌──────────────────┐    ┌──────────────────────┐
│   Board of       │    │   Worker Agents      │
│   Directors      │    │   Search · Code      │
│   (strategy)     │    │   Analyze · Execute  │
└────────┬─────────┘    └──────────┬───────────┘
         │                         │
         ▼                         ▼
┌─────────────────────────────────────────────────┐
│              Memory System                       │
│         ChromaDB · Shared Knowledge             │
│         Per-Agent History · Error Log           │
└─────────────────────────────────────────────────┘
```

---

## Development

```bash
git clone https://github.com/FraN-arti/SynPin.git
cd SynPin
dev.bat           # Start dev server (hot-reload)
dev.bat stop      # Stop
```

---

<div align="center">

**Start small. Grow gradually.**

</div>
