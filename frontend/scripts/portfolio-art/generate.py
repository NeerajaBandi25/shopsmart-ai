#!/usr/bin/env python3
"""ShopSmart portfolio product-art generator (deterministic, standard library only).

Provenance / attribution
  * Every image is original artwork produced procedurally by this script: signed-distance-field
    shapes, gradients and lighting are rasterised with anti-aliasing into RGB PNG bitmaps.
  * No external images, fonts, stock assets, brand logos, trademarks or downloads are used.
    Products are generic archetypes, not reproductions of any commercial product.
  * Output is a pure function of this source file (fixed seeds, no clock, no randomness
    outside random.Random(seed)); re-running yields byte-identical files.
  * Released as part of the ShopSmart repository under the repository's licence.

Usage:  python generate.py [--out DIR] [--sheet DIR]
Output: DIR/{category}/0{1..5}.png (+ manifest.json). Default DIR is
        frontend/public/images/products/portfolio. --sheet writes review contact sheets.
"""
import hashlib
import json
import math
import os
import random
import struct
import sys
import zlib

SC = 1.25                      # render scale over the 320-unit design space
D = 320
N = int(D * SC)                # 400 px square
PX = bytearray(N * N * 3)
PROVENANCE = ("Original procedurally generated artwork for the ShopSmart portfolio; "
              "no external assets, logos or trademarks. Generator: frontend/scripts/portfolio-art/generate.py")


# ---------------------------------------------------------------- colour helpers
def K(s):
    if len(s) == 4:
        s = '#' + ''.join(ch * 2 for ch in s[1:])
    return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def mix(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def lighten(c, t):
    return mix(c, (255, 255, 255), t)


def darken(c, t):
    return mix(c, (0, 0, 0), t)


def hsv(h, s, v):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (r * 255, g * 255, b * 255)


def lin(y0, y1, c0, c1):
    return lambda x, y: mix(c0, c1, clamp((y - y0) / (y1 - y0)))


def linx(x0, x1, c0, c1):
    return lambda x, y: mix(c0, c1, clamp((x - x0) / (x1 - x0)))


def rad(cx, cy, r, c0, c1):
    return lambda x, y: mix(c0, c1, clamp(math.hypot(x - cx, y - cy) / r))


def wall(seed, a, b, c):
    r = random.Random(seed)
    f1, f2 = r.uniform(.02, .05), r.uniform(.03, .06)
    p1, p2 = r.uniform(0, 6), r.uniform(0, 6)

    def f(x, y):
        t = .5 + .5 * math.sin(x * f1 + y * f2 * .6 + p1)
        u = .5 + .5 * math.sin(y * f2 - x * f1 * .5 + p2)
        return mix(mix(a, b, t), c, u * .6)
    return f


# ---------------------------------------------------------------- shapes: (sdf, bbox)
def S_rr(cx, cy, w, hh, r=6, rot=0):
    hw, hy = w / 2, hh / 2
    r = min(r, hw, hy)
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)

    def f(x, y):
        dx, dy = x - cx, y - cy
        px = abs(dx * ca + dy * sa)
        py = abs(-dx * sa + dy * ca)
        qx, qy = px - hw + r, py - hy + r
        return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r
    if rot:
        R = math.hypot(hw, hy)
        return f, (cx - R, cy - R, cx + R, cy + R)
    return f, (cx - hw, cy - hy, cx + hw, cy + hy)


def S_e(cx, cy, rx, ry, rot=0):
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    def f(x, y):
        dx, dy = x - cx, y - cy
        u, v = dx * ca + dy * sa, -dx * sa + dy * ca
        k0 = math.hypot(u / rx, v / ry)
        k1 = math.hypot(u / (rx * rx), v / (ry * ry))
        return k0 * (k0 - 1) / k1 if k1 > 1e-9 else -min(rx, ry)
    R = max(rx, ry)
    return f, (cx - R, cy - R, cx + R, cy + R)


def S_c(cx, cy, r):
    def f(x, y):
        return math.hypot(x - cx, y - cy) - r
    return f, (cx - r, cy - r, cx + r, cy + r)


def S_cap(x1, y1, x2, y2, r):
    dx, dy = x2 - x1, y2 - y1
    L = dx * dx + dy * dy or 1

    def f(x, y):
        t = clamp(((x - x1) * dx + (y - y1) * dy) / L)
        return math.hypot(x - x1 - t * dx, y - y1 - t * dy) - r
    return f, (min(x1, x2) - r, min(y1, y2) - r, max(x1, x2) + r, max(y1, y2) + r)


def S_poly(pts):
    n = len(pts)
    edges = [(pts[i][0], pts[i][1], pts[(i + 1) % n][0] - pts[i][0], pts[(i + 1) % n][1] - pts[i][1],
              pts[(i + 1) % n][1]) for i in range(n)]

    def f(x, y):
        d = 1e18
        s = 1
        for (vx, vy, ex, ey, ny) in edges:
            wx, wy = x - vx, y - vy
            t = clamp((wx * ex + wy * ey) / ((ex * ex + ey * ey) or 1))
            bx, by = wx - ex * t, wy - ey * t
            dd = bx * bx + by * by
            if dd < d:
                d = dd
            c1, c2, c3 = y >= vy, y < ny, ex * wy > ey * wx
            if (c1 and c2 and c3) or (not c1 and not c2 and not c3):
                s = -s
        return s * math.sqrt(d)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return f, (min(xs), min(ys), max(xs), max(ys))


def S_arc(cx, cy, r, t, a0, a1):
    a0, a1 = math.radians(a0), math.radians(a1)
    e0 = (cx + r * math.cos(a0), cy + r * math.sin(a0))
    e1 = (cx + r * math.cos(a1), cy + r * math.sin(a1))
    span = (a1 - a0) % (2 * math.pi)

    def f(x, y):
        ang = (math.atan2(y - cy, x - cx) - a0) % (2 * math.pi)
        if ang <= span:
            return abs(math.hypot(x - cx, y - cy) - r) - t / 2
        return min(math.hypot(x - e0[0], y - e0[1]), math.hypot(x - e1[0], y - e1[1])) - t / 2
    return f, (cx - r - t, cy - r - t, cx + r + t, cy + r + t)


def S_in(s, k):
    return (lambda x, y: s[0](x, y) + k), s[1]


def S_edge(s, t):
    return (lambda x, y: abs(s[0](x, y) + t / 2) - t / 2), s[1]


def S_ring(s, t):
    return (lambda x, y: abs(s[0](x, y)) - t / 2), s[1]


def S_u(*ss):
    fs = [s[0] for s in ss]
    return (lambda x, y: min(f(x, y) for f in fs)), (
        min(s[1][0] for s in ss), min(s[1][1] for s in ss), max(s[1][2] for s in ss), max(s[1][3] for s in ss))


def S_sub(a, b):
    return (lambda x, y: max(a[0](x, y), -b[0](x, y))), a[1]


def smooth(pts, it=3):
    for _ in range(it):
        out = []
        n = len(pts)
        for i in range(n):
            p, q = pts[i], pts[(i + 1) % n]
            out.append((.75 * p[0] + .25 * q[0], .75 * p[1] + .25 * q[1]))
            out.append((.25 * p[0] + .75 * q[0], .25 * p[1] + .75 * q[1]))
        pts = out
    return pts


def sym(half, cx):
    return half + [(2 * cx - x, y) for x, y in reversed(half[1:-1])]


def curve(p0, p1, p2, n=10):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / n for i in range(n + 1)]]


# ---------------------------------------------------------------- painting
def P(shape, fill, alpha=1.0, blur=0.0):
    sdf, (bx0, by0, bx1, by1) = shape
    pad = (blur or 0) * SC + 2
    x0, y0 = max(0, int(bx0 * SC - pad)), max(0, int(by0 * SC - pad))
    x1, y1 = min(N, int(bx1 * SC + pad) + 1), min(N, int(by1 * SC + pad) + 1)
    call = callable(fill)
    px = PX
    for y in range(y0, y1):
        fy = (y + .5) / SC
        row = y * N
        for x in range(x0, x1):
            fx = (x + .5) / SC
            d = sdf(fx, fy)
            cov = .5 - d / blur if blur else .5 - d * SC
            if cov <= 0:
                continue
            if cov > 1:
                cov = 1
            col = fill(fx, fy) if call else fill
            a = cov * alpha
            if len(col) == 4:
                a *= col[3]
            i = (row + x) * 3
            px[i] = int(px[i] + (col[0] - px[i]) * a)
            px[i + 1] = int(px[i + 1] + (col[1] - px[i + 1]) * a)
            px[i + 2] = int(px[i + 2] + (col[2] - px[i + 2]) * a)


def G(shape, col, k=.2, **kw):
    b = shape[1]
    P(shape, lin(b[1], b[3], lighten(col, k), darken(col, k)), **kw)


def Cy(shape, col, k=.3):
    b = shape[1]

    def f(x, y):
        t = (x - b[0]) / ((b[2] - b[0]) or 1)
        return mix(lighten(col, k), darken(col, k + .05), clamp(abs(t - .32) * 1.5))
    P(shape, f)


def rim(shape, a=.35, t=1.2):
    P(S_edge(shape, t), (255, 255, 255, a))


def sh(cx, cy, rx, ry, a=.38):
    P(S_e(cx, cy, rx, ry), (20, 25, 40), a, blur=14)


def gloss(shape, a=.22):
    b = shape[1]
    w = (b[2] - b[0]) + (b[3] - b[1])

    def f(x, y):
        t = ((x - b[0]) + (y - b[1]) * .8) / w
        return (255, 255, 255, a * clamp(1 - abs(t - .35) * 5))
    P(shape, f)


def path(pts, r, fill):
    for i in range(len(pts) - 1):
        P(S_cap(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], r), fill)


def arcpts(cx, cy, rx, ry, a0, a1, n=24):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def lens(cx, cy, r, ring='#3a3d44', iris='#3b4a8a'):
    rc = K(ring)
    P(S_c(cx, cy, r), lin(cy - r, cy + r, lighten(rc, .35), darken(rc, .45)))
    P(S_c(cx, cy, r * .84), K('#0a0b0e'))
    P(S_c(cx, cy, r * .66), rad(cx - r * .15, cy - r * .15, r * .75, K(iris), K('#080a18')))
    P(S_ring(S_c(cx, cy, r * .5), 1), (255, 255, 255, .15))
    P(S_c(cx, cy, r * .28), K('#05060c'))
    P(S_e(cx - r * .3, cy - r * .32, r * .22, r * .1, -38), (255, 255, 255, .75))
    P(S_c(cx + r * .28, cy + r * .3, r * .08), (255, 255, 255, .5))


SEG = {'0': 'abcdef', '1': 'bc', '2': 'abdeg', '3': 'abcdg', '4': 'bcfg', '5': 'acdfg', '6': 'acdefg',
       '7': 'abc', '8': 'abcdefg', '9': 'abcdfg'}


def digits(x, y, hh, text, col):
    w, t = hh * .5, max(1.4, hh * .13)
    for k, ch in enumerate(text):
        ox = x + k * (w + t * 2.2)
        pos = {'a': (ox + w / 2, y + t / 2, w, t), 'g': (ox + w / 2, y + hh / 2, w, t),
               'd': (ox + w / 2, y + hh - t / 2, w, t),
               'f': (ox + t / 2, y + hh / 4, t, hh / 2 - t), 'b': (ox + w - t / 2, y + hh / 4, t, hh / 2 - t),
               'e': (ox + t / 2, y + hh * .75, t, hh / 2 - t), 'c': (ox + w - t / 2, y + hh * .75, t, hh / 2 - t)}
        for s in SEG[ch]:
            P(S_rr(*pos[s], r=t / 2), col)


def widgets(x, y, w, h, seed):
    r = random.Random(seed)
    P(S_rr(x + w / 2, y + h * .1, w * .88, h * .08, 3), (255, 255, 255, .55))
    for i in range(3):
        P(S_rr(x + w * (.21 + .29 * i), y + h * .36, w * .25, h * .3, 5), (255, 255, 255, .22 + .1 * i))
    for i in range(5):
        hb = r.uniform(.1, .26) * h
        P(S_rr(x + w * (.1 + .1 * i), y + h * .92 - hb / 2, w * .06, hb, 2), (255, 255, 255, .55))
    P(S_ring(S_c(x + w * .78, y + h * .75, min(w, h) * .13), 3), (255, 255, 255, .6))
    P(S_arc(x + w * .78, y + h * .75, min(w, h) * .13, 3.5, -90, 120), (255, 255, 255, .95))


