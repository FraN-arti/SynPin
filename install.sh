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

# Load shared SynPin brand colors. colors.sh defines SP_BRAND/SP_OK/
# SP_WARN/SP_FAIL/etc. via ANSI 24-bit escape codes. It also defines
# sp_ok/sp_step/sp_warn/sp_fail helper functions which we rewrap below
# as step/ok/warn/fail to match the existing call sites in this file.
. "$SCRIPT_DIR/colors.sh"

# Rewrap helpers to drop the emoji glyphs (some terminals and CI logs
# render them as ???). SynPin ships clean text by design.
step() { sp_step "$@"; }
ok()   { printf "%b[OK]%b %s\n"   "$SP_OK"   "$SP_RESET" "$*"; }
warn() { printf "%b[WARN]%b %s\n" "$SP_WARN" "$SP_RESET" "$*"; }
fail() { printf "%b[FAIL]%b %s\n" "$SP_FAIL" "$SP_RESET" "$*" >&2; }

# ---------------------------------------------------------------------------
# Auto-install helpers
#
# If a required tool is missing, try to install it via the system
# package manager before bailing out. We never silently sudo - every
# privileged install is gated behind an interactive y/N prompt and
# the script clearly states what it's about to do.
# ---------------------------------------------------------------------------

# Detect the OS / distro once at startup.
OS_KIND="unknown"
PKG_INSTALL_CMD=""
if [ -f /etc/os-release ]; then
    . /etc/os-release
    case "${ID:-}" in
        ubuntu|debian|linuxmint|pop|elementary|"kde neon"|zorin)
            OS_KIND="debian"; PKG_INSTALL_CMD="sudo apt-get install -y" ;;
        fedora|rhel|centos|rocky|almalinux|nobara)
            OS_KIND="fedora"; PKG_INSTALL_CMD="sudo dnf install -y" ;;
        arch|manjaro|endeavouros)
            OS_KIND="arch"; PKG_INSTALL_CMD="sudo pacman -S --noconfirm" ;;
        opensuse*|sles)
            OS_KIND="suse"; PKG_INSTALL_CMD="sudo zypper install -y" ;;
        alpine)
            OS_KIND="alpine"; PKG_INSTALL_CMD="sudo apk add" ;;
    esac
fi
if command -v brew >/dev/null 2>&1; then
    OS_KIND="brew"; PKG_INSTALL_CMD="brew install"
fi

# Offer to run a privileged install. Returns 0 on success (or if
# the user accepted the install but it failed - caller will re-check
# and decide), 1 if the user said no.
offer_install() {
    local what="$1"
    local pkgname="$2"
    if [ -z "$PKG_INSTALL_CMD" ]; then
        warn "Cannot auto-install $what: no supported package manager found."
        warn "  Install $what manually (e.g. from https://python.org/, https://nodejs.org/)."
        return 1
    fi
    printf "\n  $what is missing. The installer can install it via:\n"
    printf "    $PKG_INSTALL_CMD $pkgname\n"
    if [ "${SYNPIN_AUTO_INSTALL:-0}" = "1" ]; then
        warn "SYNPIN_AUTO_INSTALL=1 set, installing without prompt..."
        REPLY="y"
    else
        read -p "  Install $what now? [y/N] " -n 1 -r REPLY
        printf "\n"
    fi
    if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
        warn "Skipped $what install. The script will fail unless you install it manually."
        return 1
    fi
    if $PKG_INSTALL_CMD "$pkgname"; then
        ok "$what installed."
        return 0
    else
        fail "$what install failed. Check the output above."
        return 1
    fi
}

