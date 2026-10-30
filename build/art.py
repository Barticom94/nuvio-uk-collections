"""Renders the Modern home art that nuvio-collections.json points at.

  python build/art.py [--sheet]   writes covers/tiles/*.webp (a landscape tile per card) and covers/logos/*.png (a
                                  title logo per folder); --sheet also writes build/contact-sheet.png for review (not
                                  committed)

build_uk.py runs it after writing the file. Two kinds of art, all our own:
- The cards of Movies, TV Shows and Anime: illustrated tiles and title logos drawn here as SVG and rendered to PNG by
  headless Edge (or Chrome: EDGE=path picks the browser), then saved as WebP (tiles) or PNG (logos). Each type has its
  own look: Movies is cinema (velvet red, brass, film strip), TV Shows is broadcast (petrol blue, scan lines,
  test-card bars), Anime is manga pop (bright skies, ink outlines, halftone, speed lines). Each card has its own
  motif: New and Trending rises (a film strip arrow, a transmitter's signal with an on-air flame, a flame), Top Rated
  a star (in a laurel, on a CRT set, a rosette), Genres a mosaic of genre glyphs (tiles, a video wall, manga panels),
  Decades the decades (a film strip, a TV set per decade, a timeline), Collections a box set and a reel, and
  Showcase an IMAX-shaped screen whose sun blooms past its frame. The glyphs are drawn here too.
- Streaming Services' title logos: the service name in white with a soft shadow (Pillow); its tiles are the services'
  covers.
Logos sit on a transparent canvas with the aspect of the hero's logo slot (ModernHomeHero: 100dp high, up to 220dp
wide, ContentScale.Fit, aligned CenterStart), so every logo shows at the same scale. The font is Outfit, under the SIL
Open Font License 1.1 (build/fonts/OFL.txt), embedded in each page the browser renders.
"""
import base64, concurrent.futures as cf, json, math, os, random, re, shutil, subprocess, sys, tempfile, urllib.request
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT = os.path.join(HERE, "fonts", "Outfit.ttf")
TILE = (960, 540)   # Modern's landscape tiles are 1.77:1; Coil scales down, never up
LOGO = (660, 300)   # the logo slot at 3 px per dp (Coil asks for 2 px per dp on a 1080p TV)
OWN = re.compile(r"/covers/((?:tiles|logos)/[a-z0-9-]+\.(?:webp|png))$")
STYLE = {"Movies": "movies", "TV Shows": "tv", "Anime": "anime"}
LABEL = {"movies": "MOVIES", "tv": "TV", "anime": "ANIME"}


def font(size, weight):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_axes([weight])
    return f

def wrap(text, f, width):
    """Greedy word wrap; None when a single word is wider than the box."""
    lines = []
    for word in text.split():
        if f.getlength(word) > width: return None
        if lines and f.getlength(lines[-1] + " " + word) <= width: lines[-1] += " " + word
        else: lines.append(word)
    return lines

def fit(text, width, sizes, max_lines, weight=700):
    """(font, lines) for the first size (from sizes) whose wrap takes at most max_lines lines, else None."""
    for size in sizes:
        f = font(size, weight)
        lines = wrap(text, f, width)
        if lines and len(lines) <= max_lines: return f, lines
    return None


# ---------- Streaming Services' logos (Pillow) ----------

