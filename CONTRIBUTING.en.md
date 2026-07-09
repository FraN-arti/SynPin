# Contributing

Thanks for your interest in SynPin. This file explains how to report bugs, suggest changes, and open pull requests.

**This is a single-maintainer project.** Reviews happen in spare time after work. Set expectations accordingly — small focused PRs get reviewed fast, large rewrites get closed fast.

## Contribution priorities

In rough order of what gets merged fastest:

1. **Bug fixes** — crashes, incorrect behavior, data loss.
2. **Documentation** — typos, clarifications, missing examples.
3. **Small focused features** that fit the project direction.
4. **Refactors** that simplify code without changing behavior.
5. **New dependencies** — strong justification required.
6. **Architectural rewrites** — open an Issue to discuss first, expect pushback.

If you're unsure where your idea fits, open an Issue. A 5-minute conversation now saves a weekend of work later.

## Before you start: search first

A quick search before you build keeps the queue clean — duplicates are common.

- Search **both open and closed** issues and PRs.
- The README and INSTALL.md describe the current state of the project. Read them first.
- Signal intent on non-trivial changes so effort isn't duplicated.

## Development setup

```bash
# Clone
git clone https://github.com/FraN-arti/SynPin.git ~/synpin
cd ~/synpin

# Production-like install (creates .venv, installs deps, builds frontend)
./install.sh           # macOS / Linux
.\install.ps1          # Windows PowerShell

# Development
synpin dev             # backend :2088 + frontend :2099 with hot-reload
```

Or, faster (just what's needed):

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate  # macOS / Linux
pip install -e "core/[dev]"
cd web && npm install && npm run dev
```

See [INSTALL.md](INSTALL.md) for the production-like installation pipeline.

## Code style

**Python** — enforced by [ruff](https://github.com/astral-sh/ruff):

- Line length: **100**
- Target: Python **3.11+**
- Run before committing: `ruff check core/` and `ruff format core/`

**TypeScript / React** — match the existing style in the file you're editing. Don't introduce a new pattern in a one-line PR.

**General:**

- No emojis in code, comments, or commit messages.
- No trailing whitespace.
- Don't reformat unrelated lines. `git diff` should show only your changes.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/). Real examples from this repo:

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

Format: imperative mood, lowercase, no period at the end. Use the commit body for the *why*, not the *what*.

## Tests

Tests live outside this repo in a separate sandbox by design — they're noisy and personal. If you want to add or run tests, open an Issue first describing what to test and why; we'll figure out where they should live.

A PR with new functionality should describe how you tested it manually. This is not ideal and will change.

## Pull request checklist

- [ ] `ruff check core/` passes
- [ ] `ruff format --check core/` passes (or you ran `ruff format` and the diff is clean)
- [ ] `npm run build` in `web/` passes (no TypeScript errors)
- [ ] Manual smoke test: the affected feature actually works in dev mode
- [ ] Commit messages follow the convention
- [ ] PR description explains **why**, not just **what**
- [ ] No unrelated changes — no drive-by reformatting, no "while I was here" cleanups in separate PRs

## Reporting bugs

Use [GitHub Issues](https://github.com/FraN-arti/SynPin/issues). Include:

- Steps to reproduce
- What you expected
- What happened
- SynPin version (`/api/version` or bottom-right of the UI)
- OS and Python version

For security issues — **do not open a public Issue**. Email the maintainer directly (see git history for contact) until a SECURITY.md policy is published.

## What gets accepted

| Accepted | Won't be accepted (open an Issue first if you disagree) |
| :--- | :--- |
| Bug fixes with a clear reproduction | Big architectural rewrites |
| Doc improvements (typos, clarity, examples) | New heavy dependencies without strong justification |
| Small features that fit the project direction | Features designed for a single user's workflow that don't generalize |
| Refactors that simplify without changing behavior | Anything that breaks AGPL v3 license terms |

## License

By contributing, you agree your contributions are licensed under [AGPL v3](LICENSE) — the same license as the project.

---

For Russian version of this document, see [CONTRIBUTING.md](CONTRIBUTING.md).
