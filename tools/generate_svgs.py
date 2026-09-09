#!/usr/bin/env python3
"""
generate_svgs.py — builds every animated asset in /assets.

Palette: "Scary Forest" — #0c1622 · #23444b · #628d7c · #1f2b29 · #000000
Everything is pure SVG + SMIL animation (no JavaScript), which is what GitHub
allows inside a README <img>.

Re-run whenever you change something:   python tools/generate_svgs.py
"""
from __future__ import annotations

import math
import random
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
TTT = ASSETS / "ttt"

# ---- Scary Forest palette ---------------------------------------------------
NAVY = "#0c1622"    # background
TEAL = "#23444b"    # secondary / edges / avatar backdrop
SAGE = "#628d7c"    # accent, text, nodes
MOSS = "#1f2b29"    # dark fills
BLACK = "#000000"   # hair, shadows
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
FRAMES = 60


# ---- helpers ----------------------------------------------------------------
def f1(v: float) -> str:
    return f"{v:.1f}"


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def anim(attr, values, dur, extra=""):
    return (f'<animate attributeName="{attr}" values="{";".join(values)}" '
            f'dur="{dur}" repeatCount="indefinite"{extra}/>')


def svg_open(w, h, label):
    label = label.replace("&", "&amp;")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{label}">')


def defs(extra=""):
    return f"""<defs>
  <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur stdDeviation="2" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <radialGradient id="vignette" cx="50%" cy="50%" r="75%">
    <stop offset="0" stop-color="{NAVY}"/>
    <stop offset="1" stop-color="{BLACK}"/>
  </radialGradient>
  <pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse">
    <circle cx="1.5" cy="1.5" r="1.2" fill="{TEAL}" opacity="0.45"/>
  </pattern>
  {extra}
</defs>"""


# ---- neural network drawing --------------------------------------------------
def neural_net(layers, x0, y0, w, h, *, seed=1, node_r=6.5, edge_color=TEAL,
               node_color=SAGE, pulse_color=SAGE, pulses=14, pulse_r=2.6,
               edge_width=1.2, extra_inputs=None, labels=False):
    """Draw a layered neural network with signals travelling along the edges.

    extra_inputs: optional list of (x, y) points that feed the first layer
    (used to plug the avatar into the network in the banner).
    """
    rnd = random.Random(seed)
    cols = []
    for i, n in enumerate(layers):
        x = x0 + (w * i / (len(layers) - 1) if len(layers) > 1 else 0)
        gap = h / (n + 1)
        cols.append([(x, y0 + gap * (k + 1)) for k in range(n)])

    edges = []
    for a, b in zip(cols, cols[1:]):
        for p in a:
            for q in b:
                edges.append((p, q))
    if extra_inputs:
        for p in extra_inputs:
            for q in cols[0]:
                edges.append((p, q))

    out = [f'<g stroke="{edge_color}" stroke-width="{edge_width}" stroke-linecap="round" opacity="0.7">']
    for (x1, y1), (x2, y2) in edges:
        out.append(f'<line x1="{f1(x1)}" y1="{f1(y1)}" x2="{f1(x2)}" y2="{f1(y2)}"/>')
    out.append("</g>")

    # travelling signals
    out.append(f'<g fill="{pulse_color}" filter="url(#glow)">')
    for (x1, y1), (x2, y2) in rnd.sample(edges, min(pulses, len(edges))):
        dur = rnd.uniform(1.6, 3.2)
        begin = -rnd.uniform(0, dur)
        out.append(
            f'<circle r="{pulse_r}" opacity="0">'
            f'<animateMotion dur="{dur:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite" '
            f'path="M {f1(x1)} {f1(y1)} L {f1(x2)} {f1(y2)}"/>'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.15;0.85;1" '
            f'dur="{dur:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite"/></circle>')
    out.append("</g>")

    # nodes with a staggered pulse
    for i, col in enumerate(cols):
        for k, (x, y) in enumerate(col):
            begin = -((i * 0.35 + k * 0.2) % 2.4)
            out.append(
                f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{node_r}" fill="{MOSS}" '
                f'stroke="{node_color}" stroke-width="2"/>'
                f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{node_r * 0.45}" fill="{node_color}">'
                f'<animate attributeName="r" values="{f1(node_r * 0.35)};{f1(node_r * 0.75)};{f1(node_r * 0.35)}" '
                f'dur="2.4s" begin="{begin:.2f}s" repeatCount="indefinite"/></circle>')
    return "\n".join(out), cols


