<div align="center">

<br/>

<img src="synpin.png" alt="SynPin" width="400">

**The operating system for AI agents.**

Not a chat, not a copilot — an autonomous organization that works while you sleep.

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6.svg)](https://typescriptlang.org)
[![WebSocket](https://img.shields.io/badge/WebSocket-realtime-4FC08D.svg)](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
[![React Flow](https://img.shields.io/badge/React%20Flow-12-FF007F.svg)](https://reactflow.dev)
[![dnd-kit](https://img.shields.io/badge/dnd--kit-latest-FF6B35.svg)](https://dndkit.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-latest-FF6F00.svg)](https://www.trychroma.com)
[![YAML](https://img.shields.io/badge/Config-YAML-0B5D9C.svg)](https://yaml.org)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063.svg)](https://docs.pydantic.dev)
[![Vite](https://img.shields.io/badge/Vite-6-646CFF.svg)](https://vite.dev)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)

<br/>

[English](README.en.md) · [Русский](README.md)

</div>

---

<br/>

## The problem

Every AI coding tool today works the same way: you write a prompt, the agent executes, you wait. A single agent, a single thread, a single context window.

But what happens when you want the agent to **work on its own**? When you want it to plan, delegate, review, and ship — without you sitting in front of the keyboard at 2 AM?

**Nothing.** Because none of them are built for that.

---

## The shift

A month ago, models had 256K context windows. A year ago — 128K. Today, production models have 1M. And within months — **10M tokens** of context.

This changes everything.

With 10M tokens, an agent can hold your entire codebase, all open issues, last month of logs, every decision you ever made — and still have room to think.

But a **single** agent, no matter how much context it has, is still a single agent. It cannot specialize, cannot delegate, cannot work in parallel.

To use 10M tokens effectively, you need **more than one agent**. You need a system.

---

## The idea

SynPin is not an AI coding assistant. It is a **multi-agent operating system** — a platform where AI agents live and work as an autonomous organization, not as anonymous chatbots.

Think of it like an orchestra:

- **The user is the conductor.** One gesture sets the direction. You don't play every instrument — you guide.
- **The agents are the musicians.** Each has a role, a specialization, a place in the hierarchy.
- **The departments are the sections.** Strings, brass, woodwinds — isolated, focused, synchronous.
- **The cron scheduler is the metronome.** Work happens even when you're not in the room.
- **The Kanban board is the sheet music.** Every task has a place, a status, a performer.

You don't write twenty prompts to ship a feature. You describe the feature once. The orchestrator plans, delegates to departments, monitors execution, and delivers the result.

---

## How it works

### Hierarchy

```
              ┌─────────────────────┐
              │   Orchestrator AI   │  ← sees everything, plans, delegates
              │  (main agent)       │
              └──────┬──────┬───────┘
                     │      │
           ┌─────────┘      └─────────┐
           ▼                          ▼
    ┌──────────────┐         ┌──────────────┐
    │  Department  │         │  Department  │  ← isolated memory & context
    │  Head AI     │◄───────►│  Head AI     │  ← cross-department links
    └──────┬───────┘         └──────┬───────┘
           │                        │
      ┌────┼────┐              ┌────┼────┐
      ▼    ▼    ▼              ▼    ▼    ▼
   Worker Worker Worker    Worker Worker Worker  ← parallel execution
```

Each department has:
- A **head** — receives tasks, decomposes, delegates, synthesizes results
- **Workers** — specialists who execute in parallel
- **Isolated memory** — departments don't leak context
- **Links** — task escalation, delegation, and collaboration between departments

### Autonomy

SynPin works without you.

- **Cron** schedules nightly QA runs, report generation, task creation
- **Kanban** tracks every task from creation to delivery across departments
- **Memory** persists across sessions — agents remember what they learned
- **Orchestrator** monitors all departments, reassigns blocked tasks, escalates bottlenecks

You wake up to a daily report. Not because you asked for it at midnight — because the system knew you'd need it in the morning.

---

## What makes SynPin different

| | Single-agent tools | SynPin |
|---|---|---|
| **Structure** | One agent per session | Hierarchical multi-agent organization |
| **Autonomy** | Requires user for every step | Works independently on schedule |
| **Memory** | Session-scoped (forgets on restart) | Persistent per agent and department |
| **Parallelism** | Single thread | Multiple agents execute simultaneously |
| **Context model** | One window per task | Shared context across orchestrated agents |
| **User role** | Operator | Conductor |

---

## Quick start

```bash
git clone https://github.com/FraN-arti/SynPin.git
cd SynPin
.\install.ps1          # Windows
./install.sh           # Linux / macOS
synpin dev             # development mode
```

Open `http://localhost:2099`.

Or run with the system wizard:
```bash
synpin setup           # interactive first-run wizard
synpin start           # production mode
```

---

## Why open source

Because the AI agent ecosystem should not be owned by one company.

SynPin is licensed under AGPL v3 — you can use it, fork it, modify it. If you build on it publicly, the changes stay open.

Commercial use without source disclosure? Reach out.

---

## The road ahead

The models are getting smarter. The context windows are exploding. The cost of inference is dropping.

In 2026, the question is no longer "can an AI write code?" — it's "can a system of AI agents run a project?"

SynPin is our answer.

<br/>

<div align="center">

<br/>

**You are not the trigger. You are the conductor.**

<br/>

</div>
