#!/usr/bin/env python3
"""
Tagdeem card renderer - Sudanese heritage template.

The template PNG carries the page logo, ornament borders, the location and
deadline labels with their icons, and the footer bar. This module composites
only the job-specific text onto it, plus an org logo when one is available.

To change the whole design, replace template.png - no code change needed.
Text positions are the constants below.

Files expected in the repo:
    template.png              1024x1024 background
    fonts/Tajawal-Bold.ttf
    fonts/Tajawal-Regular.ttf
    logos/<slug>.png          optional org logos, transparent PNG
"""
import os
import re

from PIL import Image, ImageDraw, ImageFont, features

import translate

W = H = 1024
TEMPLATE = "template.png"
FONTS = "fonts"
LOGOS = "logos"

BLUE = (8, 74, 152)
INK  = (38, 44, 58)
GREY = (110, 112, 110)

# --- layout constants, tuned to the template artwork -----------------------
CX = 512               # centre axis for the content stack
MAXW = 700             # text wrap width
TOP, BOTTOM = 216, 545  # vertical band available for the content stack
BADGE_R = 52

LOC_VALUE_X, LOC_Y = 742, 570      # values sit left of the template's labels
CLOSE_VALUE_X, CLOSE_Y = 556, 652
# ---------------------------------------------------------------------------


def _assert_raqm():
    if not features.check("raqm"):
        raise RuntimeError(
            "Pillow lacks RAQM - Arabic will not shape. "
            "Install libraqm (apt: libraqm0)."
        )


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _ar(d, xy, t, f, fill, anchor="ma"):
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


def _logo_path(org_en, slug):
    cands = [c for c in (slug,
                         re.sub(r"[^a-z0-9]", "", (org_en or "").lower())[:24]) if c]
    for cand in cands:
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            p = os.path.join(LOGOS, cand + ext)
            if os.path.exists(p):
                return p
    return None


def _paste_logo(im, path, cx, cy, r=BADGE_R):
    lg = Image.open(path).convert("RGBA")
    k = min((r * 2) / lg.width, (r * 2) / lg.height)
    lg = lg.resize((max(1, int(lg.width * k)), max(1, int(lg.height * k))))
    im.paste(lg, (cx - lg.width // 2, cy - lg.height // 2), lg)


def _text_fields(job):
    translate.enrich(job)
    return (job.get("org_ar") or job["org"],
            job.get("title_ar") or job["title"],
            job.get("location_ar") or job["location"],
            job.get("closing_ar") or job["closing"])


def build_card(job, out_path):
    _assert_raqm()
    org, title, loc, closing = _text_fields(job)

    im = Image.open(TEMPLATE).convert("RGB")
    d = ImageDraw.Draw(im)

    f_lab = _font("Tajawal-Bold.ttf", 40)
    f_org = _font("Tajawal-Bold.ttf", 36)
    org_lines = _wrap(d, org, f_org, MAXW)[:2]

    logo = _logo_path(job.get("org", ""), job.get("org_slug", ""))
    badge_h = (BADGE_R * 2 + 18) if logo else 0

    fixed = badge_h + 52 + len(org_lines) * 46 + 10
    budget = BOTTOM - TOP - fixed

    for size in (62, 56, 50, 44, 38, 34):
        f_ti = _font("Tajawal-Bold.ttf", size)
        lines = _wrap(d, title, f_ti, MAXW)
        if len(lines) <= 3 and len(lines) * (size + 10) <= budget:
            break
    lines = lines[:3]

    stack = fixed + len(lines) * (size + 10)
    top = TOP + max(0, (BOTTOM - TOP - stack) // 2)

    if logo:
        _paste_logo(im, logo, CX, top + BADGE_R)
        d = ImageDraw.Draw(im)
    y = top + badge_h

    _ar(d, (CX, y), "فرصة عمل", f_lab, GREY)
    y += 52
    for ln in org_lines:
        _ar(d, (CX, y), ln, f_org, BLUE)
        y += 46
    y += 10
    for ln in lines:
        _ar(d, (CX, y), ln, f_ti, INK)
        y += size + 10

    # values follow the labels already printed on the template
    _ar(d, (LOC_VALUE_X, LOC_Y), loc,
        _font("Tajawal-Regular.ttf", 38), INK, anchor="ra")
    if closing:
        _ar(d, (CLOSE_VALUE_X, CLOSE_Y), closing,
            _font("Tajawal-Bold.ttf", 38), BLUE, anchor="ra")

    im.save(out_path, "PNG", optimize=True)
    return out_path
    
