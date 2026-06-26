<div align="center">

<br/>

<img src="synpin.png" alt="SynPin" width="400">

### Operating system for AI agents.

**An organization that works while you sleep.**

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6.svg)](https://typescriptlang.org)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)

[English](README.en.md) · [Русский](README.md)

</div>

---

<br/>

## One question

What happens when you turn off your computer?

Today's AI tools have one answer: **nothing**. They sleep. Close the tab, and everything they knew evaporates. No action taken while you were away.

But it doesn't have to be that way.

You have work that can happen without you. Reports that are better written at night. Reminders that shouldn't depend on your memory. Checks that need to run every half hour. Ideas that happen in the background.

**SynPin is agents living by those rules.**

<br/>

---

<br/>

## What it is

SynPin is not another chat framework. It's **an operating system for agents**, where:

- **Agents set their own reminders.** You said *"tomorrow evening let's talk about X"* — the agent already remembers and will remind you itself, no prompting needed.
- **The head agent delegates to departments** — and watches the progress itself, extends timers, escalates blocked work.
- **Memory survives the session.** What an agent learned today, it remembers a month from now. Not as "vector DB search", but as **its own knowledge**.
- **Cron, like Linux — but for agents.** Schedule, sweep, retention, daemon manager. All real.
- **Three kinds of memory:** who you are (USER), what matters (MEMORY), what was decided (FACTS). Every fact goes where it belongs.

This is infrastructure for AI agents. **Process management. Persistent state. Proactive autonomy.**

<br/>

---

<br/>

## What it looks like in practice

At 9 PM you tell Lyutik: *"Tomorrow I want to review the quarterly report"*.

Lyutik:
1. Checks `MEMORY.md` — there's "User is usually home by 9 PM".
2. Calculates: tomorrow, 9 PM.
3. **Itself** creates a cron job with the right `target`, `agent`, `delivery`.
4. Confirms: *"Done. I'll remind you tomorrow at 9 PM."*

You **never told it** to create a cron. It saw the pattern and acted. That's **proactivity** — what makes SynPin feel alive instead of another form with a button.

Another day you tell the head agent: *"In an hour, message the head of the Communication department to greet everyone"*.

The head agent:
1. Sees the "Communication" department in `otdels.yaml`.
2. Takes the head's slug (not main_agent — this matters, otherwise the result goes to the wrong place).
3. Creates a cron with `action_target="otdel:<id>"`, `delivery="otdel"`.
4. In an hour — the department's head **itself** writes the greeting **in its own chat**, not in your private one.

You don't run the process. You set the goal, and the agents choose the route.

<br/>

---

<br/>

## Why this way

In the LLM world today there are two extremes. **One agent doing everything** — even with 10M context it's still one agent. Can't delegate, can't parallelize, can't specialize.

**One agent per role** — assistant for code, assistant for design, assistant for something else. Each on its own. No memory between them.

SynPin is **the third path**. A system where agents are **citizens**, not tools.

- Each has a role.
- Each has a place in the hierarchy.
- Each has long-term memory.
- Each has the right to set reminders and take work.
- Each has duties to the department.

And most importantly — **they're not perfect workers, they're part of your life**. They remember what worried you a week ago. They ask "how are you". Not because they were told to — because they live in your context and they care.

<br/>

---

<br/>

## Already working

You're not buying an idea — you run it and see:

- **28 tests** covering memory, cron, limits, retention.
- **3 hierarchy levels:** head agent → department heads → workers.
- **Real-time WS** — events without polling.
- **Glassmorphism UI** with dark theme.
- **v0.5.1.42** on GitHub, AGPL-3.0.

<br/>

---

<br/>

## Quick start

```bash
git clone https://github.com/FraN-arti/SynPin.git
cd SynPin
.\install.ps1          # Windows
./install.sh           # Linux / macOS
synpin dev             # development mode
```

Open `http://localhost:2099`.

<br/>

---

<br/>

## The road

This isn't an MVP. It's **a foundation**. Every day something gets added — but not for features. For **agents to feel at home**.

A year ago models couldn't hold long context. Today they can. Tomorrow they'll hold everything. But context without **purpose** is just text in a buffer.

SynPin gives agents **purpose**. Place, work, memory, colleagues.

**This isn't about AI that answers questions. It's about AI that lives.**

<br/>

---

<div align="center">

<br/>

*SynPin — because one AI agent shouldn't be lonely.*

<br/>

</div>