def fabric(col, k=.12):
    hi, lo = lighten(col, k), darken(col, k)

    def f(x, y):
        s = .5 + .5 * math.sin((x + y) * 1.7)
        return mix(mix(hi, lo, clamp((y - 40) / 220)), darken(col, .18), s * .12)
    return f


# ================================================================ LAPTOPS
def laptop1():
    sh(160, 232, 140, 11)
    lid = S_rr(160, 130, 206, 128, 9)
    G(lid, K('#2b2e35'), .08)
    scr = S_rr(160, 130, 192, 114, 4)
    P(scr, wall(1, K('#1d4ed8'), K('#22d3ee'), K('#f472b6')))
    widgets(64, 74, 192, 114, 1)
    gloss(scr)
    base = S_poly([(46, 196), (274, 196), (296, 224), (24, 224)])
    G(base, K('#cfd4dc'), .14)
    P(S_poly([(46, 196), (274, 196), (270, 201), (50, 201)]), K('#8e95a2'))
    for r in range(3):
        for c in range(13):
            x = 66 + c * 14.2 + r * 0
            P(S_rr(x + (160 - 160) + 0, 206 + r * 4.6, 10.5, 3.4, 1.2), K('#4b5160'))
    P(S_rr(160, 220, 70, 4, 2), K('#aab1bd'))
    P(S_rr(160, 196.5, 36, 3, 1.5), K('#6c7380'))


def laptop2():
    sh(160, 234, 146, 11)
    lid = S_rr(160, 126, 212, 124, 8)
    G(lid, K('#17181c'), .12)
    scr = S_rr(160, 126, 200, 112, 3)
    P(scr, wall(7, K('#7f1d1d'), K('#f97316'), K('#111827')))
    P(S_e(160, 120, 36, 36), (255, 220, 120, .7), blur=10)
    P(S_poly([(100, 160), (140, 100), (170, 140), (200, 90), (230, 160)]), (20, 10, 10, .85))
    gloss(scr, .18)
    base = S_poly([(40, 192), (280, 192), (302, 226), (18, 226)])
    G(base, K('#1b1c21'), .18)
    P(S_rr(160, 190.5, 240, 3, 1.5), (255, 255, 255, .15))
    for r in range(3):
        for c in range(14):
            P(S_rr(62 + c * 14, 202 + r * 5.2, 11, 3.8, 1.2), hsv(.0 + c * .07, .8, .95), .85)
    P(S_rr(160, 221, 66, 4, 2), K('#2b2e36'))
    P(S_rr(160, 226.5, 250, 3.2, 1.6), linx(30, 290, K('#ff0055'), K('#00d4ff')))
    P(S_rr(160, 226.5, 250, 7, 3), linx(30, 290, K('#ff0055'), K('#00d4ff')), .35, blur=5)


def laptop3():
    sh(160, 236, 130, 10)
    panel = S_poly([(72, 70), (248, 70), (270, 202), (50, 202)])
    G(panel, K('#d8dbe2'), .1)
    scr = S_poly([(80, 78), (240, 78), (258, 194), (62, 194)])
    P(scr, wall(3, K('#7c3aed'), K('#fb7185'), K('#fcd34d')))
    for i in range(4):
        P(S_c(120 + i * 27, 150, 9), (255, 255, 255, .6 - i * .05))
    P(S_rr(160, 110, 100, 10, 5), (255, 255, 255, .6))
    gloss(scr)
    G(S_poly([(50, 202), (270, 202), (286, 218), (34, 218)]), K('#b7bcc7'), .1)
    P(S_cap(70, 210, 250, 210, 2.5), K('#8f96a3'))
    P(S_cap(210, 240, 285, 228, 3.4), K('#222'))
    P(S_cap(210, 240, 285, 228, 1.2), K('#9ca3af'))


def laptop4():
    sh(160, 224, 138, 9)
    lid = S_rr(160, 125, 222, 134, 10)
    G(lid, K('#e8c9a8'), .12)
    scr = S_rr(160, 125, 214, 126, 6)
    P(scr, wall(11, K('#0f172a'), K('#2563eb'), K('#a78bfa')))
    P(S_e(185, 105, 50, 50), (255, 255, 255, .25), blur=18)
    widgets(53, 62, 214, 126, 5)
    gloss(scr, .2)
    P(S_rr(160, 62, 3, 3, 1.5), K('#111'))
    base = S_poly([(36, 193), (284, 193), (290, 203), (30, 203)])
    G(base, K('#dcb892'), .12)
    P(S_rr(160, 193.5, 50, 3, 1.5), K('#8c6c4c'))
    P(S_poly([(30, 203), (290, 203), (286, 208), (34, 208)]), K('#a8825f'))


def laptop5():
    sh(160, 238, 130, 10)
    top = S_poly([(52, 112), (250, 92), (278, 196), (36, 220)])
    G(top, K('#c6733a'), .2)
    P(S_poly([(36, 220), (278, 196), (280, 208), (38, 232)]), K('#8e4a22'))
    P(top, lambda x, y: (255, 255, 255, .08 * (.5 + .5 * math.sin(x * .9 + y * .35))))
    cx, cy = 160, 156
    P(S_ring(S_c(cx, cy, 30), 5), (255, 235, 210, .85))
    P(S_ring(S_c(cx, cy, 16), 3), (255, 235, 210, .85))
    P(S_cap(cx - 40, cy + 38, cx + 40, cy + 34, 1.5), (255, 235, 210, .7))
    gloss(top, .16)


# ================================================================ SMARTPHONES
def phone1():
    sh(160, 262, 74, 9)
    body = S_rr(160, 150, 110, 224, 22)
    G(body, K('#262a31'), .2)
    P(S_rr(213, 118, 3, 28, 1.5), K('#8f96a3'))
    scr = S_rr(160, 150, 100, 214, 17)
    P(scr, wall(21, K('#0ea5e9'), K('#6366f1'), K('#ec4899')))
    P(S_c(160, 56, 4), K('#05060a'))
    digits(119, 76, 26, '0941', (255, 255, 255, .95))
    widgets(115, 128, 90, 130, 2)
    gloss(scr, .2)


def phone2():
    sh(160, 262, 74, 9)
    body = S_rr(160, 150, 110, 224, 20)
    P(body, lambda x, y: mix(K('#6d28d9'), K('#e879f9'), clamp(((x - 105) + (y - 38) * .5) / 200)))
    rim(body, .4)
    isl = S_rr(126, 76, 52, 56, 13)
    G(isl, K('#1b1d24'), .15)
    rim(isl, .25)
    for (x, y) in [(114, 64), (114, 90), (139, 77)]:
        lens(x, y, 10, '#51556a', '#4b5fa8')
    P(S_c(140, 56, 4), K('#fff7d6'))
    P(S_c(140, 98, 2.5), K('#222'))
    gloss(body, .25)


def phone3():
    sh(160, 244, 130, 10)
    for cx in (108, 212):
        G(S_rr(cx, 148, 100, 196, 12), K('#2c3038'), .2)
    P(S_rr(160, 148, 6, 196, 2), K('#11131a'))
    for cx in (108, 212):
        P(S_rr(cx, 148, 92, 188, 8), wall(33, K('#f59e0b'), K('#ef4444'), K('#6d28d9')))
    P(S_rr(160, 148, 2, 190, 1), (0, 0, 0, .35))
    P(S_c(236, 68, 3.5), K('#05060a'))
    widgets(66, 70, 188, 150, 9)
    gloss(S_rr(108, 148, 92, 188, 8), .2)
    gloss(S_rr(212, 148, 92, 188, 8), .14)


def phone4():
    sh(160, 262, 100, 9)
    back = S_rr(212, 148, 100, 206, 18, 12)
    P(back, lambda x, y: mix(K('#0f766e'), K('#5eead4'), clamp((y - 40) / 200)))
    rim(back, .35)
    P(S_rr(240, 80, 36, 40, 10, 12), K('#0b1f1d'))
    lens(236, 72, 9, '#3f6a64', '#2b6a78')
    lens(241, 94, 9, '#3f6a64', '#2b6a78')
    front = S_rr(118, 158, 100, 206, 18, -8)
    G(front, K('#20242b'), .2)
    scr = S_rr(118, 158, 92, 198, 13, -8)
    P(scr, wall(44, K('#fb923c'), K('#f43f5e'), K('#4c1d95')))
    P(S_c(103, 63, 3.2), K('#05060a'))
    widgets(78, 110, 80, 100, 4)
    gloss(scr, .22)


def phone5():
    sh(160, 262, 80, 9)
    outer = S_rr(160, 150, 120, 230, 24)
    G(outer, K('#f59e0b'), .12)
    P(S_rr(160, 150, 106, 216, 18), K('#171a20'))
    for (x, y) in [(114, 54), (206, 54), (114, 246), (206, 246)]:
        P(S_c(x, y, 3), K('#d1d5db'))
    scr = S_rr(160, 142, 92, 160, 7)
    P(scr, wall(55, K('#065f46'), K('#10b981'), K('#fde047')))
    widgets(114, 62, 92, 160, 8)
    gloss(scr, .18)
    for x in (130, 160, 190):
        P(S_c(x, 238, 7), K('#2c313a'))
    P(S_rr(160, 238, 6, 6, 2), K('#fbbf24'))
    P(S_rr(220, 110, 5, 40, 2), K('#92400e'))


# ================================================================ HEADPHONES
def cup(cx, cy, w, h, col, side):
    b = S_rr(cx, cy, w, h, w * .42)
    Cy(b, col)
    rim(b, .3)
    P(S_e(cx + side * w * .5, cy, w * .22, h * .38), K('#16181d'))
    P(S_e(cx + side * w * .46, cy - 4, w * .12, h * .2), (255, 255, 255, .12))


def headphone1():
    sh(160, 244, 120, 10)
    path(arcpts(160, 135, 84, 86, 190, 350), 8, K('#2b2f38'))
    path(arcpts(160, 135, 84, 86, 200, 340), 3.5, K('#9aa3b2'))
    P(S_cap(78, 140, 78, 160, 6), K('#8d95a3'))
    P(S_cap(242, 140, 242, 160, 6), K('#8d95a3'))
    cup(78, 178, 46, 86, K('#cfd4dc'), 1)
    cup(242, 178, 46, 86, K('#cfd4dc'), -1)


def headphone2():
    sh(160, 240, 110, 10)
    case = S_rr(160, 196, 148, 82, 34)
    G(case, K('#f1f3f6'), .05)
    rim(case, .6)
    P(S_rr(160, 178, 130, 3, 1.5), (0, 0, 0, .12))
    P(S_c(160, 226, 3), K('#34d399'))
    for s in (-1, 1):
        cx = 160 + s * 44
        P(S_cap(cx + s * 6, 120, cx + s * 2, 168, 8), K('#e5e7eb'))
        P(S_e(cx + s * 4, 104, 25, 28, s * 14), lin(76, 132, K('#ffffff'), K('#c7ccd6')))
        P(S_e(cx - s * 6, 108, 12, 14), K('#2c3038'))
        P(S_e(cx + s * 12, 96, 7, 4, -35), (255, 255, 255, .8))
    P(S_rr(160, 174, 50, 8, 4), K('#d3d8e0'))


def headphone3():
    sh(160, 250, 110, 9)
    band = arcpts(160, 112, 92, 112, 5, 175)
    path(band, 8, K('#0f766e'))
    path(arcpts(160, 112, 92, 112, 20, 160), 3, (255, 255, 255, .25))
    for s in (-1, 1):
        x = 160 + s * 92
        P(S_rr(x, 112, 22, 40, 10), K('#134e4a'))
        P(S_cap(x, 130, x - s * 6, 190, 1.4), K('#0b3b38'))
        P(S_e(x - s * 6, 200, 12, 14), lin(188, 214, K('#e2e8f0'), K('#94a3b8')))
        P(S_e(x - s * 6 - s * 1, 212, 8, 6), K('#1f2937'))
    P(S_rr(160, 224, 70, 12, 6), K('#134e4a'))
    P(S_c(160, 224, 2.4), K('#4ade80'))


def headphone4():
    sh(160, 246, 118, 10)
    path(arcpts(160, 132, 84, 84, 190, 350), 9, K('#111317'))
    path(arcpts(160, 132, 84, 84, 215, 325), 3, K('#ef4444'))
    for cx, s in ((76, 1), (244, -1)):
        b = S_rr(cx, 176, 50, 92, 22)
        Cy(b, K('#1c1f26'), .2)
        P(S_ring(S_c(cx + s * 4, 176, 17), 4), linx(50, 270, K('#ff0040'), K('#ff9500')))
        P(S_c(cx + s * 4, 176, 17), K('#ff0040'), .12, blur=6)
        P(S_e(cx + s * 24, 176, 11, 34), K('#0c0d10'))
    path(curve((60, 206), (58, 242), (100, 248)), 3.5, K('#2a2e37'))
    P(S_e(104, 248, 12, 8), K('#111317'))
    P(S_c(112, 248, 3), K('#ef4444'))


