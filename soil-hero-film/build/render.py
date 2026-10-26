"""Soil hero film mockup renderer. Usage: python3 render.py out.mp4 [t_start t_end] [--stills t1,t2,...]"""
import os, sys, math
import numpy as np, cv2
from multiprocessing import Pool
import subprocess

cv2.setNumThreads(1)
BASE = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(BASE, *a)
W, H, FPS = 1920, 1080, 24
DUR = 61.5
SHUTTER = 0.75  # fraction of a frame the virtual shutter stays open
SCRIM_K = 0.22


# ---------- helpers ----------
def imread(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED).astype(np.float32) / 255.0
    return im


def smooth(x):
    x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out(x):
    x = min(max(x, 0.0), 1.0); return 1 - (1 - x) ** 3


def ease_in(x):
    x = min(max(x, 0.0), 1.0); return x ** 3


def lerp(a, b, u): return a + (b - a) * u


def logzoom(a, b, u): return math.exp(lerp(math.log(a), math.log(b), u))


def feather_rect(h, w, f):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.minimum(np.minimum(xx, w - 1 - xx) / (w * f), np.minimum(yy, h - 1 - yy) / (h * f))
    return smooth(d)


class Layer:
    """An image placed in world space: top-left (x0, y0), width ww world units."""

    def __init__(self, img, x0, y0, ww, alpha=None, levels=6):
        if img.shape[2] == 4 and alpha is None:
            alpha = img[..., 3]; img = img[..., :3]
        if alpha is None: alpha = np.ones(img.shape[:2], np.float32)
        pm = np.dstack([img * alpha[..., None], alpha]).astype(np.float32)
        self.pyr = [pm]
        for _ in range(levels):
            if min(self.pyr[-1].shape[:2]) < 64: break
            self.pyr.append(cv2.pyrDown(self.pyr[-1]))
        self.ih, self.iw = img.shape[:2]
        self.x0, self.y0, self.ww = x0, y0, ww

    def warp(self, cam, rot=0.0):
        cx, cy, cw = cam
        s = W / cw
        f = self.ww / self.iw * s
        L = 0 if f >= 0.71 else min(len(self.pyr) - 1, int(round(math.log2(1 / f))))
        img = self.pyr[L]
        k = f * (2 ** L)
        tx = (self.x0 - cx) * s + W / 2; ty = (self.y0 - cy) * s + H / 2
        # visibility test
        x1 = tx + self.iw * f; y1 = ty + self.ih * f
        if x1 < -2 or y1 < -2 or tx > W + 2 or ty > H + 2: return None
        if (x1 - tx) < 3: return None
        M = np.array([[k, 0, tx], [0, k, ty], [0, 0, 1]], np.float64)
        if rot:
            pcx, pcy = (tx + x1) / 2, (ty + y1) / 2
            c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
            R = np.array([[c, -s_, pcx - c * pcx + s_ * pcy], [s_, c, pcy - s_ * pcx - c * pcy], [0, 0, 1]])
            M = R @ M
        return cv2.warpAffine(img, M[:2], (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def composite(layers, cam, base=(0, 0, 0)):
    out = np.empty((H, W, 3), np.float32); out[:] = base
    for item in layers:
        lay, rot = (item if isinstance(item, tuple) else (item, 0.0))
        w = lay.warp(cam, rot)
        if w is None: continue
        a = w[..., 3:4]
        out = out * (1 - a) + w[..., :3]
    return out


# ---------- assets ----------
print('loading plates', flush=True)
PL = lambda n: imread(P('plates', n + '.png'))
TX = {os.path.splitext(f)[0]: imread(P('text', f)) for f in os.listdir(P('text')) if f.endswith('.png')}
for k_, v in TX.items():
    v[..., :3] *= v[..., 3:4]  # premultiply

strata = PL('strata'); rx, ry, rw, rh = map(int, open(P('plates', 'strata_rect.txt')).read().split())
sidx = np.load(P('plates', 'strata_idx.npy'))
soil = PL('soil')
band_k = int(np.bincount(sidx[ry:ry + rh, rx:rx + rw].ravel()).argmax())
soil_alpha = cv2.resize((sidx[ry:ry + rh, rx:rx + rw] == band_k).astype(np.float32), (soil.shape[1], soil.shape[0]), interpolation=cv2.INTER_LINEAR)
soil_alpha = cv2.GaussianBlur(soil_alpha, (0, 0), 6)
L_strata = Layer(strata, 0, 0, 3840)
L_soil = Layer(soil, rx, ry, rw, alpha=soil_alpha)
col = (sidx[:, rx + rw // 2] == band_k)
band_rows = np.where(col)[0]
SOIL_CY = float(band_rows.mean())
SOIL_CX = rx + rw / 2

L_farm = Layer(PL('farm'), 0, 0, 3840)

pile = PL('pile'); hx, hy, hs = open(P('plates', 'pile_hero.txt')).read().split()
hx, hy, hs = float(hx), float(hy), int(hs)
bean_big = PL('bean_big')
L_pile = Layer(pile, 0, 0, 3840)
L_bean = Layer(bean_big, int(hx - hs / 2), int(hy - hs / 2), hs)
BEAN_SCALE = bean_big.shape[1] / hs  # bean px per world unit

crema = PL('crema')
L_tablecup = Layer(PL('table_cup'), 0, 0, 3840)
L_crema_tc = Layer(crema, 1920 - 318, 1080 - 318, 636)

L_table = Layer(PL('table'), 0, 0, 3840)
cup = PL('cup'); cup_sh = PL('cup_shadow')
CUP_WW = 1100 * 0.635
L_pour = Layer(PL('pourover'), 0, 0, 3840)

kraft = PL('kraft'); bx, by, bw, bh = map(int, open(P('plates', 'bag_rect.txt')).read().split())
L_bag = Layer(PL('bag'), 0, 0, 3840)
L_kraft = Layer(kraft, bx, by, bw, alpha=feather_rect(kraft.shape[0], kraft.shape[1], 0.2))

# drum assets
DRUM = [[imread(P('plates', 'drum', f'b{i}_{j}.png')) for j in range(12)] for i in range(6)]
for row in DRUM:
    for s_ in row: s_[..., :3] *= s_[..., 3:4]
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
dd = np.hypot(xx - W / 2, yy - H / 2)
drum_bg = np.zeros((H, W, 3), np.float32)
glow = np.exp(-(dd / 520) ** 2)
drum_bg[:] = np.array([0.03, 0.035, 0.05])
drum_bg += glow[..., None] * np.array([0.05, 0.12, 0.26])  # BGR warm glow
drum_ring = np.exp(-((dd - 470) / 26) ** 2)
ang = np.arctan2(yy - H / 2, xx - W / 2)
metal = 0.35 + 0.25 * np.cos(ang * 2 - 0.6) + 0.1 * np.cos(ang * 9)
drum_rim = (dd > 452).astype(np.float32)
rim_col = (np.array([0.42, 0.44, 0.46]) * metal[..., None]) * np.clip(1 - (dd - 452) / 120, 0.15, 1)[..., None]
outside = cv2.GaussianBlur((dd > 452).astype(np.float32), (0, 0), 1.5)[..., None]
drum_ring3 = drum_ring[..., None]

# bands assets for the reveal (downscaled strata)
strata_small = cv2.resize(strata[..., :3], (W, H), interpolation=cv2.INTER_AREA)
sidx_small = cv2.resize(sidx, (W, H), interpolation=cv2.INTER_NEAREST)
NB = int(sidx_small.max()) + 1
band_masks = [cv2.GaussianBlur((sidx_small == k).astype(np.float32), (0, 0), 0.8) for k in range(NB)]

soil_dark = cv2.GaussianBlur(cv2.resize(soil, (2400, 1350), interpolation=cv2.INTER_AREA), (0, 0), 5) * 0.32
vign = (1 - 0.55 * np.clip((np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)) - 0.45) / 0.9, 0, 1) ** 1.6)[..., None]
grain_rng = np.random.default_rng(1)
GRAIN = [cv2.resize(grain_rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32), (W, H)) for _ in range(6)]


# ---------- shots ----------
class Shot:
    blur_extra = 0  # forced subframes

    def __init__(self, t0, t1, whip_in=0.0, whip_out=0.0, wdir=1):
        self.t0, self.t1, self.whip_in, self.whip_out, self.wdir = t0, t1, whip_in, whip_out, wdir

    def whip(self, tl):
        d = self.t1 - self.t0; off = 0.0
        if self.whip_in and tl < self.whip_in: off -= (1 - ease_out(tl / self.whip_in)) * 2.6 * W
        if self.whip_out and tl > d - self.whip_out: off += ease_in((tl - (d - self.whip_out)) / self.whip_out) * 2.6 * W
        return off * self.wdir

    def motion(self, tl):
        dt = 1.0 / FPS
        a, b = self.cam_full(tl - dt / 2), self.cam_full(tl + dt / 2)
        s = W / a[2]
        return abs(b[0] - a[0]) * s + abs(b[1] - a[1]) * s + abs(math.log(b[2] / a[2])) * W * 0.6

    def cam_full(self, tl, pan=(0, 0)):
        cx, cy, cw = self.cam(tl)
        s = W / cw
        return (cx + (self.whip(tl) + pan[0]) / s, cy + pan[1] / s, cw)

    def render(self, tl, pan=(0, 0)):
        cam = self.cam_full(tl, pan)
        img = composite(self.layers(tl), cam)
        return self.post(img, tl)

    def post(self, img, tl): return img


class SoilStrata(Shot):
    def cam(self, tl):
        if tl < 8:
            return (SOIL_CX + lerp(-60, 50, tl / 8), SOIL_CY + lerp(6, -4, tl / 8), lerp(215, 190, ease_io(tl / 8)))
        u = ease_io((tl - 8) / 5.0)
        return (lerp(SOIL_CX + 50, 1920, u), lerp(SOIL_CY - 4, 1080, u), logzoom(190, 3840, u))

    def layers(self, tl): return [L_strata, L_soil]

    def post(self, img, tl):
        sig = 13 * (1 - smooth((tl - 0.2) / 2.8))
        return cv2.GaussianBlur(img, (0, 0), sig) if sig > 0.3 else img


class Farm(Shot):
    def cam(self, tl):
        u = tl / (self.t1 - self.t0)
        return (lerp(1750, 2050, u), lerp(1150, 1050, u), lerp(2900, 2450, ease_io(u)))

    def layers(self, tl): return [L_farm]


class Bean(Shot):
    def cam(self, tl):
        cw0 = 1500 / BEAN_SCALE
        if tl < 1.8: return (hx + lerp(-3, 4, tl / 1.8), hy + 1.5, cw0)
        u = ease_io((tl - 1.8) / 3.5)
        return (lerp(hx + 4, 1920, u), lerp(hy + 1.5, 1080, u), logzoom(cw0, 3700, u))

    def layers(self, tl): return [L_pile, L_bean]

    def post(self, img, tl):
        sig = 7 * (1 - smooth(tl / 1.3))
        return cv2.GaussianBlur(img, (0, 0), sig) if sig > 0.3 else img


class Drum(Shot):
    N = 330

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        r = np.random.default_rng(5)
        self.r = r.uniform(120, 420, self.N) ** 1.0
        self.r = np.sqrt(r.uniform(120 ** 2, 425 ** 2, self.N))
        self.ph = r.uniform(0, 1, self.N)
        self.var = r.integers(0, 6, self.N)
        self.spin = r.uniform(-3, 3, self.N)
        self.sp0 = r.uniform(0, 12, self.N)
        self.order = np.argsort(self.r)

    def motion(self, tl): return 60 + abs(self.whip(tl + 1 / FPS) - self.whip(tl))

    def cam(self, tl): return (0, 0, W)

    def render(self, tl, pan=(0, 0)):
        T = tl + 0.0
        img = drum_bg.copy()
        flick = 1 + 0.06 * math.sin(T * 17) + 0.04 * math.sin(T * 29)
        img *= flick
        # paddle
        pa = T * 2 * math.pi * 0.45
        p1 = (int(W / 2), int(H / 2)); p2 = (int(W / 2 + 450 * math.cos(pa)), int(H / 2 + 450 * math.sin(pa)))
        p = (self.ph + T * 0.55) % 1.0
        for i in self.order:
            if p[i] < 0.78:
                th = math.radians(15 + 185 * p[i] / 0.78); rr = self.r[i]
                x, y = W / 2 + rr * math.cos(th), H / 2 + rr * math.sin(th)
            else:
                q = (p[i] - 0.78) / 0.22
                a0 = math.radians(200); a1 = math.radians(15)
                x0_, y0_ = W / 2 + self.r[i] * math.cos(a0), H / 2 + self.r[i] * math.sin(a0)
                x1_, y1_ = W / 2 + self.r[i] * 0.85 * math.cos(a1), H / 2 + self.r[i] * 0.85 * math.sin(a1)
                x, y = lerp(x0_, x1_, q), lerp(y0_, y1_, q) + 260 * q * (1 - q) * -0.4 + 380 * q * q * 0.3
            j = int(self.sp0[i] + self.spin[i] * T * 4) % 12
            spr = DRUM[self.var[i]][j]
            hh, ww_ = spr.shape[:2]
            X0, Y0 = int(x - ww_ / 2), int(y - hh / 2)
            if X0 < 0 or Y0 < 0 or X0 + ww_ > W or Y0 + hh > H: continue
            roi = img[Y0:Y0 + hh, X0:X0 + ww_]
            roi *= (1 - spr[..., 3:4]); roi += spr[..., :3] * flick
        # drum wall outside window and rim
        img = img * (1 - outside) + rim_col * outside
        img += drum_ring3 * np.array([0.25, 0.27, 0.3]) * (0.6 + 0.4 * metal[..., None])
        # glass reflection
        img += (np.clip(1 - np.abs((xx - yy * 0.6) - 500) / 300, 0, 1) * (dd < 452))[..., None] * 0.035
        # push in plus pan
        z = 1.32 + 0.08 * (tl / (self.t1 - self.t0)) + (0.15 if pan != (0, 0) else 0)
        M = np.array([[z, 0, W / 2 - z * W / 2 - self.whip(tl) - pan[0]], [0, z, H / 2 - z * H / 2 - pan[1]]], np.float32)
        return cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)


