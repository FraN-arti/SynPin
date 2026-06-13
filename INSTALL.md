# SynPin — Installation & Quick Start

## First-time install

### Windows
```powershell
# From the repo root:
.\install.ps1
```

### Linux / macOS
```bash
./install.sh
```

The installer verifies Python ≥ 3.11, git, and (optionally) Node.js ≥ 18.
It installs `synpin-core` in editable mode and runs `npm install` for the
web frontend.

## Running

### Web (full dev server with unified output)

**Windows:**
```
dev.bat
```

**Unix / any platform:**
```bash
./bin/synpin dev
# or, if you've added bin/ to PATH:
synpin dev
```

This starts Core (FastAPI on :2088) and Web (Vite on :2099) with a
unified console output — green [CORE] lines and cyan [WEB] lines,
Ctrl+C stops both.

### Backend only (production-style)
```bash
synpin start       # foreground
synpin stop        # kills via pidfile
synpin status      # checks /api/health
synpin doctor      # full prerequisites check
synpin version     # reads from pyproject.toml or installed metadata
synpin update      # git pull + reinstall
synpin setup       # first-run wizard (creates config dir, asks for keys)
synpin logs        # tail of last 50 log lines
synpin config      # show config location
```

## Directory layout

```
D:\synpin\
├── pyproject.toml         # package definition (name: synpin-core)
├── dev.bat                # Windows dev launcher
├── install.sh / .ps1      # installers
├── package.json           # npm wrapper (npm run dev, npm run build:web)
├── bin/
│   ├── synpin             # Unix launcher
│   └── synpin.cmd         # Windows launcher
├── web/                   # React/Vite frontend
└── core/
    ├── pyproject.toml     # (legacy — re-export of root one)
    ├── data/              # (legacy — empty; data moved to synpin/data/)
    └── synpin/
        ├── __main__.py    # synpin CLI entry
        ├── cli/            # synpin commands (start, stop, dev, doctor, ...)
        ├── data/           # per-entity data (tasks, departments, otdels)
        │   ├── departments/<id>/department.yaml
        │   ├── otdels/<id>/otdel.yaml
        │   └── tasks/<id>.yaml
        ├── api/            # FastAPI routers
        ├── agents/         # agent + department + otdel managers
        ├── kanban/         # kanban service + models
        ├── chat/           # chat routers
        ├── tools/          # agent tool implementations
        ├── paths.py        # new path resolver (XDG/platformdirs)
        └── paths_legacy.py # old resolvers, kept for back-compat
```

## Updating

```bash
synpin update    # git pull + pip install -e core/ + (if web changed) cd web && npm install
```

## Uninstalling

Remove `core/.synpin/` (dev) or `~/.synpin/` (prod) to wipe local data.
The package itself can be removed with `pip uninstall synpin-core`.
