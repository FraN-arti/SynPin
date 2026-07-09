# SynPin — Installation

One command per platform. The bootstrap script clones the repo to `~/synpin/`, creates `.venv`, installs Python dependencies, builds the frontend. Everything lives inside that single folder.

## Quick install

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/FraN-arti/SynPin/main/install | bash
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/FraN-arti/SynPin/main/bootstrap.ps1 | iex
```

The installer opens a new shell where `synpin` is on PATH. After it finishes:

```
synpin start
```

UI: <http://localhost:2088>

The wizard walks you through picking an LLM provider and creating your first agent.

## Manual install

If the bootstrap doesn't fit your environment — corporate proxy, air-gapped machine, custom mirror.

```bash
git clone https://github.com/FraN-arti/SynPin.git ~/synpin
cd ~/synpin
./install.sh           # Linux / macOS
# or
.\install.ps1          # Windows PowerShell
```

The installer checks Python ≥ 3.11, pip, git, and (optionally) Node.js ≥ 18. It installs `synpin-core` editable into `.venv/` and runs `npm install && npm run build` for the frontend.

## Development mode

```bash
cd ~/synpin
synpin dev
```

Brings up:
- Core on `:2088` (FastAPI + uvicorn reload)
- Web on `:2099` (Vite + HMR)
- Unified colored output in one terminal (Ctrl+C stops both)

For a production-style server (no reload, no Vite, just Python):

```
synpin start
synpin stop
synpin status
synpin doctor
synpin version
synpin update    # git pull --rebase + reinstall
synpin logs      # last 50 server log lines
```

## Update

```
synpin update
```

Equivalent to `git pull --rebase` plus re-running the install steps. Safe to run multiple times.

## Directory layout

After install, `~/synpin/` contains everything:

```
~/synpin/
├── core/                       ← Python (FastAPI backend)
│   └── synpin/
│       ├── agents/             ← agents, profiles, managers
│       ├── chat/               ← WebSocket routing
│       ├── cron/               ← scheduled tasks
│       ├── memory/             ← USER.md, MEMORY.md, FACTS
│       ├── otdels/             ← departments
│       ├── kanban/             ← board engine
│       ├── tools/              ← built-in tools
│       ├── triggers/           ← event handlers
│       ├── providers/          ← LLM providers
│       ├── cli/                ← `synpin` command
│       └── api/                ← REST + WebSocket
│
├── web/                        ← React + Vite + TypeScript
│   ├── src/
│   └── dist/                   ← built by install
│
├── .venv/                      ← Python virtualenv (created by install)
├── .synpin.pid                 ← runtime pid file
│
├── install / bootstrap.ps1     ← one-line bootstraps
├── install.sh / install.ps1    ← native installers
├── dev.bat / dev.ps1           ← development mode
├── bin/synpin.cmd / bin/synpin ← CLI launchers
│
└── core/synpin/config/         ← YAMLs (settings, providers, agents, ...)
```

The install dir IS the data dir. No `.synpin/` user-home directory, no scattered state.

## Uninstall

```
rm -rf ~/synpin       # macOS / Linux
# or
Remove-Item -Recurse ~/synpin   # Windows
```

This removes code, venv, configs, logs — everything. Your `bin/` is also gone, so `synpin` won't be on PATH anymore.

If you only want to start fresh while keeping the source:

```
rm -rf ~/synpin/.venv ~/synpin/web/dist
cd ~/synpin && ./install.sh
```

## Troubleshooting

### `python` not found / wrong version

Installer requires Python 3.11+. Get it from <https://python.org/downloads/> or via your package manager. On Windows, check **Add Python to PATH** during install.

### Port 2088 already in use

`synpin start` automatically kills whatever holds the port — see the log output for which PID was stopped.

### Front-end shows blank screen

`web/dist` is probably stale. Re-run `install.sh` / `install.ps1`.

### `synpin` not recognised after install

Open a NEW PowerShell / shell — PATH updates apply to new sessions only.

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `SYNPIN_HOST` | `0.0.0.0` | Bind address for `synpin start` |
| `SYNPIN_PORT` | `2088` | Bind port |
| `SYNPIN_DEV` | unset | Set to `1` in dev mode (HMR, debug output) |
| `WIZARD_S` | unset | `1` forces the setup wizard visible (dev only) |
| `SYNPIN_DATA_DIR` | unset | Override config/data location (advanced) |