class Crema(Shot):
    def cam(self, tl):
        if tl < 1.3: return (1920 + 40 + 10 * tl, 1080 - 25, 240)
        u = ease_io((tl - 1.3) / 3.45)
        return (lerp(1973, 1920, u), lerp(1055, 1080, u), logzoom(240, 2900, u))

    def layers(self, tl): return [L_tablecup, (L_crema_tc, -9 * tl)]


class Pour(Shot):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        S = 640
        y_, x_ = np.mgrid[0:S, 0:S].astype(np.float32)
        self.d = np.hypot(x_ - S / 2, y_ - S / 2) / (S / 2) * 300  # world units from centre
        self.th = np.arctan2(y_ - S / 2, x_ - S / 2)
        self.alpha = np.clip((300 - self.d) / 4, 0, 1)
        n = cv2.resize(crema[..., :3], (S, S), interpolation=cv2.INTER_AREA)
        self.bed = n * 0.35 + np.array([0.03, 0.06, 0.11]) * 0.65
        self.S = S

    def cam(self, tl):
        u = tl / (self.t1 - self.t0)
        return (lerp(1900, 1930, u), lerp(1090, 1075, u), lerp(3300, 2800, ease_io(u)))

    def layers(self, tl):
        sx, sy = 8 * math.sin(tl * 3.1), 6 * math.cos(tl * 2.3)
        dd_ = np.hypot(self.d * np.cos(self.th) - sx, self.d * np.sin(self.th) - sy)
        rip = 0.22 * np.sin(dd_ / 10 - tl * 14) * np.exp(-dd_ / 160)
        bloom = 1 + 0.25 * np.exp(-(dd_ / 70) ** 2)
        img = self.bed * (bloom + rip)[..., None]
        stream = np.exp(-(dd_ / 9) ** 2)[..., None]
        img = img * (1 - stream) + np.array([0.30, 0.42, 0.55]) * stream
        img += (np.exp(-((dd_ - 4) / 3) ** 2) * 0.25)[..., None]
        bed = Layer(np.dstack([img, self.alpha]), 1920 - 300, 1080 - 300, 600, levels=3)
        return [L_pour, bed]