def logo(name):
    w, h = LOGO
    # One line when it fits at 96 px or more, else two at 86 px at most, so a two line logo doesn't outweigh a short
    # one; a 24 px margin keeps the soft shadow inside the canvas
    f, lines = (fit(name, w - 48, range(114, 95, -2), 1) or fit(name, w - 48, range(86, 65, -4), 2)
                or sys.exit(f"art: logo {name!r} does not fit"))
    step = round(f.size * 1.02)
    cap = f.getbbox("H", anchor="ls")[1] * -1  # cap height, so every logo sits on the same baseline grid
    y = (h - cap - step * (len(lines) - 1)) / 2 + cap
    text = Image.new("L", LOGO, 0)
    for i, line in enumerate(lines):
        ImageDraw.Draw(text).text((24, y + i * step), line, font=f, fill=255, anchor="ls")
    # Two shadows: a soft drop shadow that darkens a bright backdrop under the words and a tight one that edges them
    soft = ImageChops.offset(text, 0, 5).filter(ImageFilter.GaussianBlur(11)).point(lambda v: min(255, v * 2) * 150 // 255)
    edge = text.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.5)).point(lambda v: v * 190 // 255)
    # White where the letters are, black in the shadows
    out = Image.composite(Image.new("RGB", LOGO, (255, 255, 255)), Image.new("RGB", LOGO, (0, 0, 0)), text).convert("RGBA")
    out.putalpha(ImageChops.lighter(ImageChops.lighter(soft, edge), text))
    return out


# ---------- the cards' art (SVG) ----------

INK = "#1b1035"
IVORY = "#fff5e1"
GOLD = '<stop offset="0" stop-color="#fff1c4"/><stop offset=".45" stop-color="#f5c451"/><stop offset="1" stop-color="#b9771b"/>'
AQUA, CORAL, AMBER, CREAM = "#5fe6d6", "#ff6a45", "#ffc24f", "#efe6d3"
BARS = ["#ececec", "#e8cf3b", "#40cbd5", "#4ec45e", "#cb5cba", "#e6483c", "#3c61d6"]  # a test card's colour bars
PINK, YELLOW, CYAN = "#ff4f9a", "#ffd84a", "#55d6ff"

# Glyphs on a 24 unit grid, drawn as strokes
GLYPHS = {
    "bolt": '<path d="M13 2.5 5 13.5h6.5l-1 8 8.5-11.5H12.5z"/>',
    "heart": '<path d="M12 20.5s-7.5-4.6-7.5-10.3A4.2 4.2 0 0 1 12 7.6a4.2 4.2 0 0 1 7.5 2.6c0 5.7-7.5 10.3-7.5 10.3z"/>',
    "ghost": '<path d="M5.5 20.5V11a6.5 6.5 0 0 1 13 0v9.5l-2.2-1.6-2.2 1.6-2.1-1.6-2.1 1.6-2.2-1.6z"/>'
             '<path d="M9.6 10.6v1.2M14.4 10.6v1.2"/>',
    "rocket": '<path d="M12 2.5c3.3 2.4 4.8 6.2 4.8 10v4.3H7.2v-4.3c0-3.8 1.5-7.6 4.8-10z"/><circle cx="12" cy="10" r="1.8"/>'
              '<path d="M7.2 12.8 4.5 15.6v3.4h2.7M16.8 12.8l2.7 2.8v3.4h-2.7M10.2 19.8 12 21.6l1.8-1.8"/>',
    "mask": '<circle cx="12" cy="12" r="8.5"/><path d="M8 13.6a4.5 4.5 0 0 0 8 0M8.4 9.6h2.2M13.4 9.6h2.2"/>',
    "magnifier": '<circle cx="10.5" cy="10.5" r="6"/><path d="M15 15l5.5 5.5"/>',
    "crown": '<path d="M4.2 17.5 3 7.8l5 4 4-6.3 4 6.3 5-4-1.2 9.7z"/><path d="M4.5 20.5h15"/>',
    "note": '<path d="M9 17.5V5.5l10.5-2v12"/><circle cx="6.5" cy="17.5" r="2.5"/><circle cx="17" cy="15.5" r="2.5"/>',
    "cactus": '<path d="M10 20.5V5a2 2 0 0 1 4 0v15.5M10 13H7.5a2 2 0 0 1-2-2V8.5M14 10.5h2.5a2 2 0 0 0 2-2V6.5M5 20.5h14"/>',
    "house": '<path d="M4 11 12 4l8 7v8.5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z"/><path d="M10 20.5V15h4v5.5"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    "hourglass": '<path d="M6.5 3.5h11M6.5 20.5h11M8 3.5c0 4.5 8 5 8 8.5s-8 4-8 8.5M16 3.5c0 4.5-8 5-8 8.5s8 4 8 8.5"/>',
    "couch": '<path d="M5 11V8.5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2V11"/>'
             '<path d="M3 12a1.5 1.5 0 0 1 3 0v2.5h12V12a1.5 1.5 0 0 1 3 0v5.5H3zM5 17.5v2M19 17.5v2"/>',
    "cross": '<path d="M9.5 3.5h5v6h6v5h-6v6h-5v-6h-6v-5h6z"/>',
    "scales": '<path d="M12 3.5v17M8 20.5h8M5 6.5h14M5 6.5 2.5 13h5zM19 6.5 16.5 13h5zM2.5 13a2.5 2.5 0 0 0 5 0M16.5 13a2.5 2.5 0 0 0 5 0"/>',
    "fingerprint": '<path d="M6.5 18.5C5.5 16.5 5 14.4 5 12a7 7 0 0 1 14 0v1M9.2 20.5c-.8-2.4-1.2-5-1.2-8.5a4 4 0 0 1 8 0'
                   'c0 3.4-.3 5.8-1 8M12 12c0 3.6.4 6.2 1 8.5M19 16.5c-.2 1.3-.5 2.6-.9 3.6"/>',
    "camera": '<rect x="2.5" y="7" width="13" height="10" rx="2"/><path d="M15.5 10.5l6-3.5v10l-6-3.5"/>',
    "shield": '<path d="M12 3l7.5 3v5.5c0 4.8-3.2 8.3-7.5 9.5-4.3-1.2-7.5-4.7-7.5-9.5V6z"/><path d="M12.8 7.5l-3.3 5h3l-1 4.2 3.5-5.2h-3z"/>',
    "sword": '<path d="M20.5 3.5l-1 4.2L10 17.2 6.8 14l9.5-9.5zM5.5 12.5l6 6M7.4 16.6 4 20"/>',
    "robot": '<rect x="5" y="8" width="14" height="11" rx="2.5"/><path d="M12 8V5.2M3 12v3.5M21 12v3.5M9.5 16h5"/>'
             '<circle cx="12" cy="4.2" r="1.1"/><circle cx="9.5" cy="12.6" r="1.2"/><circle cx="14.5" cy="12.6" r="1.2"/>',
    "ball": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5v17M6 6c2.6 2.6 2.6 9.4 0 12M18 6c-2.6 2.6-2.6 9.4 0 12"/>',
}

def glyph(name, x, y, size, color, width=2, under=None):
    """A glyph centred on (x, y), size px across; `under` = (colour, extra width) strokes an outline beneath it."""
    tf = f'transform="translate({x - size / 2:.1f},{y - size / 2:.1f}) scale({size / 24:.3f})"'
    common = 'fill="none" stroke-linecap="round" stroke-linejoin="round"'
    out = f'<g {tf} {common} stroke="{under[0]}" stroke-width="{width + under[1]}">{GLYPHS[name]}</g>' if under else ""
    return out + f'<g {tf} {common} stroke="{color}" stroke-width="{width}">{GLYPHS[name]}</g>'

def esc(t): return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def star(cx, cy, R, r, n=5, rot=-90):
    pts = []
    for i in range(2 * n):
        a = math.radians(rot + i * 180 / n)
        rr = R if i % 2 == 0 else r
        pts.append(f"{cx + rr * math.cos(a):.1f},{cy + rr * math.sin(a):.1f}")
    return " ".join(pts)

def sparkle(cx, cy, r, fill, stroke=None, sw=0, pinch=.16):
    k = r * pinch
    d = (f"M{cx} {cy - r}Q{cx + k} {cy - k} {cx + r} {cy}Q{cx + k} {cy + k} {cx} {cy + r}"
         f"Q{cx - k} {cy + k} {cx - r} {cy}Q{cx - k} {cy - k} {cx} {cy - r}Z")
    st = f' stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"' if stroke else ""
    return f'<path d="{d}" fill="{fill}"{st}/>'

# A flame with two tongues, 330 units tall around (0, 0): outer, middle and inner shapes
FLAME = [
    "M0,-170 C34,-112 112,-82 108,14 C104,104 52,160 0,160 C-60,160 -108,102 -104,24 C-100,-42 -64,-70 -58,-128 "
    "C-34,-86 -22,-66 -10,-56 C-18,-104 -8,-142 0,-170Z",
    "M6,-84 C24,-48 72,-22 70,48 C68,112 36,150 0,150 C-40,150 -70,110 -68,60 C-66,14 -42,-8 -36,-42 "
    "C-20,-12 -8,-4 0,0 C-6,-36 -2,-62 6,-84Z",
    "M2,14 C16,40 40,64 38,100 C36,132 18,148 0,148 C-20,148 -38,132 -38,106 C-38,76 -12,54 2,14Z"]

def flame(cx, cy, s, fills, outline=None):
    tf = f'transform="translate({cx},{cy}) scale({s})"'
    st = f' stroke="{outline[0]}" stroke-width="{outline[1] / s:.1f}" stroke-linejoin="round"' if outline else ""
    return "".join(f'<path d="{d}" fill="{f}"{st if i == 0 else ""} {tf}/>' for i, (d, f) in enumerate(zip(FLAME, fills)))

def speed_lines(seed, n, box, angle, length, color, opacity, width=(2, 6)):
    """n streaks at `angle` degrees starting anywhere in box (x0, y0, x1, y1), seeded so every build draws the same."""
    rnd = random.Random(seed)
    dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    out = []
    for _ in range(n):
        x, y = rnd.uniform(box[0], box[2]), rnd.uniform(box[1], box[3])
        ln = rnd.uniform(*length)
        out.append(f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{x + dx * ln:.0f}" y2="{y + dy * ln:.0f}" '
                   f'stroke-width="{rnd.uniform(*width):.1f}" opacity="{rnd.uniform(.35, 1) * opacity:.2f}"/>')
    return f'<g stroke="{color}" stroke-linecap="round">{"".join(out)}</g>'

def halftone(pid, color, step=16, r=3.2):
    return (f'<pattern id="{pid}" width="{step}" height="{step}" patternUnits="userSpaceOnUse">'
            f'<circle cx="{step / 2}" cy="{step / 2}" r="{r}" fill="{color}"/></pattern>')

DEFS = """
<filter id="blur24" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="24"/></filter>
<filter id="drop" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="12" stdDeviation="12" flood-color="#000" flood-opacity=".5"/></filter>
<filter id="glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="5" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="textshadow" x="-10%" y="-30%" width="120%" height="160%">
  <feDropShadow dx="0" dy="5" stdDeviation="9" flood-color="#000" flood-opacity=".65"/>
  <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="#000" flood-opacity=".55"/></filter>
<linearGradient id="gold" x1="0" y1="0" x2=".35" y2="1">""" + GOLD + """</linearGradient>
<linearGradient id="goldh" x1="0" y1="0" x2="1" y2="0">""" + GOLD + """</linearGradient>
"""


# --- backgrounds ---

MOVIE_HUES = {"New and Trending": ("#b3203a", "#5e0d1e", "#23060c"), "Top Rated": ("#9c1838", "#4f0a22", "#1c040e"),
              "Genres": ("#bd1f45", "#5f0c22", "#22050c"), "Decades": ("#93173a", "#4d0a1f", "#1d040b"),
              "Collections": ("#a01f4a", "#520d29", "#1f0511"), "Showcase": ("#a81c3c", "#560b20", "#20040b")}
# crimson to burgundy, hues 340 to 355

def movies_bg(card, spot=(700, 250)):
    hi, mid, deep = MOVIE_HUES[card]
    # velvet: a deep radial light, curtain folds strongest at the top, a spotlight cone and a dark floor for the title
    return f"""
<defs><radialGradient id="bg" cx="{spot[0] / 960:.2f}" cy="{spot[1] / 540:.2f}" r=".85">
  <stop offset="0" stop-color="{hi}"/><stop offset=".55" stop-color="{mid}"/><stop offset="1" stop-color="{deep}"/></radialGradient>
<linearGradient id="fold" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000" stop-opacity=".55"/>
  <stop offset=".5" stop-color="#fff" stop-opacity=".10"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></linearGradient>
<pattern id="folds" width="58" height="540" patternUnits="userSpaceOnUse"><rect width="58" height="540" fill="url(#fold)"/></pattern>
<linearGradient id="foldfade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".9"/>
  <stop offset=".7" stop-color="#fff" stop-opacity=".25"/><stop offset="1" stop-color="#fff" stop-opacity=".1"/></linearGradient>
<mask id="foldmask"><rect width="960" height="540" fill="url(#foldfade)"/></mask>
<linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe9b8" stop-opacity=".34"/>
  <stop offset="1" stop-color="#ffe9b8" stop-opacity="0"/></linearGradient>
<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset=".45" stop-color="#000" stop-opacity="0"/>
  <stop offset="1" stop-color="#000" stop-opacity=".62"/></linearGradient></defs>
<rect width="960" height="540" fill="url(#bg)"/>
<rect width="960" height="540" fill="url(#folds)" mask="url(#foldmask)" opacity=".7"/>
<polygon points="{spot[0] - 70},-10 {spot[0] + 70},-10 {spot[0] + 300},560 {spot[0] - 300},560" fill="url(#beam)" filter="url(#blur24)"/>
<rect width="960" height="540" fill="url(#floor)"/>"""

TV_HUES = {"New and Trending": ("#16607c", "#0a2c42"), "Top Rated": ("#1e5280", "#0c1f42"),
           "Genres": ("#136a6e", "#073135"), "Decades": ("#235f72", "#0e2b39")}

def tv_bg(card, glow=(720, 260)):
    top, bottom = TV_HUES[card]
    # petrol night, a screen-light glow behind the motif, scan lines, and the test card's bars along the bottom edge
    bars = "".join(f'<rect x="{i * 960 / 7:.1f}" y="528" width="{960 / 7 + 1:.1f}" height="12" fill="{c}"/>' for i, c in enumerate(BARS))
    return f"""
<defs><linearGradient id="bg" x1="0" y1="0" x2=".6" y2="1"><stop offset="0" stop-color="{top}"/>
  <stop offset="1" stop-color="{bottom}"/></linearGradient>
<radialGradient id="screenlight" cx="{glow[0] / 960:.2f}" cy="{glow[1] / 540:.2f}" r=".55">
  <stop offset="0" stop-color="{AQUA}" stop-opacity=".42"/><stop offset="1" stop-color="{AQUA}" stop-opacity="0"/></radialGradient>
<pattern id="scan" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="2" fill="#000" opacity=".12"/></pattern>
<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset=".5" stop-color="#000" stop-opacity="0"/>
  <stop offset="1" stop-color="#000" stop-opacity=".5"/></linearGradient></defs>
<rect width="960" height="540" fill="url(#bg)"/>
<rect width="960" height="540" fill="url(#screenlight)"/>
<rect width="960" height="540" fill="url(#floor)"/>
<rect width="960" height="540" fill="url(#scan)"/>
{bars}"""

ANIME_SKY = {"New and Trending": ("#ff8a2a", "#ff4040", "#c3124d"), "Top Rated": ("#100a38", "#2f2183", "#5a3ab8"),
             "Genres": ("#1f6fe8", "#3d9cff", "#8bd6ff"), "Decades": ("#0f9f97", "#25c4ad", "#8ee8cc")}

def anime_bg(card, tone_at=(860, 90)):
    a, b, c = ANIME_SKY[card]
    # a cel sky, a halftone corner and a darker floor for the title
    return f"""
<defs><linearGradient id="bg" x1="0" y1="0" x2=".3" y2="1"><stop offset="0" stop-color="{a}"/>
  <stop offset=".55" stop-color="{b}"/><stop offset="1" stop-color="{c}"/></linearGradient>
{halftone("dots", "#fff", 18, 3.6)}
<radialGradient id="tonefade" cx="{tone_at[0] / 960:.2f}" cy="{tone_at[1] / 540:.2f}" r=".6">
  <stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<mask id="tonemask"><rect width="960" height="540" fill="url(#tonefade)"/></mask>
<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset=".55" stop-color="{INK}" stop-opacity="0"/>
  <stop offset="1" stop-color="{INK}" stop-opacity=".45"/></linearGradient></defs>
<rect width="960" height="540" fill="url(#bg)"/>
<rect width="960" height="540" fill="url(#dots)" mask="url(#tonemask)"/>
<rect width="960" height="540" fill="url(#floor)"/>"""


# --- motifs ---

def movies_rising():
    path = "M600 600 C660 520 640 420 730 380 S860 300 880 150"
    end, ctrl = (880, 150), (860, 300)  # the arrow follows the last tangent
    a = math.atan2(end[1] - ctrl[1], end[0] - ctrl[0])
    def at(u, v): return f"{end[0] + u * math.cos(a) - v * math.sin(a):.1f},{end[1] + u * math.sin(a) + v * math.cos(a):.1f}"
    return f"""
<circle cx="860" cy="150" r="230" fill="#ffb54d" opacity=".28" filter="url(#blur24)"/>
<g filter="url(#drop)">
  <path d="{path}" fill="none" stroke="url(#gold)" stroke-width="100"/>
  <path d="{path}" fill="none" stroke="#2b0a10" stroke-width="84"/>
  <path d="{path}" fill="none" stroke="#f9dc8e" stroke-width="72" stroke-dasharray="9 12"/>
  <path d="{path}" fill="none" stroke="#2b0a10" stroke-width="52"/>
  <path d="{path}" fill="none" stroke="#ffd26a" stroke-width="44" stroke-dasharray="58 9" opacity=".95"/>
  <polygon points="{at(96, 0)} {at(-6, 74)} {at(-6, -74)}" fill="url(#gold)" stroke="#8a5512" stroke-width="3" stroke-linejoin="round"/>
</g>"""

def laurel(cx, cy, R, n=11):
    out = []
    for side in (1, -1):  # left, then right (y grows downwards)
        a0, a1 = 90 + side * 16, 90 + side * 160
        p0 = f"{cx + R * math.cos(math.radians(a0)):.1f} {cy + R * math.sin(math.radians(a0)):.1f}"
        p1 = f"{cx + R * math.cos(math.radians(a1)):.1f} {cy + R * math.sin(math.radians(a1)):.1f}"
        out.append(f'<path d="M{p0} A{R} {R} 0 0 {1 if side == 1 else 0} {p1}" fill="none" stroke="url(#gold)" '
                   f'stroke-width="7" stroke-linecap="round"/>')
        for i in range(n):
            t = i / (n - 1)
            a = math.radians(a0 + (a1 - a0) * t)
            tang = math.degrees(math.atan2(side * math.cos(a), -side * math.sin(a)))  # direction up the stem
            L = 38 - 14 * t
            for k, off in ((1, 10), (-1, -10)):  # a leaf outside the stem and one inside
                x, y = cx + (R + off) * math.cos(a), cy + (R + off) * math.sin(a)
                out.append(f'<path d="M{-L} 0Q0 {-L * .55:.1f} {L} 0Q0 {L * .55:.1f} {-L} 0Z" fill="url(#gold)" '
                           f'stroke="#8a5512" stroke-width="1.5" transform="translate({x:.1f},{y:.1f}) rotate({tang - k * side * 38:.1f})"/>')
    return "".join(out)

def movies_top():
    cx, cy = 762, 250
    return f"""
<circle cx="{cx}" cy="{cy}" r="200" fill="#ffcf73" opacity=".22" filter="url(#blur24)"/>
<g filter="url(#drop)">{laurel(cx, cy, 168)}
  <polygon points="{star(cx, cy - 6, 112, 48)}" fill="url(#gold)" stroke="#8a5512" stroke-width="4" stroke-linejoin="round"/>
  <polygon points="{star(cx - 8, cy - 18, 66, 28)}" fill="#fff6d6" opacity=".35"/>
</g>"""

def movies_genres():
    names = ["bolt", "heart", "ghost", "rocket", "mask", "magnifier", "crown", "note", "cactus", "house", "eye", "hourglass"]
    lit = {1, 6, 8}
    cells = []
    for i, g in enumerate(names):
        r, c = divmod(i, 4)
        x, y = 470 + c * 136, 44 + r * 136
        cells.append(f'<rect x="{x}" y="{y}" width="118" height="118" rx="22" fill="{"url(#gold)" if i in lit else "#3a0a14"}" '
                     f'stroke="url(#gold)" stroke-width="3"/>' + glyph(g, x + 59, y + 59, 66, "#3a0a14" if i in lit else "#f8cf6a", 2))
    return f"""
<circle cx="720" cy="250" r="260" fill="#ff9a6b" opacity=".16" filter="url(#blur24)"/>
<g transform="rotate(-8 720 250)" filter="url(#drop)">{"".join(cells)}</g>"""

def movies_decades():
    labels = ["50s", "60s", "70s", "80s", "90s", "00s", "10s", "20s"]
    fw, gap, h, x0 = 112, 12, 150, -12
    frames, holes = [], []
    for i, lab in enumerate(labels):
        x, lit = x0 + i * (fw + gap), lab == "80s"
        frames.append(f'<rect x="{x}" y="{-h / 2 + 26}" width="{fw}" height="{h - 52}" rx="8" '
                      f'fill="{"url(#gold)" if lit else "#3b0d12"}" stroke="#f1c35a" stroke-opacity=".5" stroke-width="2"/>'
                      f'<text x="{x + fw / 2}" y="17" text-anchor="middle" font-family="Outfit" font-weight="800" font-size="50" '
                      f'fill="{"#3b0d12" if lit else "#ffd779"}">{lab}</text>')
    for j in range(42):
        x = x0 + 4 + j * 24
        holes += [f'<rect x="{x}" y="{-h / 2 + 7}" width="13" height="11" rx="3"/>', f'<rect x="{x}" y="{h / 2 - 18}" width="13" height="11" rx="3"/>']
    return f"""
<circle cx="560" cy="180" r="300" fill="#ffb05a" opacity=".14" filter="url(#blur24)"/>
<g transform="translate(0,196) rotate(-9 480 0)" filter="url(#drop)">
  <rect x="-40" y="{-h / 2}" width="1060" height="{h}" fill="#1e0709" stroke="url(#goldh)" stroke-width="4"/>
  <g fill="#f6d590">{"".join(holes)}</g>{"".join(frames)}
</g>"""

def reel(cx, cy, r):
    holes = "".join(f'<circle cx="{cx + r * .55 * math.cos(math.radians(a)):.1f}" cy="{cy + r * .55 * math.sin(math.radians(a)):.1f}" '
                    f'r="{r * .2:.1f}" fill="#2a0712"/>' for a in range(-90, 270, 60))
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#gold)" stroke="#8a5512" stroke-width="4"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * .9:.1f}" fill="none" stroke="#8a5512" stroke-width="2" opacity=".6"/>{holes}'
            f'<circle cx="{cx}" cy="{cy}" r="{r * .14:.1f}" fill="#2a0712"/><circle cx="{cx}" cy="{cy}" r="{r * .06:.1f}" fill="#f6d590"/>')

