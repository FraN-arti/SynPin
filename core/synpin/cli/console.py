"""Shared Rich console with SynPin branding colors.

Color scheme matches the web app's --orange/--accent CSS variables
(--orange: #f97316, --accent: #f59e0b), so the CLI and the web
sidebar share the same brand identity. Use #f97316 for "info" and
the badge-y #f59e0b for "success" — they read as the same hue
family, just one warmer (amber) and one cooler (orange).
"""
import io
import sys
from rich.console import Console
from rich.theme import Theme

# SynPin CLI brand — orange/amber family, matching the web's CSS vars.
synpin_theme = Theme({
    "info":     "#f97316",   # --orange
    "success":  "#f59e0b",   # --accent (slightly warmer, reads as gold)
    "warning":  "#fbbf24",   # amber-400
    "error":    "red",
    "brand":    "bold #f97316",
    "accent":   "bold #f59e0b",
    "dim":      "#a8b5c4",   # sea-breeze slate: warm grey-blue, not cold
    "muted":    "#7a8a9c",   # slightly dimmer variant for secondary meta
})

# When launched from a Tauri cockpit (or any tool that captures stderr),
# three things go wrong on Windows:
#
#   1. Rich's default Console() switches to stdout when stderr is not a
#      TTY — so cockpit never sees the output.
#   2. Legacy Windows renderer crashes with OSError: [Errno 22] because
#      it tries Win32 console API on a pipe.
#   3. Windows uses cp1251 for piped stderr, which can't encode emojis
#      or Unicode — causing another OSError: [Errno 22].
#
# Fixes:
#   - Replace sys.stderr with a UTF-8 TextIOWrapper when encoding is not
#     UTF-8 (fixes #3).
#   - force_terminal=None lets Rich auto-detect TTY via isatty() —
#     colors in dev.bat (stderr is TTY), plain text in cockpit (pipe).
#   - legacy_windows=False skips Win32 console API entirely (#2).
#   - file=sys.stderr forces Rich to write to stderr, not stdout (#1).
#
# In a real terminal these are all no-ops — stderr is already UTF-8,
# is a TTY, and the legacy renderer works fine.
if not sys.stderr.encoding or sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console(
    theme=synpin_theme,
    file=sys.stderr,
    force_terminal=None,
    legacy_windows=False,
)