class Table(Shot):
    LAND = 1.5

    def motion(self, tl):
        m = super().motion(tl)
        return m + (120 if 0.5 < tl < self.LAND + 0.05 else 0)

    def cam(self, tl):
        u = tl / (self.t1 - self.t0)
        return (lerp(2000, 2140, u), lerp(1120, 1130, u), lerp(3550, 3150, ease_io(u)))

    def cup_pose(self, tl):
        u = (tl - 0.55) / (self.LAND - 0.55)
        e = 1 - (1 - min(max(u, 0), 1)) ** 4
        x = lerp(4500, 2240, e); y = lerp(1250, 1150, e)
        return x, y, lerp(-32, 0, e)

    def layers(self, tl):
        x, y, rot = self.cup_pose(tl)
        x0, y0 = x - CUP_WW / 2, y - CUP_WW / 2
        return [L_table, (Layer(cup_sh, x0 + 26, y0 + 34, CUP_WW, levels=4), rot),
                (Layer(cup, x0, y0, CUP_WW, levels=4), rot),
                (Layer(crema, x - 318 * 0.635, y - 318 * 0.635, 636 * 0.635, levels=5), rot - 6 * tl)]

    def post(self, img, tl):
        if tl < self.LAND: return img
        cx, cy, cw = self.cam_full(tl); s = W / cw
        ox, oy = (2240 - cx) * s + W / 2, (1150 - cy) * s + H / 2
        st = min(1, (tl - self.LAND) / 1.5)
        small = steam_field(tl, 240, 240)
        sz = int(560 * s * 2)
        stm = cv2.resize(small, (sz, sz), interpolation=cv2.INTER_CUBIC) * 0.16 * st
        X0, Y0 = int(ox - sz / 2), int(oy - sz * 0.9)
        X1, Y1 = max(0, X0), max(0, Y0)
        X2, Y2 = min(W, X0 + sz), min(H, Y0 + sz)
        if X2 > X1 and Y2 > Y1:
            img[Y1:Y2, X1:X2] += stm[Y1 - Y0:Y2 - Y0, X1 - X0:X2 - X0, None]
        return img