def headphone5():
    sh(160, 244, 124, 10)
    path(arcpts(160, 140, 86, 90, 190, 350), 10, K('#6b4423'))
    path(arcpts(160, 140, 86, 90, 205, 335), 4, K('#d4a574'))
    for cx in (80, 240):
        P(S_cap(cx, 130, cx, 160, 5), K('#9ca3af'))
        wood = S_c(cx, 184, 42)
        P(wood, rad(cx - 12, cx and 170, 60, K('#c08a52'), K('#5e3a1c')))
        for r in (36, 29, 22, 15, 8):
            P(S_ring(S_c(cx, 184, r), 1.6), (30, 15, 5, .55))
        for k in range(16):
            a = k * math.pi / 8
            P(S_cap(cx + 10 * math.cos(a), 184 + 10 * math.sin(a), cx + 33 * math.cos(a), 184 + 33 * math.sin(a), .7),
              (30, 15, 5, .35))
        rim(wood, .35)


# ================================================================ SMARTWATCHES
def watch_strap_v(col, top=0, bot=320, w=66, holes=False):
    top_s = S_rr(160, 74, w, 110, 14)
    bot_s = S_rr(160, 246, w, 110, 14)
    G(top_s, col, .15)
    G(bot_s, col, .15)
    if holes:
        for i in range(5):
            P(S_c(160, 215 + i * 18, 3.2), (0, 0, 0, .55))


def watch1():
    sh(160, 262, 70, 8)
    watch_strap_v(K('#1f2937'), holes=True)
    P(S_rr(228, 148, 10, 24, 4), K('#9ca3af'))
    case = S_c(160, 160, 62)
    P(case, lin(98, 222, K('#e5e7eb'), K('#6b7280')))
    P(S_c(160, 160, 54), K('#07080b'))
    for r, c, a1 in ((44, '#fb2c4b', 280), (35, '#a3e635', 230), (26, '#22d3ee', 190)):
        P(S_ring(S_c(160, 160, r), 6), (255, 255, 255, .08))
        P(S_arc(160, 160, r, 6, -90, a1), K(c))
    P(S_c(160, 160, 7), K('#fff'), .9)
    P(S_e(135, 128, 18, 7, -40), (255, 255, 255, .12))


def watch2():
    sh(160, 262, 70, 8)
    top_s = S_rr(160, 70, 70, 100, 16)
    bot_s = S_rr(160, 250, 70, 100, 16)
    G(top_s, K('#f472b6'), .15)
    G(bot_s, K('#f472b6'), .15)
    for i in range(4):
        P(S_c(160, 222 + i * 14, 3), (0, 0, 0, .35))
    case = S_rr(160, 160, 106, 124, 28)
    G(case, K('#f5d0c5'), .15)
    rim(case, .5)
    P(S_rr(216, 142, 7, 26, 3), K('#d6a99c'))
    scr = S_rr(160, 160, 94, 112, 22)
    P(scr, K('#05060a'))
    digits(123, 116, 24, '0715', (255, 255, 255, .95))
    for i in range(6):
        P(S_rr(122 + i * 11, 190 - i * 2.2 + (i % 2) * 6, 6, 18 + (i * 7) % 20, 2), hsv(.9 - i * .04, .7, 1))
    P(S_arc(160, 160, 50, 3, -50, 60), K('#22d3ee'))
    gloss(scr, .2)


def watch3():
    sh(160, 262, 74, 8)
    for cy in (66, 254):
        s = S_rr(160, cy, 70, 104, 10)
        G(s, K('#18181b'), .15)
        for k in range(6):
            P(S_rr(160, cy - 40 + k * 15, 52, 2.5, 1), (255, 255, 255, .08))
    oct_ = S_poly([(160 + 66 * math.cos(math.radians(22.5 + 45 * i)), 160 + 66 * math.sin(math.radians(22.5 + 45 * i)))
                   for i in range(8)])
    G(oct_, K('#fb923c'), .12)
    rim(oct_, .4)
    for i in range(8):
        a = math.radians(45 * i)
        P(S_c(160 + 58 * math.cos(a), 160 + 58 * math.sin(a), 2.2), K('#7c2d12'))
    P(S_c(160, 160, 52), K('#0a0b0e'))
    P(S_rr(228, 138, 10, 22, 3), K('#d1d5db'))
    P(S_rr(228, 184, 10, 22, 3), K('#d1d5db'))
    P(S_rr(92, 160, 10, 22, 3), K('#d1d5db'))
    digits(118, 132, 28, '1224', K('#a3e635'))
    P(S_rr(160, 190, 60, 3, 1.5), K('#a3e635'), .6)
    for i in range(3):
        P(S_rr(138 + i * 22, 202, 14, 5, 2), K('#fb923c'))


def watch4():
    sh(160, 196, 130, 9)
    band = S_rr(160, 160, 268, 42, 20)
    G(band, K('#14b8a6'), .15)
    for i in range(6):
        P(S_c(32 + i * 8, 160, 2.2), (0, 0, 0, .35))
        P(S_c(288 - i * 8, 160, 2.2), (0, 0, 0, .35))
    mod = S_rr(160, 160, 80, 52, 14)
    G(mod, K('#0b0f14'), .2)
    rim(mod, .35)
    scr = S_rr(160, 160, 72, 44, 10)
    P(scr, K('#030507'))
    P(S_c(143, 154, 5), K('#fb7185'))
    P(S_c(153, 154, 5), K('#fb7185'))
    P(S_poly([(138, 156), (158, 156), (148, 168)]), K('#fb7185'))
    digits(166, 148, 20, '72', K('#ffffff'))
    P(S_cap(138, 172, 150, 172, 1.2), K('#22d3ee'))
    gloss(scr, .2)


def watch5():
    sh(160, 262, 70, 8)
    for cy, flip in ((66, 1), (254, -1)):
        s = S_rr(160, cy, 58, 108, 12)
        G(s, K('#7c4a24'), .15)
        for k in range(5):
            P(S_cap(136 + 0, cy - 40 + k * 18, 136, cy - 34 + k * 18, .8), (255, 235, 200, .6))
            P(S_cap(184, cy - 40 + k * 18, 184, cy - 34 + k * 18, .8), (255, 235, 200, .6))
    case = S_c(160, 160, 62)
    P(case, lin(98, 222, K('#fde68a'), K('#a16207')))
    P(S_c(160, 160, 55), K('#f4ecd8'))
    P(S_ring(S_c(160, 160, 55), 2), K('#8a6a1e'))
    for i in range(12):
        a = math.radians(i * 30)
        P(S_cap(160 + 44 * math.cos(a), 160 + 44 * math.sin(a), 160 + 50 * math.cos(a), 160 + 50 * math.sin(a),
                1.6 if i % 3 else 2.4), K('#3b2f1b'))
    P(S_cap(160, 160, 160 + 30 * math.cos(math.radians(-60)), 160 + 30 * math.sin(math.radians(-60)), 2.2), K('#1f2937'))
    P(S_cap(160, 160, 160 + 40 * math.cos(math.radians(30)), 160 + 40 * math.sin(math.radians(30)), 1.6), K('#1f2937'))
    P(S_c(160, 160, 3.2), K('#a16207'))
    P(S_rr(228, 150, 10, 20, 4), K('#d4a017'))
    P(S_c(160, 190, 8), K('#e7dcc0'))
    P(S_ring(S_c(160, 190, 8), 1), K('#8a6a1e'))


# ================================================================ TABLETS
def tablet1():
    sh(160, 242, 110, 8)
    P(S_poly([(150, 196), (170, 196), (200, 236), (120, 236)]), K('#9ca3af'))
    G(S_rr(160, 238, 130, 10, 5), K('#6b7280'), .2)
    body = S_rr(160, 120, 240, 156, 16)
    G(body, K('#2b2f36'), .15)
    rim(body, .3)
    scr = S_rr(160, 120, 224, 140, 8)
    P(scr, wall(61, K('#0d9488'), K('#38bdf8'), K('#fde68a')))
    widgets(48, 50, 224, 140, 6)
    gloss(scr)


def tablet2():
    sh(160, 262, 90, 9)
    body = S_rr(150, 150, 150, 220, 16)
    G(body, K('#d9dde4'), .08)
    scr = S_rr(150, 150, 138, 208, 9)
    P(scr, K('#f8fafc'))
    P(S_rr(150, 100, 100, 70, 6), wall(71, K('#fb7185'), K('#fcd34d'), K('#60a5fa')))
    P(S_cap(100, 175, 195, 175, 3), K('#334155'))
    P(S_cap(100, 190, 170, 190, 3), K('#94a3b8'))
    P(S_cap(100, 205, 185, 205, 3), K('#94a3b8'))
    P(S_c(205, 215, 14), K('#a7f3d0'))
    P(S_cap(180, 238, 262, 70, 4.5), K('#f1f5f9'))
    P(S_cap(180, 238, 262, 70, 1.4), K('#cbd5e1'))
    P(S_cap(262, 70, 266, 56, 3.4), K('#334155'))
    P(S_poly([(180, 238), (176, 250), (184, 244)]), K('#111'))


def tablet3():
    sh(160, 262, 90, 9)
    body = S_rr(160, 150, 150, 220, 16)
    P(body, lambda x, y: mix(K('#6ee7b7'), K('#0f766e'), clamp(((y - 40) + (x - 85) * .4) / 260)))
    rim(body, .35)
    cam = S_rr(100, 78, 44, 44, 12)
    P(cam, K('#c7f9e5'), .85)
    lens(100, 70, 9, '#3d5b52')
    lens(100, 92, 7, '#3d5b52')
    P(S_c(116, 70, 3), K('#fff7d6'))
    P(S_rr(237, 150, 6, 100, 3), (255, 255, 255, .45))
    P(S_cap(160, 208, 160, 208, 0.1), (0, 0, 0))
    gloss(body, .2)


def tablet4():
    sh(160, 240, 130, 9)
    body = S_rr(160, 100, 220, 134, 12)
    G(body, K('#1f2937'), .15)
    scr = S_rr(160, 100, 206, 120, 6)
    P(scr, wall(81, K('#1e3a8a'), K('#a855f7'), K('#fb923c')))
    widgets(57, 40, 206, 120, 3)
    gloss(scr)
    P(S_rr(160, 170, 224, 8, 3), K('#374151'))
    kb = S_poly([(60, 178), (260, 178), (284, 232), (36, 232)])
    G(kb, K('#2f3541'), .12)
    for r in range(4):
        t0 = r / 4
        for c in range(11):
            xl = 60 - 24 * t0 + (200 + 48 * t0) * c / 11 + 2
            xr = xl + (200 + 48 * t0) / 11 - 3
            y0 = 182 + r * 11.4
            P(S_poly([(xl, y0), (xr, y0), (xr + 1, y0 + 8), (xl - 1, y0 + 8)]), K('#59606e'))


def tablet5():
    sh(160, 262, 82, 9)
    body = S_rr(160, 150, 164, 226, 12)
    G(body, K('#c9ccd1'), .1)
    scr = S_rr(160, 150, 140, 200, 4)
    P(scr, K('#efe9d8'))
    P(S_cap(100, 74, 205, 74, 3.2), K('#2b2b2b'))
    for i in range(5):
        P(S_cap(100, 90 + i * 11, 220 - (i % 3) * 16, 90 + i * 11, 1.6), K('#555'))
    P(S_rr(160, 175, 100, 46, 3), K('#cfc7b2'))
    P(S_poly([(112, 192), (140, 164), (160, 184), (176, 170), (208, 192)]), K('#8f866f'))
    P(S_c(194, 166, 6), K('#8f866f'))
    for i in range(3):
        P(S_cap(100, 214 + i * 10, 214 - i * 18, 214 + i * 10, 1.6), K('#555'))
    P(S_rr(160, 252, 24, 4, 2), (0, 0, 0, .25))


