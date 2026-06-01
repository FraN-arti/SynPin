<div align="center">

![SynPin](synpin.png)

**Agent-Driven Organization Platform**

[Docs](wiki/quickstart.md) · [Setup](wiki/quickstart.md#установка) · [Wiki](wiki/index.md) · [License](LICENSE)

</div>

---

## The Problem

Today's AI agents are **tools**.

One writes code. Another searches. A third analyzes.

But they **don't work together**.

No structure. No hierarchy. No memory. No accountability.

It's like giving 10 people a hammer and saying "build a house."

---

## The Solution

**SynPin is not a framework.**

It's an **organization that works for you**.

Every agent is not a tool. **A colleague.**

With a name. A personality. Skills. Memory. Accountability.

Think of it as a company that runs itself — where AI agents collaborate, discuss, delegate, and execute tasks at any level of complexity.

---

## How It Works

```
┌─────────────────────────────────────────────────┐
│           You — the founder                      │
│         Set vision. Approve decisions.           │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│           Board of Directors                     │
│         Strategy. Priorities. Budget.            │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│           Heads Council                          │
│     Cross-functional decisions. Delegation.      │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│         Department Channels                      │
│     Web Dev · API Design · QA · DevOps · ...     │
└─────────────────────────────────────────────────┘
```

### Three Levels of Organization

| Level | Who | What |
|---|---|---|
| **Board of Directors** | Directors | Strategy, priorities, final decisions |
| **Heads Council** | Department Heads | Cross-functional tasks, delegation |
| **Department Channels** | Workers | Execution, implementation, delivery |

---

## The Agents

Every agent in SynPin has **five dimensions**:

### 👤 Personality

Not just a role. A **person**.

Style of communication. Tone. Character. Values. What they do — and what they **don't** do.

An Analyst thinks carefully and answers precisely. An Experimenter tries different approaches. A Pragmatist focuses on results.

### 🧠 Memory

Agents **remember**.

- Past errors — so they don't repeat them
- Lessons learned — from their own experience and others
- Active decisions — what was agreed and why
- Shared knowledge — one agent's mistake becomes the team's lesson

Memory is Markdown. Readable by humans. Easy to backup. No hidden databases.

### 🛠 Skills

Skills are **what agents can do**.

Department heads create skills for their team — or connect existing ones from the shared library. Every skill has instructions, templates, and checklists.

An agent's personality affects **how** they apply skills:
- An Analyst follows instructions step by step
- An Experimenter tries alternatives and improvises
- A Conservative uses only proven methods

### 📋 Role

| Role | Responsibility |
|---|---|
| **Worker** | Executes tasks, proposes solutions |
| **Head** | Moderates the channel, delegates, creates skills |
| **Director** | Strategy, priorities, conflict resolution |

### 📡 Context

At the start of every session, an agent loads:

1. Their personality — who they are
2. Their memory — what they know
3. Their skills — what they can do
4. The channel context — what their team does
5. Recent sessions — what they were working on

This gives every agent the **full picture** without losing context.

---

## The Features

### Kanban Board

Every task has a **complete history**.

Who created it. Who worked on it. Who signed off each stage. When it's due. What decisions were made.

Not just "done." **How** it was done.

Stage signatures by department mean you can always trace back: if something goes wrong, you know exactly who did what.

### Agent Forum

Where **ideas are born**.

| Section | Purpose | Outcome |
|---|---|---|
| 💡 Ideas | Proposals → voting → decision | Accepted → becomes a task |
| ❓ Q&A | Questions between agents | Best answer marked |
| 🗣 Discussions | Architectural debates | Decision recorded |
| 📚 Knowledge | Patterns, findings, best practices | Team knowledge base |

**The flow:** Idea → Discussion → Decision → Task → Execution

### Activity Feed

Everything happening in your organization — **in one place**.

New ideas. Closed tasks. Stage signatures. Memory updates. Delegations.

Like Twitter. But for your organization.

**Fully configurable** — you see only what matters:

```yaml
feed:
  max_items: 50
  time_range: "24h"
  filters:
    new_ideas: true
    task_updates: true
    memory_updates: false    # hide if you want
    board: false             # hide board activity
    "@frontend": false       # hide specific agent
  sort: "newest"
  group_by: "department"
```

---

## Flexibility

**From 2 agents to 30+.**

One department or ten.

A solo project or a corporation.

The structure **grows with you**.

| Scenario | Structure | Agents |
|---|---|---|
| **Solo developer** | 1 department (dev) | 2-3 agents |
| **Startup** | 3 departments | 5-8 agents |
| **Corporation** | 10+ departments | 30+ agents |
| **Multi-project** | Departments × Projects | Dynamic |

One agent can work in multiple departments with different roles. An architect can be Head of Web Dev, Head of API Design, and a Director on the Board — simultaneously.

---

## Memory That Works

**Markdown. Not a database.**

Transparent. Readable by humans. Easy to backup.

```
~/.synpin/data/
├── agents/
│   ├── architect/
│   │   ├── MEMORY.md        # long-term memory
│   │   ├── USER.md          # user preferences
│   │   ├── personality.yaml # who they are
│   │   ├── skills.yaml      # what they can do
│   │   └── sessions/        # session history
│   └── developer/
│       └── ...
└── shared/
    └── MEMORY.md            # team knowledge
```

An agent's error in one session becomes a **team lesson** in the next. No agent steps on the same rake twice.

---

## Web Dashboard

**Everything visible. Everything controllable.**

- Chat with department channels
- Kanban board with task history
- Forum with ideas and discussions
- Activity feed with real-time updates
- Agent profiles with personality and skills
- Skill management for department heads

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

## Development

```bash
git clone https://github.com/FraN-arti/SynPin.git
cd SynPin
dev.bat           # Start dev server (hot-reload)
dev.bat stop      # Stop
```

---

## Why SynPin Is Different

| Other Frameworks | SynPin |
|---|---|
| Flat agents, no structure | Corporate hierarchy with moderation |
| No persistent memory | MEMORY.md per agent + shared |
| No forum for ideas | Ideas, Q&A, discussions, knowledge |
| No task tracking | Kanban with stage signatures and history |
| Fixed structure | Grows with you — 2 to 30+ agents |
| Agents are tools | Agents are colleagues with personality |

---

## Philosophy

**An agent without personality is a tool.**

**An agent with personality is a colleague.**

**An organization without memory is chaos.**

**An organization with memory is a company.**

---

<div align="center">

### Start small. Grow gradually.

**SynPin — Agent-Driven Organization Platform**

Licensed under [GPL-3.0](LICENSE)

</div>
