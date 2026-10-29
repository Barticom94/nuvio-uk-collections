"""Renders the Modern home art that nuvio-collections.json points at.

  python build/art.py [--sheet]   writes covers/tiles/*.webp (a landscape tile per folder outside Streaming
                                  Services) and covers/logos/*.png (a title logo per folder name); --sheet also writes
                                  build/contact-sheet.png for review (not committed)

build_uk.py runs it after writing the file. Every tile is our own art: a gradient in the collection's colours and the
folder name. Logos are the folder name in white with a soft shadow, on a transparent canvas with the aspect of the
hero's logo slot (ModernHomeHero: 100dp high, up to 220dp wide, ContentScale.Fit, aligned CenterStart), so every
logo shows at the same scale. The font is Outfit, under the SIL Open Font License 1.1 (build/fonts/OFL.txt).
"""
import colorsys, json, os, re, sys, tempfile, urllib.request
import numpy
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT = os.path.join(HERE, "fonts", "Outfit.ttf")
TILE = (960, 540)   # Modern's landscape tiles are 1.77:1; Coil scales down, never up
LOGO = (660, 300)   # the logo slot at 3 px per dp (Coil asks for 2 px per dp on a 1080p TV)
# Hues per collection, taken in turn so neighbouring tiles differ but a row keeps one family
HUES = {"Movies": [352, 20, 334, 6, 344, 28], "TV Shows": [212, 188, 232, 174, 200, 246],
        "Anime": [276, 302, 256, 320, 288, 242]}
OWN = re.compile(r"/covers/((?:tiles|logos)/[a-z0-9-]+\.(?:webp|png))$")


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

def rgb(h, s, l): return tuple(round(c * 255) for c in colorsys.hls_to_rgb((h % 360) / 360, l, s))

def tile(name, hue):
    w, h = TILE
    # Diagonal gradient from a deep tone of the hue to near black, with a soft light at the top right. The dark end
    # turns 20 degrees towards red, violet and blue (oranges turning the other way go olive).
    top, bottom = rgb(hue, 0.68, 0.44), rgb(hue - 20, 0.6, 0.11)
    rows, cols = numpy.mgrid[0:h, 0:w]
    grad = Image.fromarray((numpy.clip(cols / w * 0.45 + rows / h * 0.75, 0, 1) * 255).astype("uint8"))
    im = Image.composite(Image.new("RGB", TILE, bottom), Image.new("RGB", TILE, top), grad)
    glow = Image.new("L", TILE, 0)
    ImageDraw.Draw(glow).ellipse((w * 0.45, -h * 0.9, w * 1.45, h * 0.75), fill=120)
    im = Image.composite(Image.new("RGB", TILE, rgb(hue - 12, 0.75, 0.62)), im, glow.filter(ImageFilter.GaussianBlur(120)))
    f, lines = fit(name, w - 128, range(96, 59, -4), 3) or sys.exit(f"art: tile {name!r} does not fit")
    shadow = Image.new("L", TILE, 0)
    text = Image.new("L", TILE, 0)
    step = round(f.size * 1.08)
    y = h - 64 - step * (len(lines) - 1)
    for line in lines:
        ImageDraw.Draw(shadow).text((64, y + 4), line, font=f, fill=150, anchor="ls")
        ImageDraw.Draw(text).text((64, y), line, font=f, fill=255, anchor="ls")
        y += step
    im = Image.composite(Image.new("RGB", TILE, (0, 0, 0)), im, shadow.filter(ImageFilter.GaussianBlur(10)))
    return Image.composite(Image.new("RGB", TILE, (255, 255, 255)), im, text)

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

def save(im, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if path.endswith(".webp"): im.save(path, "WEBP", quality=88, method=6)
    else: im.convert("LA").save(path, "PNG", optimize=True)  # grey and alpha: a palette would band the shadows

def jobs(cols):
    """{local path: (kind, name, hue)} for every tile and logo of ours the file points at."""
    out = {}
    for c in cols:
        for i, fo in enumerate(c["folders"]):
            for key, kind in (("coverImageUrl", "tile"), ("titleLogoUrl", "logo")):
                m = OWN.search(fo.get(key) or "")
                if not m: continue
                hues = HUES.get(c["title"], [0])
                job = (kind, fo["title"], hues[i % len(hues)] if kind == "tile" else None)
                path = os.path.join(ROOT, "covers", *m.group(1).split("/"))
                assert out.setdefault(path, job)[:2] == job[:2], f"two names for {path}"
    return out

def render(cols):
    todo = jobs(cols)
    for path, (kind, name, hue) in todo.items():
        save(tile(name, hue) if kind == "tile" else logo(name), path)
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
    """One line per Modern folder: tile, logo on near black, logo on near white, logo on its hero backdrop."""
    cw, ch, pad = 400, 225, 16
    folders = [(c["title"], f) for c in cols if c["viewMode"] == "FOLLOW_LAYOUT" for f in c["folders"]]
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
        cover = local_or_fetch(f["coverImageUrl"]).convert("RGB").resize((cw, ch))
        im.paste(cover, (x0, y))
        logo_im = local_or_fetch(f["titleLogoUrl"]).convert("RGBA")
        # the slot: 220 x 100 dp, drawn at 1.6 px per dp inside a 16:9 cell, left aligned as in the hero
        slot = logo_im.resize((352, 160), Image.LANCZOS)
        hero = fetch_image(f["heroBackdropUrl"]).resize((cw, ch))
        for k, bg in enumerate((Image.new("RGB", (cw, ch), (14, 14, 18)), bright, hero)):
            cell = bg.copy()
            cell.paste(slot, (20, (ch - 160) // 2), slot)
            im.paste(cell, (x0 + (k + 1) * (cw + pad), y))
    im.save(path, optimize=True)
    print(f"contact sheet: {len(folders)} folders, {os.path.relpath(path, ROOT)}")

if __name__ == "__main__":
    cols = json.load(open(os.path.join(ROOT, "nuvio-collections.json"), encoding="utf-8"))
    render(cols)
    if "--sheet" in sys.argv: sheet(cols, os.path.join(HERE, "contact-sheet.png"))