# ---- flat avatar (original illustration in the palette) ---------------------
def strand(bx, by, tx, ty, width, bulge=0.35, curl=0.0):
    """A pointed, slightly curved lock of hair from base (bx,by) to tip (tx,ty)."""
    dx, dy = tx - bx, ty - by
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L               # unit normal
    mx, my = bx + dx / 2 + nx * curl * L, by + dy / 2 + ny * curl * L
    hw = width / 2
    return (f"M {bx + nx * hw:.1f} {by + ny * hw:.1f} "
            f"Q {mx + nx * hw * bulge:.1f} {my + ny * hw * bulge:.1f} {tx:.1f} {ty:.1f} "
            f"Q {mx - nx * hw * bulge:.1f} {my - ny * hw * bulge:.1f} {bx - nx * hw:.1f} {by - ny * hw:.1f} Z")


def ringlet(x, y, size, flip=False, width=8, color=BLACK):
    """A loose hanging curl (hook shape) starting at (x, y)."""
    f = -1 if flip else 1
    d = (f"M {x} {y} "
         f"Q {x - f * size:.1f} {y + size * 0.8:.1f} {x - f * size * 0.3:.1f} {y + size * 1.45:.1f} "
         f"Q {x + f * size * 0.7:.1f} {y + size * 1.9:.1f} {x + f * size * 0.75:.1f} {y + size * 1.0:.1f}")
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def avatar(cx, cy, r=118):
    """Flat portrait in the palette: loose curly hair with ringlets on the forehead,
    large thin rounded-square glasses, dark eyes, light stubble, open shirt + blazer."""
    s = r / 120.0                      # designed in a 240x240 box
    rnd = random.Random(11)
    HC = (120, 66)

    # ---- hair: base mass + edge curls + interior curl texture + ringlets on the forehead
    hair = [f'<ellipse cx="{HC[0]}" cy="{HC[1]}" rx="66" ry="46" fill="{BLACK}"/>',
            f'<ellipse cx="{HC[0]}" cy="{HC[1] - 6}" rx="50" ry="44" fill="{BLACK}"/>']
    for ang in range(178, 366, 10):                 # bumpy silhouette of curls
        a = math.radians(ang)
        x = HC[0] + 66 * math.cos(a) + rnd.uniform(-3, 3)
        y = HC[1] + 46 * math.sin(a) + rnd.uniform(-3, 3)
        hair.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rnd.uniform(7, 11):.1f}" fill="{BLACK}"/>')
    for ang, dist, size, flip in ((186, 74, 9, True), (204, 76, 8, True), (228, 72, 9, True), (252, 70, 8, False),
                                  (276, 70, 8, False), (300, 72, 9, False), (324, 74, 8, False), (346, 76, 9, False),
                                  (170, 68, 8, True), (10, 68, 8, False)):
        a = math.radians(ang)                       # curls poking out of the edge
        x, y = HC[0] + dist * math.cos(a), HC[1] + dist * 0.9 * math.sin(a)
        hair.append(ringlet(x, y - 2, size, flip=flip, width=7))
    texture = []                                    # interior curl texture (dark teal on black)
    for _ in range(18):
        a = rnd.uniform(math.pi, 2 * math.pi)
        dist = rnd.uniform(10, 52)
        x, y = HC[0] + dist * math.cos(a), HC[1] + dist * 0.8 * math.sin(a)
        sz = rnd.uniform(5, 9)
        sw = 1 if rnd.random() < 0.5 else 0
        texture.append(f'<path d="M {x - sz:.1f} {y:.1f} A {sz:.1f} {sz:.1f} 0 1 {sw} {x + sz * 0.6:.1f} {y + sz * 0.7:.1f}" '
                       f'fill="none" stroke="{TEAL}" stroke-width="2" stroke-linecap="round" opacity="0.7"/>')
    forehead = [ringlet(80, 66, 13, flip=True, width=10), ringlet(96, 64, 11, flip=False, width=9),
                ringlet(112, 62, 10, flip=True, width=9), ringlet(128, 62, 10, flip=False, width=9),
                ringlet(144, 64, 11, flip=True, width=9), ringlet(158, 68, 12, flip=False, width=10),
                ringlet(68, 86, 9, flip=True, width=8), ringlet(172, 88, 9, flip=False, width=8),
                ringlet(104, 80, 6, flip=False, width=7), ringlet(136, 80, 6, flip=True, width=7)]
    forehead_hl = [ringlet(80, 66, 13, flip=True, width=2, color=SAGE).replace('/>', ' opacity="0.35"/>'),
                   ringlet(128, 62, 10, flip=False, width=2, color=SAGE).replace('/>', ' opacity="0.35"/>'),
                   ringlet(158, 68, 12, flip=False, width=2, color=SAGE).replace('/>', ' opacity="0.3"/>')]

    return f"""<g transform="translate({cx - 120 * s},{cy - 120 * s}) scale({s:.4f})">
  <animateTransform attributeName="transform" type="translate" additive="sum" values="0 0;0 -5;0 0" dur="4.5s" repeatCount="indefinite"/>
  <defs>
    <clipPath id="avclip"><circle cx="120" cy="120" r="112"/></clipPath>
  </defs>
  <circle cx="120" cy="120" r="115" fill="{TEAL}"/>
  <circle cx="120" cy="120" r="115" fill="none" stroke="{SAGE}" stroke-width="3"/>
  <g clip-path="url(#avclip)">
    <!-- blazer -->
    <path d="M -12 250 C 4 204 58 190 94 184 L 120 250 L 146 184 C 182 190 236 204 252 250 Z" fill="{MOSS}"/>
    <!-- open white shirt -->
    <path d="M 92 182 L 148 182 L 120 250 Z" fill="{SAGE}"/>
    <path d="M 120 210 L 120 250" stroke="{NAVY}" stroke-width="1.5" opacity="0.5"/>
    <path d="M 94 184 L 82 198 L 108 250 L 120 250 Z M 146 184 L 158 198 L 132 250 L 120 250 Z" fill="{BLACK}" opacity="0.35"/>
    <!-- neck -->
    <path d="M 104 164 L 104 196 Q 120 206 136 196 L 136 164 Z" fill="{SAGE}"/>
    <path d="M 104 176 Q 120 192 136 176 L 136 164 L 104 164 Z" fill="{MOSS}" opacity="0.4"/>
    <!-- shirt collar -->
    <path d="M 105 180 L 84 192 L 114 214 L 111 188 Z" fill="{SAGE}" stroke="{NAVY}" stroke-width="2" stroke-linejoin="round"/>
    <path d="M 135 180 L 156 192 L 126 214 L 129 188 Z" fill="{SAGE}" stroke="{NAVY}" stroke-width="2" stroke-linejoin="round"/>
    <path d="M 111 188 Q 120 200 129 188" fill="none" stroke="{NAVY}" stroke-width="1.6"/>
    <!-- hair behind the head -->
    <g>{"".join(hair)}</g>
    <!-- ears -->
    <ellipse cx="78" cy="118" rx="7" ry="11" fill="{SAGE}" stroke="{MOSS}" stroke-width="1.2"/>
    <ellipse cx="162" cy="118" rx="7" ry="11" fill="{SAGE}" stroke="{MOSS}" stroke-width="1.2"/>
    <!-- face: long oval, narrow chin -->
    <path d="M 80 100 C 80 58 98 42 120 42 C 142 42 160 58 160 100 C 160 126 156 146 146 158 C 138 168 128 172 120 172 C 112 172 102 168 94 158 C 84 146 80 126 80 100 Z" fill="{SAGE}"/>
    <!-- brows: thick, arched -->
    <path d="M 84 100 C 92 92 106 92 114 97" fill="none" stroke="{NAVY}" stroke-width="4.5" stroke-linecap="round"/>
    <path d="M 126 97 C 134 92 148 92 156 100" fill="none" stroke="{NAVY}" stroke-width="4.5" stroke-linecap="round"/>
    <!-- eyes: dark, slightly narrowed -->
    <g>
      <path d="M 87 119 Q 97 112 108 118 Q 98 124 87 119 Z" fill="{TEAL}"/>
      <path d="M 132 118 Q 143 112 153 119 Q 142 124 132 118 Z" fill="{TEAL}"/>
      <circle cx="98" cy="118" r="4.2" fill="{NAVY}"/><circle cx="142" cy="118" r="4.2" fill="{NAVY}"/>
      <circle cx="98" cy="118" r="2" fill="{BLACK}"/><circle cx="142" cy="118" r="2" fill="{BLACK}"/>
      <circle cx="99.4" cy="116.6" r="1" fill="{SAGE}"/><circle cx="143.4" cy="116.6" r="1" fill="{SAGE}"/>
      <path d="M 87 119 Q 97 111 108 118" fill="none" stroke="{NAVY}" stroke-width="2.4" stroke-linecap="round"/>
      <path d="M 132 118 Q 143 111 153 119" fill="none" stroke="{NAVY}" stroke-width="2.4" stroke-linecap="round"/>
    </g>
    <!-- nose (straight), lips, light stubble -->
    <path d="M 121 118 L 116 141 Q 120 145 126 142" fill="none" stroke="{MOSS}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M 107 150 q 13 -4 26 0" fill="none" stroke="{MOSS}" stroke-width="3.5" stroke-linecap="round" opacity="0.28"/>
    <path d="M 108 154 Q 120 151 132 154" fill="none" stroke="{MOSS}" stroke-width="2" stroke-linecap="round"/>
    <path d="M 110 155 Q 120 161 130 155 Z" fill="{MOSS}" opacity="0.28"/>
    <path d="M 100 152 C 104 170 136 170 140 152 C 136 164 104 164 100 152 Z" fill="{MOSS}" opacity="0.18"/>
    <!-- large thin rounded-square glasses -->
    <g stroke="{NAVY}" stroke-width="1.9" fill="{NAVY}" fill-opacity="0.14">
      <rect x="76" y="103" width="42" height="31" rx="9"/>
      <rect x="122" y="103" width="42" height="31" rx="9"/>
      <path d="M 118 114 Q 120 111 122 114" fill="none"/>
      <path d="M 76 113 L 70 110 M 164 113 L 170 110" fill="none"/>
    </g>
    <path d="M 82 111 q 6 -6 13 -5" fill="none" stroke="{SAGE}" stroke-width="1.6" stroke-linecap="round" opacity="0.8"/>
    <path d="M 128 111 q 6 -6 13 -5" fill="none" stroke="{SAGE}" stroke-width="1.6" stroke-linecap="round" opacity="0.8"/>
    <!-- hairline cap + ringlets falling onto the forehead -->
    <path d="M 72 108 C 66 66 90 36 120 36 C 150 36 174 66 168 108 C 164 90 150 66 120 66 C 90 66 76 90 72 108 Z" fill="{BLACK}"/>
    <g>{"".join(texture)}</g>
    <g>{"".join(forehead)}</g>
    <g>{"".join(forehead_hl)}</g>
  </g>
</g>"""


