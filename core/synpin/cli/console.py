"""Shared Rich console with SynPin branding colors.

Color scheme matches the web app's --orange/--accent CSS variables
(--orange: #f97316, --accent: #f59e0b), so the CLI and the web
sidebar share the same brand identity. Use #f97316 for "info" and
the badge-y #f59e0b for "success" — they read as the same hue
family, just one warmer (amber) and one cooler (orange).

The CORE / WEB prefixes use the same code as the dev script
(see synpin.cli.dev): success-styled green for Core, info-styled
cyan for Web. The banner itself is bold-orange to look "live".
"""
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
    "dim":      "#94a3b8",
    "muted":    "#64748b",
})

console = Console(theme=synpin_theme)