def movies_collections():
    """A box set: five numbered cases in a brass-edged slipcase seen from its open side, a reel behind it."""
    x0, y0, x1, y1, wall, dx, dy = 618, 136, 850, 380, 12, 54, -28  # the open face, and the depth the box recedes by
    n, gap = 5, 3
    sw = (x1 - x0 - 2 * wall - (n - 1) * gap) / n
    spines = []
    for k in range(n):
        x, top, h = x0 + wall + k * (sw + gap), y0 + wall + 6, y1 - y0 - 2 * wall - 6
        spines.append(f'<rect x="{x:.1f}" y="{top}" width="{sw:.1f}" height="{h}" rx="3" fill="{["#6a0f28", "#561024"][k % 2]}"/>'
                      f'<rect x="{x:.1f}" y="{top + 16}" width="{sw:.1f}" height="7" fill="url(#goldh)"/>'
                      f'<rect x="{x:.1f}" y="{top + h - 23}" width="{sw:.1f}" height="7" fill="url(#goldh)"/>'
                      f'<rect x="{x + 8:.1f}" y="{top + 34}" width="{sw - 16:.1f}" height="3" fill="#f1c35a" opacity=".55"/>'
                      f'<text x="{x + sw / 2:.1f}" y="{top + h / 2 + 14:.1f}" text-anchor="middle" font-family="Outfit" '
                      f'font-weight="800" font-size="40" fill="url(#gold)">{k + 1}</text>')
    edge = 'stroke="url(#gold)" stroke-width="4" stroke-linejoin="round"'
    return f"""
<circle cx="760" cy="230" r="260" fill="#ffb86b" opacity=".18" filter="url(#blur24)"/>
<g filter="url(#drop)">{reel(806, 116, 104)}</g>
<g transform="rotate(-3 734 258)" filter="url(#drop)">
  <polygon points="{x0},{y0} {x0 + dx},{y0 + dy} {x1 + dx},{y0 + dy} {x1},{y0}" fill="#7a5214" {edge}/>
  <polygon points="{x1},{y0} {x1 + dx},{y0 + dy} {x1 + dx},{y1 + dy} {x1},{y1}" fill="#3d0815" {edge}/>
  <rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="6" fill="#2a0710" {edge}/>
  <rect x="{x0 + wall}" y="{y0 + wall}" width="{x1 - x0 - 2 * wall}" height="{y1 - y0 - 2 * wall}" fill="#12030a"/>
  {"".join(spines)}
</g>"""