_steam_base = None


def steam_field(t, h, w):
    global _steam_base
    if _steam_base is None:
        r = np.random.default_rng(9)
        _steam_base = cv2.GaussianBlur(r.random((h * 3, w)).astype(np.float32), (0, 0), 6)
        _steam_base = (_steam_base - _steam_base.min()) / (np.ptp(_steam_base) + 1e-6)
    off = int(t * 40) % (h * 2)
    f = _steam_base[off:off + h]
    y_, x_ = np.mgrid[0:h, 0:w].astype(np.float32)
    sway = 10 * np.sin(y_ / 30 + t * 1.3)
    mask = np.exp(-(((x_ - w / 2 - sway) / (w * 0.18)) ** 2)) * np.clip(y_ / h * 1.4, 0, 1) * np.clip((h - y_) / (h * 0.15), 0, 1)
    return np.clip((f - 0.45) * 3, 0, 1) * mask


class Pack(Shot):
    def cam(self, tl):
        cw0 = bw * 0.62
        if tl < 0.9: return (bx + bw / 2 + 5 * tl, by + bh / 2, cw0)
        u = ease_io((tl - 0.9) / 2.85)
        return (lerp(bx + bw / 2 + 5, 1920, u), lerp(by + bh / 2, 1110, u), logzoom(cw0, 2700, u))

    def layers(self, tl): return [L_bag, L_kraft]