# ---- 3D wireframe (kept for the PATHIRA glasses) ----------------------------
def rx(p, a):
    x, y, z = p
    c, s = math.cos(a), math.sin(a)
    return (x, y * c - z * s, y * s + z * c)


def ry(p, a):
    x, y, z = p
    c, s = math.cos(a), math.sin(a)
    return (x * c + z * s, y, -x * s + z * c)


def rz(p, a):
    x, y, z = p
    c, s = math.cos(a), math.sin(a)
    return (x * c - y * s, x * s + y * c, z)


def project(p, cx, cy, scale, persp):
    x, y, z = p
    f = persp / (persp - z)
    return cx + x * scale * f, cy - y * scale * f, z


def swinging_wireframe(verts, edges, *, cx, cy, scale, dur, radius, persp=7.0,
                       tilt_x=0.25, tilt_z=0.05, sweep=0.85, wobble=0.12,
                       edge_color=SAGE, edge_width=2.4, node_color=SAGE,
                       highlight=None, frames=FRAMES):
    proj = []
    for t in range(frames + 1):
        ph = 2 * math.pi * t / frames
        th = sweep * math.sin(ph)
        tx = tilt_x + wobble * math.sin(ph)
        proj.append([project(rz(rx(ry(v, th), tx), tilt_z), cx, cy, scale, persp) for v in verts])

    out = []
    for i, j in edges:
        pts, ops = [], []
        for fr in proj:
            x1, y1, z1 = fr[i]
            x2, y2, z2 = fr[j]
            pts.append(f"{f1(x1)},{f1(y1)} {f1(x2)},{f1(y2)}")
            d = clamp(((z1 + z2) / 2 / radius + 1) / 2)
            ops.append(f"{0.3 + 0.7 * d:.2f}")
        out.append(f'<polyline fill="none" stroke="{edge_color}" stroke-width="{edge_width}" '
                   f'stroke-linecap="round" points="{pts[0]}" opacity="{ops[0]}">'
                   f'{anim("points", pts, dur)}{anim("opacity", ops, dur)}</polyline>')
    out.append('<g filter="url(#glow)">')
    for k in range(len(verts)):
        hl = (highlight or {}).get(k)
        col, rmax = (hl if hl else (node_color, 3.0))
        cxs, cys, rs = [], [], []
        for fr in proj:
            x, y, z = fr[k]
            d = clamp((z / radius + 1) / 2)
            cxs.append(f1(x))
            cys.append(f1(y))
            rs.append(f1(rmax * (0.55 + 0.45 * d)))
        out.append(f'<circle cx="{cxs[0]}" cy="{cys[0]}" r="{rs[0]}" fill="{col}">'
                   f'{anim("cx", cxs, dur)}{anim("cy", cys, dur)}{anim("r", rs, dur)}</circle>')
    out.append("</g>")
    return "\n".join(out)