def movies_showcase():
    """An IMAX-shaped screen (1.43:1) in a brass frame, a desert sunrise on it: the sun and its anamorphic flare bloom
    past the frame, as HDR highlights do."""
    x0, y0, w, h, bow = 516, 44, 386, 270, 16
    x1, y1, sx, sy = x0 + w, y0 + h, x0 + w * .64, y0 + h * .62
    screen = f"M{x0} {y0}Q{x0 + w / 2} {y0 - bow} {x1} {y0}L{x1} {y1}Q{x0 + w / 2} {y1 + bow} {x0} {y1}Z"
    dunes = [(f"M{x0 - 5} {y0 + h * .70}C{x0 + 90} {y0 + h * .58} {x0 + 170} {y0 + h * .74} {x1 + 5} {y0 + h * .64}"
              f"L{x1 + 5} {y1 + 20}L{x0 - 5} {y1 + 20}Z", "#7c2430"),
             (f"M{x0 - 5} {y0 + h * .84}C{x0 + 120} {y0 + h * .70} {x0 + 210} {y0 + h * .90} {x1 + 5} {y0 + h * .78}"
              f"L{x1 + 5} {y1 + 20}L{x0 - 5} {y1 + 20}Z", "#3a0b16"),
             (f"M{x0 - 5} {y0 + h * .95}C{x0 + 80} {y0 + h * .86} {x0 + 150} {y0 + h * .97} {x1 + 5} {y0 + h * .92}"
              f"L{x1 + 5} {y1 + 20}L{x0 - 5} {y1 + 20}Z", "#1c050b")]
    return f"""
<defs><clipPath id="screen"><path d="{screen}"/></clipPath>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1d0731"/><stop offset=".38" stop-color="#7a1d3e"/>
  <stop offset=".62" stop-color="#ff9a4a"/><stop offset=".72" stop-color="#ffd98f"/></linearGradient>
<radialGradient id="halo"><stop offset="0" stop-color="#fffbe8"/><stop offset=".3" stop-color="#ffe6a6" stop-opacity=".85"/>
  <stop offset="1" stop-color="#ffb35c" stop-opacity="0"/></radialGradient>
<linearGradient id="flare" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ffe2b0" stop-opacity="0"/>
  <stop offset=".5" stop-color="#fff8e4"/><stop offset="1" stop-color="#ffe2b0" stop-opacity="0"/></linearGradient></defs>
<circle cx="{sx:.0f}" cy="{sy:.0f}" r="250" fill="#ffb86b" opacity=".2" filter="url(#blur24)"/>
<g transform="rotate(-3 {x0 + w / 2:.0f} {y0 + h / 2:.0f})">
<g filter="url(#drop)"><path d="{screen}" fill="#12030a" stroke="url(#gold)" stroke-width="22" stroke-linejoin="round"/></g>
<g clip-path="url(#screen)">
  <rect x="{x0 - 5}" y="{y0 - 15}" width="{w + 10}" height="{h + 30}" fill="url(#sky)"/>
  <circle cx="{sx:.0f}" cy="{sy:.0f}" r="96" fill="url(#halo)"/>
  <circle cx="{sx:.0f}" cy="{sy:.0f}" r="25" fill="#fffdf4"/>
  {"".join(f'<path d="{d}" fill="{c}"/>' for d, c in dunes)}
</g>
<path d="{screen}" fill="none" stroke="#8a5512" stroke-width="3" stroke-linejoin="round"/>
<circle cx="{sx:.0f}" cy="{sy:.0f}" r="58" fill="#fff4cf" opacity=".55" filter="url(#blur24)"/>
<ellipse cx="{sx:.0f}" cy="{sy:.0f}" rx="230" ry="4" fill="url(#flare)" opacity=".9"/>
<ellipse cx="{sx:.0f}" cy="{sy:.0f}" rx="120" ry="10" fill="url(#flare)" opacity=".35" filter="url(#glow)"/>
</g>"""

