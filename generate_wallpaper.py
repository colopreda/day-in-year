#!/usr/bin/env python3
"""
Year Progress Wallpaper — iPhone 16 Pro
Generates a minimalist black wallpaper showing days of the year.
- River Plate match days (next 60d) show the River logo
- Argentina national team match days (next 60d) show the AFA logo
"""

import os
import re
import math
import io
import numpy as np
import requests
import cairosvg
from PIL import Image, ImageDraw, ImageFont, ImageOps
from datetime import date, timezone, datetime, timedelta

# ── Config ───────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# En GitHub Actions guarda en el repo; localmente guarda en iCloud
if os.environ.get("GITHUB_ACTIONS"):
    OUTPUT = os.path.join(SCRIPT_DIR, "wallpaper.png")
else:
    ICLOUD = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs")
    OUTPUT = os.path.join(ICLOUD, "year_wallpaper.png")

W, H  = 1206, 2622   # iPhone 16 Pro resolution
COLS  = 15
DOT_R = 25
GAP   = 11

# Colors
BG         = (0, 0, 0)
PAST       = (220, 220, 220)
FUTURE     = (32, 32, 32)
TODAY_FILL = (210, 45, 45)    # rojo
MATCH_LOGO = (210, 45, 45)    # rojo para logos de equipos
TEXT_YEAR  = (80, 80, 80)
TEXT_INFO  = (100, 100, 100)

# Font paths: macOS first, then common Linux locations
FONT_CANDIDATES = [
    "/System/Library/Fonts/HelveticaNeue.ttc",                          # macOS
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Ubuntu/Debian
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",                  # Ubuntu/Debian fallback
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",           # Fedora/RHEL
]
FONT_PATH = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)

# Teams config: (espn_url, svg_logo_url, cache_filename)
TEAMS = {
    "river": (
        "https://www.espn.com/soccer/team/fixtures/_/id/16/river-plate",
        "https://upload.wikimedia.org/wikipedia/commons/4/43/Club_Atl%C3%A9tico_River_Plate_logo.svg",
        "river_logo_cache.png",
    ),
    "argentina": (
        "https://www.espn.com/soccer/team/fixtures/_/id/202/arg",
        os.path.join(SCRIPT_DIR, "afa.svg"),
        "argentina_logo_cache.png",
    ),
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def load_font(size):
    if FONT_PATH:
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except Exception:
            pass
    return ImageFont.load_default(size=size)

def centered_text(draw, y, text, font, color):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, fill=color, font=font)