def glasses_geometry():
    verts, edges = [], []

    def ring(cx, r, n=16):
        start = len(verts)
        for k in range(n):
            a = 2 * math.pi * k / n
            verts.append((cx + r * math.cos(a), r * 0.78 * math.sin(a), 0.0))
        for k in range(n):
            edges.append((start + k, start + (k + 1) % n))
        return start

    L = ring(-1.15, 0.85)
    R = ring(1.15, 0.85)
    edges.append((L + 0, R + 8))

    def temple(hinge_idx, x):
        a = len(verts)
        verts.extend([(x, 0.15, -0.15), (x, 0.15, -2.3), (x, -0.45, -2.75)])
        edges.extend([(hinge_idx, a), (a, a + 1), (a + 1, a + 2)])

    temple(L + 8, -2.05)
    temple(R + 0, 2.05)
    return verts, edges, L + 10


# ---- assets -----------------------------------------------------------------
# ---- avatar from the illustration (assets/avatar_source.png) ----------------
AVATAR_SOURCE = ASSETS / "avatar_source.png"
AVATAR_DUOTONE = True      # False = keep the illustration's original colours in the banner


def _duotone(img):
    """Map a greyscale image onto the palette: black -> navy -> teal -> sage."""
    from PIL import Image, ImageOps
    g = ImageOps.autocontrast(img.convert("L"), cutoff=1)
    stops = [(0, (0, 0, 0)), (0.32, (12, 22, 34)), (0.62, (35, 68, 75)), (1.0, (98, 141, 124))]
    lut = []
    for ch in range(3):
        table = []
        for v in range(256):
            t = v / 255
            for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
                if t0 <= t <= t1:
                    k = (t - t0) / (t1 - t0)
                    table.append(int(round(c0[ch] + (c1[ch] - c0[ch]) * k)))
                    break
        lut.append(table)
    return Image.merge("RGB", [g.point(lut[ch]) for ch in range(3)])