def crt(cx, cy, sw, sh, content, tilt=0, cid="scr"):
    """A retro TV set: a screen sw x sh centred on (cx, cy), a knob panel on the right, antenna and feet."""
    bx, by, bw, bh = cx - sw / 2 - 34, cy - sh / 2 - 34, sw + 68 + 92, sh + 68
    px = cx + sw / 2 + 30
    slots = "".join(f'<path d="M{px + 12} {cy + 30 + k * 16}h36"/>' for k in range(4))
    return f"""
<g transform="rotate({tilt} {cx} {cy})">
<defs><clipPath id="{cid}"><rect x="{cx - sw / 2}" y="{cy - sh / 2}" width="{sw}" height="{sh}" rx="30"/></clipPath>
<radialGradient id="{cid}g" cx=".5" cy=".45" r=".7"><stop offset="0" stop-color="#11606e"/><stop offset="1" stop-color="#03161f"/></radialGradient>
<linearGradient id="{cid}b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2c3b4b"/><stop offset="1" stop-color="#121a24"/></linearGradient></defs>
<g filter="url(#drop)">
<path d="M{cx - 40} {by + 4}L{cx - 120} {by - 96}M{cx + 30} {by + 4}L{cx + 110} {by - 110}" stroke="#9fb0bf" stroke-width="6" stroke-linecap="round"/>
<circle cx="{cx - 120}" cy="{by - 96}" r="9" fill="{CORAL}"/><circle cx="{cx + 110}" cy="{by - 110}" r="9" fill="{AQUA}"/>
<rect x="{bx + 40}" y="{by + bh - 6}" width="34" height="26" rx="6" fill="#0d141c"/><rect x="{bx + bw - 74}" y="{by + bh - 6}" width="34" height="26" rx="6" fill="#0d141c"/>
<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="42" fill="url(#{cid}b)" stroke="#3e5163" stroke-width="3"/>
<rect x="{cx - sw / 2 - 10}" y="{cy - sh / 2 - 10}" width="{sw + 20}" height="{sh + 20}" rx="38" fill="#0a1017"/>
<rect x="{cx - sw / 2}" y="{cy - sh / 2}" width="{sw}" height="{sh}" rx="30" fill="url(#{cid}g)"/>
<g clip-path="url(#{cid})">{content}<rect x="{cx - sw / 2}" y="{cy - sh / 2}" width="{sw}" height="{sh}" fill="url(#scan)"/>
  <ellipse cx="{cx - sw * .18}" cy="{cy - sh * .42}" rx="{sw * .42}" ry="{sh * .2}" fill="#fff" opacity=".07"/></g>
<circle cx="{px + 30}" cy="{cy - sh / 2 + 40}" r="22" fill="{CREAM}"/><circle cx="{px + 30}" cy="{cy - sh / 2 + 40}" r="8" fill="#b9ae96"/>
<circle cx="{px + 30}" cy="{cy - sh / 2 + 104}" r="16" fill="{CREAM}"/>
<g stroke="#0b1118" stroke-width="5" stroke-linecap="round">{slots}</g>
</g></g>"""

def tv_trending():
    """A transmitter mast sending rising signal arcs, with a flame in an on-air bug."""
    cx, top, base, beacon = 742, 236, 528, 176
    lv = [top + (base - top) * k / 6 for k in range(7)]
    def half(y): return 12 + (y - top) / (base - top) * 92  # the mast's half width at height y
    legs = f'M{cx - half(base):.0f} {base}L{cx - 12} {top}M{cx + half(base):.0f} {base}L{cx + 12} {top}'
    braces = "".join(f'M{cx - half(y0):.1f} {y0:.1f}L{cx + half(y1):.1f} {y1:.1f}M{cx + half(y0):.1f} {y0:.1f}L{cx - half(y1):.1f} {y1:.1f}'
                     for y0, y1 in zip(lv, lv[1:]))
    rungs = "".join(f'<line x1="{cx - half(y):.1f}" y1="{y:.1f}" x2="{cx + half(y):.1f}" y2="{y:.1f}" stroke="{CORAL if k % 2 else "#dfe8ef"}"/>'
                    for k, y in enumerate(lv[1:-1]))
    def arc(r): return (f'M{cx + r * math.cos(math.radians(-152)):.1f} {beacon + r * math.sin(math.radians(-152)):.1f}'
                        f'A{r} {r} 0 0 1 {cx + r * math.cos(math.radians(-28)):.1f} {beacon + r * math.sin(math.radians(-28)):.1f}')
    arcs = "".join(f'<path d="{arc(r)}" fill="none" stroke="{AQUA}" stroke-width="{w}" stroke-linecap="round" opacity="{o}"/>'
                   for r, w, o in ((50, 13, 1), (92, 12, .85), (134, 11, .65), (172, 10, .45)))
    return f"""
<circle cx="{cx}" cy="{beacon}" r="230" fill="{AQUA}" opacity=".14" filter="url(#blur24)"/>
<g filter="url(#drop)">
  <g fill="none" stroke="#9fb3c4" stroke-width="5" stroke-linecap="round"><path d="{braces}"/></g>
  <g stroke-width="7" stroke-linecap="round">{rungs}</g>
  <path d="{legs}" fill="none" stroke="#dfe8ef" stroke-width="9" stroke-linecap="round"/>
  <path d="M{cx} {top}V{beacon + 12}" stroke="#dfe8ef" stroke-width="8" stroke-linecap="round"/>
  <circle cx="{cx}" cy="{beacon}" r="15" fill="{CORAL}" filter="url(#glow)"/>
  {arcs}
</g>
<g filter="url(#drop)">
  <rect x="818" y="356" width="108" height="108" rx="24" fill="#0a1017" stroke="{CORAL}" stroke-width="5"/>
  <circle cx="872" cy="414" r="40" fill="{CORAL}" opacity=".35" filter="url(#blur24)"/>
  {flame(872, 408, .26, (CORAL, AMBER, "#fff4d0"))}
</g>"""

def tv_top():
    cx, cy = 714, 236
    small = "".join(f'<polygon points="{star(cx - 72 + k * 36, cy + 66, 14, 6)}" fill="{AMBER if k < 4 else "#3b6f78"}"/>' for k in range(5))
    screen = (f'<circle cx="{cx}" cy="{cy - 18}" r="100" fill="{AMBER}" opacity=".45" filter="url(#blur24)"/>'
              f'<polygon points="{star(cx, cy - 20, 72, 29)}" fill="{AMBER}" stroke="#fff1c2" stroke-width="4" stroke-linejoin="round"/>{small}')
    return (f'<circle cx="{cx}" cy="{cy}" r="260" fill="{AMBER}" opacity=".12" filter="url(#blur24)"/>'
            + crt(cx, cy, 256, 190, screen, tilt=-4))

