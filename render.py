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
    