def avatar_image_data(size=480, duotone=AVATAR_DUOTONE):
    """Return (data_uri, ok). Also writes assets/avatar.png (+ avatar_duotone.png)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None, False
    if not AVATAR_SOURCE.exists():
        return None, False
    import base64, io
    src = Image.open(AVATAR_SOURCE).convert("RGB")
    side = min(src.size)
    src = src.crop(((src.width - side) // 2, (src.height - side) // 2,
                    (src.width + side) // 2, (src.height + side) // 2))
    fx0, fy0, fs = 0.10, 0.02, 0.80                       # focus on the face and hand
    src = src.crop((int(side * fx0), int(side * fy0), int(side * (fx0 + fs)), int(side * (fy0 + fs))))

    def circle_png(img, path, px=512):
        img = img.resize((px, px), Image.LANCZOS).convert("RGBA")
        mask = Image.new("L", (px, px), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, px - 1, px - 1), fill=255)
        img.putalpha(mask)
        img.save(path, optimize=True)

    circle_png(src, ASSETS / "avatar.png")
    tinted = _duotone(src)
    circle_png(tinted, ASSETS / "avatar_duotone.png")

    chosen = (tinted if duotone else src).resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    chosen.save(buf, "JPEG", quality=84, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii"), True


def avatar_photo(cx, cy, r=118, duotone=AVATAR_DUOTONE):
    """Circular photo/illustration avatar for the banner; falls back to the drawn one."""
    uri, ok = avatar_image_data(duotone=duotone)
    if not ok:
        return avatar(cx, cy, r)
    return f"""<g>
  <animateTransform attributeName="transform" type="translate" values="0 0;0 -5;0 0" dur="4.5s" repeatCount="indefinite"/>
  <defs><clipPath id="avclip"><circle cx="{cx}" cy="{cy}" r="{r - 3}"/></clipPath></defs>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{TEAL}"/>
  <image xlink:href="{uri}" href="{uri}" x="{cx - r}" y="{cy - r}" width="{2 * r}" height="{2 * r}"
         preserveAspectRatio="xMidYMid slice" clip-path="url(#avclip)"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{SAGE}" stroke-width="3"/>