class Bands(Shot):
    def cam(self, tl): return (0, 0, W)

    def motion(self, tl):
        moving = any(0 < tl - 0.11 * k < 0.6 for k in range(NB))
        return 140 if moving else 2

    def render(self, tl, pan=(0, 0)):
        img = np.empty((H, W, 3), np.float32); img[:] = (0.03, 0.05, 0.08)
        for k in range(NB - 1, -1, -1):
            u = (tl - 0.11 * (NB - 1 - k)) / 0.6
            if u <= 0: continue
            off = (1 - ease_out(u)) * 2200 * (1 if k % 2 else -1)
            M = np.float32([[1, 0, off], [0, 1, 0]])
            m = cv2.warpAffine(band_masks[k], M, (W, H))[..., None]
            c = cv2.warpAffine(strata_small, M, (W, H), borderMode=cv2.BORDER_WRAP)
            img = img * (1 - m) + c * m
        z = 1 + 0.07 * smooth((tl - 1.8) / 9)
        M = np.float32([[z, 0, W / 2 - z * W / 2], [0, z, H / 2 - z * H / 2]])
        img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        dark = smooth((tl - 2.0) / 0.8)
        return img * (1 - dark * np.array([0.62, 0.52, 0.42], np.float32))


class Close(Shot):
    def cam(self, tl): return (0, 0, W)

    def motion(self, tl): return 1

    def render(self, tl, pan=(0, 0)):
        x = int(200 + tl * 18); y = 120
        return soil_dark[y:y + H, x:x + W].copy()


