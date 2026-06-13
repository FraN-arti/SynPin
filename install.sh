#!/usr/bin/env bash
# SynPin installer for Linux / macOS
#
# Verifies prerequisites, sets up a Python venv, installs the package
# in editable mode, and (if Node.js is present) installs web
# dependencies. Safe to re-run.
#
# Usage:
#   ./install.sh           # install / verify
#   ./install.sh doctor   # run prerequisites check only
#   ./install.sh update   # pull latest + reinstall

set -e

# Anchor to repo root (where this script lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=11
REQUIRED_NODE_MAJOR=18

color_red()    { printf "\033[31m%s\033[0m\n" "$*"; }
color_green()  { printf "\033[32m%s\033[0m\n" "$*"; }
color_yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
color_blue()   { printf "\033[34m%s\033[0m\n" "$*"; }

step() { printf "\n\033[1;34m==> %s\033[0m\n" "$*"; }
ok()   { color_green "✓ $*"; }
warn() { color_yellow "⚠ $*"; }
fail() { color_red "✗ $*"; }

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

check_python() {
    step "Checking Python >= ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
    if ! command -v python3 >/dev/null 2>&1; then
        fail "python3 not found. Install Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+"
        echo "  macOS:  brew install python@${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
        echo "  Ubuntu:  sudo apt install python${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
        exit 1
    fi

    local py_version
    py_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    local py_major py_minor
    py_major=$(echo "$py_version" | cut -d. -f1)
    py_minor=$(echo "$py_version" | cut -d. -f2)

    if [ "$py_major" -lt "$REQUIRED_PYTHON_MAJOR" ] || \
       { [ "$py_major" -eq "$REQUIRED_PYTHON_MAJOR" ] && [ "$py_minor" -lt "$REQUIRED_PYTHON_MINOR" ]; }; then
        fail "Python $py_version found, need >= ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
        exit 1
    fi
    ok "Python $py_version"
}

check_pip() {
    step "Checking pip"
    if ! python3 -m pip --version >/dev/null 2>&1; then
        fail "pip not available. Run: python3 -m ensurepip --upgrade"
        exit 1
    fi
    ok "pip $(python3 -m pip --version | awk '{print $2}')"
}

check_git() {
    step "Checking git"
    if ! command -v git >/dev/null 2>&1; then
        fail "git not found. Install git."
        exit 1
    fi
    ok "git $(git --version | awk '{print $3}')"
}

check_node() {
    step "Checking Node.js >= ${REQUIRED_NODE_MAJOR} (optional — only needed for the web frontend)"
    if ! command -v node >/dev/null 2>&1; then
        warn "Node.js not found. Web frontend won't work without it."
        warn "  Install from https://nodejs.org/ or via your package manager."
        return 0
    fi
    local node_version
    node_version=$(node --version | sed 's/^v//')
    local node_major
    node_major=$(echo "$node_version" | cut -d. -f1)
    if [ "$node_major" -lt "$REQUIRED_NODE_MAJOR" ]; then
        warn "Node.js $node_version found, recommend >= ${REQUIRED_NODE_MAJOR}"
    else
        ok "Node.js $node_version"
    fi
    if command -v npm >/dev/null 2>&1; then
        ok "npm $(npm --version)"
    else
        warn "npm not found. Install Node.js with npm bundled."
    fi
}

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

install_python_deps() {
    step "Installing Python dependencies (editable install of synpin-core)"
    python3 -m pip install --upgrade pip --quiet
    python3 -m pip install -e core/ --quiet
    ok "synpin-core installed (editable)"
}

install_web_deps() {
    if [ -d web/node_modules ]; then
        step "Web dependencies already installed (web/node_modules exists). Skipping."
        return
    fi
    if ! command -v npm >/dev/null 2>&1; then
        warn "npm not available — skipping web install. Run \`npm install\` in web/ manually."
        return
    fi
    step "Installing web dependencies (npm install in web/)"
    (cd web && npm install --no-fund --no-audit)
    ok "web/node_modules installed"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

cmd_doctor() {
    check_python
    check_pip
    check_git
    check_node
    ok "All required prerequisites met."
    return 0
}

cmd_install() {
    step "SynPin Installer"
    check_python
    check_pip
    check_git
    check_node
    install_python_deps
    install_web_deps
    step "Done."
    ok "SynPin installed. Run \`./bin/synpin start\` or \`./bin/synpin dev\` to begin."
}

cmd_update() {
    step "Updating SynPin"
    if [ ! -d .git ]; then
        fail "Not a git repository — cannot update."
        exit 1
    fi
    git pull --rebase --autostash
    install_python_deps
    install_web_deps
    ok "Updated."
}

case "${1:-install}" in
    doctor)  cmd_doctor ;;
    install|"") cmd_install ;;
    update)  cmd_update ;;
    *)
        echo "Usage: $0 [install|doctor|update]"
        exit 1
        ;;
esac
