<div align="center">

<br/>

<img src="synpin.png" alt="SynPin" width="400">

### Operating system for AI agents.

**An organisation that lives between your conversations.**

<br/>

[![Version](https://img.shields.io/badge/version-0.6.6-orange.svg)](https://github.com/FraN-arti/SynPin)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.133-009688.svg)](https://fastapi.tiangolo.com)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6.svg)](https://typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-6-646CFF.svg)](https://vitejs.dev)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-4-38B2AC.svg)](https://tailwindcss.com)
[![Cockpit](https://img.shields.io/badge/Cockpit-private-lightgrey.svg)](https://github.com/FraN-arti/SynPin-Cockpit)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)

[English](README.en.md) · [Русский](README.md)

</div>

---

<br/>

## What SynPin is

SynPin is a working environment in which **multiple AI agents solve tasks under your supervision**. A head agent coordinates specialisation departments, assigns work, delegates, and tracks progress. Every agent has long-term memory, a role, and a place in the hierarchy.

The system is built for continuity **across sessions**: agents set their own reminders, escalate stuck work, return to unfinished things. This isn't a chat framework or a plugin bundle. It is an organisation that lives as long as you let it.

SynPin is useful when tasks spill out of one conversation — multi-week projects, reports that are better written overnight, ideas that need to be carried forward. Anywhere you don't want to re-explain context every time.

<br/>

## Principles

**Agents are citizens, not tools.** Every agent has a role, a department, a long-term memory. They can set their own reminders, take work from neighbours, escalate up the chain. Not "one agent does everything" and not "a bundle of assistants that don't share any memory."

**Memory is private knowledge.** Each agent has three scopes: `USER` (who you are), `MEMORY` (what it has learned), `FACTS` (what has been decided). The agent itself decides where a fact belongs and finds it later. Not a vector search — structured knowledge with history.

**Proactivity, not reactivity.** Agents create cron jobs, sweep memory, react to channel events. SynPin runs a Linux-style daemon manager — schedule, retention, automated actions — while the computer is on.

**Dark palette, glass panels.** The UI is designed for long late-night sessions. Low contrast, low detail, warm dark grey background, orange accent. Only what you need right now.

<br/>

## Capabilities

- **Head agent with coordination.** Delegates tasks to departments, aggregates summaries, speaks to the user on behalf of the system.
- **Specialisation departments.** Each department has its own agents and contracts. Example: "Communication", "Ideas", "Code", "Kanban".
- **Connections between departments.** Reference `otdel:<id>` → `agent:primary` from code; configure task flows.
- **Long-term memory.** Per agent: `USER.md`, `MEMORY.md`, `FACTS`. With retention and archival.
- **Cron for agents.** Any agent can schedule with `target`, `action_target`, `delivery`, schedule.
- **Kanban.** Task boards with stages, assignees, deadlines.
- **Projects, sessions, facts, triggers, plugins, skills.** All pluggable.

<br/>

## Installation

One command on each platform. The script clones the repo into `~/synpin/`, creates `.venv`, installs Python dependencies, builds the frontend. One folder.

**macOS / Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/FraN-arti/SynPin/main/install | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/FraN-arti/SynPin/main/bootstrap.ps1 | iex
```

After installation, open a new terminal and run:

```
synpin start
```

UI on `http://localhost:2088`. The wizard walks you through provider selection and creating your first agent.

<br/>

## Development

If you want to contribute or fork:

```bash
git clone https://github.com/FraN-arti/SynPin.git
cd SynPin
./install.sh           # or install.ps1 on Windows
synpin dev              # backend + frontend with hot-reload
```

`dev` brings up the API on `:2088` and Vite on `:2099`. Changes in `core/synpin/` are picked up by uvicorn reload, changes in `web/src/` — by Vite HMR.

Contributors: see [CONTRIBUTING.md](CONTRIBUTING.md) for architecture, conventions, and the `AGENTS.md` rules.

<br/>

## License

[AGPL v3](LICENSE). You may use, fork, deploy SynPin for yourself — but if you build a SaaS on top of it, the source code of any derivative product must also be open. For a commercial non-copyleft license, contact the author.

<br/>

## Status

**Active development.** The project is young (~2 months). Concepts and architecture have settled; many features are still in progress. Channels and forum are under development.

SynPin is an open platform. Pull requests, ideas, and bug reports are welcome.

<br/>

---