class Montage(Shot):
    def __init__(self, t0, t1, items):
        super().__init__(t0, t1)
        self.items = items; self.seg = (t1 - t0) / len(items)

    def motion(self, tl): return 150

    def render(self, tl, pan=(0, 0)):
        i = min(len(self.items) - 1, int(tl / self.seg))
        shot, at, d = self.items[i]
        q = (tl - i * self.seg) / self.seg
        p = (q - 0.5) * 900 * d
        img = shot.render(at + q * 0.2, pan=(p, 0))
        # identity element overlapping: sliding strata bands
        off = int((tl * 900) % W)
        band = np.roll(strata_small, off * (1 if i % 2 else -1), axis=1)
        return img * 0.68 + band * 0.32


S_A = SoilStrata(0.0, 13.25, whip_out=0.32)
S_B = Farm(13.1, 17.35, whip_in=0.32, whip_out=0.32)
S_C = Bean(17.2, 22.55, whip_in=0.32, whip_out=0.3)
S_D = Drum(22.4, 25.95, whip_in=0.3, whip_out=0.3)
S_E = Crema(25.8, 30.55, whip_in=0.3)
S_F = Pour(30.25, 33.75)
S_G = Table(33.45, 40.45, whip_out=0.3)
S_H = Montage(40.3, 42.6, [(S_A, 4.0, 1), (S_C, 0.4, -1), (S_D, 1.0, 1), (S_E, 0.4, -1), (S_B, 1.5, 1), (S_A, 12.6, -1), (S_G, 4.5, 1)])
S_I = Pack(42.45, 46.2, whip_in=0.3)
S_J = Bands(46.0, 56.75)
S_K = Close(56.45, DUR)
SHOTS = [S_A, S_B, S_C, S_D, S_E, S_F, S_G, S_H, S_I, S_J, S_K]

TEXTS = [  # id, t0, t1
    ('t1', 2.8, 7.4), ('t2', 10.6, 13.0), ('t3', 19.0, 23.4), ('t5', 35.9, 39.9),
    ('logo', 48.4, 50.3), ('t6', 50.7, 53.0), ('t7', 53.3, 56.5), ('close1', 57.0, 61.6), ('close2', 58.0, 61.6),
    ('ch1', 0.8, 8.0), ('ch2', 8.4, 30.0), ('ch3', 30.6, 40.0), ('ch4', 40.5, 56.2), ('ch5', 56.8, 61.6),
]
KASH = (26.6, 30.3, 27.0, 28.7)  # visible window, stretch start, stretch end


