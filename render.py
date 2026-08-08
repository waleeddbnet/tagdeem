#!/usr/bin/env python3
"""
Tagdeem card renderer - fully generated, no background images required.

Every card is drawn from code. Palette, motif, frame style, label and call to
action are chosen deterministically from the job's fingerprint, so the same
job always looks the same while consecutive posts differ. 8 palettes x 5
motifs x 5 frame styles.

To adjust the look, edit theme.PALETTES / theme.MOTIFS or the frame() styles.

Files expected in the repo:
    fonts/Tajawal-Bold.ttf
    fonts/Tajawal-Regular.ttf
    logos/page.png        optional, your page mark
"""
import os

from PIL import Image, ImageDraw, ImageFont, features

import theme
import translate

FONTS = "fonts"
LOGOS = "logos"
CARD_W, CARD_H = 1080, 1350          # portrait 4:5 - more feed space than square


def _assert_raqm():
    if not features.check("raqm"):
        raise RuntimeError(
            "Pillow lacks RAQM - Arabic will not shape. "
            "Install libraqm (apt: libraqm0)."
        )


def _text_fields(job):
    translate.enrich(job)
    return job


def F(n, s): return ImageFont.truetype(f"{FONTS}/{n}", s)


def ar(d, xy, t, f, fill, anchor="ma"):
    d.text(xy, t, font=f, fill=fill, anchor=anchor,
           direction="rtl", language="ar", features=["kern", "liga"])


def wrap(d, text, f, maxw):
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


def _tint(c, bg, k):
    return tuple(int(bg[i] + (c[i] - bg[i]) * k) for i in range(3))


