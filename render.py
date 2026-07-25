#!/usr/bin/env python3
"""
Image card renderer. Two layouts, auto-selected:

  * logo present  -> branded card: brand color band + org logo + Arabic text
  * no logo        -> background overlay: pick a bg from backgrounds/, dim it,
                      lay the same Arabic text on top

Both share one text block, so wording is identical regardless of layout.
Requires Pillow built with RAQM (HarfBuzz + FriBidi) for correct Arabic shaping.

Files expected in repo:
  fonts/Tajawal-Bold.ttf
  fonts/Tajawal-Regular.ttf
  logos/<org_slug>.png       (optional, per org)
  backgrounds/*.jpg          (optional, any number; used when no logo)
"""
import glob
import os
import random

import translate

from PIL import Image, ImageDraw, ImageFont, features

W, H = 1200, 630
MARGIN = 80
FONTS = "fonts"
LOGOS = "logos"
BACKGROUNDS = "backgrounds"

# brand palette, deterministic per org so a given org always gets one color
PALETTE = [
    (11, 79, 108),    # deep teal
    (23, 55, 94),     # navy
    (91, 33, 50),     # maroon
    (46, 74, 38),     # forest
    (74, 47, 89),     # plum
    (140, 74, 20),    # ochre
]
FG = (255, 255, 255)
ACCENT = (240, 200, 90)


def _assert_raqm():
    if not features.check("raqm"):
        raise RuntimeError(
            "Pillow lacks RAQM - Arabic will not shape. "
            "Install libraqm (apt: libraqm0) or a Pillow wheel with RAQM."
        )


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _ar(draw, xy, text, font, fill, anchor="ra"):
    """Draw one line of Arabic, right-aligned by default."""
    draw.text(xy, text, font=font, fill=fill, anchor=anchor,
              direction="rtl", language="ar", features=["kern", "liga"])


def _color_for(slug):
    return PALETTE[hash(slug) % len(PALETTE)]


def _wrap_rtl(draw, text, font, max_w):
    """Greedy word wrap that respects pixel width."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font, direction="rtl", language="ar") <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _text_fields(job):
    """Arabic strings, preferring hand-written overrides from manual.json."""
    translate.enrich(job)
    title = job.get("title_ar") or job["title"]
    org = job.get("org_ar") or job["org"]
    loc = job.get("location_ar") or job["location"]
    closing = job.get("closing_ar") or job["closing"]
    return org, title, loc, closing


def _paste_logo(canvas, slug, box):
    path = os.path.join(LOGOS, f"{slug}.png")
    if not slug or not os.path.exists(path):
        return False
    logo = Image.open(path).convert("RGBA")
    bx, by, bw, bh = box
    ratio = min(bw / logo.width, bh / logo.height)
    logo = logo.resize((int(logo.width * ratio), int(logo.height * ratio)))
    canvas.paste(logo, (bx + (bw - logo.width) // 2,
                        by + (bh - logo.height) // 2), logo)
    return True


def _pick_background():
    files = glob.glob(os.path.join(BACKGROUNDS, "*.jpg")) + \
            glob.glob(os.path.join(BACKGROUNDS, "*.png"))
    return random.choice(files) if files else None


def _base_card(slug):
    """Solid brand color with a darker header band."""
    color = _color_for(slug)
    img = Image.new("RGB", (W, H), color)
    d = ImageDraw.Draw(img)
    darker = tuple(int(c * 0.72) for c in color)
    d.rectangle([0, 0, W, 150], fill=darker)
    d.rectangle([0, H - 12, W, H], fill=ACCENT)
    return img


def _base_background():
    path = _pick_background()
    if not path:
        return None
    img = Image.open(path).convert("RGB").resize((W, H))
    # dim for text legibility
    overlay = Image.new("RGB", (W, H), (10, 15, 25))
    img = Image.blend(img, overlay, 0.55)
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - 12, W, H], fill=ACCENT)
    return img


def build_card(job, out_path):
    _assert_raqm()
    org, title, loc, closing = _text_fields(job)
    slug = job.get("org_slug", "")

    has_logo = os.path.exists(os.path.join(LOGOS, f"{slug}.png")) if slug else False

    if has_logo:
        img = _base_card(slug)
    else:
        img = _base_background() or _base_card(slug)

    d = ImageDraw.Draw(img)
    f_org = _font("Tajawal-Bold.ttf", 46)
    f_title = _font("Tajawal-Bold.ttf", 62)
    f_meta = _font("Tajawal-Regular.ttf", 40)
    f_tag = _font("Tajawal-Bold.ttf", 34)

    right = W - MARGIN

    # header: "فرصة عمل" tag + org name
    _ar(d, (right, 45), "فرصة عمل", f_tag, ACCENT)
    if has_logo:
        _paste_logo(img, slug, (MARGIN, 30, 220, 90))

    _ar(d, (right, 175), org, f_org, FG)

    # title, wrapped
    y = 275
    for line in _wrap_rtl(d, title, f_title, W - 2 * MARGIN)[:2]:
        _ar(d, (right, y), line, f_title, FG)
        y += 78

    # meta block
    y = max(y + 20, 470)
    if loc:
        _ar(d, (right, y), f"الموقع: {loc}", f_meta, FG)
        y += 55
    _ar(d, (right, y), f"آخر موعد: {closing}", f_meta, ACCENT)

    img.save(out_path, "PNG", optimize=True)
    return out_path


if __name__ == "__main__":
    # local smoke test
    jobs = [
        {"org": "UNHCR", "org_ar": "المفوضية السامية للأمم المتحدة لشؤون اللاجئين",
         "title": "Senior Government Liaison Assistant",
         "title_ar": "مساعد أول لشؤون الاتصال الحكومي (فئة الخدمات العامة) ر.ع-5",
         "location": "Khartoum", "location_ar": "الخرطوم، السودان",
         "closing": "29 يوليو 2026", "org_slug": "unhcr"},
        {"org": "World Food Programme", "org_ar": "برنامج الأغذية العالمي",
         "title": "Finance Officer", "title_ar": "موظف شؤون مالية — للسودانيين فقط",
         "location": "Khartoum", "location_ar": "الخرطوم، السودان",
         "closing": "4 أغسطس 2026", "org_slug": "wfp"},
    ]
    for i, j in enumerate(jobs):
        p = build_card(j, f"sample_{i}.png")
        print("wrote", p)
     