# ── Match days scraper ────────────────────────────────────────────────────────
def get_match_days(team_name, espn_url, year, days_limit=None):
    """
    Scrapes ESPN fixtures page and returns a set of day-of-year ints
    for confirmed future matches. If days_limit is set, only includes
    matches within that many days from today.
    """
    try:
        resp = requests.get(espn_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        print(f"  ⚠ No se pudo obtener calendario de {team_name}: {e}")
        return set()

    pattern = r'"date":"(20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}Z)","tbd":(true|false)'
    matches = re.findall(pattern, resp.text)

    match_days = set()
    tz_arg   = timezone(timedelta(hours=-3))
    today_dt = datetime.now(tz_arg)
    cutoff   = today_dt + timedelta(days=days_limit) if days_limit else None

    for date_str, tbd in matches:
        if tbd == "true":
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            dt_arg = dt.astimezone(tz_arg)
            if dt_arg.year == year and dt_arg >= today_dt:
                if cutoff is None or dt_arg <= cutoff:
                    match_days.add(dt_arg.timetuple().tm_yday)
        except Exception:
            continue

    limit_str = f"próx. {days_limit} días" if days_limit else "todo el año"
    print(f"  ⚽ {team_name} — partidos confirmados ({limit_str}): {sorted(match_days)}")
    return match_days

# ── Logo loader ───────────────────────────────────────────────────────────────
def tint_logo(logo, color):
    """Returns a copy of the logo tinted with the given RGB color."""
    _, _, _, a = logo.split()
    gray = ImageOps.grayscale(logo.convert("RGB"))
    mask = ImageOps.invert(gray)
    combined = (np.array(mask, dtype=np.float32) / 255.0 *
                np.array(a,    dtype=np.float32) / 255.0 * 255).astype(np.uint8)
    r, g, b = color
    solid = Image.new("RGBA", logo.size, (r, g, b, 255))
    solid.putalpha(Image.fromarray(combined))
    return solid

def get_logo(team_name, svg_url, cache_file, size):
    """Downloads an SVG logo, returns two PIL RGBA Images: (future_tint, today_tint)."""
    dot_d      = size * 2
    cache_path = os.path.join(SCRIPT_DIR, cache_file)

    if os.path.exists(cache_path):
        logo = Image.open(cache_path).convert("RGBA")
    else:
        try:
            if os.path.exists(svg_url):
                # Local file
                with open(svg_url, "rb") as f:
                    src = f.read()
            else:
                resp = requests.get(svg_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                src = resp.content

            if svg_url.endswith(".svg"):
                png_bytes = cairosvg.svg2png(bytestring=src, output_width=dot_d, output_height=dot_d)
                logo = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            else:
                logo = Image.open(io.BytesIO(src)).convert("RGBA")
            logo.save(cache_path)
        except Exception as e:
            print(f"  ⚠ No se pudo cargar el logo de {team_name}: {e}")
            return None, None

    logo = logo.resize((dot_d, dot_d), Image.LANCZOS)
    return tint_logo(logo, FUTURE), tint_logo(logo, MATCH_LOGO)

# ── Main ──────────────────────────────────────────────────────────────────────
def generate():
    today = date.today()
    year  = today.year
    doy   = today.timetuple().tm_yday
    total = 366 if is_leap(year) else 365
    pct   = doy / total * 100

    espn_river, svg_river, cache_river       = TEAMS["river"]
    espn_arg,   svg_arg,   cache_arg         = TEAMS["argentina"]

    river_days = get_match_days("River Plate", espn_river, year, days_limit=60)
    arg_days   = get_match_days("Argentina",   espn_arg,   year)

    river_logo, river_logo_today = get_logo("River Plate", svg_river, cache_river, DOT_R) if river_days else (None, None)
    arg_logo,   arg_logo_today   = get_logo("Argentina",   svg_arg,   cache_arg,   DOT_R) if arg_days   else (None, None)

    step   = DOT_R * 2 + GAP
    rows   = math.ceil(total / COLS)
    grid_w = COLS * step - GAP
    grid_h = rows * step - GAP

    x0 = (W - grid_w) // 2   # = 151px margin each side
    y0 = 693                  # matches reference top margin exactly

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    for i in range(total):
        col = i % COLS
        row = i // COLS
        cx  = x0 + col * step + DOT_R
        cy  = y0 + row * step + DOT_R
        day = i + 1
        lx, ly = cx - DOT_R, cy - DOT_R

        if day < doy:
            draw.ellipse([cx-DOT_R, cy-DOT_R, cx+DOT_R, cy+DOT_R], fill=PAST)
        elif day == doy:
            if day in river_days and river_logo_today:
                img.paste(river_logo_today, (lx, ly), river_logo_today)
            elif day in arg_days and arg_logo_today:
                img.paste(arg_logo_today, (lx, ly), arg_logo_today)
            else:
                draw.ellipse([cx-DOT_R, cy-DOT_R, cx+DOT_R, cy+DOT_R], fill=TODAY_FILL)
        elif day in river_days and river_logo:
            img.paste(river_logo, (lx, ly), river_logo)
        elif day in arg_days and arg_logo:
            img.paste(arg_logo, (lx, ly), arg_logo)
        else:
            draw.ellipse([cx-DOT_R, cy-DOT_R, cx+DOT_R, cy+DOT_R], fill=FUTURE)

    font_info = load_font(44)
    info = f"Día {doy} de {total}  ·  {total - doy} restantes  ·  {pct:.1f}%"
    centered_text(draw, y0 + grid_h + 30, info, font_info, TEXT_INFO)

    img.save(OUTPUT, "PNG")
    print(f"✓ Guardado en iCloud Drive: {OUTPUT}")
    print(f"  {year} — Día {doy}/{total} ({pct:.1f}%)")

if __name__ == "__main__":
    generate()