# ================================================================ CAMERAS
def camera1():
    sh(160, 244, 136, 10)
    P(S_rr(150, 108, 90, 34, 10), lin(90, 126, K('#2a2c33'), K('#101114')))
    P(S_poly([(112, 126), (190, 126), (206, 140), (96, 140)]), K('#1b1d22'))
    body = S_rr(160, 178, 238, 108, 16)
    G(body, K('#23252b'), .12)
    rim(body, .25)
    P(S_rr(236, 180, 50, 108, 16), K('#16171b'))
    for k in range(7):
        P(S_cap(222, 148 + k * 10, 252, 148 + k * 10, .8), (255, 255, 255, .08))
    P(S_rr(78, 134, 36, 14, 4), K('#8e95a1'))
    P(S_c(230, 126, 8), K('#ef4444'))
    P(S_rr(125, 146, 18, 6, 2), K('#8e95a1'))
    P(S_rr(204, 126, 24, 8, 3), K('#b9bec8'))
    lens(150, 182, 58)
    P(S_ring(S_c(150, 182, 62), 4), K('#52555e'))
    P(S_rr(78, 160, 20, 12, 4), K('#e5e7eb'))


def camera2():
    sh(160, 238, 130, 9)
    body = S_rr(160, 160, 232, 118, 12)
    G(body, K('#d8dbe1'), .15)
    P(S_rr(160, 190, 232, 60, 12), K('#1b1c20'))
    P(S_rr(160, 164, 232, 4, 1), K('#9aa1ad'))
    P(S_rr(96, 98, 48, 22, 5), K('#cbd0d8'))
    P(S_rr(96, 98, 42, 16, 3), K('#2a2d34'))
    P(S_rr(205, 92, 36, 18, 3), lin(80, 104, K('#e9ecf0'), K('#9ca3af')))
    P(S_c(237, 94, 14), lin(80, 108, K('#f3f4f6'), K('#9ca3af')))
    for k in range(18):
        a = k * math.pi / 9
        P(S_cap(237 + 11 * math.cos(a), 94 + 11 * math.sin(a), 237 + 14 * math.cos(a), 94 + 14 * math.sin(a), .8),
          K('#4b5160'))
    P(S_c(160, 170, 52), K('#16171b'))
    lens(160, 170, 46, '#2b2d34', '#2f6f8f')
    P(S_c(250, 150, 5), K('#ef4444'))
    P(S_rr(80, 142, 20, 8, 3), K('#2a2d34'))