</g>"""


def build_banner(duotone=AVATAR_DUOTONE, name="banner.svg"):
    W, H = 1200, 340
    AV = (760, 170)
    ring_r = 118
    # points on the right rim of the avatar that feed the network
    feed = [(AV[0] + ring_r * math.cos(a), AV[1] + ring_r * math.sin(a))
            for a in (-0.55, -0.18, 0.18, 0.55)]
    net, _ = neural_net([4, 5, 3], 930, 62, 220, 216, seed=3, extra_inputs=feed, pulses=18)

    text_grad = f"""
  <linearGradient id="tg" gradientUnits="userSpaceOnUse" x1="60" y1="0" x2="520" y2="0" spreadMethod="reflect">
    <stop offset="0" stop-color="{SAGE}"/>
    <stop offset="0.55" stop-color="{TEAL}"/>
    <stop offset="1" stop-color="{SAGE}"/>
    <animateTransform attributeName="gradientTransform" type="translate" values="-460 0;460 0;-460 0" dur="9s" repeatCount="indefinite"/>
  </linearGradient>"""

    parts = [
        svg_open(W, H, "Ziad Elsayed — AI Engineer"),
        defs(text_grad),
        f'<rect width="{W}" height="{H}" rx="18" fill="url(#vignette)"/>',
        f'<rect width="{W}" height="{H}" rx="18" fill="url(#dots)"/>',
        net,
        avatar_photo(*AV, ring_r, duotone=duotone),
        f'<text x="60" y="126" font-family="{FONT}" font-size="22" fill="{SAGE}" opacity="0.85">Hi, I\'m</text>',
        f'<text x="58" y="192" font-family="{FONT}" font-size="70" font-weight="800" '
        f'letter-spacing="-1" fill="url(#tg)">Ziad Elsayed</text>',
        f'<text x="60" y="236" font-family="{FONT}" font-size="28" font-weight="500" fill="{SAGE}">AI Engineer</text>',
        "</svg>",
    ]
    (ASSETS / name).write_text("\n".join(parts), encoding="utf-8")


def build_avatar():
    W = H = 260
    parts = [svg_open(W, H, "Ziad Elsayed — avatar"), defs(), avatar_photo(130, 130, 122), "</svg>"]
    (ASSETS / "avatar.svg").write_text("\n".join(parts), encoding="utf-8")


def build_neural_nets():
    W = H = 300
    net, _ = neural_net([3, 5, 5, 2], 30, 20, 240, 260, seed=5, pulses=16)
    (ASSETS / "neural_net.svg").write_text("\n".join([
        svg_open(W, H, "Animated neural network"), defs(), net, "</svg>"]), encoding="utf-8")

    W2, H2 = 320, 300
    net2, _ = neural_net([4, 6, 6, 3], 30, 16, 260, 268, seed=9, node_r=6, pulses=22)
    (ASSETS / "neural_net_deep.svg").write_text("\n".join([
        svg_open(W2, H2, "Animated deep neural network"), defs(), net2, "</svg>"]), encoding="utf-8")


def build_glasses():
    W, H = 360, 220
    gv, ge, cam = glasses_geometry()
    parts = [
        svg_open(W, H, "Swinging wireframe smart glasses — PATHIRA VISION"),
        defs(),
        f'<rect x="40" y="30" width="2" height="160" fill="{SAGE}" opacity="0.3">'
        f'<animate attributeName="x" values="40;320;40" dur="5s" repeatCount="indefinite"/></rect>',
        swinging_wireframe(gv, ge, cx=180, cy=110, scale=52, dur="14s", radius=2.9,
                           highlight={cam: (SAGE, 7)}),
        "</svg>",
    ]
    (ASSETS / "glasses.svg").write_text("\n".join(parts), encoding="utf-8")


def build_ttt_cells():
    base = (f'<rect x="3" y="3" width="94" height="94" rx="16" fill="{MOSS}" '
            f'stroke="{TEAL}" stroke-width="2"/>')
    empty = f"""{svg_open(100, 100, "Empty cell — click to play here")}
{defs()}
{base}
<rect x="3" y="3" width="94" height="94" rx="16" fill="none" stroke="{SAGE}" stroke-width="2" stroke-dasharray="7 7" opacity="0.5">
  <animate attributeName="stroke-dashoffset" values="0;28" dur="1.8s" repeatCount="indefinite"/>
