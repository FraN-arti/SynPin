"""TweakCN theme import and management API."""
import re
import json
import httpx
from pathlib import Path
from colorsys import rgb_to_hls, hls_to_rgb
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/themes", tags=["themes"])

# --- Storage ---
_themes_dir = Path.home() / ".synpin" / "themes"
_themes_dir.mkdir(parents=True, exist_ok=True)
_custom_themes_file = _themes_dir / "custom.json"


def _load_custom_themes() -> dict:
    if _custom_themes_file.exists():
        return json.loads(_custom_themes_file.read_text(encoding="utf-8"))
    return {}


def _save_custom_themes(themes: dict):
    _custom_themes_file.write_text(
        json.dumps(themes, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# --- Color helpers ---

import re as _re

def _parse_css_color(color: str) -> str:
    """Parse any CSS color format and return hex (#rrggbb).

    Supports: #hex, rgb(), rgba(), hsl(), hsla(), oklch(), oklab(), named colors.
    """
    if not color or not isinstance(color, str):
        return "#888888"

    color = color.strip()

    # Already hex
    if color.startswith("#"):
        h = color.lstrip("#")
        if len(h) == 3:
            h = h[0]*2 + h[1]*2 + h[2]*2
        if len(h) == 6 and all(c in "0123456789abcdefABCDEF" for c in h):
            return f"#{h.lower()}"
        return "#888888"

    # oklch(L C H) or oklch(L C H / A)
    m = _re.match(r"oklch\s*\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)", color, _re.IGNORECASE)
    if m:
        L, C, H = float(m.group(1)), float(m.group(2)), float(m.group(3))
        return _oklch_to_hex(L, C, H)

    # oklab(L a b)
    m = _re.match(r"oklab\s*\(\s*([\d.]+)\s+([\d.-]+)\s+([\d.-]+)", color, _re.IGNORECASE)
    if m:
        L, a, b = float(m.group(1)), float(m.group(2)), float(m.group(3))
        return _oklab_to_hex(L, a, b)

    # rgb(r g b) or rgb(r, g, b) or rgba(r, g, b, a)
    m = _re.match(r"rgba?\s*\(\s*([\d.]+)\s*[,/]\s*([\d.]+)\s*[,/]\s*([\d.]+)", color, _re.IGNORECASE)
    if m:
        r, g, b = int(float(m.group(1))), int(float(m.group(2))), int(float(m.group(3)))
        return f"#{r:02x}{g:02x}{b:02x}"

    # hsl(h s% l%) or hsl(h, s%, l%) or hsla(...)
    m = _re.match(r"hsla?\s*\(\s*([\d.]+)\s*[,/]\s*([\d.]+)%?\s*[,/]\s*([\d.]+)%?", color, _re.IGNORECASE)
    if m:
        h, s, l = float(m.group(1)), float(m.group(2)), float(m.group(3))
        return _hsl_to_hex(h, s / 100, l / 100)

    # Named colors fallback
    named = {
        "white": "#ffffff", "black": "#000000", "red": "#ff0000",
        "green": "#008000", "blue": "#0000ff", "yellow": "#ffff00",
        "orange": "#ffa500", "purple": "#800080", "gray": "#808080",
        "grey": "#808080", "transparent": "#000000",
    }
    if color.lower() in named:
        return named[color.lower()]

    return "#888888"


def _oklch_to_hex(L: float, C: float, H: float) -> str:
    """Convert OKLCH to hex via OKLab -> linear sRGB."""
    h_rad = H * 3.14159265 / 180
    a = C * max(0, 1e-6) * max(0, 1e-6)  # ensure non-negative for cos
    import math
    a = C * math.cos(h_rad)
    b = C * math.sin(h_rad)
    return _oklab_to_hex(L, a, b)


def _oklab_to_hex(L: float, a: float, b: float) -> str:
    """Convert OKLab to hex via linear sRGB."""
    import math
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b

    l = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3

    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    # Linear to sRGB
    def to_srgb(x):
        x = max(0, min(1, x))
        return int(round(255 * (12.92 * x if x <= 0.0031308 else 1.055 * x ** (1/2.4) - 0.055)))

    return f"#{to_srgb(r):02x}{to_srgb(g):02x}{to_srgb(bl):02x}"


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    """Convert HSL (h 0-360, s 0-1, l 0-1) to hex."""
    def hue2rgb(p, q, t):
        if t < 0: t += 1
        if t > 1: t -= 1
        if t < 1/6: return p + (q - p) * 6 * t
        if t < 1/2: return q
        if t < 2/3: return p + (q - p) * (2/3 - t) * 6
        return p

    if s == 0:
        r = g = b = l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue2rgb(p, q, h/360 + 1/3)
        g = hue2rgb(p, q, h/360)
        b = hue2rgb(p, q, h/360 - 1/3)

    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = _parse_css_color(h if h.startswith("#") else f"#{h}").lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _darken(hex_color: str, amount: float = 0.15) -> str:
    """Darken a hex color by amount (0-1)."""
    r, g, b = _hex_to_rgb(hex_color)
    r = max(0, int(r * (1 - amount)))
    g = max(0, int(g * (1 - amount)))
    b = max(0, int(b * (1 - amount)))
    return _rgb_to_hex(r, g, b)


def _lighten(hex_color: str, amount: float = 0.15) -> str:
    """Lighten a hex color by amount (0-1)."""
    r, g, b = _hex_to_rgb(hex_color)
    r = min(255, int(r + (255 - r) * amount))
    g = min(255, int(g + (255 - g) * amount))
    b = min(255, int(b + (255 - b) * amount))
    return _rgb_to_hex(r, g, b)


def _with_alpha(hex_color: str, alpha: float) -> str:
    """Convert hex color to rgba with alpha."""
    r, g, b = _hex_to_rgb(hex_color)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _interpolate_color(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two hex colors (t=0→c1, t=1→c2)."""
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return _rgb_to_hex(r, g, b)


def _rem_to_px(rem_str: str) -> str:
    """Convert rem string like '1.4rem' to px string like '22px'."""
    try:
        val = float(rem_str.replace("rem", "").strip())
        return f"{round(val * 16)}px"
    except (ValueError, AttributeError):
        return "2px"  # SynPin default


# --- TweakCN parsing ---

async def _fetch_tweakcn_theme(url: str) -> dict:
    """Fetch and parse a TweakCN theme from its share URL."""
    if not re.match(r"https?://tweakcn\.com/themes/[a-zA-Z0-9]+", url):
        raise HTTPException(status_code=400, detail="Invalid TweakCN URL format")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"TweakCN returned {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch: {str(e)}")

    html = resp.text

    name_match = re.search(r'"name":"([^"]+)"', html)
    theme_name = name_match.group(1) if name_match else "Custom Theme"

    light_match = re.search(r'"light":\s*\{[^}]+\}', html)
    dark_match = re.search(r'"dark":\s*\{[^}]+\}', html)

    if not light_match or not dark_match:
        light_match = re.search(r'light\\\\?":\s*\\?\{[^}]+\}', html)
        dark_match = re.search(r'dark\\\\?":\s*\\?\{[^}]+\}', html)

    if not light_match or not dark_match:
        raise HTTPException(status_code=422, detail="Could not parse theme styles from page")

    def _parse_styles(raw: str) -> dict:
        s = raw.strip()
        s = s.replace('\\"', '"').replace('\\\\', '\\')
        if not s.startswith('{'):
            s = '{' + s
        if not s.endswith('}'):
            s = s + '}'
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pairs = {}
            for m in re.finditer(r'"([^"]+)":\s*"([^"]+)"', s):
                pairs[m.group(1)] = m.group(2)
            return pairs

    light_styles = _parse_styles(light_match.group())
    dark_styles = _parse_styles(dark_match.group())

    theme_id_match = re.search(r"/themes/([a-zA-Z0-9]+)", url)
    theme_id = theme_id_match.group(1) if theme_id_match else "unknown"

    return {
        "id": theme_id,
        "name": theme_name,
        "source_url": url,
        "styles": {
            "light": light_styles,
            "dark": dark_styles,
        }
    }


# --- Mapping: TweakCN → SynPin CSS variables ---

def _map_to_synpin_vars(tweakcn: dict) -> dict:
    """
    Map TweakCN/shadcn CSS variables to SynPin variable format.
    SynPin uses: --orange, --orange-hover, --orange-muted,
    --black, --white, --gray-950..--gray-300, --radius
    """
    mapped = {}

    # --- Primary accent ---
    primary = tweakcn.get("primary", "#f97316")
    mapped["--orange"] = primary
    mapped["--orange-hover"] = _darken(primary, 0.15)
    mapped["--orange-muted"] = _with_alpha(primary, 0.1)

    # --- Backgrounds ---
    bg = tweakcn.get("background", "#0a0a0a")
    mapped["--black"] = bg
    mapped["--gray-950"] = bg

    # --- Text ---
    fg = tweakcn.get("foreground", "#f0f0f0")
    mapped["--white"] = fg

    # --- Card / sidebar background ---
    card = tweakcn.get("card", tweakcn.get("sidebar", bg))
    mapped["--gray-900"] = card

    # --- Borders / input ---
    border = tweakcn.get("border", "#262626")
    inp = tweakcn.get("input", border)
    mapped["--gray-800"] = inp

    # --- Secondary bg ---
    secondary = tweakcn.get("secondary", tweakcn.get("muted", border))
    mapped["--gray-700"] = secondary

    # --- Muted foreground (subtle text) ---
    muted_fg = tweakcn.get("muted-foreground", "#969696")
    mapped["--gray-600"] = muted_fg

    # --- Interpolate grays between gray-600 (subtle text) and gray-950 (bg) ---
    # gray-500 = slightly lighter than gray-600
    mapped["--gray-500"] = _interpolate_color(muted_fg, fg, 0.2)
    # gray-400 = more towards fg
    mapped["--gray-400"] = _interpolate_color(muted_fg, fg, 0.45)
    # gray-300 = close to fg but not quite
    mapped["--gray-300"] = _interpolate_color(muted_fg, fg, 0.7)

    # --- Radius ---
    radius_raw = tweakcn.get("radius", "0.625rem")
    mapped["--radius"] = _rem_to_px(radius_raw)

    # --- Shadow (SynPin doesn't use CSS vars for shadows yet, but store for future) ---
    shadow_color = tweakcn.get("shadow-color", "oklch(0 0 0)")
    shadow_opacity = tweakcn.get("shadow-opacity", "0.1")
    shadow_blur = tweakcn.get("shadow-blur", "3px")
    shadow_spread = tweakcn.get("shadow-spread", "0px")
    shadow_oy = tweakcn.get("shadow-offset-y", "1px")
    shadow_ox = tweakcn.get("shadow-offset-x", "0")

    # Build a CSS shadow string from TweakCN params
    mapped["--shadow"] = f"{shadow_ox} {shadow_oy} {shadow_blur} {shadow_spread} rgba(0, 0, 0, {shadow_opacity})"

    return mapped


# --- API Endpoints ---

class ThemeImportRequest(BaseModel):
    url: str


class ThemeSaveRequest(BaseModel):
    id: str
    name: str
    url: str
    light: dict
    dark: dict
    raw: dict | None = None  # Keep original TweakCN styles


@router.post("/tweakcn/import")
async def import_tweakcn_theme(req: ThemeImportRequest):
    """Fetch and parse a TweakCN theme, return mapped SynPin variables."""
    theme_data = await _fetch_tweakcn_theme(req.url)

    light_mapped = _map_to_synpin_vars(theme_data["styles"]["light"])
    dark_mapped = _map_to_synpin_vars(theme_data["styles"]["dark"])

    return {
        "id": theme_data["id"],
        "name": theme_data["name"],
        "source_url": theme_data["source_url"],
        "light": light_mapped,
        "dark": dark_mapped,
        "raw": theme_data["styles"],
    }


@router.post("/tweakcn/save")
async def save_tweakcn_theme(req: ThemeSaveRequest):
    """Save a TweakCN theme for later use."""
    themes = _load_custom_themes()
    themes[req.id] = {
        "name": req.name,
        "source_url": req.url,
        "light": req.light,
        "dark": req.dark,
    }
    if req.raw:
        themes[req.id]["raw"] = req.raw
    _save_custom_themes(themes)
    return {"status": "ok", "id": req.id}


@router.get("/tweakcn/list")
async def list_tweakcn_themes():
    """List all saved TweakCN themes. 'current' always first."""
    themes = _load_custom_themes()
    result = []
    # "current" always first
    if "current" in themes:
        result.append({"id": "current", **themes["current"]})
    for k, v in themes.items():
        if k != "current":
            result.append({"id": k, **v})
    return {"themes": result}


@router.delete("/tweakcn/{theme_id}")
async def delete_tweakcn_theme(theme_id: str):
    """Delete a saved TweakCN theme."""
    themes = _load_custom_themes()
    if theme_id in themes:
        del themes[theme_id]
        _save_custom_themes(themes)
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Theme not found")