def camera3():
    sh(160, 236, 120, 9)
    body = S_rr(160, 162, 214, 118, 18)
    P(body, lambda x, y: mix(K('#f5e1b9'), K('#bd9a5c'), clamp((y - 100) / 130)))
    rim(body, .5)
    P(S_rr(232, 164, 26, 100, 12), K('#a8864a'))
    P(S_rr(222, 118, 34, 18, 5), K('#fffbe8'))
    P(S_rr(222, 118, 28, 12, 3), K('#e9d9a5'))
    P(S_c(116, 112, 7), K('#2a2d34'))
    P(S_rr(88, 120, 14, 8, 3), K('#2a2d34'))
    lens(128, 168, 42, '#7a6a48', '#385f84')
    P(S_c(196, 128, 6), K('#e11d48'))
    for k in range(6):
        P(S_c(190 + (k % 3) * 6, 192 + (k // 3) * 6, 1.4), K('#7a6a48'))
    P(S_rr(196, 158, 20, 14, 3), K('#2a2d34'))


def camera4():
    sh(160, 256, 100, 8)
    frame = S_rr(150, 160, 156, 130, 26)
    G(frame, K('#facc15'), .1)
    body = S_rr(150, 160, 134, 108, 18)
    G(body, K('#16181d'), .2)
    rim(body, .3)
    lens(132, 160, 36, '#2e3138', '#2d5aa8')
    scr = S_rr(190, 134, 40, 30, 6)
    P(scr, K('#0b1626'))
    P(S_ring(S_c(190, 135, 8), 2), K('#38bdf8'))
    P(S_rr(190, 156, 22, 6, 3), K('#ef4444'))
    P(S_rr(150, 242, 44, 22, 4), K('#facc15'))
    P(S_c(150, 246, 7), K('#6b7280'))
    P(S_c(150, 246, 3), K('#d1d5db'))
    P(S_rr(150, 226, 16, 10, 2), K('#facc15'))


def camera5():
    sh(160, 246, 112, 9)
    photo = S_rr(160, 82, 100, 62, 3)
    P(photo, K('#fdfdf7'))
    P(S_rr(160, 78, 88, 44, 2), wall(91, K('#38bdf8'), K('#f472b6'), K('#fde68a')))
    body = S_rr(160, 168, 216, 150, 26)
    G(body, K('#99f6e4'), .12)
    rim(body, .5)
    P(S_rr(160, 114, 216, 30, 15), K('#f8fafc'))
    P(S_rr(160, 120, 80, 4, 2), (0, 0, 0, .3))
    for i in range(5):
        P(S_rr(160, 214 + i * 3.4, 110, 2.6, 1), hsv(.02 + i * .17, .75, .95))
    P(S_c(160, 170, 50), K('#e5e7eb'))
    P(S_ring(S_c(160, 170, 50), 3), K('#9ca3af'))
    lens(160, 170, 42, '#4b5563', '#5b4fa8')
    P(S_rr(228, 138, 30, 18, 4), K('#fff7d1'))
    P(S_c(94, 136, 8), K('#111'))
    P(S_c(94, 136, 4), K('#334155'))
    P(S_c(210, 214, 6), K('#fb7185'))


# ================================================================ TELEVISIONS
def tv_stand(cx, y, w=120):
    G(S_rr(cx, y + 8, w, 8, 4), K('#3f444e'), .2)
    P(S_rr(cx, y, 28, 18, 3), K('#2a2e36'))


def tv1():
    sh(160, 244, 130, 8)
    tv_stand(160, 206)
    fr = S_rr(160, 124, 262, 150, 5)
    G(fr, K('#0e1014'), .2)
    scr = S_rr(160, 124, 254, 142, 2)
    P(scr, lin(53, 195, K('#1e3a8a'), K('#fcd34d')))
    P(S_c(205, 128, 18), K('#fff3b0'))
    P(S_c(205, 128, 30), (255, 240, 170, .35), blur=14)
    P(S_poly([(33, 195), (33, 160), (80, 120), (118, 160), (150, 130), (200, 195)]), K('#1f3b5c'))
    P(S_poly([(120, 195), (170, 150), (220, 170), (287, 140), (287, 195)]), K('#0f2540'))
    P(S_poly([(33, 195), (33, 178), (90, 168), (140, 195)]), K('#091a30'))
    gloss(scr, .16)


def tv2():
    sh(160, 244, 140, 8)
    tv_stand(160, 208, 130)
    top = curve((22, 92), (160, 104), (298, 92))
    bot = curve((298, 192), (160, 204), (22, 192))
    G(S_poly(top + bot), K('#0d0f13'), .2)
    t2 = curve((28, 98), (160, 108), (292, 98))
    b2 = curve((292, 186), (160, 198), (28, 186))
    sc = S_poly(t2 + b2)
    P(sc, lin(98, 196, K('#4c1d95'), K('#fb923c')))
    P(S_c(160, 160, 22), K('#fff1c2'))
    P(S_e(160, 160, 60, 28), (255, 200, 140, .3), blur=16)
    P(S_poly([(28, 160), (292, 160), (292, 188), (28, 188)]), (20, 10, 50, .55))
    for i in range(6):
        P(S_cap(110 + i * 4, 168 + i * 3, 210 - i * 4, 168 + i * 3, 1), (255, 220, 160, .6))
    gloss(sc, .14)


def tv3():
    sh(160, 244, 130, 8)
    fr = S_rr(160, 106, 252, 142, 5)
    G(fr, K('#101216'), .2)
    scr = S_rr(160, 106, 244, 134, 2)
    P(scr, K('#12141c'))
    cols = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#14b8a6']
    for i in range(6):
        P(S_rr(78 + (i % 3) * 64, 90 + (i // 3) * 54, 58, 46, 5), wall(100 + i, K(cols[i]), K(cols[(i + 2) % 6]),
                                                                           K('#111827')))
    P(S_rr(160, 54, 64, 5, 2.5), (255, 255, 255, .6))
    gloss(scr, .12)
    bar = S_rr(160, 204, 236, 24, 11)
    G(bar, K('#2a2d34'), .2)
    for i in range(30):
        P(S_c(60 + i * 6.8, 204, 1.2), (255, 255, 255, .22))
    P(S_rr(160, 232, 200, 6, 3), K('#1a1c21'))


def tv4():
    sh(160, 248, 120, 9)
    for sx in (-1, 1):
        P(S_cap(160, 62, 160 + sx * 56, 18, 2), K('#c8ccd4'))
    for sx in (-70, 70):
        P(S_rr(160 + sx, 244, 22, 14, 3), K('#3f2a14'))
    body = S_rr(160, 156, 244, 176, 22)
    G(body, K('#9a6232'), .18)
    P(S_rr(160, 156, 244, 176, 22), lambda x, y: (60, 30, 5, .08 * math.sin(y * 1.9 + x * .2)))
    rim(body, .3)
    P(S_rr(125, 156, 158, 138, 34), K('#1b1d22'))
    scr = S_rr(125, 156, 148, 128, 30)
    P(scr, rad(110, 140, 100, K('#8ba39a'), K('#33423c')))
    P(S_rr(125, 156, 130, 6, 2), (255, 255, 255, .16))
    P(S_e(100, 124, 30, 12, -25), (255, 255, 255, .25))
    P(S_rr(228, 156, 56, 126, 8), K('#5b3a1b'))
    for y in (112, 150):
        P(S_c(228, y, 14), rad(224, y - 4, 16, K('#e5e7eb'), K('#6b7280')))
        P(S_cap(228, y, 228, y - 11, 1.6), K('#1f2937'))
    for k in range(5):
        P(S_cap(210, 186 + k * 6, 246, 186 + k * 6, 1.1), K('#2b1a0a'))


def tv5():
    sh(160, 244, 130, 6, .2)
    P(S_rr(160, 238, 250, 9, 3), K('#8a6a4a'))
    P(S_rr(160, 248, 230, 6, 3), K('#6b4f35'))
    P(S_rr(164, 146, 252, 150, 4), (0, 0, 0), .22, blur=12)
    fr = S_rr(160, 140, 252, 150, 3)
    G(fr, K('#d9c7a6'), .1)
    scr = S_rr(160, 140, 234, 132, 1)
    P(scr, lin(74, 206, K('#fef3c7'), K('#fcd9a8')))
    P(S_c(120, 130, 38), K('#ea580c'))
    P(S_c(205, 120, 24), K('#0f766e'))
    P(S_poly([(43, 206), (43, 168), (110, 150), (180, 186), (277, 160), (277, 206)]), K('#7c2d12'))
    P(S_poly([(43, 206), (43, 188), (150, 178), (277, 192), (277, 206)]), K('#431407'))
    P(S_rr(160, 140, 234, 132, 1), (255, 255, 255, 0.0))
    gloss(scr, .1)
    P(S_rr(262, 222, 14, 20, 3), K('#e5e7eb'))
    P(S_e(262, 206, 11, 10), K('#e5e7eb'))
    P(S_cap(262, 200, 270, 188, 1.6), K('#3f6b3a'))


# ================================================================ GAMING
def gamepad():
    sh(160, 240, 120, 10)
    body = S_u(S_rr(160, 140, 156, 84, 38), S_e(96, 182, 30, 54, 16), S_e(224, 182, 30, 54, -16))
    P(body, lin(98, 236, K('#f8fafc'), K('#aeb6c3')))
    rim(body, .6)
    P(S_rr(104, 94, 52, 16, 7), K('#3b4252'))
    P(S_rr(216, 94, 52, 16, 7), K('#3b4252'))
    P(S_c(110, 140, 17), K('#d4d9e2'))
    P(S_c(110, 140, 12), rad(106, 136, 14, K('#4b5563'), K('#111827')))
    P(S_rr(110, 184, 12, 38, 3), K('#2b3140'))
    P(S_rr(110, 184, 38, 12, 3), K('#2b3140'))
    P(S_c(194, 184, 17), K('#d4d9e2'))
    P(S_c(194, 184, 12), rad(190, 180, 14, K('#4b5563'), K('#111827')))
    for (x, y, c) in ((216, 114, '#22c55e'), (238, 134, '#ef4444'), (194, 134, '#3b82f6'), (216, 154, '#facc15')):
        P(S_c(x, y, 10), K(c))
        P(S_ring(S_c(x, y, 10), 1), (0, 0, 0, .25))
    P(S_rr(150, 138, 14, 7, 3), K('#6b7280'))
    P(S_rr(172, 138, 14, 7, 3), K('#6b7280'))
    P(S_c(160, 160, 7), K('#0ea5e9'))


def handheld():
    sh(160, 232, 140, 9)
    L = S_rr(88, 150, 112, 140, 34)
    R = S_rr(232, 150, 112, 140, 34)
    G(L, K('#22d3ee'), .12)
    G(R, K('#f43f5e'), .12)
    P(S_rr(160, 150, 144, 120, 6), K('#0d1017'))
    scr = S_rr(160, 150, 132, 108, 3)
    P(scr, lin(96, 204, K('#60a5fa'), K('#bae6fd')))
    P(S_rr(160, 190, 132, 28, 0), K('#4d8f3a'))
    for i in range(7):
        P(S_rr(100 + i * 20, 197, 18, 10, 0), K('#8a5a2b'))
    P(S_rr(140, 142, 20, 20, 2), K('#8a5a2b'))
    P(S_rr(160, 142, 20, 20, 2), K('#fbbf24'))
    P(S_c(188, 172, 8), K('#7f1d1d'))
    P(S_c(88, 108, 15), K('#0b0e14'))
    P(S_c(88, 108, 10), K('#374151'))
    P(S_rr(88, 190, 10, 30, 3), K('#0b0e14'))
    P(S_rr(88, 190, 30, 10, 3), K('#0b0e14'))
    for (x, y) in ((232, 110), (252, 130), (212, 130), (232, 150)):
        P(S_c(x, y, 8), K('#fff1f2'))
    P(S_c(232, 190, 14), K('#0b0e14'))
    P(S_c(232, 190, 9), K('#374151'))
    gloss(scr, .14)


def vr():
    sh(160, 236, 120, 9)
    for sx in (-1, 1):
        P(S_rr(160 + sx * 112, 150, 28, 62, 12), K('#d1d5db'))
        P(S_cap(160 + sx * 112, 110, 160 + sx * 70, 72, 7), K('#e5e7eb'))
    path(curve((88, 82), (160, 36), (232, 82)), 6, K('#e5e7eb'))
    body = S_rr(160, 148, 206, 108, 38)
    G(body, K('#f8fafc'), .02)
    rim(body, .6)
    vis = S_rr(160, 148, 190, 90, 30)
    P(vis, lin(103, 193, K('#232634'), K('#05060a')))
    P(S_e(120, 128, 40, 8, -18), (255, 255, 255, .28))
    P(S_e(205, 160, 50, 22, -18), (140, 120, 255, .14), blur=10)
    P(S_poly([(144, 193), (176, 193), (170, 202), (150, 202)]), K('#cbd5e1'))
    P(S_c(120, 148, 5), K('#6b7280'))
    P(S_c(200, 148, 5), K('#6b7280'))
    P(S_rr(160, 210, 70, 10, 5), K('#1f2937'))


def arcade():
    sh(160, 246, 130, 11)
    top = S_poly([(52, 170), (268, 170), (294, 236), (26, 236)])
    G(top, K('#1b1c24'), .18)
    P(S_poly([(26, 236), (294, 236), (294, 248), (26, 248)]), K('#0b0c10'))
    rim(top, .25)
    P(S_c(110, 206, 24), K('#0c0d12'))
    P(S_ring(S_c(110, 206, 24), 3), K('#8b93a3'))
    P(S_cap(110, 206, 110, 144, 5), lin(144, 206, K('#e5e7eb'), K('#6b7280')))
    ball = S_c(110, 130, 22)
    P(ball, rad(102, 122, 30, K('#fca5a5'), K('#b91c1c')))
    P(S_e(102, 122, 7, 4, -30), (255, 255, 255, .8))
    cols = ['#facc15', '#22c55e', '#3b82f6', '#ef4444', '#a855f7', '#f97316']
    for i in range(6):
        x = 170 + (i % 3) * 36 + (i // 3) * 8
        y = 196 + (i // 3) * 26
        P(S_c(x, y, 13), K('#0c0d12'))
        P(S_e(x, y - 1, 11, 11), rad(x - 3, y - 5, 14, lighten(K(cols[i]), .45), darken(K(cols[i]), .1)))
    P(S_rr(150, 180, 16, 5, 2), K('#8b93a3'))
    P(S_rr(270, 188, 14, 5, 2), K('#8b93a3'))


def gamekeys():
    sh(160, 246, 140, 10)
    kb = S_poly([(36, 150), (256, 150), (276, 226), (16, 226)])
    G(kb, K('#14151a'), .18)
    rim(kb, .2)
    rows, cols = 5, 14
    for r in range(rows):
        for c in range(cols):
            t0, t1 = r / rows, (r + .8) / rows
            xl = lambda t: 36 - 20 * t
            xr = lambda t: 256 + 20 * t
            ua, ub = c / cols, (c + .8) / cols
            y0, y1 = 156 + t0 * 66, 156 + t1 * 66

            def X(u, t):
                return xl(t) + (xr(t) - xl(t)) * u
            col = hsv(.55 + c * .05 + r * .03, .75, 1)
            P(S_poly([(X(ua, t0) + 4, y0), (X(ub, t0) + 4, y0), (X(ub, t1) + 4, y1), (X(ua, t1) + 4, y1)]),
              darken(col, .55))
            P(S_poly([(X(ua, t0) + 5, y0 + .5), (X(ub, t0) + 3.5, y0 + .5), (X(ub, t1) + 3.5, y1 - 1),
                      (X(ua, t1) + 5, y1 - 1)]), col, .7)
    mouse = S_e(264, 96, 28, 40, 10)
    P(mouse, lin(56, 136, K('#2b2d35'), K('#0e0f13')))
    rim(mouse, .3)
    P(S_cap(255, 70, 263, 118, 1), K('#000'))
    P(S_rr(266, 82, 6, 16, 3), K('#22d3ee'))
    P(S_cap(240, 118, 280, 108, 2), hsv(.8, .8, 1))


# ================================================================ HOME APPLIANCES
def washer():
    sh(160, 252, 100, 9)
    body = S_rr(160, 148, 176, 216, 12)
    G(body, K('#f1f3f7'), .02)
    rim(body, .6)
    P(S_rr(160, 70, 176, 38, 0), K('#e1e5ec'))
    P(S_rr(100, 70, 28, 18, 4), K('#0b1220'))
    digits(88, 62, 16, '45', K('#38bdf8'))
    P(S_c(215, 70, 12), rad(212, 66, 14, K('#fff'), K('#9ca3af')))
    P(S_cap(215, 70, 215, 60, 1.5), K('#374151'))
    P(S_c(160, 170, 70), K('#9ca3af'))
    P(S_c(160, 170, 62), lin(108, 232, K('#e5e7eb'), K('#6b7280')))
    glass = S_c(160, 170, 52)
    P(glass, rad(150, 160, 60, K('#3b82c4'), K('#08162e')))
    P(S_c(165, 182, 28), (120, 190, 255, .25), blur=8)
    P(S_e(138, 148, 20, 8, -40), (255, 255, 255, .5))
    P(S_rr(238, 170, 6, 22, 3), K('#9ca3af'))


def fridge():
    sh(160, 258, 80, 8)
    body = S_rr(160, 142, 126, 232, 10)
    G(body, K('#cfd5de'), .1)
    rim(body, .5)
    P(S_rr(160, 106, 126, 2.5, 0), K('#6b7280'))
    P(S_rr(160, 106, 126, 8, 0), (0, 0, 0, .14), blur=4)
    for y0, y1 in ((60, 96), (116, 160)):
        P(S_rr(122, (y0 + y1) / 2 + (30 if y0 > 100 else 0) - (0 if y0 > 100 else 0), 5, 40 if y0 > 100 else 22, 2.5),
          K('#6b7280'))
    P(S_rr(160, 70, 24, 36, 3), K('#0d1625'))
    digits(152, 62, 14, '4', K('#38bdf8'))
    P(S_cap(176, 66, 180, 66, 1), K('#38bdf8'))
    P(S_e(150, 120, 8, 70, 0), (255, 255, 255, .12))
    P(S_rr(160, 262, 100, 4, 2), (0, 0, 0, .3))
    P(S_rr(112, 264, 10, 6, 2), K('#374151'))
    P(S_rr(208, 264, 10, 6, 2), K('#374151'))


def robovac():
    sh(160, 236, 120, 12)
    P(S_e(160, 188, 108, 64), K('#101217'))
    top = S_e(160, 172, 108, 66)
    P(top, rad(140, 150, 130, K('#4b5563'), K('#0f1115')))
    rim(top, .35)
    P(S_ring(S_e(160, 172, 92, 54), 2), (255, 255, 255, .18))
    P(S_e(160, 166, 30, 18), K('#1a1c22'))
    P(S_e(160, 160, 30, 18), rad(150, 156, 34, K('#8b93a3'), K('#2b2f38')))
    P(S_e(160, 156, 18, 10), K('#0c0d10'))
    P(S_e(212, 178, 16, 10), K('#22c55e'), .9)
    P(S_e(212, 178, 22, 14), K('#22c55e'), .15, blur=6)
    P(S_e(108, 182, 10, 6), K('#d1d5db'))
    for k in range(5):
        P(S_cap(66 + k * 3, 220 - k * 3, 54 + k * 2, 228 - k * 3, 1.2), K('#fb923c'))


def purifier():
    sh(160, 258, 80, 9)
    body = S_rr(160, 145, 106, 220, 26)
    Cy(body, K('#f6f7f9'), .06)
    rim(body, .6)
    for r in range(8):
        for c in range(7):
            P(S_c(122 + c * 12, 62 + r * 11, 2.4), K('#9aa3b2'))
    P(S_rr(160, 172, 90, 4, 2), K('#d1d5db'))
    P(S_ring(S_c(160, 206, 24), 5), K('#d9dee6'))
    P(S_arc(160, 206, 24, 5, -90, 160), K('#2dd4bf'))
    P(S_c(160, 206, 11), K('#0f172a'))
    digits(154, 200, 12, '8', K('#2dd4bf'))
    P(S_rr(160, 254, 90, 8, 4), K('#cbd1da'))
    P(S_rr(160, 188, 56, 3, 1.5), (0, 0, 0, .1))


def fan():
    sh(160, 250, 70, 9)
    P(S_e(160, 242, 56, 10), lin(232, 252, K('#d1d5db'), K('#6b7280')))
    P(S_rr(160, 190, 9, 104, 4), K('#9ca3af'))
    P(S_rr(160, 148, 14, 24, 3), K('#4b5563'))
    P(S_c(160, 100, 76), (255, 255, 255, .25), blur=3)
    for ang in (-90, 30, 150):
        a = math.radians(ang)
        P(S_e(160 + 34 * math.cos(a), 100 + 34 * math.sin(a), 38, 15, ang), lin(60, 140, K('#7dd3fc'), K('#0369a1')), .9)
    P(S_c(160, 100, 12), lin(88, 112, K('#e5e7eb'), K('#6b7280')))
    for r in (72, 58, 44, 30):
        P(S_ring(S_c(160, 100, r), 1.6), K('#cbd0d8'))
    for k in range(10):
        a = math.radians(k * 36)
        P(S_cap(160, 100, 160 + 73 * math.cos(a), 100 + 73 * math.sin(a), .8), (200, 205, 215, .8))
    P(S_ring(S_c(160, 100, 75), 4), K('#e5e7eb'))
    P(S_c(160, 100, 5), K('#374151'))


# ================================================================ KITCHEN APPLIANCES
def toaster():
    sh(160, 232, 120, 10)
    P(S_rr(125, 112, 62, 44, 12), lin(90, 134, K('#e2a653'), K('#a8672c')))
    P(S_rr(195, 112, 62, 44, 12), lin(90, 134, K('#e2a653'), K('#a8672c')))
    body = S_rr(160, 168, 204, 118, 38)
    Cy(body, K('#e6e9ee'), .12)
    rim(body, .6)
    top = S_rr(160, 124, 196, 24, 12)
    P(top, K('#9aa1ad'))
    for cx in (125, 195):
        P(S_rr(cx, 124, 66, 7, 3.5), K('#1d1f25'))
    P(S_rr(160, 186, 150, 3, 1.5), (0, 0, 0, .1))
    P(S_rr(248, 168, 18, 44, 7), K('#4b5563'))
    P(S_rr(248, 160, 8, 12, 3), K('#d1d5db'))
    P(S_c(88, 162, 13), rad(84, 158, 16, K('#f3f4f6'), K('#6b7280')))
    P(S_cap(88, 162, 88, 152, 1.6), K('#111'))
    P(S_rr(160, 224, 180, 10, 5), K('#6b7280'))


def blender():
    sh(160, 252, 100, 9)
    base = S_rr(160, 226, 130, 52, 14)
    G(base, K('#be123c'), .1)
    rim(base, .3)
    P(S_c(160, 228, 13), rad(156, 224, 16, K('#f3f4f6'), K('#6b7280')))
    P(S_cap(160, 228, 160, 218, 1.6), K('#111'))
    jar = S_poly([(110, 66), (210, 66), (200, 196), (120, 196)])
    P(jar, (200, 225, 240, .35))
    P(S_poly([(113, 120), (207, 120), (200, 196), (120, 196)]), lin(120, 196, K('#fb7185'), K('#be185d')), .92)
    P(S_e(160, 120, 47, 5), K('#fda4af'))
    for (x, y, r) in ((140, 150, 4), (172, 164, 6), (152, 178, 3), (184, 138, 3)):
        P(S_c(x, y, r), (255, 255, 255, .35))
    P(S_poly([(114, 70), (126, 70), (126, 190), (122, 190)]), (255, 255, 255, .35))
    P(S_ring(S_poly([(110, 66), (210, 66), (200, 196), (120, 196)]), 1.5), (255, 255, 255, .5))
    G(S_rr(160, 202, 84, 12, 4), K('#9ca3af'), .2)
    P(S_rr(160, 58, 108, 16, 7), K('#1f2937'))
    P(S_rr(160, 48, 28, 12, 5), K('#374151'))


def kettle():
    sh(160, 244, 110, 9)
    P(S_rr(150, 236, 150, 18, 9), K('#1f2937'))
    body = S_poly(smooth([(98, 98), (200, 98), (222, 220), (78, 220)], 3))
    Cy(body, K('#34d399'), .2)
    rim(body, .35)
    P(S_poly(smooth([(204, 128), (252, 98), (258, 108), (222, 168)], 2)), K('#10b981'))
    P(S_ring(S_rr(86, 150, 52, 94, 24), 12), K('#1f2937'))
    P(S_rr(150, 94, 100, 14, 7), K('#1f2937'))
    P(S_c(150, 82, 10), K('#1f2937'))
    P(S_rr(150, 154, 8, 90, 4), (255, 255, 255, .3))
    P(S_rr(150, 205, 76, 6, 3), (0, 0, 0, .14))
    P(S_c(188, 190, 5), K('#fb923c'))
    P(S_rr(150, 224, 96, 8, 4), K('#2f3846'))


def coffee():
    sh(160, 250, 126, 9)
    G(S_rr(160, 242, 196, 14, 6), K('#1f2937'), .2)
    col = S_rr(236, 142, 54, 196, 10)
    G(col, K('#2b303a'), .15)
    head = S_rr(170, 80, 140, 46, 12)
    G(head, K('#374151'), .15)
    rim(head, .25)
    P(S_rr(170, 100, 90, 6, 3), K('#0f1217'))
    digits(228, 56, 18, '07', K('#fb923c'))
    for k in range(3):
        P(S_cap(190 + k * 5, 108, 190 + k * 5, 122 + k * 3, 1), K('#6b4423'))
    carafe = S_rr(166, 190, 84, 90, 16)
    P(carafe, (210, 225, 235, .3))
    P(S_rr(166, 213, 80, 44, 12), lin(190, 235, K('#6b3f1d'), K('#2a1507')))
    P(S_e(166, 192, 36, 4), K('#8a5530'))
    P(S_ring(S_rr(166, 190, 84, 90, 16), 2), (255, 255, 255, .5))
    P(S_ring(S_rr(222, 195, 28, 56, 12), 7), K('#111827'))
    P(S_rr(166, 140, 98, 10, 5), K('#111827'))
    P(S_c(196, 184, 4), K('#f87171'))


def mixer():
    sh(160, 252, 118, 9)
    base = S_rr(172, 238, 170, 26, 12)
    G(base, K('#dc2626'), .12)
    col = S_poly(smooth([(212, 80), (236, 100), (236, 232), (196, 232), (200, 130)], 2))
    G(col, K('#ef4444'), .15)
    head = S_poly(smooth([(80, 62), (216, 56), (240, 86), (236, 112), (90, 112), (74, 92)], 3))
    G(head, K('#ef4444'), .18)
    rim(head, .4)
    P(S_rr(150, 120, 44, 12, 5), K('#9ca3af'))
    P(S_cap(104, 106, 104, 138, 5), K('#9ca3af'))
    P(S_c(236, 78, 8), rad(233, 75, 10, K('#f3f4f6'), K('#6b7280')))
    P(S_rr(110, 215, 60, 4, 2), K('#9ca3af'))
    bowl = S_poly(smooth([(72, 160), (150, 160), (140, 222), (84, 222)], 2))
    P(bowl, linx(72, 150, K('#f3f4f6'), K('#8b93a3')))
    P(S_e(111, 160, 40, 8), K('#cbd0d8'))
    P(S_ring(S_c(104, 150, 11), 3), K('#6b7280'))
    for k in range(4):
        a = k * 45
        P(S_e(104, 146, 3, 12, a), K('#6b7280'), .8)
    P(S_e(100, 190, 8, 20, 12), (255, 255, 255, .3))


# ================================================================ FASHION
def tee():
    sh(160, 262, 100, 7, .25)
    half = [(160, 62), (190, 58), (230, 66), (282, 98), (262, 140), (232, 124), (234, 250), (160, 254)]
    pts = sym(half, 160)
    body = S_poly(smooth(pts, 2))
    P(body, fabric(K('#2563eb')))
    P(S_in(body, 0), (0, 0, 0, 0))
    for i in range(7):
        P(S_poly(smooth(pts, 2)), lambda x, y, i=i: (255, 255, 255, .5 if abs(((y - 100) % 22) - 11) < 4 and 100 < y < 240 else 0), .7)
        break
    P(S_e(160, 64, 28, 14), K('#1d4ed8'))
    P(S_e(160, 60, 22, 8), K('#0b1220'), .45)
    P(S_cap(130, 120, 132, 246, .8), (0, 0, 0, .12))
    P(S_cap(190, 120, 188, 246, .8), (0, 0, 0, .12))
    P(S_cap(232, 236, 90, 236, 0.1), K('#000'), 0)


def dress():
    sh(160, 262, 90, 7, .25)
    half = [(160, 44), (178, 46), (184, 88), (176, 120), (192, 132), (262, 250), (160, 256)]
    body = S_poly(smooth(sym(half, 160), 2))
    P(body, fabric(K('#e11d48')))
    for dx in (-1, 1):
        P(S_cap(160 + dx * 18, 46, 160 + dx * 22, 88, 3), K('#9f1239'))
    P(S_rr(160, 130, 38, 10, 4), K('#fcd34d'))
    for i in range(6):
        P(S_cap(160 + (i - 2.5) * 20, 142, 160 + (i - 2.5) * 36, 252, .9), (0, 0, 0, .14))
    P(S_e(160, 82, 22, 12), K('#be123c'))


def jacket():
    sh(160, 262, 100, 7, .25)
    half = [(160, 56), (196, 56), (250, 74), (292, 218), (262, 228), (236, 130), (234, 246), (160, 250)]
    body = S_poly(smooth(sym(half, 160), 1))
    P(body, fabric(K('#78350f')))
    rim(body, .12)
    P(S_poly([(160, 56), (196, 56), (210, 90), (160, 130)]), K('#5c2a0b'))
    P(S_poly([(160, 56), (124, 56), (110, 90), (160, 130)]), K('#5c2a0b'))
    P(S_cap(160, 130, 160, 248, 1.6), K('#e5e7eb'))
    for y in range(138, 246, 8):
        P(S_cap(158, y, 162, y, 2), K('#9ca3af'))
    for dx in (-1, 1):
        P(S_rr(160 + dx * 46, 200, 38, 6, 3), K('#3b1a07'))
        P(S_cap(160 + dx * 100, 150, 160 + dx * 88, 215, 0.9), (0, 0, 0, .15))


def jeans():
    sh(160, 262, 90, 7, .25)
    pts = [(104, 52), (216, 52), (232, 256), (176, 256), (160, 120), (144, 256), (88, 256)]
    body = S_poly(smooth(pts, 2))
    P(body, fabric(K('#1e40af'), .2))
    P(S_rr(160, 60, 112, 14, 2), K('#1a3a99'))
    for x in (126, 160, 194):
        P(S_rr(x, 60, 8, 12, 2), K('#0f1f5c'))
    P(S_cap(160, 66, 160, 120, 1), K('#f59e0b'))
    P(S_poly([(112, 76), (150, 76), (146, 112), (130, 122), (116, 108)]), K('#f59e0b'), .0)
    path(curve((112, 76), (124, 116), (150, 76)), 1, K('#fbbf24'))
    path(curve((208, 76), (196, 116), (170, 76)), 1, K('#fbbf24'))
    P(S_cap(118, 130, 106, 250, .9), (255, 255, 255, .18))
    P(S_cap(202, 130, 214, 250, .9), (255, 255, 255, .18))
    P(S_e(120, 200, 8, 40, 4), (255, 255, 255, .12), blur=6)


def hoodie():
    sh(160, 264, 100, 7, .25)
    half = [(160, 70), (194, 60), (226, 78), (284, 108), (268, 232), (242, 226), (240, 250), (160, 254)]
    body = S_poly(smooth(sym(half, 160), 1))
    P(body, fabric(K('#64748b')))
    hood = S_e(160, 66, 44, 34)
    P(hood, K('#475569'))
    P(S_e(160, 76, 24, 18), K('#1e293b'))
    pocket = S_poly([(106, 190), (214, 190), (226, 238), (94, 238)])
    P(pocket, K('#586577'))
    P(S_cap(104, 192, 216, 192, .8), (255, 255, 255, .25))
    P(S_cap(144, 94, 140, 150, 1.8), K('#e2e8f0'))
    P(S_cap(176, 94, 180, 150, 1.8), K('#e2e8f0'))
    P(S_c(140, 152, 3), K('#cbd5e1'))
    P(S_c(180, 152, 3), K('#cbd5e1'))
    P(S_rr(160, 252, 150, 8, 4), K('#475569'))


# ================================================================ FOOTWEAR
def sole(y=232, col='#f8fafc', bot='#9ca3af', x0=48, x1=280):
    s = S_poly(smooth([(x0, y - 8), (x1 - 8, y - 10), (x1, y + 6), (x1 - 12, y + 18), (x0 + 2, y + 18)], 2))
    P(s, lin(y - 10, y + 18, K(col), K(bot)))
    P(S_cap(x0 + 6, y + 15, x1 - 14, y + 15, 1.6), (0, 0, 0, .25))


def shoe_shadow():
    sh(166, 252, 120, 8, .3)


def sneaker():
    shoe_shadow()
    up = smooth([(60, 112), (92, 104), (112, 118), (124, 140), (150, 150), (188, 160), (228, 178), (258, 198),
                 (272, 214), (272, 230), (56, 230), (52, 170)], 1)
    P(S_poly(up), lin(100, 230, K('#f8fafc'), K('#d8dde6')))
    P(S_poly([(52, 170), (60, 112), (88, 106), (92, 150), (84, 200), (60, 228)]), K('#e11d48'))
    path(curve((96, 214), (150, 200), (206, 182)), 5, K('#0f172a'))
    P(S_poly([(112, 118), (124, 94), (142, 98), (136, 142)]), K('#e5e9f0'))
    for i in range(5):
        P(S_cap(140 + i * 16, 152 + i * 6, 156 + i * 16, 146 + i * 6, 2), K('#94a3b8'))
    P(S_e(250, 216, 26, 14, 30), K('#ffffff'), .8)
    P(S_poly(smooth([(48, 226), (276, 226), (284, 240), (272, 250), (56, 250), (46, 240)], 1)),
      lin(226, 250, K('#ffffff'), K('#aab2bf')))
    P(S_cap(56, 246, 270, 246, 1.4), (0, 0, 0, .25))


def boot():
    shoe_shadow()
    up = smooth([(92, 46), (160, 44), (166, 140), (214, 170), (262, 196), (266, 222), (86, 222), (84, 150)], 2)
    P(S_poly(up), lin(44, 222, K('#a16207'), K('#4a2c08')))
    rim(S_poly(up), .12)
    P(S_poly([(92, 46), (160, 44), (160, 62), (92, 66)]), K('#3a2108'))
    for i in range(6):
        y = 80 + i * 16
        P(S_cap(112, y, 148, y + 4, 2.4), K('#e5e7eb'))
        P(S_c(112, y, 2.8), K('#9ca3af'))
        P(S_c(148, y + 4, 2.8), K('#9ca3af'))
    P(S_poly(smooth([(214, 170), (262, 196), (266, 222), (218, 222)], 2)), K('#8a540c'))
    P(S_cap(86, 200, 266, 200, 1), (255, 220, 160, .35))
    sole(230, '#2b2118', '#0c0805', 80, 276)
    P(S_rr(106, 248, 52, 14, 3), K('#1a120a'))


def heel():
    shoe_shadow()
    P(S_poly([(62, 194), (112, 198), (92, 252), (82, 252)]), K('#7f1d1d'))
    P(S_rr(87, 252, 12, 4, 2), K('#111'))
    up = smooth([(64, 112), (100, 108), (114, 146), (150, 168), (210, 196), (256, 222), (276, 238), (268, 248),
                 (236, 246), (200, 242), (150, 208), (112, 198), (66, 198), (60, 150)], 1)
    P(S_poly(up), lin(108, 248, K('#f43f5e'), K('#9f1239')))
    rim(S_poly(up), .35)
    P(S_e(86, 140, 5, 22, 8), (255, 255, 255, .35))
    path(curve((120, 160), (160, 176), (205, 204)), 1.6, (255, 255, 255, .45))
    P(S_e(248, 232, 14, 4, 22), (255, 255, 255, .3))
    P(S_poly([(150, 208), (200, 242), (236, 246), (268, 248), (268, 250), (200, 248), (146, 214)]), K('#4a0d17'))


def sandal():
    shoe_shadow()
    P(S_poly(smooth([(52, 232), (200, 228), (272, 240), (276, 252), (200, 252), (52, 252)], 1)), K('#3a2108'))
    P(S_poly(smooth([(52, 220), (200, 216), (272, 230), (276, 238), (200, 240), (52, 240)], 2)),
      lin(216, 240, K('#e0b07a'), K('#a8743c')))
    path(curve((104, 226), (150, 130), (196, 222)), 9, K('#1e3a8a'))
    path(curve((196, 226), (222, 172), (254, 232)), 8, K('#1e3a8a'))
    path(curve((58, 224), (50, 176), (100, 168)), 6, K('#1e3a8a'))
    P(S_rr(150, 168, 16, 12, 3), K('#fbbf24'))
    P(S_e(150, 150, 24, 4, -12), (255, 255, 255, .3))


def runner():
    shoe_shadow()
    up = smooth([(58, 100), (96, 96), (112, 116), (126, 136), (160, 142), (196, 156), (236, 176), (264, 200),
                 (276, 216), (274, 228), (52, 228), (46, 170)], 1)
    P(S_poly(up), lambda x, y: mix(K('#f97316'), K('#fde047'), clamp((x - 50) / 230)))
    for i in range(30):
        P(S_c(70 + (i % 10) * 19, 150 + (i // 10) * 22, 1.7), (255, 255, 255, .4))
    P(S_poly([(46, 170), (58, 100), (84, 98), (88, 150), (80, 200), (52, 228)]), K('#111827'))
    path(curve((100, 212), (160, 196), (230, 180)), 7, K('#111827'))
    for i in range(5):
        P(S_cap(144 + i * 15, 150 + i * 6, 158 + i * 15, 144 + i * 6, 2), K('#111827'))
    P(S_poly([(112, 118), (124, 92), (142, 96), (136, 140)]), K('#fb923c'))
    s = S_poly(smooth([(40, 226), (274, 224), (288, 240), (276, 254), (48, 254), (36, 242)], 1))
    P(s, lin(224, 254, K('#ffffff'), K('#9ca3af')))
    for i in range(10):
        P(S_cap(70 + i * 20, 238, 70 + i * 20, 250, 1.2), (0, 0, 0, .15))
    P(S_cap(50, 252, 276, 252, 1.6), K('#111827'))


# ================================================================ BEAUTY
def lipstick():
    sh(160, 252, 70, 8)
    tube = S_rr(160, 202, 58, 100, 6)
    Cy(tube, K('#1f2937'), .25)
    P(S_rr(160, 240, 58, 18, 3), lin(228, 252, K('#fcd34d'), K('#92400e')))
    P(S_rr(160, 160, 50, 40, 4), lin(140, 180, K('#f5d98a'), K('#a97c28')))
    P(S_rr(160, 130, 38, 18, 2), K('#c8cdd6'))
    bullet = S_poly(smooth([(142, 124), (180, 124), (180, 66), (160, 50), (142, 80)], 2))
    P(bullet, lin(50, 124, K('#fb7185'), K('#be123c')))
    P(S_poly([(145, 120), (150, 120), (150, 80), (146, 90)]), (255, 255, 255, .4))
    P(S_rr(150, 198, 6, 80, 3), (255, 255, 255, .25))


def perfume():
    sh(160, 254, 90, 8)
    body = S_rr(160, 176, 130, 126, 18)
    P(body, (190, 220, 235, .4))
    P(S_rr(160, 196, 122, 86, 12), lin(150, 238, K('#f9a8d4'), K('#a21caf')), .92)
    P(S_ring(body, 2), (255, 255, 255, .6))
    P(S_poly([(110, 120), (124, 120), (118, 228), (106, 228)]), (255, 255, 255, .4))
    P(S_rr(160, 190, 72, 34, 4), (255, 255, 255, .85))
    P(S_cap(132, 184, 188, 184, 1.4), K('#7e22ce'))
    P(S_cap(140, 196, 180, 196, 1.2), K('#a78bfa'))
    P(S_rr(160, 104, 34, 14, 4), K('#9ca3af'))
    cap = S_rr(160, 78, 56, 46, 8)
    G(cap, K('#fcd34d'), .25)
    P(S_rr(150, 78, 8, 38, 3), (255, 255, 255, .45))
    P(S_rr(160, 242, 140, 8, 3), (255, 255, 255, .5))


def cream():
    sh(160, 244, 98, 9)
    jar = S_rr(160, 196, 150, 74, 14)
    Cy(jar, K('#f4eadb'), .1)
    rim(jar, .6)
    lid = S_rr(160, 148, 160, 36, 10)
    Cy(lid, K('#2f6b4f'), .2)
    P(S_rr(160, 138, 150, 4, 2), (255, 255, 255, .35))
    P(S_rr(160, 198, 112, 46, 6), (255, 255, 255, .85))
    path(curve((130, 214), (140, 180), (160, 178)), 1.6, K('#2f6b4f'))
    path(curve((190, 214), (180, 180), (160, 178)), 1.6, K('#2f6b4f'))
    P(S_e(143, 196, 8, 4, -30), K('#4a9a72'))
    P(S_e(177, 196, 8, 4, 30), K('#4a9a72'))
    P(S_cap(160, 178, 160, 218, 1.2), K('#2f6b4f'))
    P(S_cap(130, 222, 190, 222, 1), K('#9ca3af'))


def compact():
    sh(160, 246, 118, 11)
    base = S_rr(160, 188, 200, 100, 22)
    G(base, K('#be185d'), .2)
    P(S_rr(160, 188, 180, 80, 12), K('#4a0d2b'))
    cols = ['#fde68a', '#fb7185', '#a855f7', '#f97316', '#34d399', '#38bdf8', '#f472b6', '#facc15']
    for i in range(8):
        P(S_rr(88 + (i % 4) * 48, 168 + (i // 4) * 38, 40, 30, 8), rad(88 + (i % 4) * 48, 160 + (i // 4) * 38, 30, lighten(K(cols[i]), .35), K(cols[i])))
    lid = S_rr(160, 88, 200, 100, 22)
    G(lid, K('#e11d48'), .2)
    rim(lid, .4)
    P(S_rr(160, 88, 176, 76, 14), lin(50, 126, K('#e8edf3'), K('#aab4c2')))
    P(S_poly([(100, 124), (130, 52), (150, 52), (120, 124)]), (255, 255, 255, .55))
    P(S_poly([(156, 124), (172, 70), (180, 70), (164, 124)]), (255, 255, 255, .35))
    P(S_rr(160, 142, 40, 5, 2), K('#9f1239'))


def nailpolish():
    sh(160, 252, 70, 8)
    bottle = S_rr(160, 196, 82, 82, 18)
    P(bottle, lin(155, 237, K('#fb7185'), K('#7f1d4a')))
    rim(bottle, .35)
    P(S_e(138, 176, 8, 22, 6), (255, 255, 255, .45))
    P(S_rr(160, 148, 30, 12, 3), K('#d1d5db'))
    cap = S_rr(160, 98, 34, 90, 10)
    Cy(cap, K('#111827'), .3)
    for k in range(7):
        P(S_cap(144, 62 + k * 11, 176, 62 + k * 11, .7), (255, 255, 255, .09))
    P(S_rr(160, 232, 60, 3, 1.5), (0, 0, 0, .15))
    P(S_e(160, 238, 30, 3), (255, 255, 255, .35))


# ================================================================ ACCESSORIES
def sunglasses():
    sh(160, 224, 112, 8)
    path([(60, 126), (30, 120), (22, 168)], 5, K('#111827'))
    path([(260, 126), (290, 120), (298, 168)], 5, K('#111827'))
    for cx in (112, 208):
        lensS = S_poly(smooth([(cx - 56, 116), (cx + 56, 116), (cx + 50, 176), (cx + 14, 196), (cx - 30, 192), (cx - 56, 150)], 3))
        G(lensS, K('#f59e0b'), .0)
        P(lensS, lin(116, 196, K('#7c2d12'), K('#fbbf24')))
        P(S_e(cx - 20, 134, 20, 6, -15), (255, 255, 255, .35))
        P(S_ring(lensS, 7), K('#111827'))
    path(curve((166, 128), (160, 118), (154, 128)), 4, K('#111827'))
    P(S_rr(160, 124, 22, 8, 4), K('#111827'))
    P(S_rr(160, 114, 214, 6, 3), K('#111827'))


def backpack():
    sh(160, 256, 100, 8)
    path(curve((118, 70), (160, 20), (202, 70)), 6, K('#374151'))
    body = S_rr(160, 160, 160, 190, 44)
    G(body, K('#0f766e'), .15)
    rim(body, .25)
    P(S_rr(160, 126, 140, 4, 2), (0, 0, 0, .25))
    P(S_cap(110, 124, 210, 124, 1.5), K('#e5e7eb'))
    P(S_c(160, 124, 4), K('#e5e7eb'))
    pocket = S_rr(160, 192, 116, 78, 22)
    G(pocket, K('#0d9488'), .15)
    P(S_cap(118, 168, 202, 168, 1.8), K('#e5e7eb'))
    P(S_rr(160, 176, 14, 8, 3), K('#f1f5f9'))
    P(S_rr(100, 160, 14, 100, 6), K('#115e59'))
    P(S_rr(220, 160, 14, 100, 6), K('#115e59'))
    P(S_rr(160, 212, 34, 3, 1.5), (0, 0, 0, .25))
    P(S_rr(115, 236, 12, 5, 2), K('#d1d5db'))
    P(S_rr(205, 236, 12, 5, 2), K('#d1d5db'))


def wallet():
    sh(160, 234, 110, 9)
    back = S_rr(160, 150, 190, 118, 12)
    G(back, K('#6b3f1e'), .15)
    for i in range(3):
        P(S_rr(160, 100 + i * 5, 150, 22, 4), K(['#2563eb', '#f43f5e', '#fde047'][i]))
    front = S_rr(160, 164, 200, 106, 12)
    G(front, K('#8a5226'), .15)
    rim(front, .25)
    P(S_ring(S_rr(160, 164, 180, 86, 8), 1.4), (255, 230, 190, .7))
    P(S_rr(160, 126, 200, 2, 1), (0, 0, 0, .35))
    P(S_rr(160, 178, 36, 18, 4), K('#d1d5db'))
    P(S_c(160, 178, 4), K('#6b7280'))
    P(S_e(120, 150, 36, 6, -8), (255, 255, 255, .12))


def belt():
    sh(160, 236, 120, 8, .25)
    strap = S_rr(160, 160, 270, 40, 8)
    G(strap, K('#5b2a0f'), .18)
    P(S_rr(160, 142, 270, 2.5, 1), (255, 230, 190, .35))
    P(S_rr(160, 178, 270, 2.5, 1), (255, 230, 190, .35))
    P(S_cap(36, 143, 284, 143, .7), (255, 220, 170, .5))
    for i in range(7):
        P(S_c(190 + i * 12, 160, 3.2), K('#1f0e03'))
        P(S_ring(S_c(190 + i * 12, 160, 3.2), 1), (255, 255, 255, .15))
    buckle = S_rr(112, 160, 66, 62, 8)
    G(buckle, K('#facc15'), .35)
    P(S_rr(112, 160, 44, 40, 4), K('#5b2a0f'))
    P(S_cap(112, 124, 112, 196, 3), K('#d4a017'))
    P(S_rr(112, 160, 8, 62, 3), K('#fef08a'))
    P(S_rr(150, 160, 10, 34, 4), K('#2b1407'))


def cap():
    sh(160, 240, 120, 9)
    brim = S_poly(smooth([(60, 176), (160, 196), (280, 188), (292, 204), (170, 228), (60, 204)], 3))
    G(brim, K('#1e3a8a'), .2)
    dome = S_poly(smooth([(64, 190), (70, 118), (110, 82), (160, 74), (210, 82), (250, 118), (258, 180), (160, 196)], 3))
    P(dome, lin(74, 196, K('#3b82f6'), K('#1e40af')))
    rim(dome, .2)
    for x in (112, 160, 208):
        P(S_cap(160, 78, x * .6 + 160 * .4 + (x - 160) * .2, 192, .8), (0, 0, 0, .22))
    P(S_c(160, 76, 7), K('#1e3a8a'))
    P(S_e(150, 110, 32, 8, -25), (255, 255, 255, .22))
    P(S_rr(160, 160, 54, 28, 6), K('#fde047'))
    P(S_cap(144, 160, 176, 160, 2), K('#1e3a8a'))


# ================================================================ HOME LIVING
def lamp():
    sh(160, 252, 80, 8)
    P(S_e(160, 200, 100, 80), (255, 224, 160, .35), blur=30)
    P(S_e(160, 246, 52, 9), K('#3b2f26'))
    P(S_rr(160, 244, 56, 12, 5), K('#7c5a3a'))
    P(S_rr(160, 190, 8, 104, 4), lin(130, 245, K('#d6b270'), K('#8a6a2e')))
    shade = S_poly([(110, 60), (210, 60), (238, 138), (82, 138)])
    P(shade, lin(60, 138, K('#fff1c9'), K('#f6c365')))
    P(S_ring(shade, 2), (180, 120, 40, .4))
    P(S_e(160, 138, 78, 8), (255, 240, 200, .8))
    P(S_e(160, 60, 50, 6), K('#fdf0cf'))
    P(S_poly([(138, 64), (182, 64), (190, 134), (130, 134)]), (255, 255, 255, .25), blur=6)


def sofa():
    sh(160, 244, 130, 10)
    for x in (70, 250):
        P(S_poly([(x - 6, 226), (x + 6, 226), (x + 8, 244), (x - 4, 244)]), K('#5b3a1b'))
    back = S_rr(160, 124, 220, 80, 28)
    G(back, K('#6d7ea0'), .12)
    for dx in (-1, 1):
        arm = S_rr(160 + dx * 118, 172, 46, 100, 20)
        G(arm, K('#5b6b8c'), .12)
    seat = S_rr(160, 190, 196, 56, 14)
    G(seat, K('#7c8db0'), .12)
    for i in range(2):
        cx = 112 + i * 96
        P(S_rr(cx, 188, 92, 48, 14), lin(164, 212, K('#8d9dc0'), K('#6a7b9f')))
        rim(S_rr(cx, 188, 92, 48, 14), .2)
    P(S_rr(86, 134, 38, 36, 8, -12), K('#fbbf24'))
    P(S_rr(228, 138, 34, 34, 8, 14), K('#34d399'))
    P(S_rr(160, 216, 196, 5, 2), (0, 0, 0, .15))


def plant():
    sh(160, 254, 70, 8)
    for ang, ln, c in ((-70, 100, '#15803d'), (-40, 90, '#22c55e'), (-98, 112, '#166534'), (-125, 94, '#22c55e'),
                       (-150, 78, '#15803d'), (-10, 70, '#166534'), (-170, 60, '#22c55e')):
        a = math.radians(ang)
        cx, cy = 160 + math.cos(a) * ln / 2, 176 + math.sin(a) * ln / 2
        P(S_e(cx, cy, ln / 2, 17, ang), lin(cy - 30, cy + 30, lighten(K(c), .25), darken(K(c), .1)))
        P(S_cap(160, 176, 160 + math.cos(a) * ln, 176 + math.sin(a) * ln, .9), (255, 255, 255, .3))
    pot = S_poly(smooth([(104, 172), (216, 172), (200, 250), (120, 250)], 2))
    P(pot, linx(104, 216, K('#f2c9a6'), K('#b9784a')))
    P(S_rr(160, 176, 120, 14, 5), K('#cf8d5e'))
    P(S_rr(160, 214, 80, 3, 1.5), (255, 255, 255, .45))


def clock():
    sh(160, 254, 90, 7, .25)
    P(S_c(160, 150, 100), lin(50, 250, K('#a67549'), K('#5e3b1c')))
    P(S_c(160, 150, 88), K('#faf4e6'))
    P(S_ring(S_c(160, 150, 88), 3), K('#8a5a2b'))
    for i in range(12):
        a = math.radians(i * 30)
        r0 = 70 if i % 3 else 64
        P(S_cap(160 + r0 * math.cos(a), 150 + r0 * math.sin(a), 160 + 80 * math.cos(a), 150 + 80 * math.sin(a), 2.2 if i % 3 == 0 else 1.2), K('#2b2118'))
    a = math.radians(-60)
    P(S_cap(160, 150, 160 + 42 * math.cos(a), 150 + 42 * math.sin(a), 3.4), K('#2b2118'))
    a = math.radians(40)
    P(S_cap(160, 150, 160 + 62 * math.cos(a), 150 + 62 * math.sin(a), 2.4), K('#2b2118'))
    a = math.radians(160)
    P(S_cap(160, 150, 160 + 66 * math.cos(a), 150 + 66 * math.sin(a), .9), K('#dc2626'))
    P(S_c(160, 150, 5), K('#dc2626'))
    P(S_e(120, 100, 36, 12, -40), (255, 255, 255, .25))


def shelf():
    sh(160, 256, 110, 8)
    unit = S_rr(160, 148, 200, 220, 6)
    G(unit, K('#a3743f'), .12)
    for i in range(3):
        P(S_rr(160, 78 + i * 70, 184, 62, 2), K('#2b1d10'))
    for y in (113, 183):
        P(S_rr(160, y, 200, 8, 2), K('#c28f55'))
    cols = ['#ef4444', '#3b82f6', '#fde047', '#10b981', '#a855f7', '#f97316']
    r = random.Random(5)
    x = 80
    for i in range(7):
        w, hh = r.randint(10, 15), r.randint(38, 54)
        P(S_rr(x + w / 2, 107 - hh / 2, w, hh, 1.5), lin(107 - hh, 107, lighten(K(cols[i % 6]), .15), K(cols[i % 6])))
        x += w + 2
    P(S_c(215, 88, 0.1), K('#000'), 0)
    P(S_poly(smooth([(196, 110), (236, 110), (232, 90), (216, 78), (200, 90)], 2)), K('#e5e7eb'))
    P(S_rr(216, 70, 8, 14, 2), K('#e5e7eb'))
    for k in range(3):
        P(S_e(100 + k * 30, 176, 10, 16), K(['#fbbf24', '#f87171', '#60a5fa'][k]))
        P(S_rr(100 + k * 30, 162, 6, 10, 2), K('#374151'))
    P(S_rr(160, 252, 200, 4, 2), (0, 0, 0, .3))
    P(S_rr(200, 232, 70, 34, 5), K('#fb7185'))
    P(S_rr(150, 236, 50, 28, 5), K('#38bdf8'))


DRAW = {
    'laptops': [laptop1, laptop2, laptop3, laptop4, laptop5],
    'smartphones': [phone1, phone2, phone3, phone4, phone5],
    'headphones': [headphone1, headphone2, headphone3, headphone4, headphone5],
    'smartwatches': [watch1, watch2, watch3, watch4, watch5],
    'tablets': [tablet1, tablet2, tablet3, tablet4, tablet5],
    'cameras': [camera1, camera2, camera3, camera4, camera5],
    'televisions': [tv1, tv2, tv3, tv4, tv5],
    'gaming': [gamepad, handheld, vr, arcade, gamekeys],
    'home_appliances': [washer, fridge, robovac, purifier, fan],
    'kitchen_appliances': [toaster, blender, kettle, coffee, mixer],
    'fashion': [tee, dress, jacket, jeans, hoodie],
    'footwear': [sneaker, boot, heel, sandal, runner],
    'beauty': [lipstick, perfume, cream, compact, nailpolish],
    'accessories': [sunglasses, backpack, wallet, belt, cap],
    'home_living': [lamp, sofa, plant, clock, shelf],
}
HUE = {c: i / len(DRAW) for i, c in enumerate(DRAW)}


# ---------------------------------------------------------------- output
def background(cat, v):
    h = HUE[cat] + v * .035
    top, bot = hsv(h, .10, .99), hsv(h + .03, .26, .86)
    gx, gy = D * (.3 + .1 * v), D * .22
    for y in range(N):
        fy = (y + .5) / SC
        base = mix(top, bot, fy / D)
        if fy > 248:
            base = darken(base, .05 * (fy - 248) / 72)
        for x in range(N):
            fx = (x + .5) / SC
            g = clamp(1 - math.hypot(fx - gx, fy - gy) / 260) * .22
            vg = clamp(math.hypot(fx - 160, fy - 160) / 240) ** 2 * .12
            r = (base[0] + (255 - base[0]) * g) * (1 - vg)
            gg = (base[1] + (255 - base[1]) * g) * (1 - vg)
            b = (base[2] + (255 - base[2]) * g) * (1 - vg)
            i = (y * N + x) * 3
            PX[i], PX[i + 1], PX[i + 2] = int(r), int(gg), int(b)


def chunk(tag, data):
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)


def png_bytes(title):
    raw = bytearray()
    stride = N * 3
    for y in range(N):
        row = PX[y * stride:(y + 1) * stride]
        raw.append(1)
        raw += bytes((row[i] - (row[i - 3] if i >= 3 else 0)) & 255 for i in range(stride))
    text = lambda k, v: chunk(b'tEXt', k.encode('latin-1') + b'\0' + v.encode('latin-1'))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', N, N, 8, 2, 0, 0, 0)) +
            text('Title', title) + text('Comment', PROVENANCE) +
            chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.normpath(os.path.join(here, '..', '..', 'public', 'images', 'products', 'portfolio'))
    sheet = None
    if '--out' in argv:
        out = os.path.abspath(argv[argv.index('--out') + 1])
    if '--sheet' in argv:
        sheet = os.path.abspath(argv[argv.index('--sheet') + 1])
        os.makedirs(sheet, exist_ok=True)
    only = argv[argv.index('--only') + 1] if '--only' in argv else None
    manifest, thumbs = [], {}
    for cat, fns in DRAW.items():
        if only and cat != only:
            continue
        os.makedirs(os.path.join(out, cat), exist_ok=True)
        for i, fn in enumerate(fns, 1):
            background(cat, i)
            fn()
            data = png_bytes(f'{cat} {i:02d} - {fn.__name__}')
            rel = f'{cat}/{i:02d}.png'
            with open(os.path.join(out, rel), 'wb') as fh:
                fh.write(data)
            manifest.append({'file': rel, 'subject': fn.__name__, 'width': N, 'height': N, 'bytes': len(data),
                             'sha256': hashlib.sha256(data).hexdigest()})
            thumbs.setdefault(cat, []).append(bytes(PX))
            print(rel, len(data), flush=True)
    if not only:
        with open(os.path.join(out, 'manifest.json'), 'w', encoding='utf-8', newline='\n') as fh:
            json.dump({'provenance': PROVENANCE, 'images': manifest}, fh, indent=2)
            fh.write('\n')
    if sheet:
        cats = list(thumbs)
        for g in range(0, len(cats), 3):
            group = cats[g:g + 3]
            T = N // 2
            sheet_w = T * 5
            buf = bytearray(sheet_w * T * len(group) * 3)
            for ri, cat in enumerate(group):
                for ci, img in enumerate(thumbs[cat]):
                    for y in range(T):
                        for x in range(T):
                            s = ((y * 2) * N + x * 2) * 3
                            d = ((ri * T + y) * sheet_w + ci * T + x) * 3
                            buf[d:d + 3] = img[s:s + 3]
            raw = bytearray()
            for y in range(T * len(group)):
                raw.append(0)
                raw += buf[y * sheet_w * 3:(y + 1) * sheet_w * 3]
            data = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', sheet_w, T * len(group), 8, 2, 0, 0, 0)) +
                    chunk(b'IDAT', zlib.compress(bytes(raw), 6)) + chunk(b'IEND', b''))
            with open(os.path.join(sheet, f'sheet{g // 3 + 1}.png'), 'wb') as fh:
                fh.write(data)


if __name__ == '__main__':
    main(sys.argv[1:])