def text_alpha(t, t0, t1, fi=0.7, fo=0.6):
    return smooth((t - t0) / fi) * smooth((t1 - t) / fo), smooth((t - t0) / fi)


def put_text(img, tex, a, a_in, blur=True):
    if a <= 0.002: return img
    t = tex
    sig = (1 - a_in) * 9
    dy = (1 - a_in) * 14
    if blur and sig > 0.4:
        t = cv2.GaussianBlur(t, (0, 0), sig)
    if dy > 0.5:
        t = cv2.warpAffine(t, np.float32([[1, 0, 0], [0, 1, dy]]), (W, H))
    return img * (1 - t[..., 3:4] * a) + t[..., :3] * a


def frame_at(t):
    active = [s for s in SHOTS if s.t0 <= t < s.t1]
    if not active: active = [SHOTS[-1]]
    out = np.zeros((H, W, 3), np.float32); wsum = 0
    for s in active:
        # crossfade weight inside overlaps
        w = 1.0
        for o in active:
            if o is s: continue
            if o.t0 > s.t0:  # o comes after s: s fades out over the overlap
                w *= 1 - smooth((t - o.t0) / max(1e-3, s.t1 - o.t0))
            else:
                w *= smooth((t - s.t0) / max(1e-3, o.t1 - s.t0))
        if w < 1e-3: continue
        tl = t - s.t0
        n = int(min(10, max(1, math.ceil(s.motion(tl) * SHUTTER / 5))))
        acc = np.zeros((H, W, 3), np.float32)
        for i in range(n):
            dt = ((i + 0.5) / n - 0.5) * SHUTTER / FPS
            acc += s.render(tl + dt)
        out += acc / n * w; wsum += w
    img = out / max(wsum, 1e-6)
    # type
    for tid, t0, t1 in TEXTS:
        if t0 <= t <= t1 + 0.01:
            a, ai = text_alpha(t, t0, t1)
            if tid.startswith('ch'): a *= 1.0; ai = 1.0
            if tid in ('t1', 't2', 't3', 't5', 't6', 't7'):
                img = img * (1 - SCRIM_K * a * scrim)
            img = put_text(img, TX[tid], a, ai, blur=not tid.startswith('ch'))
    v0, v1, k0, k1 = KASH
    if v0 <= t <= v1:
        a, ai = text_alpha(t, v0, v1)
        img = img * (1 - SCRIM_K * a * scrim)
        n0 = int(round(ease_io((t - k0) / (k1 - k0)) * 14))
        img = put_text(img, TX[f't4_{n0}'], a, ai)
    # finish: grade, vignette, grain, global fades, mockup tag
    img = np.clip(img, 0, None)
    img = img / (1 + img * 0.12) * 1.1
    img = img * vign
    img += GRAIN[int(t * FPS) % len(GRAIN)][..., None] * 0.016
    fade = smooth(t / 0.9) * smooth((DUR - t) / 1.0)
    img *= fade
    tag = TX['tag']
    img = img * (1 - tag[..., 3:4]) + tag[..., :3]
    return img


scrim = np.exp(-(((yy - H / 2) / 170) ** 2))[..., None] * np.exp(-(((xx - W / 2) / 900) ** 2))[..., None]


def render_index(i):
    t = i / FPS
    img = frame_at(t)
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes()


if __name__ == '__main__':
    out = sys.argv[1]
    if '--stills' in sys.argv:
        ts = [float(x) for x in sys.argv[sys.argv.index('--stills') + 1].split(',')]
        for t in ts:
            img = frame_at(t)
            cv2.imwrite(os.path.join(out, f'still_{t:05.2f}.jpg'), (np.clip(img, 0, 1) * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 88])
        sys.exit()
    t_s = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    t_e = float(sys.argv[3]) if len(sys.argv) > 3 else DUR
    idx = list(range(int(t_s * FPS), int(t_e * FPS)))
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for k, buf in enumerate(pool.imap(render_index, idx, chunksize=2)):
            ff.stdin.write(buf)
            if k % 48 == 0: print(f'{k}/{len(idx)}', flush=True)
    ff.stdin.close(); ff.wait()
    print('done', out)