def frame(im, d, W, H, style, pal, seed):
    bg, panel, ink, accent, muted = pal
    M = int(W * 0.055)

    if style == 0:                       # full keyline frame
        d.rectangle([M, M, W - M, H - M], outline=accent, width=4)
        d.rectangle([M + 12, M + 12, W - M - 12, H - M - 12],
                    outline=_tint(accent, bg, 0.35), width=2)

    elif style == 1:                     # corner brackets
        L = int(W * 0.13)
        for cx, cy, sx, sy in ((M, M, 1, 1), (W - M, M, -1, 1),
                               (M, H - M, 1, -1), (W - M, H - M, -1, -1)):
            d.line([(cx, cy), (cx + sx * L, cy)], fill=accent, width=6)
            d.line([(cx, cy), (cx, cy + sy * L)], fill=accent, width=6)

    elif style == 2:                     # side band with motif
        BW = int(W * 0.10)
        d.rectangle([0, 0, BW, H], fill=accent)
        fn = theme.pick(f"{seed}:motif", theme.MOTIFS)
        for cy in range(-30, H + 60, 72):
            fn(d, BW // 2, cy, 22, _tint((255, 255, 255), accent, 0.30), 2)
        d.rectangle([BW, 0, BW + 5, H], fill=_tint(accent, bg, 0.45))

    elif style == 3:                     # top and bottom rules
        d.rectangle([0, 0, W, int(H * 0.012)], fill=accent)
        d.rectangle([M, int(H * 0.175), W - M, int(H * 0.175) + 4], fill=accent)
        d.rectangle([M, int(H * 0.175) + 12, W - M, int(H * 0.175) + 14],
                    fill=_tint(accent, bg, 0.4))

    else:                                # arch panel
        d.rounded_rectangle([M, int(H * 0.14), W - M, H - M],
                            radius=int(W * 0.09), fill=panel,
                            outline=accent, width=3)
    return M


def build_card(job, out_path, W=CARD_W, H=CARD_H):
    _assert_raqm()
    _text_fields(job)
    out = out_path
    seed = job.get("fp") or job.get("key") or job.get("title", "x")
    pal = theme.pick(f"{seed}:pal", theme.PALETTES)
    bg, panel, ink, accent, muted = pal
    style = theme.variant(seed, "frame", 5)

    im = theme.texture((W, H), seed, _tint(ink, bg, 0.10), bg)
    d = ImageDraw.Draw(im)

    # content panel keeps text off the texture
    PX = int(W * 0.10)
    PY0, PY1 = int(H * 0.20), int(H * 0.74)
    if style != 4:
        d.rounded_rectangle([PX, PY0, W - PX, PY1], radius=int(W * 0.035),
                            fill=panel)
    M = frame(im, d, W, H, style, pal, seed)
    d = ImageDraw.Draw(im)

    CX = W // 2 + (int(W * 0.05) if style == 2 else 0)
    MAXW = int(W * 0.72)

    # header: page mark
    pg = os.path.join(LOGOS, "page.png")
    if os.path.exists(pg):
        lg = Image.open(pg).convert("RGBA")
        lw = int(W * 0.20)
        lg = lg.resize((lw, int(lg.height * lw / lg.width)))
        im.paste(lg, (CX - lw // 2, int(H * 0.045)), lg)
    else:
        ar(d, (CX, int(H * 0.05)), "تقديم للوظائف",
           F("Tajawal-Bold.ttf", int(W * 0.042)), accent)

    kind = job.get("kind", "job")
    label = {"job": "فرصة عمل", "course": "فرصة تدريب",
             "volunteer": "فرصة تطوّع"}.get(kind, "فرصة عمل")

    org = job.get("org_ar") or job.get("org", "")
    title = job.get("title_ar") or job.get("title", "")
    loc = job.get("location_ar") or job.get("location", "")
    close = job.get("closing_ar") or job.get("closing", "")

    y = PY0 + int(H * 0.035)
    ar(d, (CX, y), label, F("Tajawal-Bold.ttf", int(W * 0.033)), accent)
    y += int(H * 0.042)

    f_org = F("Tajawal-Regular.ttf", int(W * 0.034))
    for ln in wrap(d, org, f_org, MAXW)[:2]:
        ar(d, (CX, y), ln, f_org, muted)
        y += int(H * 0.032)
    y += int(H * 0.012)

    budget = PY1 - y - int(H * 0.16)
    for sz in (0.062, 0.055, 0.048, 0.042, 0.036):
        f_ti = F("Tajawal-Bold.ttf", int(W * sz))
        lines = wrap(d, title, f_ti, MAXW)
        if len(lines) <= 3 and len(lines) * (f_ti.size + 12) <= budget:
            break
    for ln in lines[:3]:
        ar(d, (CX, y), ln, f_ti, ink)
        y += f_ti.size + 12

    # meta rule + values
    y = PY1 - int(H * 0.115)
    d.rectangle([PX + 40, y, W - PX - 40, y + 2], fill=_tint(muted, panel, 0.5))
    y += int(H * 0.018)
    f_m = F("Tajawal-Regular.ttf", int(W * 0.030))
    if loc:
        ar(d, (CX, y), f"الموقع:  {loc}", f_m, ink)
        y += int(H * 0.034)
    if close:
        ar(d, (CX, y), f"آخر موعد:  {close}",
           F("Tajawal-Bold.ttf", int(W * 0.030)), accent)

    # CTA pill
    cta = {"job": "قدّم الآن", "course": "سجّل الآن",
           "volunteer": "تطوّع الآن"}.get(kind, "قدّم الآن")
    f_c = F("Tajawal-Bold.ttf", int(W * 0.034))
    tw = d.textlength(cta, font=f_c, direction="rtl", language="ar")
    pw, ph = tw + int(W * 0.075), f_c.size + int(H * 0.028)
    by = int(H * 0.795)
    d.rounded_rectangle([CX - pw / 2, by, CX + pw / 2, by + ph],
                        radius=ph / 2, fill=accent)
    ar(d, (CX, by + int(H * 0.014)), cta, f_c, (255, 255, 255))

    # footer
    fh = int(H * 0.062)
    d.rectangle([0, H - fh, W, H], fill=accent)
    ar(d, (CX, H - fh + int(fh * 0.26)), "شركاؤك في الوصول",
       F("Tajawal-Bold.ttf", int(W * 0.030)), (255, 255, 255))

    im.save(out)
    return out


# ---------------------------------------------------------------------------
# Digest card: one image listing many open vacancies.
# ---------------------------------------------------------------------------
def build_digest(jobs, out_path, total=None, W=CARD_W, H=CARD_H):
    _assert_raqm()
    n = len(jobs)
    total = total or n
    seed = f"digest-{total}-{n}"

    pal = theme.pick(f"{seed}:pal", theme.PALETTES)
    bg, panel, ink, accent, muted = pal

    im = theme.texture((W, H), seed, _tint(ink, bg, 0.10), bg)
    d = ImageDraw.Draw(im)

    PX = int(W * 0.055)
    PY0, PY1 = int(H * 0.135), int(H * 0.905)
    d.rounded_rectangle([PX, PY0, W - PX, PY1], radius=int(W * 0.035), fill=panel)
    d.rectangle([0, 0, W, 6], fill=accent)

    CX = W // 2

    pg = os.path.join(LOGOS, "page.png")
    if os.path.exists(pg):
        lg = Image.open(pg).convert("RGBA")
        lw = int(W * 0.17)
        lg = lg.resize((lw, int(lg.height * lw / lg.width)))
        im.paste(lg, (CX - lw // 2, int(H * 0.020)), lg)

    y = PY0 + int(H * 0.026)
    ar(d, (CX, y), "وظائف شاغرة", F("Tajawal-Bold.ttf", 34), accent)
    y += 52
    ar(d, (CX, y), f"{total} فرصة عمل متاحة الآن",
       F("Tajawal-Bold.ttf", 50), ink)
    y += 74
    d.rectangle([PX + 60, y, W - PX - 60, y + 3], fill=_tint(accent, panel, 0.5))
    y += 26

    # size rows to the space available
    avail = (PY1 - int(H * 0.085)) - y
    step = max(46, min(74, avail // max(1, n)))
    f_t = F("Tajawal-Bold.ttf", max(22, min(32, int(step * 0.46))))
    f_m = F("Tajawal-Regular.ttf", max(18, min(24, int(step * 0.33))))
    RX = W - PX - 46

    for j in jobs:
        org = j.get("org_ar") or j.get("org", "")
        title = j.get("title_ar") or j.get("title", "")
        close = j.get("closing_ar") or j.get("closing", "")

        maxw = W - 2 * PX - 120
        while d.textlength(title, font=f_t, direction="rtl",
                           language="ar") > maxw and len(title) > 8:
            title = title[:-2]
        if title != (j.get("title_ar") or j.get("title", "")):
            title += "…"

        cy = y + f_t.size * 0.55
        d.ellipse([RX + 10, cy - 7, RX + 24, cy + 7], fill=accent)
        ar(d, (RX, y), title, f_t, ink, anchor="ra")

        meta = f"{org} — {close}" if close else org
        while d.textlength(meta, font=f_m, direction="rtl",
                           language="ar") > maxw and len(meta) > 8:
            meta = meta[:-2]
        ar(d, (RX, y + f_t.size + 4), meta, f_m, muted, anchor="ra")
        y += step

    if total > n:
        y += 6
        ar(d, (CX, y), f"و{total - n} فرصة أخرى في التعليقات",
           F("Tajawal-Bold.ttf", 28), accent)

    ar(d, (CX, PY1 - int(H * 0.045)), "الروابط في التعليقات",
       F("Tajawal-Bold.ttf", 30), accent)

    fh = int(H * 0.062)
    d.rectangle([0, H - fh, W, H], fill=accent)
    ar(d, (CX, H - fh + int(fh * 0.26)), "شركاؤك في الوصول",
       F("Tajawal-Bold.ttf", 30), (255, 255, 255))

    im.save(out_path, "PNG", optimize=True)
    return out_path


# ---------------------------------------------------------------------------
# Tip card: advice, checklists and questions. Not a vacancy.
# ---------------------------------------------------------------------------
KIND_LABEL = {
    "tip": "نصيحة",
    "steps": "خطوات عملية",
    "mistake": "أخطاء شائعة",
    "fact": "معلومة مفيدة",
    "question": "سؤال لكم",
}


def build_tip(tip, out_path, W=CARD_W, H=CARD_H):
    """tip: dict from tips.TIPS"""
    _assert_raqm()
    kind = tip.get("kind", "tip")
    seed = tip["title"]

    pal = theme.pick(f"{seed}:pal", theme.PALETTES)
    bg, panel, ink, accent, muted = pal

    im = theme.texture((W, H), seed, _tint(ink, bg, 0.10), bg)
    d = ImageDraw.Draw(im)

    PX = int(W * 0.06)
    PY0, PY1 = int(H * 0.145), int(H * 0.895)
    d.rounded_rectangle([PX, PY0, W - PX, PY1], radius=int(W * 0.035), fill=panel)
    d.rectangle([0, 0, W, 6], fill=accent)

    CX = W // 2

    pg = os.path.join(LOGOS, "page.png")
    if os.path.exists(pg):
        lg = Image.open(pg).convert("RGBA")
        lw = int(W * 0.17)
        lg = lg.resize((lw, int(lg.height * lw / lg.width)))
        im.paste(lg, (CX - lw // 2, int(H * 0.022)), lg)

    y = PY0 + int(H * 0.030)
    ar(d, (CX, y), KIND_LABEL.get(kind, "نصيحة"),
       F("Tajawal-Bold.ttf", 34), accent)
    y += 56

    # headline, wrapped
    for sz in (58, 52, 46, 40):
        f_h = F("Tajawal-Bold.ttf", sz)
        hl = wrap(d, tip["title"], f_h, W - 2 * PX - 80)
        if len(hl) <= 2:
            break
    for ln in hl[:2]:
        ar(d, (CX, y), ln, f_h, ink)
        y += sz + 10
    y += 18

    d.rectangle([PX + 70, y, W - PX - 70, y + 3], fill=_tint(accent, panel, 0.5))
    y += 34

    # body rows, numbered for steps, bulleted otherwise
    rows = tip["body"]
    avail = (PY1 - int(H * 0.09)) - y
    step = max(60, min(96, avail // max(1, len(rows))))
    f_b = F("Tajawal-Regular.ttf", max(26, min(36, int(step * 0.40))))
    RX = W - PX - 56

    for i, b in enumerate(rows, 1):
        cy = y + f_b.size * 0.52
        if kind == "steps":
            d.ellipse([RX + 8, cy - 21, RX + 50, cy + 21], fill=accent)
            d.text((RX + 29, cy), str(i), font=F("Tajawal-Bold.ttf", 26),
                   fill=(255, 255, 255), anchor="mm")
            tx = RX - 12
        elif kind == "mistake":
            d.line([(RX + 14, cy - 11), (RX + 38, cy + 11)], fill=accent, width=5)
            d.line([(RX + 38, cy - 11), (RX + 14, cy + 11)], fill=accent, width=5)
            tx = RX - 6
        else:
            d.ellipse([RX + 18, cy - 9, RX + 36, cy + 9], fill=accent)
            tx = RX - 2

        line = b
        while d.textlength(line, font=f_b, direction="rtl",
                           language="ar") > (W - 2 * PX - 130) and len(line) > 8:
            line = line[:-2]
        if line != b:
            line += "…"
        ar(d, (tx, y), line, f_b, ink, anchor="ra")
        y += step

    fh = int(H * 0.062)
    d.rectangle([0, H - fh, W, H], fill=accent)
    ar(d, (CX, H - fh + int(fh * 0.26)), "شركاؤك في الوصول",
       F("Tajawal-Bold.ttf", 30), (255, 255, 255))

    im.save(out_path, "PNG", optimize=True)
    return out_path


# ---------------------------------------------------------------------------
# Photo tip card: a documentary photo with the advice laid over a dark scrim.
# Falls back to build_tip (drawn card) when no photo exists for the category.
# ---------------------------------------------------------------------------
PHOTOS = "photos"


def _photo_path(name):
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = os.path.join(PHOTOS, str(name) + ext)
        if os.path.exists(p):
            return p
    return None


def _scrim(im, W, H, top_strength=0.90, dark=(8, 14, 26)):
    """Darken from the top so white text reads over any photo."""
    sc = Image.new("L", (1, H))
    px = sc.load()
    for y in range(H):
        q = 1 - (y / H)
        px[0, y] = int(255 * min(1.0, max(0.0, (q - 0.10) / 0.65)) ** 1.1
                       * top_strength)
    sc = sc.resize((W, H))
    return Image.composite(Image.new("RGB", (W, H), dark), im, sc)


def build_photo_tip(tip, out_path, W=CARD_W, H=CARD_H):
    """tip: dict from tips.TIPS, optionally carrying a 'photo' key."""
    _assert_raqm()
    path = _photo_path(tip.get("photo") or "default")
    if not path:
        return build_tip(tip, out_path, W, H)

    kind = tip.get("kind", "tip")
    accent = (7, 74, 153)
    gold = (212, 180, 110)
    white = (255, 255, 255)

    p = Image.open(path).convert("RGB")
    r = max(W / p.width, H / p.height)
    p = p.resize((max(1, int(p.width * r)), max(1, int(p.height * r))),
                 Image.LANCZOS)
    left = (p.width - W) // 2
    im = p.crop((left, 0, left + W, H))
    im = _scrim(im, W, H)
    d = ImageDraw.Draw(im)

    CX = W // 2
    M = int(W * 0.075)

    pg = os.path.join(LOGOS, "page.png")
    if os.path.exists(pg):
        lg = Image.open(pg).convert("RGBA")
        lw = int(W * 0.15)
        lg = lg.resize((lw, int(lg.height * lw / lg.width)))
        solid = Image.new("RGBA", lg.size, (255, 255, 255, 255))
        solid.putalpha(lg.split()[3])
        im.paste(solid, (CX - lw // 2, int(H * 0.030)), solid)

    y = int(H * 0.105)
    ar(d, (CX, y), KIND_LABEL.get(kind, "نصيحة"),
       F("Tajawal-Bold.ttf", 34), gold)
    y += 54

    for sz in (56, 50, 44, 38):
        f_h = F("Tajawal-Bold.ttf", sz)
        hl = wrap(d, tip["title"], f_h, W - 2 * M)
        if len(hl) <= 2:
            break
    for ln in hl[:2]:
        ar(d, (CX, y), ln, f_h, white)
        y += sz + 8
    y += 22

    rows = tip["body"]
    f_b = F("Tajawal-Regular.ttf", 34 if len(rows) <= 5 else 30)
    step = f_b.size + 42
    RX = W - M

    for i, b in enumerate(rows, 1):
        cy = y + f_b.size * 0.52
        if kind == "steps":
            d.ellipse([RX - 42, cy - 21, RX, cy + 21], fill=accent)
            d.text((RX - 21, cy), str(i), font=F("Tajawal-Bold.ttf", 26),
                   fill=white, anchor="mm")
        elif kind == "mistake":
            d.line([(RX - 36, cy - 11), (RX - 12, cy + 11)], fill=gold, width=5)
            d.line([(RX - 12, cy - 11), (RX - 36, cy + 11)], fill=gold, width=5)
        else:
            d.ellipse([RX - 32, cy - 9, RX - 14, cy + 9], fill=gold)

        line = b
        while d.textlength(line, font=f_b, direction="rtl",
                           language="ar") > (W - 2 * M - 70) and len(line) > 8:
            line = line[:-2]
        if line != b:
            line += "…"
        ar(d, (RX - 62, y), line, f_b, white, anchor="ra")
        y += step

    fh = int(H * 0.062)
    d.rectangle([0, H - fh, W, H], fill=accent)
    ar(d, (CX, H - fh + int(fh * 0.26)), "شركاؤك في الوصول",
       F("Tajawal-Bold.ttf", 30), white)

    im.save(out_path, "PNG", optimize=True)
    return out_path
    