def tv_genres():
    names = ["couch", "cross", "scales", "ghost", "fingerprint", None, "rocket", "mask", "camera", "shield", "house", "heart"]
    lit = {1: CORAL, 6: AMBER, 8: AQUA}  # screens lit in one colour, their glyph dark
    cells = []
    for i, g in enumerate(names):
        r, c = divmod(i, 4)
        x, y = 462 + c * 128, 58 + r * 104
        cells.append(f'<rect x="{x}" y="{y}" width="118" height="94" rx="14" fill="#0a1017"/>'
                     f'<rect x="{x + 6}" y="{y + 6}" width="106" height="82" rx="10" fill="{lit.get(i, "url(#wallg)")}"/>')
        if g is None:  # one screen shows the test card
            cells.append("".join(f'<rect x="{x + 6 + k * 106 / 7:.1f}" y="{y + 6}" width="{106 / 7 + .5:.1f}" height="82" fill="{col}"/>'
                                 for k, col in enumerate(BARS)))
        else:
            cells.append(glyph(g, x + 59, y + 47, 70, "#0a1017" if i in lit else [AQUA, CREAM, CORAL][i % 3], 2.8))
        cells.append(f'<rect x="{x + 6}" y="{y + 6}" width="106" height="82" rx="10" fill="url(#scan)"/>')  # scan lines on screen
    return f"""
<defs><radialGradient id="wallg" cx=".5" cy=".45" r=".75"><stop offset="0" stop-color="#1b7480"/><stop offset="1" stop-color="#06222b"/></radialGradient></defs>
<circle cx="700" cy="230" r="280" fill="{AQUA}" opacity=".16" filter="url(#blur24)"/>
<g filter="url(#drop)">{"".join(cells)}</g>"""

# The TV set by decade: body width and height, screen inset, corner radius, body colour, what it stands on
TV_SETS = {"60s": (100, 118, 14, 18, "#7a4a26", "legs"), "70s": (92, 106, 12, 16, "#a0672f", "ears"),
           "80s": (100, 102, 10, 10, "#55626f", "knobs"), "90s": (94, 100, 9, 14, "#2a333e", "foot"),
           "00s": (110, 84, 8, 8, "#b4bfca", "pedestal"), "10s": (116, 80, 5, 4, "#151b22", "stand"),
           "20s": (124, 80, 3, 3, "#0c1015", "feet")}
LIFT = {"legs": 24, "ears": 6, "knobs": 6, "foot": 8, "pedestal": 26, "stand": 26, "feet": 10}

def tv_set(x, base, era, lit):
    """The TV of an era standing on the line y = base from x, its decade on screen; returns (svg, width)."""
    w, h, inset, rx, body, stand = TV_SETS[era]
    lift = LIFT[stand]
    y = base - lift - h
    sx, sy, swd, sht = x + inset, y + inset, w - 2 * inset - (24 if stand == "knobs" else 0), h - 2 * inset
    out = []
    if stand == "legs":
        out.append(f'<path d="M{x + 16} {y + h}l-8 {lift}M{x + w - 16} {y + h}l8 {lift}" stroke="#4a2c16" stroke-width="7" stroke-linecap="round"/>')
    if stand == "ears":
        out.append(f'<path d="M{x + w / 2} {y + 2}l-30 -52M{x + w / 2} {y + 2}l26 -56" stroke="#c9d3dc" stroke-width="4" stroke-linecap="round"/>'
                   f'<rect x="{x + 18}" y="{y + h}" width="12" height="{lift}" fill="#3b2412"/>'
                   f'<rect x="{x + w - 30}" y="{y + h}" width="12" height="{lift}" fill="#3b2412"/>')
    if stand in ("knobs", "foot", "feet"):
        out.append(f'<rect x="{x + 14}" y="{y + h}" width="{w - 28}" height="{lift}" rx="3" fill="#0d1218"/>')
    if stand in ("pedestal", "stand"):
        nw = 14 if stand == "stand" else 26
        out.append(f'<rect x="{x + w / 2 - nw / 2}" y="{y + h}" width="{nw}" height="{lift - 6}" fill="#7d8894"/>'
                   f'<rect x="{x + w / 2 - 36}" y="{base - 7}" width="72" height="7" rx="3" fill="#7d8894"/>')
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{body}" stroke="#0a1017" stroke-width="3"/>')
    if stand == "knobs":
        out.append(f'<circle cx="{x + w - 17}" cy="{y + 26}" r="7" fill="{CREAM}"/><circle cx="{x + w - 17}" cy="{y + 50}" r="5" fill="{CREAM}"/>')
    out.append(f'<rect x="{sx}" y="{sy}" width="{swd}" height="{sht}" rx="{max(2, rx - inset / 2)}" fill="{AMBER if lit else "url(#setg)"}"/>'
               f'<text x="{sx + swd / 2}" y="{sy + sht / 2 + 11}" text-anchor="middle" font-family="Outfit" font-weight="800" '
               f'font-size="34" fill="{"#0a1017" if lit else "#e9fbf8"}">{era}</text>')
    return "".join(out), w

def tv_decades():
    """The TV set through the decades, 60s to 20s, on a timeline, the 80s one lit."""
    x, base, gap, sets, dots = 58, 334, 17, [], []
    for era in TV_SETS:
        svg, w = tv_set(x, base, era, era == "80s")
        sets.append(svg)
        dots.append(f'<circle cx="{x + w / 2}" cy="{base + 18}" r="7" fill="{CORAL if era == "80s" else AQUA}"/>')
        x += w + gap
    return f"""
<defs><radialGradient id="setg" cx=".5" cy=".45" r=".75"><stop offset="0" stop-color="#1b7480"/><stop offset="1" stop-color="#06222b"/></radialGradient></defs>
<ellipse cx="480" cy="250" rx="460" ry="170" fill="{AQUA}" opacity=".12" filter="url(#blur24)"/>
<line x1="40" y1="{base + 18}" x2="{x}" y2="{base + 18}" stroke="#9fb3c4" stroke-width="4" stroke-linecap="round" opacity=".7"/>
{"".join(dots)}
<g filter="url(#drop)">{"".join(sets)}</g>"""

def anime_trending():
    cx, cy = 715, 262
    return f"""
{speed_lines(11, 30, (580, 40, 960, 560), -78, (90, 260), "#fff", .55)}
<circle cx="{cx}" cy="{cy + 40}" r="190" fill="#fff3b0" opacity=".45" filter="url(#blur24)"/>
<g transform="translate(10,12)">{flame(cx, cy, 1.08, (PINK,), (INK, 9))}</g>
{flame(cx, cy, 1.08, (YELLOW, "#fff1b0", "#ffffff"), (INK, 9))}
<path d="M{cx - 50} {cy + 60}q-12 -60 24 -110" fill="none" stroke="#fff" stroke-width="10" stroke-linecap="round" opacity=".7"/>
{sparkle(905, 150, 24, "#fff", INK, 5)}"""

def anime_top():
    cx, cy = 728, 236
    rnd = random.Random(7)
    pts = [(rnd.uniform(420, 960), rnd.uniform(0, 520), rnd.uniform(1.5, 3.5), rnd.uniform(.4, .9)) for _ in range(60)]
    dots = "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="#fff" opacity="{o:.2f}"/>'
                   for x, y, r, o in pts if x > 630 or y < 360)  # none by the title
    ink = f'stroke="{INK}" stroke-width="9" stroke-linejoin="round"'
    def tail(x0, x1, y1):  # a ribbon tail with a notched end
        return (f'<polygon points="{x0 - 26},{cy + 70} {x0 + 26},{cy + 70} {x1 + 30},{y1} {x1},{y1 - 26} {x1 - 30},{y1}" '
                f'fill="{CYAN}" {ink}/>')
    return f"""
{dots}
{speed_lines(5, 10, (620, 400, 800, 530), -28, (120, 240), "#fff", .5, (3, 6))}
<circle cx="{cx}" cy="{cy}" r="200" fill="{YELLOW}" opacity=".30" filter="url(#blur24)"/>
{tail(cx - 34, cx - 80, 488)}{tail(cx + 34, cx + 74, 498)}
<circle cx="{cx}" cy="{cy}" r="150" fill="none" stroke="#fff" stroke-width="5" stroke-dasharray="4 18" stroke-linecap="round" opacity=".7"/>
<polygon points="{star(cx + 10, cy + 12, 160, 72)}" fill="{PINK}" {ink}/>
<polygon points="{star(cx, cy, 160, 72)}" fill="{YELLOW}" {ink}/>
<polygon points="{star(cx - 10, cy - 14, 70, 31)}" fill="#fff7c9"/>
{sparkle(905, 96, 26, CYAN, INK, 5)}"""

