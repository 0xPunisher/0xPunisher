"""Shared helpers for the profile SVG generators.

Fonts (Space Grotesk, JetBrains Mono, both OFL) are downloaded once into
scripts/.fonts/, pinned from variable to static weights, subset to the exact
characters an SVG uses and embedded as base64 WOFF2 in @font-face rules.
"""

import base64
import io
import pathlib
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = ROOT / "scripts" / ".fonts"

FONT_URLS = {
    "SpaceGrotesk": "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf",
    "JetBrainsMono": "https://github.com/google/fonts/raw/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
}

# Palette
BG = "#0a0a0a"
LINE = "#1f1f1f"
TEXT = "#e8e8e8"
MUTED = "#7a7a7a"
ACCENT = "#e5383b"

MAX_BYTES = 150 * 1024

# Font stacks for the embedded families (prefixed so they never collide with local fonts)
CSS_MONO = ".mono{font-family:'PX Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;}"
CSS_TEXT = (
    f".value{{font-family:'PX Text','Space Grotesk',system-ui,sans-serif;font-weight:500;fill:{TEXT};}}"
)
CSS_COLORS = f".muted{{fill:{MUTED};}}.text{{fill:{TEXT};}}.accent{{fill:{ACCENT};}}"


def font_path(name):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.ttf"
    if not path.exists():
        urllib.request.urlretrieve(FONT_URLS[name], path)
    return path


_static_cache = {}


def static_font(name, weight):
    key = (name, weight)
    if key not in _static_cache:
        font = TTFont(font_path(name))
        _static_cache[key] = instancer.instantiateVariableFont(font, {"wght": weight})
    return _static_cache[key]


def text_width(name, weight, text, size, letter_spacing=0.0):
    font = static_font(name, weight)
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    upm = font["head"].unitsPerEm
    units = sum(hmtx[cmap[ord(ch)]][0] for ch in text)
    return units * size / upm + letter_spacing * len(text)


def cap_height(name, weight, size):
    font = static_font(name, weight)
    return font["OS/2"].sCapHeight * size / font["head"].unitsPerEm


def glyph_bounds(name, weight, ch, size):
    """(left side bearing, right edge of ink, advance) of one glyph, in px."""
    font = static_font(name, weight)
    glyf = font["glyf"]
    gname = font.getBestCmap()[ord(ch)]
    glyph = glyf[gname]
    glyph.recalcBounds(glyf)
    scale = size / font["head"].unitsPerEm
    advance = font["hmtx"][gname][0]
    return glyph.xMin * scale, glyph.xMax * scale, advance * scale


def woff2_base64(name, weight, chars):
    buf = io.BytesIO()
    static_font(name, weight).save(buf)
    buf.seek(0)
    font = TTFont(buf)
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["kern", "liga", "calt"]
    options.hinting = False
    options.desubroutinize = True
    options.name_IDs = []
    options.notdef_outline = True
    subsetter = subset.Subsetter(options)
    subsetter.populate(text="".join(sorted(set(chars))))
    subsetter.subset(font)
    out = io.BytesIO()
    font.flavor = "woff2"
    font.save(out)
    return base64.b64encode(out.getvalue()).decode("ascii")


def font_face(family, name, weight, chars):
    data = woff2_base64(name, weight, chars)
    return (
        f"@font-face{{font-family:'{family}';font-weight:{weight};"
        f"src:url(data:font/woff2;base64,{data}) format('woff2');}}"
    )


def write(filename, svg):
    path = ASSETS / filename
    path.write_text(svg, encoding="utf-8")
    size = path.stat().st_size
    assert size <= MAX_BYTES, f"{filename} is {size} bytes, over budget"
    print(f"{filename}: {size / 1024:.1f} KB")
