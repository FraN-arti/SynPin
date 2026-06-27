# Contributing

Thanks for your interest in SynPin. Before you start, read this — it will save you time and me review cycles.

## TL;DR

- Fork → branch → PR
- One logical change per PR
- Tests pass locally before you open the PR
- Commit messages follow Conventional Commits

## Ground rules

**This is a single-maintainer project.** I'm not a foundation, there is no "core team", and I review PRs in my spare time after work. Please set expectations accordingly:

- Response time: anywhere from a few days to a few weeks. Not because I don't care — because I have a day job.
- Small focused PRs get reviewed fast. Large "rewrite everything" PRs get closed fast.
- If your PR is stuck for more than a month with no feedback, ping me — assume it slipped through, not that I'm ignoring you.

## Before opening a PR

**Open an Issue first.** Especially for non-trivial changes. I'll tell you upfront if it's:

- **aligned** with the project direction — go ahead
- **interesting but not now** — I'll explain why and what would make it mergeable later
- **out of scope** — I'd rather say it now than after you've spent a weekend on it

For typos, doc fixes, obvious bugs — skip the Issue, PR is fine.

## Development setup

```bash
# Clone
git clone https://github.com/FraN-arti/SynPin.git
cd SynPin

# Backend
cd core
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -e ".[dev]"

# Frontend
cd ../web
npm install
npm run dev
```

See [INSTALL.md](INSTALL.md) for the full installation pipeline (production-like setup).

## Code style

**Python** — enforced by [ruff](https://github.com/astral-sh/ruff):

- Line length: **100**
- Target: Python **3.11+**
- Run before committing: `ruff check core/` and `ruff format core/`

**TypeScript / React** — please match the existing style in the file you're editing. Don't introduce a new pattern in a one-line PR.

**General:**

- No emojis in code, comments, or commit messages.
- No trailing whitespace.
- Don't reformat unrelated lines. `git diff` should show only your changes.

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/). Real examples from this repo:

```
feat: add /start/ route for setup wizard
fix: merge /start/ guard and virgin detection into one fetch
docs: rewrite README in Jensen Huang style — narrative over features
chore(web): bump version 0.5.1.35 → 0.5.1.38
```

For version bumps, prefix with the new version:

```
v0.5.1.43: short human description
```

Format: imperative mood, lowercase, no period at the end. The body is optional — use it for the *why*, not the *what* (the diff already shows the what).

## Tests

Tests live outside this repo in a separate sandbox (by design — they're noisy and personal). If you want to add or run tests:

- Open an Issue first describing what you want to test and why
- I'll tell you where they should live and what harness to use
- For now: **a PR with new functionality should describe how you tested it manually**

This is not ideal and I'm aware. It will change.

## Pull request checklist

Before opening a PR:

- [ ] `ruff check core/` passes
- [ ] `ruff format --check core/` passes (or you ran `ruff format` and the diff is clean)
- [ ] `npm run build` in `web/` passes (no TypeScript errors)
- [ ] Manual smoke test: the affected feature actually works in dev mode
- [ ] Commit messages follow the convention
- [ ] PR description explains **why**, not just **what**
- [ ] No unrelated changes (no drive-by reformatting, no "while I was here" cleanups in separate PRs)

## Reporting bugs

Use [GitHub Issues](https://github.com/FraN-arti/SynPin/issues). Include:

- What you did (steps to reproduce)
- What you expected
- What happened
- SynPin version (`/api/version` or bottom-right of the UI)
- OS and Python version

For security issues — **do not open a public Issue**. Email the maintainer directly (see git history for contact) until a SECURITY.md policy is published.

## What I will and won't accept

**Will accept:**

- Bug fixes with a clear reproduction
- Documentation improvements (typos, clarity, missing examples)
- Small, focused features that fit the project direction
- Refactors that simplify code without changing behavior (open an Issue first)

**Won't accept (open an Issue to discuss first if you disagree):**

- Big architectural rewrites
- New dependencies (especially heavy ones) — strong justification required
- Features designed for a single user's workflow that don't generalize
- Anything that breaks the AGPL v3 license terms

## License

By contributing, you agree your contributions are licensed under [AGPL v3](LICENSE) — the same license as the project.