def anime_genres():
    # a manga page: six panels with slanted gutters, each with a halftone tint and an ink-outlined glyph
    panels = [((470, 40), (690, 40), (676, 220), (470, 220), PINK, "sword"),
              ((706, 40), (940, 40), (940, 200), (692, 220), YELLOW, "robot"),
              ((470, 236), (610, 236), (600, 400), (470, 400), CYAN, "heart"),
              ((626, 236), (940, 216), (940, 380), (616, 400), "#ffffff", "magnifier"),
              ((470, 416), (720, 416), (712, 560), (470, 560), "#b9a4ff", "ghost"),
              ((736, 416), (940, 396), (940, 560), (728, 560), "#ff9b5e", "ball")]
    out = []
    for i, (*pts, col, g) in enumerate(panels):
        poly = " ".join(f"{x},{y}" for x, y in pts)
        cx, cy = sum(x for x, _ in pts) / 4, sum(y for _, y in pts) / 4
        out.append(f'<clipPath id="pc{i}"><polygon points="{poly}"/></clipPath><polygon points="{poly}" fill="{col}"/>'
                   f'<rect x="440" y="0" width="520" height="560" fill="url(#inkdots)" clip-path="url(#pc{i})" opacity=".18"/>'
                   + glyph(g, cx, min(cy, 480), 92, "#fff", 2.6, (INK, 3.2))
                   + f'<polygon points="{poly}" fill="none" stroke="{INK}" stroke-width="7" stroke-linejoin="round"/>')
    return f"""
<defs>{halftone("inkdots", INK, 12, 2.6)}</defs>
<g transform="translate(26,0) rotate(-5 700 270)" filter="url(#drop)">
  <polygon points="452,22 958,22 958,578 452,578" fill="#fffaf2" stroke="{INK}" stroke-width="6"/>
  {"".join(out)}
</g>
{sparkle(466, 104, 22, YELLOW, INK, 4)}"""

def anime_decades():
    labels = ["80s", "90s", "00s", "10s", "20s"]
    cols = [CYAN, PINK, YELLOW, "#ffffff", "#b9a4ff"]
    pts = [(612 + 72 * k, 404 - 74 * k) for k in range(5)]
    line = " ".join(f"{x},{y}" for x, y in pts)
    badges = "".join(f'<circle cx="{x + 7}" cy="{y + 8}" r="56" fill="{INK}"/>'
                     f'<circle cx="{x}" cy="{y}" r="56" fill="{col}" stroke="{INK}" stroke-width="7"/>'
                     f'<text x="{x}" y="{y + 15}" text-anchor="middle" font-family="Outfit" font-weight="800" font-size="42" '
                     f'fill="{INK}">{lab}</text>' for (x, y), lab, col in zip(pts, labels, cols))
    return f"""
{speed_lines(3, 24, (560, 100, 960, 560), -40, (100, 260), "#fff", .45)}
<polyline points="{line}" fill="none" stroke="{INK}" stroke-width="22" stroke-linecap="round" stroke-linejoin="round"/>
<polyline points="{line}" fill="none" stroke="#fff" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="2 18"/>
{badges}
{sparkle(935, 270, 22, YELLOW, INK, 4)}{sparkle(660, 150, 18, "#fff", INK, 4)}"""

# (type, card): (motif, where the background's light sits)
MOTIFS = {
    ("movies", "New and Trending"): (movies_rising, {"spot": (860, 160)}),
    ("movies", "Top Rated"): (movies_top, {"spot": (730, 230)}),
    ("movies", "Genres"): (movies_genres, {"spot": (720, 230)}),
    ("movies", "Decades"): (movies_decades, {"spot": (560, 230)}),
    ("movies", "Collections"): (movies_collections, {"spot": (760, 220)}),
    ("movies", "Showcase"): (movies_showcase, {"spot": (720, 200)}),
    ("tv", "New and Trending"): (tv_trending, {"glow": (680, 262)}),
    ("tv", "Top Rated"): (tv_top, {"glow": (680, 262)}),
    ("tv", "Genres"): (tv_genres, {"glow": (700, 230)}),
    ("tv", "Decades"): (tv_decades, {"glow": (720, 262)}),
    ("anime", "New and Trending"): (anime_trending, {"tone_at": (880, 80)}),
    ("anime", "Top Rated"): (anime_top, {"tone_at": (900, 480)}),
    ("anime", "Genres"): (anime_genres, {"tone_at": (120, 60)}),
    ("anime", "Decades"): (anime_decades, {"tone_at": (900, 60)}),
}
BACKGROUNDS = {"movies": movies_bg, "tv": tv_bg, "anime": anime_bg}


# --- the small type label and the card's name ---

LABEL_SIZE = {"movies": 40, "tv": 40, "anime": 35}  # read from the sofa on a row-size tile

def label_svg(style, x, y, scale=1.0, pill=False):
    """The type label with its top-left at (x, y); pill sets Movies' and TV's on a dark pill (for logos, which land on
    bright backdrops too)."""
    text, size, track = LABEL[style], round(LABEL_SIZE[style] * scale), 5 * scale
    tw = font(size, 800).getlength(text) + track * (len(text) - 1)
    base = y + size * .86
    t = f'font-family="Outfit" font-size="{size}" font-weight="800" letter-spacing="{track:.1f}"'
    def under(width, colour):
        h = size + 18 * scale
        return (f'<rect x="{x - 16 * scale:.1f}" y="{y - 9 * scale:.1f}" width="{width + 32 * scale:.1f}" height="{h:.1f}" '
                f'rx="{h / 2:.1f}" fill="{colour}" fill-opacity=".72"/>') if pill else ""
    if style == "movies":  # brass lettering, and a rule on the tiles
        rule = "" if pill else (f'<rect x="{x + tw + 18 * scale:.1f}" y="{base - size * .38:.1f}" width="{70 * scale:.1f}" '
                                f'height="{5 * scale:.1f}" rx="2" fill="url(#goldh)"/>')
        return under(tw, "#1c0508") + f'<text x="{x}" y="{base:.1f}" {t} fill="url(#goldh)">{text}</text>' + rule
    if style == "tv":  # an on-air light
        r = 11 * scale
        return (under(2 * r + 14 * scale + tw, "#04111f") + f'<circle cx="{x + r:.1f}" cy="{base - size * .36:.1f}" r="{r:.1f}" fill="{CORAL}" filter="url(#glow)"/>'
                f'<text x="{x + 2 * r + 14 * scale:.1f}" y="{base:.1f}" {t} fill="{AQUA}">{text}</text>')
    pad, h = 18 * scale, size * 1.55  # a sticker
    w, rx = tw + 2 * pad, 10 * scale
    return (f'<g transform="rotate(-5 {x} {y + h})"><rect x="{x + 5 * scale:.1f}" y="{y + 5 * scale:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" fill="{INK}"/>'
            f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" fill="{YELLOW}" stroke="{INK}" stroke-width="{5 * scale:.1f}"/>'
            f'<text x="{x + pad:.1f}" y="{y + h / 2 + size * .36:.1f}" {t} fill="{INK}">{text}</text></g>')

def label_height(style, scale=1.0): return LABEL_SIZE[style] * scale * (1.55 if style == "anime" else 1)

def name_svg(style, lines, x, y0, step, size):
    """The card's name, first baseline at y0: ivory (Movies) or white with a dark edge, Anime's in ink with a pink
    offset copy."""
    def texts(attrs, dx=0.0, dy=0.0):
        return "".join(f'<text x="{x + dx:.1f}" y="{y0 + i * step + dy:.1f}" font-family="Outfit" font-weight="800" '
                       f'font-size="{size}" {attrs}>{esc(line)}</text>' for i, line in enumerate(lines))
    def edge(colour, width): return f'stroke="{colour}" stroke-width="{width}" stroke-linejoin="round" paint-order="stroke"'
    if style == "anime":
        ink = edge(INK, max(8, round(size * .13)))
        shadow = texts(f'fill="{PINK}" {ink}', size * .06, size * .07)
        return f'<g filter="url(#textshadow)">{shadow}</g>' + texts(f'fill="#fff" {ink}')
    fill, dark = (IVORY, "#2a0710") if style == "movies" else ("#ffffff", "#04111f")
    return f'<g filter="url(#textshadow)">{texts(f"fill=\"{fill}\" " + edge(dark, round(size * .065)))}</g>'

