#!/usr/bin/env python3
"""
Tagdeem card renderer - typographic layout.

White ground, brand blue accents, no photography. One consistent design
for every organisation. Title is sized to the space available so it never
collides with the meta block.

Files expected in the repo:
    fonts/Tajawal-Bold.ttf
    fonts/Tajawal-Regular.ttf
    logos/page.png        your page logo, transparent PNG (optional)
"""
import os

from PIL import Image, ImageDraw, ImageFont, features

import translate

W = H = 1080
M = 78
FONTS = "fonts"
LOGOS = "logos"

BLUE  = (7, 74, 153)
DARK  = (23, 35, 54)
GREY  = (122, 134, 152)
RULE  = (223, 230, 240)
WHITE = (255, 255, 255)

TAGLINE = "شركاؤك في الوصول"


def _assert_raqm():
    if not features.check("raqm"):
        raise RuntimeError(
            "Pillow lacks RAQM - Arabic will not shape. "
            "Install libraqm (apt: libraqm0)."
        )


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _ar(d, xy, t, f, fill, anchor="ra"):
    d.text(xy, t, font=f, fill=fill, anchor=anchor,
           direction="rtl", language="ar", features=["kern", "liga"])


def _wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f, direction="rtl", language="ar") <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _text_fields(job):
    translate.enrich(job)
    return (job.get("org_ar") or job["org"],
            job.get("title_ar") or job["title"],
            job.get("location_ar") or job["location"],
            job.get("closing_ar") or job["closing"])


def build_card(job, out_path):
    _assert_raqm()
    org, title, loc, closing = _text_fields(job)

    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)

    # header: logo right, blue edge mark left
    logo_p = os.path.join(LOGOS, "page.png")
    if os.path.exists(logo_p):
        lg = Image.open(logo_p).convert("RGBA")
        lw = 200
        lg = lg.resize((lw, int(lg.height * lw / lg.width)))
        im.paste(lg, (W - M - lw, 34), lg)
    else:
        _ar(d, (W - M, 70), "تقديم للوظائف", _font("Tajawal-Bold.ttf", 46), BLUE)
    d.rectangle([0, 0, 16, 190], fill=BLUE)

    # double rule under the header
    d.rectangle([M, 196, W - M, 200], fill=BLUE)
    d.rectangle([M, 208, W - M, 210], fill=BLUE)

    fy = H - 96
    rule_y = fy - 160
    LABEL, ORG = 56, 70

    # size the title to the space between header and meta rule
    top = 300
    budget = rule_y - top - LABEL - ORG - 40
    for size in (104, 94, 84, 76, 68, 60, 52, 46):
        ft = _font("Tajawal-Bold.ttf", size)
        lines = _wrap(d, title, ft, W - 2 * M)
        if len(lines) <= 4 and len(lines) * (size + 20) <= budget:
            break
    lines = lines[:4]

    y = top
    _ar(d, (W - M, y), "فرصة عمل", _font("Tajawal-Bold.ttf", 34), BLUE)
    y += LABEL
    _ar(d, (W - M, y), org, _font("Tajawal-Regular.ttf", 42), GREY)
    y += ORG
    for ln in lines:
        _ar(d, (W - M, y), ln, ft, DARK)
        y += size + 20

    # meta above a double rule
    d.rectangle([M, rule_y, W - M, rule_y + 3], fill=RULE)
    d.rectangle([M, rule_y + 11, W - M, rule_y + 13], fill=RULE)
    my = rule_y + 34
    if loc:
        _ar(d, (W - M, my), f"الموقع:  {loc}", _font("Tajawal-Regular.ttf", 38), DARK)
        my += 58
    if closing:
        _ar(d, (W - M, my), f"آخر موعد للتقديم:  {closing}",
            _font("Tajawal-Bold.ttf", 38), BLUE)

    # footer with a double keyline above
    d.rectangle([0, fy - 14, W, fy - 11], fill=BLUE)
    d.rectangle([0, fy, W, H], fill=BLUE)
    _ar(d, (W - M, fy + 26), TAGLINE, _font("Tajawal-Bold.ttf", 34), WHITE)
    for i in range(3):
        cx = M + 26 + i * 44
        d.ellipse([cx - 8, fy + 40, cx + 8, fy + 56], fill=WHITE)

    im.save(out_path, "PNG", optimize=True)
    return out_path
    
