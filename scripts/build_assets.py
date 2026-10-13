#!/usr/bin/env python3
"""Build the static SVG assets for the GitHub profile README.

Fonts, palette and subsetting live in svgkit.py (shared with build_stats.py).

Usage:
    pip install fonttools brotli
    python3 scripts/build_assets.py
"""

from xml.sax.saxutils import escape

from svgkit import (
    ACCENT,
    ASSETS,
    BG,
    CSS_COLORS,
    CSS_MONO,
    CSS_TEXT,
    LINE,
    MUTED,
    TEXT,
    cap_height,
    font_face,
    glyph_bounds,
    text_width,
    write,
)


# ---------------------------------------------------------------- header

def build_header():
    W, H = 1000, 340
    PAD = 40

    top_left = "[ profile ]"
    top_center = "github.com/0xPunisher"
    top_right = "online"
    title_prefix = "0x"
    title_name = "Punisher"
    prompt = ">"
    tagline = " building bots that find the edge"
    columns = [
        ("(Role)", "Builder / Bot developer"),
        ("(Polymarket)", "Top 0.1% among arbitrage bots"),
        ("(Building)", "Creator of CrawlScan"),
    ]

    mono_chars = top_left + top_center + top_right + prompt + tagline + "".join(c[0] for c in columns)
    title_chars = title_name
    value_chars = "".join(c[1] for c in columns)

    css_fonts = (
        font_face("PX Mono", "JetBrainsMono", 400, mono_chars)
        + font_face("PX Mono", "JetBrainsMono", 700, title_prefix)
        + font_face("PX Display", "SpaceGrotesk", 700, title_chars)
        + font_face("PX Text", "SpaceGrotesk", 500, value_chars)
    )

    # Top row
    top_y = 42
    top_size = 13
    online_w = text_width("JetBrainsMono", 400, top_right, top_size)
    dot_cx = W - PAD - online_w - 12
    dot_cy = top_y - 4.5

    # Title: "0x" in JetBrains Mono (dotted zero, so it never reads as "Ox"),
    # "Punisher" in Space Grotesk Bold. Mono size is scaled so both cap heights
    # match on one baseline; letters are placed by their ink so the gaps look
    # like regular letter spacing.
    title_y = 156
    title_size = 76
    title_ls = -1.5
    prefix_size = title_size * cap_height("SpaceGrotesk", 700, 1) / cap_height("JetBrainsMono", 700, 1)
    ink_gap = 6
    zero_l, zero_r, _ = glyph_bounds("JetBrainsMono", 700, "0", prefix_size)
    x_l, x_r, _ = glyph_bounds("JetBrainsMono", 700, "x", prefix_size)
    p_l, _, _ = glyph_bounds("SpaceGrotesk", 700, "P", title_size)
    zero_x = PAD + 1 - zero_l
    x_x = zero_x + zero_r + ink_gap - x_l
    name_x = x_x + x_r + ink_gap - p_l

    # Tagline typing
    type_size = 18
    type_y = 206
    full = prompt + tagline
    type_w = text_width("JetBrainsMono", 400, full, type_size)
    n_chars = len(full)
    type_delay = 0.6
    type_dur = round(n_chars * 0.07, 2)
    char_w = type_w / n_chars

    # Columns
    col_w = (W - 2 * PAD) / 3
    label_size = 12
    value_size = 18
    for _, value in columns:
        vw = text_width("SpaceGrotesk", 500, value, value_size)
        assert vw < col_w - 24, f"column value too wide: {value} ({vw:.0f}px)"

    col_svg = []
    for i, (label, value) in enumerate(columns):
        x = PAD + i * col_w + (0 if i == 0 else 24)
        col_svg.append(
            f'<text class="mono muted" x="{x:.1f}" y="276" font-size="{label_size}">{escape(label)}</text>'
            f'<text class="value" x="{x:.1f}" y="304" font-size="{value_size}">{escape(value)}</text>'
        )
        if i > 0:
            lx = PAD + i * col_w
            col_svg.append(
                f'<line x1="{lx:.1f}" y1="262" x2="{lx:.1f}" y2="312" stroke="{LINE}" stroke-width="1"/>'
            )

    css = f"""{css_fonts}
{CSS_MONO}
.display{{font-family:'PX Display','Space Grotesk',system-ui,sans-serif;font-weight:700;}}
{CSS_TEXT}
{CSS_COLORS}
.scan{{animation:scan 6s linear infinite;}}
@keyframes scan{{0%{{transform:translateY(-40px);}}100%{{transform:translateY({H + 10}px);}}}}
.pulse{{transform-box:fill-box;transform-origin:center;animation:pulse 2.4s ease-out infinite;}}
@keyframes pulse{{0%{{transform:scale(1);opacity:.55;}}100%{{transform:scale(3.2);opacity:0;}}}}
.dot{{animation:breathe 2.4s ease-in-out infinite;}}
@keyframes breathe{{0%,100%{{opacity:1;}}50%{{opacity:.6;}}}}
.cover{{animation:type {type_dur}s steps({n_chars},end) {type_delay}s both;}}
.caret-move{{animation:type {type_dur}s steps({n_chars},end) {type_delay}s both;}}
@keyframes type{{from{{transform:translateX(0);}}to{{transform:translateX({type_w:.2f}px);}}}}
.caret{{animation:blink 1.2s ease-in-out {type_delay + type_dur}s infinite;}}
@keyframes blink{{0%,100%{{opacity:.85;}}50%{{opacity:0;}}}}
@media (prefers-reduced-motion:reduce){{
.scan,.pulse,.dot,.caret{{animation:none;}}
.pulse,.scan{{opacity:0;}}
.cover{{animation:none;display:none;}}
.caret-move{{animation:none;transform:translateX({type_w:.2f}px);}}
}}"""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">0xPunisher</title>
<desc id="d">Builder and bot developer. Top 0.1% among arbitrage bots on Polymarket. Creator of CrawlScan.</desc>
<defs>
<style>{css}</style>
<clipPath id="card"><rect x="0" y="0" width="{W}" height="{H}" rx="14"/></clipPath>
<linearGradient id="scanLine" x1="0" y1="0" x2="1" y2="0">
<stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/>
<stop offset=".5" stop-color="{ACCENT}" stop-opacity=".55"/>
<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/>
</linearGradient>
<linearGradient id="scanGlow" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/>
<stop offset="1" stop-color="{ACCENT}" stop-opacity=".06"/>
</linearGradient>
</defs>
<rect x="0" y="0" width="{W}" height="{H}" rx="14" fill="{BG}"/>
<g clip-path="url(#card)">
<text class="mono muted" x="{PAD}" y="{top_y}" font-size="{top_size}">{escape(top_left)}</text>
<text class="mono muted" x="{W / 2}" y="{top_y}" font-size="{top_size}" text-anchor="middle">{escape(top_center)}</text>
<text class="mono muted" x="{W - PAD}" y="{top_y}" font-size="{top_size}" text-anchor="end">{escape(top_right)}</text>
<circle class="pulse" cx="{dot_cx:.1f}" cy="{dot_cy}" r="3.5" fill="{ACCENT}"/>
<circle class="dot" cx="{dot_cx:.1f}" cy="{dot_cy}" r="3.5" fill="{ACCENT}"/>
<line x1="{PAD}" y1="66" x2="{W - PAD}" y2="66" stroke="{LINE}" stroke-width="1"/>
<text y="{title_y}"><tspan class="mono accent" x="{zero_x:.2f}" font-size="{prefix_size:.2f}" font-weight="700">0</tspan><tspan class="mono accent" x="{x_x:.2f}" font-size="{prefix_size:.2f}" font-weight="700">x</tspan><tspan class="display text" x="{name_x:.2f}" font-size="{title_size}" letter-spacing="{title_ls}">{escape(title_name)}</tspan></text>
<text class="mono" x="{PAD}" y="{type_y}" font-size="{type_size}" xml:space="preserve"><tspan class="accent">{escape(prompt)}</tspan><tspan class="text">{escape(tagline)}</tspan></text>
<rect class="cover" x="{PAD}" y="{type_y - 18}" width="{type_w + 4:.2f}" height="26" fill="{BG}"/>
<g class="caret-move"><rect class="caret" x="{PAD + 2}" y="{type_y - 15}" width="{char_w - 2:.2f}" height="19" fill="{TEXT}" opacity=".85"/></g>
<line x1="{PAD}" y1="244" x2="{W - PAD}" y2="244" stroke="{LINE}" stroke-width="1"/>
{"".join(col_svg)}
<g class="scan">
<rect x="0" y="-28" width="{W}" height="28" fill="url(#scanGlow)"/>
<rect x="0" y="0" width="{W}" height="1" fill="url(#scanLine)"/>
</g>
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="13.5" fill="none" stroke="{LINE}" stroke-width="1"/>
</svg>
"""
    write("header.svg", svg)


# --------------------------------------------------------------- buttons

ICON_X = (
    '<path fill="{color}" transform="translate({x} {y}) scale(.6667)" '
    'd="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835'
    'L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>'
)

ICON_GLOBE = (
    '<g fill="none" stroke="{color}" stroke-width="1.4" transform="translate({x} {y})">'
    '<circle cx="8" cy="8" r="7"/>'
    '<ellipse cx="8" cy="8" rx="3" ry="7"/>'
    '<path d="M1 8h14M2.2 4.3h11.6M2.2 11.7h11.6"/>'
    "</g>"
)


def build_button(filename, icon, label, aria):
    H = 44
    PAD_X = 20
    ICON = 16
    GAP = 10
    size = 14
    arrow = "↗"

    label_w = text_width("JetBrainsMono", 400, label, size)
    arrow_w = text_width("JetBrainsMono", 400, arrow, size)
    W = round(PAD_X + ICON + GAP + label_w + GAP + arrow_w + PAD_X)

    text_x = PAD_X + ICON + GAP
    arrow_x = text_x + label_w + GAP
    baseline = H / 2 + 5
    icon_svg = icon.format(color=TEXT, x=PAD_X, y=(H - ICON) / 2)

    css = (
        font_face("PX Mono", "JetBrainsMono", 400, label + arrow)
        + CSS_MONO
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{escape(aria)}">
<defs><style>{css}</style></defs>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="{(H - 1) / 2}" fill="{BG}" stroke="{LINE}" stroke-width="1"/>
{icon_svg}
<text class="mono" x="{text_x}" y="{baseline}" font-size="{size}" fill="{TEXT}">{escape(label)}</text>
<text class="mono" x="{arrow_x:.2f}" y="{baseline}" font-size="{size}" fill="{MUTED}">{arrow}</text>
</svg>
"""
    write(filename, svg)


def main():
    ASSETS.mkdir(exist_ok=True)
    build_header()
    build_button("btn-x.svg", ICON_X, "@0x_Punisher", "X: @0x_Punisher")
    build_button("btn-crawlscan.svg", ICON_GLOBE, "crawlscan.fun", "CrawlScan: crawlscan.fun")


if __name__ == "__main__":
    main()
