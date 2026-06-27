#!/usr/bin/env bash
# SynPin brand colors for shell scripts (ANSI 24-bit escape codes).
#
# Mirrors core/synpin/cli/console.py:synpin_theme exactly. PowerShell
# 5.1 can't use hex codes in Write-Host, so it has to use named
# approximations (see colors.ps1). Bash can do true 24-bit color via
# ANSI escapes on any modern terminal (gnome-terminal, iTerm2,
# Windows Terminal + WSL, etc.).
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/colors.sh"
#   echo -e "${SP_BRAND}SynPin v0.5.1.42${SP_RESET}"
#
# Disable colors when:
#   - stdout is not a TTY (piped output, captured by a tool)
#   - NO_COLOR is set (https://no-color.org convention)
#
# Keep this in sync with core/synpin/cli/console.py:synpin_theme.

if [ ! -t 1 ] || [ -n "${NO_COLOR:-}" ]; then
    # No TTY or user requested no color — define empty strings.
    SP_BRAND=""
    SP_ACCENT=""
    SP_INFO=""
    SP_OK=""
    SP_WARN=""
    SP_FAIL=""
    SP_DIM=""
    SP_PATH=""
    SP_RESET=""
else
    # 24-bit ANSI escape codes. Format: \033[38;2;R;G;Bm
    SP_BRAND='\033[38;2;249;115;22m'     # #f97316 --orange
    SP_ACCENT='\033[38;2;245;158;11m'    # #f59e0b --accent
    SP_INFO='\033[38;2;249;115;22m'      # alias for brand
    SP_OK='\033[38;2;34;197;94m'          # green for success
    SP_WARN='\033[38;2;251;191;36m'       # amber-400
    SP_FAIL='\033[38;2;239;68;68m'        # red
    SP_DIM='\033[38;2;122;138;156m'      # muted slate
    SP_PATH='\033[38;2;168;181;196m'     # sea-breeze slate
    SP_RESET='\033[0m'
fi

# Helper that prints a message with a brand label and dim text,
# matching the look of synpin cli output:
#   sp_labeled "OK" "synpin-core installed"
sp_labeled() {
    local label="$1"; shift
    local color="$1"; shift
    local msg="$*"
    printf "%b[%s]%b %s\n" "$color" "$label" "$SP_RESET" "$msg"
}

sp_step()  { printf "\n%b==>%b %s\n" "$SP_BRAND" "$SP_RESET" "$*"; }
sp_ok()    { sp_labeled "OK"   "$SP_OK"   "$*"; }
sp_warn()  { sp_labeled "WARN" "$SP_WARN" "$*"; }
sp_fail()  { sp_labeled "FAIL" "$SP_FAIL" "$*" >&2; }
