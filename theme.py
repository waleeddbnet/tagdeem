"""Procedural design system: palettes, motifs, frames. Deterministic per job."""
import hashlib
import math
from PIL import Image, ImageDraw, ImageFilter

# --- palettes: (bg, panel, ink, accent, muted) -----------------------------
PALETTES = [
    ((248, 244, 236), (255, 255, 255), (26, 42, 66), (7, 74, 153), (128, 136, 150)),   # brand blue
    ((246, 240, 228), (255, 253, 248), (44, 32, 26), (176, 92, 42), (132, 116, 100)),  # terracotta
    ((240, 244, 242), (255, 255, 255), (18, 44, 42), (14, 110, 98), (110, 128, 124)),  # teal
    ((245, 241, 232), (255, 254, 250), (38, 30, 46), (108, 58, 122), (128, 118, 136)), # aubergine
    ((243, 245, 240), (255, 255, 255), (24, 42, 26), (32, 100, 56), (114, 130, 116)),  # forest
    ((248, 243, 233), (255, 254, 249), (48, 26, 30), (150, 40, 56), (140, 116, 118)),  # burgundy
    ((246, 243, 235), (255, 255, 252), (36, 34, 28), (170, 124, 34), (138, 130, 112)), # ochre
    ((242, 243, 246), (255, 255, 255), (22, 30, 44), (40, 74, 128), (120, 128, 142)),  # slate blue
]


def pick(seed, seq):
    h = int(hashlib.sha1(str(seed).encode()).hexdigest()[:8], 16)
    return seq[h % len(seq)]


def variant(seed, salt, n):
    h = int(hashlib.sha1(f"{seed}:{salt}".encode()).hexdigest()[:8], 16)
    return h % n


# --- motifs ----------------------------------------------------------------
def m_star(d, cx, cy, r, col, w):
    p = []
    for i in range(16):
        a = math.pi / 8 * i
        rr = r if i % 2 == 0 else r * 0.45
        p.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(p, outline=col, width=w)


def m_diamond(d, cx, cy, r, col, w):
    for k in (1.0, 0.6, 0.28):
        s = r * k
        d.polygon([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)],
                  outline=col, width=w)


def m_zigzag(d, cx, cy, r, col, w):
    for off in (-r * 0.5, 0, r * 0.5):
        pts = []
        for i in range(5):
            pts.append((cx - r + i * r / 2, cy + off + (r * 0.28 if i % 2 else -r * 0.28)))
        d.line(pts, fill=col, width=w)


def m_arch(d, cx, cy, r, col, w):
    d.arc([cx - r, cy - r, cx + r, cy + r], 180, 360, fill=col, width=w)
    d.line([(cx - r, cy), (cx - r, cy + r * 0.7)], fill=col, width=w)
    d.line([(cx + r, cy), (cx + r, cy + r * 0.7)], fill=col, width=w)


def m_cross(d, cx, cy, r, col, w):
    d.line([(cx - r, cy), (cx + r, cy)], fill=col, width=w)
    d.line([(cx, cy - r), (cx, cy + r)], fill=col, width=w)
    s = r * 0.5
    d.polygon([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)],
              outline=col, width=w)


MOTIFS = [m_star, m_diamond, m_zigzag, m_arch, m_cross]


def texture(size, seed, col, bg):
    """Faint tiled motif field used as the page background."""
    W, H = size
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    fn = pick(f"{seed}:motif", MOTIFS)
    step = [96, 120, 150][variant(seed, "step", 3)]
    r = step * 0.34
    for iy, cy in enumerate(range(-step, H + step, step)):
        for ix, cx in enumerate(range(-step, W + step, step)):
            ox = (step // 2) if iy % 2 else 0
            fn(d, cx + ox, cy, r, col, 2)
    return im
              