# Re-check a command after install attempt.
recheck() {
    local cmd="$1"
    if command -v "$cmd" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

check_python() {
    step "Checking Python >= ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
    if ! command -v python3 >/dev/null 2>&1; then
        # Pick the right package name for the distro.
        case "$OS_KIND" in
            debian)  pkg="python3.11 python3-pip" ;;  # may not be in default repos
            fedora)  pkg="python3.11" ;;               # may need extra repo
            arch)    pkg="python python-pip" ;;
            suse)    pkg="python3 python3-pip" ;;
            alpine)  pkg="python3 py3-pip" ;;
            brew)    pkg="python@3.11" ;;
            *)       pkg="" ;;
        esac
        if [ -n "$pkg" ]; then
            offer_install "Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+" "$pkg" || exit 1
        else
            fail "python3 not found. Install Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+"
            echo "  macOS:  brew install python@${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
            echo "  Ubuntu: sudo apt install python${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
            exit 1
        fi
        # Re-check after install attempt.
        if ! recheck python3; then
            fail "python3 still not on PATH after install. Try opening a new shell."
            exit 1
        fi
    fi

    local py_version
    py_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    local py_major py_minor
    py_major=$(echo "$py_version" | cut -d. -f1)
    py_minor=$(echo "$py_version" | cut -d. -f2)

    if [ "$py_major" -lt "$REQUIRED_PYTHON_MAJOR" ] || \
       { [ "$py_major" -eq "$REQUIRED_PYTHON_MAJOR" ] && [ "$py_minor" -lt "$REQUIRED_PYTHON_MINOR" ]; }; then
        # Try to install a newer Python via the package manager. On
        # Debian/Ubuntu, 3.11 isn't in the default repos of older
        # releases - we point at the deadsnakes PPA as a last resort
        # but only if the user opts in.
        if [ "$OS_KIND" = "debian" ] && [ "${SYNPIN_AUTO_INSTALL:-0}" = "1" ]; then
            warn "System Python is too old. Adding deadsnakes PPA + installing 3.11..."
            sudo apt-get install -y software-properties-common
            sudo add-apt-repository -y ppa:deadsnakes/ppa
            sudo apt-get update
            sudo apt-get install -y python3.11 python3.11-venv python3.11-distutils
        else
            fail "Python $py_version found, need >= ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
            echo "  Set SYNPIN_AUTO_INSTALL=1 to attempt automatic upgrade."
            echo "  Or install Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+ manually."
            exit 1
        fi
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
        case "$OS_KIND" in
            debian)  pkg="git" ;;
            fedora)  pkg="git" ;;
            arch)    pkg="git" ;;
            suse)    pkg="git" ;;
            alpine)  pkg="git" ;;
            brew)    pkg="git" ;;
            *)       pkg="" ;;
        esac
        if [ -n "$pkg" ]; then
            offer_install "git" "$pkg" || exit 1
        else
            fail "git not found."
            exit 1
        fi
        recheck git || { fail "git still missing after install"; exit 1; }
    fi
    ok "git $(git --version | awk '{print $3}')"
}

check_node() {
    step "Checking Node.js >= ${REQUIRED_NODE_MAJOR} (optional - only needed for the web frontend)"
    if ! command -v node >/dev/null 2>&1; then
        case "$OS_KIND" in
            debian)  pkg="nodejs npm" ;;
            fedora)  pkg="nodejs npm" ;;
            arch)    pkg="nodejs npm" ;;
            suse)    pkg="nodejs npm" ;;
            alpine)  pkg="nodejs npm" ;;
            brew)    pkg="node" ;;
            *)       pkg="" ;;
        esac
        if [ -n "$pkg" ]; then
            offer_install "Node.js ${REQUIRED_NODE_MAJOR}+" "$pkg" || return 0
        else
            warn "Node.js not found. Web frontend won't work without it."
            warn "  Install from https://nodejs.org/ or via your package manager."
            return 0
        fi
        recheck node || { warn "node still missing after install; skipping web"; return 0; }
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
    step "Installing Python dependencies (synpin-core)"
    python3 -m pip install --upgrade pip --quiet
    python3 -m pip install core/ --quiet
    ok "synpin-core installed"
}

install_web_deps() {
    if [ -d web/node_modules ]; then
        step "Web dependencies already installed (web/node_modules exists). Skipping."
        return
    fi
    if ! command -v npm >/dev/null 2>&1; then
        warn "npm not available - skipping web install. Run \`npm install\` in web/ manually."
        return
    fi
    step "Installing web dependencies (npm install in web/)"
    (cd web && npm install --no-fund --no-audit)
    ok "web/node_modules installed"

    # Build frontend for production
    if [ -d web/dist ]; then
        step "web/dist already exists - rebuilding..."
    fi
    step "Building web frontend (npm run build in web/)"
    (cd web && npm run build)
    ok "web/dist built"

    # Copy dist to ~/.synpin/web/dist/ for production
    step "Copying web/dist to ~/.synpin/web/dist/"
    mkdir -p "$HOME/.synpin/web"
    rm -rf "$HOME/.synpin/web/dist"
    cp -r web/dist "$HOME/.synpin/web/dist"
    ok "web/dist installed to ~/.synpin/web/dist/"
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

    # Ask to remove source repo (everything is in site-packages + ~/.synpin now)
    REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
    step "Installation complete. Source repo: $REPO_DIR"
    printf "
  Remove source repository? (the installed package doesn't need it) [y/N] "
    read -r answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
        step "Removing source repository..."
        rm -rf "$REPO_DIR"
        ok "Source repository removed."
    else
        ok "Source repository kept at $REPO_DIR"
    fi

    step "Done."
    ok "SynPin installed. Run \`synpin start\` or \`synpin dev\` to begin."
}

cmd_update() {
    step "Updating SynPin"
    if [ ! -d .git ]; then
        fail "Not a git repository - cannot update."
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