def tile_svg(ctitle, card):
    style = STYLE[ctitle]
    motif, light = MOTIFS[(style, card)]
    f, lines = fit(card, 560, range(112, 71, -4), 2, 800) or sys.exit(f"art: tile {card!r} does not fit")
    step, y_last = f.size, 540 - 66
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540"><defs>{DEFS}</defs>'
            f'{BACKGROUNDS[style](card, **light)}{motif()}{label_svg(style, 64, 52)}'
            f'{name_svg(style, lines, 64, y_last - step * (len(lines) - 1), step, f.size)}</svg>')

def logo_svg(ctitle, card):
    style = STYLE[ctitle]
    w, h = LOGO
    # One line when it fits at 96 px or more, else two at 86 px at most (78 under Anime's taller sticker), under the
    # type label
    f, lines = (fit(card, w - 60, range(112, 95, -2), 1, 800)
                or fit(card, w - 60, range(78 if style == "anime" else 86, 65, -4), 2, 800)
                or sys.exit(f"art: logo {card!r} does not fit"))
    cap, gap, scale = -f.getbbox("H", anchor="ls")[1], 22, .95
    # centred on the cap heights, 10 px higher for the descenders and the shadow under the last line
    top = (h - (label_height(style, scale) + gap + cap + f.size * (len(lines) - 1))) / 2 - 10
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><defs>{DEFS}</defs>'
            f'{label_svg(style, 28 if style == "anime" else 42, top, scale, pill=True)}'
            f'{name_svg(style, lines, 24, top + label_height(style, scale) + gap + cap, f.size, f.size)}</svg>')


# --- rendering ---

def browser():
    for p in (os.environ.get("EDGE"), r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", shutil.which("msedge"),
              shutil.which("chromium"), shutil.which("google-chrome")):
        if p and os.path.exists(p): return p
    sys.exit("art: needs Edge or Chrome to render the cards (EDGE=path)")

def shoot(svg, size):
    """One SVG as an image of exactly `size` on a transparent background, from a headless browser of its own (its own
    profile, muted, closed when the screenshot is written)."""
    with open(FONT, "rb") as fh: data = base64.b64encode(fh.read()).decode()
    css = ("@font-face{font-family:Outfit;src:url(data:font/ttf;base64," + data + ") format('truetype');font-weight:100 900}"
           "html,body{margin:0;padding:0;background:transparent;overflow:hidden}svg{display:block}")
    tmp = tempfile.mkdtemp(prefix="nuvio-art-")
    try:
        page, png = os.path.join(tmp, "page.html"), os.path.join(tmp, "shot.png")
        with open(page, "w", encoding="utf-8") as fh:
            fh.write(f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{svg}</body></html>')
        subprocess.run([browser(), "--headless", "--mute-audio", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                        "--no-default-browser-check", "--force-device-scale-factor=1", f"--user-data-dir={os.path.join(tmp, 'profile')}",
                        "--default-background-color=00000000", f"--window-size={size[0]},{size[1]}", f"--screenshot={png}",
                        "--virtual-time-budget=3000", "file:///" + page.replace(os.sep, "/")],
                       check=True, capture_output=True, timeout=120)
        im = Image.open(png)
        im.load()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if im.size != size: sys.exit(f"art: the browser drew {im.size}, not {size}")
    return im

def save(im, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if path.endswith(".webp"): im.convert("RGB").save(path, "WEBP", quality=86, method=6)
    else: im.save(path, "PNG", optimize=True)

def jobs(cols):
    """{local path: (kind, collection title, folder title)} for every tile and logo of ours the file points at."""
    out = {}
    for c in cols:
        for fo in c["folders"]:
            for key, kind in (("coverImageUrl", "tile"), ("titleLogoUrl", "logo")):
                m = OWN.search(fo.get(key) or "")
                if not m: continue
                job = (kind, c["title"], fo["title"])
                path = os.path.join(ROOT, "covers", *m.group(1).split("/"))
                assert out.setdefault(path, job) == job, f"two pictures for {path}"
    return out

def draw(path, job):
    kind, ctitle, card = job
    if ctitle not in STYLE:  # a service: its logo only
        assert kind == "logo", f"no tile style for {ctitle}"
        return save(logo(card).convert("LA"), path)  # grey and alpha: a palette would band the shadows
    save(shoot(tile_svg(ctitle, card), TILE) if kind == "tile" else shoot(logo_svg(ctitle, card), LOGO), path)

def render(cols):
    todo = jobs(cols)
    with cf.ThreadPoolExecutor(6) as ex:
        list(ex.map(draw, todo, todo.values()))
    sizes = [os.path.getsize(p) for p in todo]
    print(f"art: {len(todo)} files, largest {max(sizes) // 1024} KB, total {sum(sizes) // 1024} KB")
    return todo


# ---------- contact sheet (review only) ----------

def fetch_image(url, cache=os.path.join(tempfile.gettempdir(), "nuvio-art-cache")):
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, re.sub(r"[^A-Za-z0-9.]", "_", url[-60:]))
    if not os.path.exists(path):
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "nuvio-uk-art"}), timeout=30) as r:
            data = r.read()
        with open(path, "wb") as f: f.write(data)
    return Image.open(path).convert("RGB")

def local_or_fetch(url):
    m = OWN.search(url or "")
    if m: return Image.open(os.path.join(ROOT, "covers", *m.group(1).split("/")))
    return fetch_image(url)

def sheet(cols, path):
    """One line per card: tile, logo on near black, logo on near white, logo on its hero backdrop."""
    cw, ch, pad = 400, 225, 16
    folders = [(c["title"], f) for c in cols if c["title"] in STYLE for f in c["folders"]]
    per_line, cols_w = 2, 4 * (cw + pad) + pad
    lines = (len(folders) + per_line - 1) // per_line
    label_h = 30
    im = Image.new("RGB", (per_line * cols_w, lines * (ch + label_h + pad) + pad), (40, 40, 44))
    d = ImageDraw.Draw(im)
    small = font(20, 500)
    bright = Image.linear_gradient("L").rotate(90).resize((cw, ch)).point(lambda v: 205 + v // 6).convert("RGB")
    for n, (ctitle, f) in enumerate(folders):
        x0 = (n % per_line) * cols_w + pad
        y0 = (n // per_line) * (ch + label_h + pad) + pad
        d.text((x0, y0 + 4), f"{ctitle} / {f['title']} ({len(f['sources'])} rows)", font=small, fill=(230, 230, 230))
        y = y0 + label_h
        im.paste(local_or_fetch(f["coverImageUrl"]).convert("RGB").resize((cw, ch), Image.LANCZOS), (x0, y))
        # the logo slot: 220 x 100 dp, drawn at 1.6 px per dp inside a 16:9 cell, left aligned as in the hero
        slot = local_or_fetch(f["titleLogoUrl"]).convert("RGBA").resize((352, 160), Image.LANCZOS)
        hero = fetch_image(f["heroBackdropUrl"]).resize((cw, ch))
        for k, bg in enumerate((Image.new("RGB", (cw, ch), (14, 14, 18)), bright, hero)):
            cell = bg.copy()
            cell.paste(slot, (20, (ch - 160) // 2), slot)
            im.paste(cell, (x0 + (k + 1) * (cw + pad), y))
    im.save(path, optimize=True)
    print(f"contact sheet: {len(folders)} cards, {os.path.relpath(path, ROOT)}")

if __name__ == "__main__":
    cols = json.load(open(os.path.join(ROOT, "nuvio-collections.json"), encoding="utf-8"))
    render(cols)
    if "--sheet" in sys.argv: sheet(cols, os.path.join(HERE, "contact-sheet.png"))
