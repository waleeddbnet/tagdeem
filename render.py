#!/usr/bin/env python3
"""
Tagdeem card renderer.

Light layout: white ground, brand blue accents, photo band with a bright
blue tint, Arabic type. One consistent design for every organisation.

The photo band is the flexible element - text is measured first and the
photo takes whatever height remains. This is what prevents long titles
from colliding with the meta block.

Files expected in the repo:
    fonts/Tajawal-Bold.ttf
    fonts/Tajawal-Regular.ttf
    logos/page.png          your page logo, transparent PNG
    backgrounds/*.jpg       photos; <category>.jpg or default.jpg
"""
import glob
import os
import random

from PIL import Image, ImageDraw, ImageFont, ImageOps, features

import translate

W = H = 1080
M = 78
FONTS = "fonts"
LOGOS = "logos"
BACKGROUNDS = "backgrounds"

BLUE  = (7, 74, 153)
DARK  = (23, 35, 54)
GREY  = (122, 134, 152)
RULE  = (223, 230, 240)
WHITE = (255, 255, 255)

TAGLINE = "شركاؤك في الوصول"


def _assert_raqm():
    if not features.check("raqm"):
        raise RuntimeError(
            "Pillow lacks RAQM - Arabic will not shape correctly. "
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


# --------------------------------------------------------------------------
# Category detection -> background image choice
# --------------------------------------------------------------------------
CATEGORIES = [
    ("health",      ["nurse", "midwife", "doctor", "medical", "clinic", "health",
                     "pharmacist", "nutrition", "surgeon", "lab"]),
    ("education",   ["teacher", "education", "school", "training", "trainer",
                     "curriculum", "learning"]),
    ("it",          ["software", "developer", "cloud", "infrastructure", "network",
                     "database", "cyber", "ict", "data center", "devops",
                     "system", "technology", "digital"]),
    ("finance",     ["finance", "account", "budget", "audit", "ledger", "payroll",
                     "treasury", "tax", "cashier", "grants"]),
    ("logistics",   ["logistic", "supply chain", "warehouse", "storekeeper",
                     "procurement", "fleet", "transport", "inventory"]),
    ("driver",      ["driver", "mechanic", "vehicle"]),
    ("engineering", ["engineer", "technician", "electrician", "construction",
                     "workshop", "power", "maintenance"]),
    ("wash",        ["wash", "water", "sanitation", "hygiene", "borehole"]),
    ("agriculture", ["agricultur", "livelihood", "farm", "veterinary", "food security"]),
    ("protection",  ["protection", "gbv", "child", "psychosocial", "social worker",
                     "case management", "counsel", "legal"]),
    ("security",    ["security", "safety", "guard", "access"]),
    ("marketing",   ["marketing", "communication", "media", "creative", "design",
                     "brand", "advocacy"]),
    ("callcenter",  ["call center", "contact center", "customer service", "agent"]),
    ("hr",          ["human resources", "recruitment", "personnel", "talent"]),
    ("admin",       ["admin", "office", "clerk", "receptionist", "secretary",
                     "assistant", "coordinator", "data entry"]),
    ("management",  ["director", "manager", "head of", "chief", "lead", "officer"]),
]


def detect_category(job):
    hay = (job.get("title", "") + " " + job.get("category", "")).lower()
    for slug, keys in CATEGORIES:
        if any(k in hay for k in keys):
            return slug
    return None


def _bg_file(name):
    for ext in (".jpg", ".jpeg", ".png"):
        p = os.path.join(BACKGROUNDS, name + ext)
        if os.path.exists(p):
            return p
    return None


def _pick_background(job=None):
    if job:
        cat = detect_category(job)
        if cat:
            p = _bg_file(cat)
            if p:
                return p
    p = _bg_file("default")
    if p:
        return p
    files = glob.glob(os.path.join(BACKGROUNDS, "*.jpg")) + \
            glob.glob(os.path.join(BACKGROUNDS, "*.png"))
    return random.choice(files) if files else None


def _light_tint(img):
    """Bright airy blue tint. Lifts tones first so nothing reads as gloomy."""
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g, cutoff=3)
    g = g.point(lambda v: min(255, int(70 + v * 0.86)))
    return ImageOps.colorize(g, black=(31, 82, 150), mid=(126, 168, 214),
                             white=(255, 255, 255),
                             blackpoint=0, midpoint=128, whitepoint=255)


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

    # measure text first; the photo takes whatever height is left
    fy, TOP = H - 96, 210
    rule_y = fy - 150
    LABEL, ORG = 50, 62

    for size in (76, 70, 64, 58, 52, 46, 40):
        ft = _font("Tajawal-Bold.ttf", size)
        lines = _wrap(d, title, ft, W - 2 * M)[:3]
        text_h = LABEL + ORG + len(lines) * (size + 14)
        photo_h = rule_y - 24 - TOP - text_h - 54
        if photo_h >= 240:
            break
    photo_h = max(200, photo_h)

    # photo band
    bg = _pick_background(job)
    if bg:
        p = Image.open(bg).convert("RGB")
        r = max(W / p.width, photo_h / p.height)
        p = p.resize((int(p.width * r) + 1, int(p.height * r) + 1))
        im.paste(_light_tint(p.crop((0, 0, W, photo_h))), (0, TOP))
    else:
        d.rectangle([0, TOP, W, TOP + photo_h], fill=(214, 228, 244))
    d.rectangle([0, TOP - 4, W, TOP], fill=BLUE)
    d.rectangle([0, TOP + photo_h, W, TOP + photo_h + 4], fill=BLUE)

    # content
    y = TOP + photo_h + 54
    _ar(d, (W - M, y), "فرصة عمل", _font("Tajawal-Bold.ttf", 32), BLUE)
    y += LABEL
    _ar(d, (W - M, y), org, _font("Tajawal-Regular.ttf", 38), GREY)
    y += ORG
    for ln in lines:
        _ar(d, (W - M, y), ln, ft, DARK)
        y += size + 14

    # meta
    d.rectangle([M, rule_y, W - M, rule_y + 2], fill=RULE)
    my = rule_y + 22
    if loc:
        _ar(d, (W - M, my), f"الموقع:  {loc}", _font("Tajawal-Regular.ttf", 36), DARK)
        my += 54
    if closing:
        _ar(d, (W - M, my), f"آخر موعد للتقديم:  {closing}",
            _font("Tajawal-Bold.ttf", 36), BLUE)

    # footer
    d.rectangle([0, fy, W, H], fill=BLUE)
    _ar(d, (W - M, fy + 26), TAGLINE, _font("Tajawal-Bold.ttf", 34), WHITE)
    for i in range(3):
        cx = M + 26 + i * 44
        d.ellipse([cx - 8, fy + 40, cx + 8, fy + 56], fill=WHITE)

    im.save(out_path, "PNG", optimize=True)
    return out_path