</rect>
<g stroke="{SAGE}" stroke-width="3" stroke-linecap="round">
  <line x1="50" y1="37" x2="50" y2="63"/><line x1="37" y1="50" x2="63" y2="50"/>
  <animate attributeName="opacity" values="0.3;0.9;0.3" dur="2s" repeatCount="indefinite"/>
</g>
</svg>"""
    x = f"""{svg_open(100, 100, "X — a human move")}
{defs()}
{base}
<g stroke="{SAGE}" stroke-width="9" stroke-linecap="round" fill="none" filter="url(#glow)">
  <line x1="28" y1="28" x2="72" y2="72" stroke-dasharray="63" stroke-dashoffset="0">
    <animate attributeName="stroke-dashoffset" values="63;0" dur="0.35s" fill="freeze"/>
  </line>
  <line x1="72" y1="28" x2="28" y2="72" stroke-dasharray="63" stroke-dashoffset="0">
    <animate attributeName="stroke-dashoffset" values="63;63;0" keyTimes="0;0.45;1" dur="0.65s" fill="freeze"/>
  </line>
</g>
</svg>"""
    o = f"""{svg_open(100, 100, "O — the AI's move")}
{defs()}
{base}
<circle cx="50" cy="50" r="24" fill="none" stroke="{SAGE}" stroke-width="13" opacity="0.35"/>
<circle cx="50" cy="50" r="24" fill="none" stroke="{BLACK}" stroke-width="9" stroke-linecap="round"
        stroke-dasharray="151" stroke-dashoffset="0" transform="rotate(-90 50 50)">
  <animate attributeName="stroke-dashoffset" values="151;0" dur="0.6s" fill="freeze"/>
</circle>
</svg>"""
    (TTT / "empty.svg").write_text(empty, encoding="utf-8")
    (TTT / "x.svg").write_text(x, encoding="utf-8")
    (TTT / "o.svg").write_text(o, encoding="utf-8")


if __name__ == "__main__":
    ASSETS.mkdir(parents=True, exist_ok=True)
    TTT.mkdir(parents=True, exist_ok=True)
    for old in ("cube.svg", "neural_sphere.svg"):
        (ASSETS / old).unlink(missing_ok=True)
    build_banner()
    build_banner(duotone=False, name="banner_original_colors.svg")
    build_avatar()
    build_neural_nets()
    build_glasses()
    build_ttt_cells()
    for p in sorted(ASSETS.rglob("*.svg")):
        print(f"{p.relative_to(ASSETS.parent)}  {p.stat().st_size / 1024:.0f} KB")
