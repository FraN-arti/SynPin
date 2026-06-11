"""Shared Rich console with SynPin branding colors."""
from rich.console import Console
from rich.theme import Theme

# SynPin brand colors (from CSS variables)
# --green: #15f9a2, --orange: #f97316, --cyan: #22d3ee
# --text: #f1f5f9, --text-dim: #94a3b8

synpin_theme = Theme({
    "info": "cyan",
    "success": "#15f9a2",
    "warning": "#f97316",
    "error": "red",
    "brand": "bold #15f9a2",
    "accent": "bold #f97316",
    "dim": "#94a3b8",
    "muted": "#64748b",
})

console = Console(theme=synpin_theme)
