"""Soil hero film mockup, stock cut: real footage for the world, renders for the reveals and identity.
Usage: python3 render_stock.py out.mp4 | python3 render_stock.py outdir --stills t1,t2"""
import os, sys, math, subprocess
import numpy as np, cv2
import render as R
from render import W, H, FPS, ease_io, ease_out, smooth, lerp, logzoom, Layer, composite

STOCK = os.path.join(os.path.dirname(R.BASE), 'stock')
R.SHUTTER = 1.0   # 360 degree shutter: the brief asks for visible motion blur
R.SCRIM_K = 0.38


def clip(name):
    return next(os.path.join(STOCK, f) for f in os.listdir(STOCK) if name in f)


def grade(img, exposure=1.0, sat=0.85, warm=0.06):
    # one warm, slightly muted look across all footage (BGR)
    g = img.mean(2, keepdims=True)
    img = g + (img - g) * sat
    img = img * np.array([1 - warm, 1.0, 1 + warm], np.float32) * exposure
    return img


class Clip:
    """Frames of one stock clip held in memory between two source times."""

    def __init__(self, name, t_from, t_to):
        cap = cv2.VideoCapture(clip(name))
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t_from * self.fps))
        self.t_from = int(t_from * self.fps) / self.fps
        n = int((t_to - t_from) * self.fps) + 2
        self.frames = []
        for _ in range(n):
            ok, f = cap.read()
            if not ok: break
            self.frames.append(f)
        cap.release()

    def at(self, t):
        x = (t - self.t_from) * self.fps
        x = min(max(x, 0), len(self.frames) - 1.001)
        i = int(x); fr = x - i
        a = self.frames[i].astype(np.float32)
        if fr > 0.02:
            a = a * (1 - fr) + self.frames[i + 1].astype(np.float32) * fr
        return a / 255.0


class Stock(R.Shot):
    """A clip with a digital camera on top: zoom from z0 to z1 (a pull-back reveal when z0 > z1)."""

    def __init__(self, t0, t1, c, src0, speed=1.0, z0=1.05, z1=1.05, zt=(0, 1), fx=0.5, fy=0.5, fx1=None, fy1=None,
                 rack=0.0, exposure=1.0, sat=0.85, **k):
        super().__init__(t0, t1, **k)
        self.c, self.src0, self.speed = c, src0, speed
        self.z0, self.z1, self.zt = z0, z1, zt
        self.fx, self.fy = fx, fy
        self.fx1 = fx if fx1 is None else fx1; self.fy1 = fy if fy1 is None else fy1
        self.rack, self.exposure, self.sat = rack, exposure, sat

    def cam(self, tl):
        d = self.t1 - self.t0
        u = ease_io((tl / d - self.zt[0]) / max(1e-3, self.zt[1] - self.zt[0]))
        z = logzoom(self.z0, self.z1, u)
        return (lerp(self.fx, self.fx1, u), lerp(self.fy, self.fy1, u), z)

    def motion(self, tl):
        m = super().motion(tl)
        return max(m, 40)  # always blend clip time across the shutter

    def cam_full(self, tl, pan=(0, 0)):
        fx, fy, z = self.cam(tl)
        return (fx, fy, W / z)  # cw only used by the base motion estimate

    def render(self, tl, pan=(0, 0)):
        fx, fy, z = self.cam(tl)
        src = self.c.at(self.src0 + tl * self.speed)
        sh, sw = src.shape[:2]
        k = W / sw * z
        # keep the crop inside the frame
        cx = min(max(fx * sw, sw / (2 * z)), sw - sw / (2 * z))
        cy = min(max(fy * sh, sh / (2 * z)), sh - sh / (2 * z))
        ox = -self.whip(tl) * 0.3 - pan[0]; oy = -pan[1]  # shorter travel, the shutter does the smear
        M = np.float32([[k, 0, W / 2 - cx * k + ox], [0, k, H / 2 - cy * k + oy]])
        img = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        if self.rack:
            sig = self.rack * (1 - smooth(tl / 2.6))
            if sig > 0.3: img = cv2.GaussianBlur(img, (0, 0), sig)
        return grade(img, self.exposure, self.sat)

    def motion_base(self, tl): return 0


# whip motion estimate for stock shots: base Shot.motion uses cam_full, so give it world-like numbers
def _stock_motion(self, tl):
    dt = 1.0 / FPS
    a, b = self.cam(tl - dt / 2), self.cam(tl + dt / 2)
    zoom = abs(math.log(b[2] / a[2])) * W * 0.6
    pan = abs((b[0] - a[0]) * W * a[2]) + abs((b[1] - a[1]) * H * a[2])
    whip = abs(self.whip(tl + dt / 2) - self.whip(tl - dt / 2)) * 0.3
    return max(40, zoom + pan + whip)


Stock.motion = _stock_motion

print('loading stock', flush=True)
C_soil = Clip('Soil_Earth', 0, 18.6)
C_terr = Clip('Panyaweuyan', 0, 13.2)
C_rice = Clip('Rice_Terrace', 2, 9)
C_bean = Clip('0_Coffee_Bean_1280', 0, 8.0)
C_fall = Clip('Coffee_Bean_Falling', 0, 9.2)
C_grind = Clip('Coffee_Beans_Coffee_Grinder', 0, 4.0)
C_top = Clip('2142467_Coffee_Coffees', 0, 3.0)
C_foam = Clip('Coffee_Foam', 0, 5.8)
C_bloom = Clip('Tea_Infusion', 0, 6.6)
C_pour = Clip('Drink_Glass', 2, 12)


# ---- soil to strata: the real soil clip becomes one layer of the sand strata ----
mid = cv2.resize(C_soil.at(6.0), (R.rw, R.rh), interpolation=cv2.INTER_AREA)
mid = grade(mid, 1.15, 0.85)
quad = np.vstack([np.hstack([mid, mid[:, ::-1]]), np.hstack([mid[::-1], mid[::-1, ::-1]])])
reps = np.tile(quad, (2160 // (2 * R.rh) + 3, 3840 // (2 * R.rw) + 3, 1))
oy, ox = (2 * R.rh) - (R.ry % (2 * R.rh)), (2 * R.rw) - (R.rx % (2 * R.rw))
strata2 = R.strata.copy()
m = R.sidx == R.band_k
strata2[m] = reps[oy:oy + 2160, ox:ox + 3840][m]
L_strata2 = Layer(strata2, 0, 0, 3840)
soil_mask = cv2.resize((R.sidx[R.ry:R.ry + R.rh, R.rx:R.rx + R.rw] == R.band_k).astype(np.float32), (1280, 720))
soil_mask = cv2.GaussianBlur(soil_mask, (0, 0), 4)


class SoilToStrata(R.Shot):
    def cam(self, tl):
        u = ease_io(tl / (self.t1 - self.t0))
        return (lerp(R.SOIL_CX, 1920, u), lerp(R.SOIL_CY, 1080, u), logzoom(R.rw * 0.95, 3840, u))

    def layers(self, tl):
        f = grade(C_soil.at(8.0 + tl * 0.6), 1.15, 0.85)
        return [L_strata2, Layer(f, R.rx, R.ry, R.rw, alpha=soil_mask, levels=4)]


# ---- montage of the real details, sand bands sliding over ----
class MontageS(R.Montage):
    pass


T = [
    Stock(0.0, 8.2, C_soil, 0.5, speed=0.6, z0=2.3, z1=1.25, zt=(0, 1), fx=0.45, fy=0.55, rack=14, exposure=1.2),
    SoilToStrata(8.0, 13.25, whip_out=0.32),
    Stock(13.1, 17.35, C_terr, 1.0, z0=1.5, z1=1.08, fx=0.55, fy=0.4, whip_in=0.32, whip_out=0.32),
    Stock(17.2, 22.55, C_bean, 0.4, speed=0.7, z0=3.2, z1=1.05, zt=(0.25, 1), fx=0.36, fy=0.44, fx1=0.5, fy1=0.5,
          rack=6, whip_in=0.32, whip_out=0.3),
    Stock(22.4, 24.2, C_fall, 2.0, speed=0.8, z0=1.15, z1=1.35, whip_in=0.3),
    Stock(24.1, 25.95, C_grind, 0.0, speed=1.0, z0=1.25, z1=1.05, whip_out=0.3),
    Stock(25.8, 30.55, C_foam, 0.2, speed=0.9, z0=2.6, z1=1.05, zt=(0.2, 1), fx=0.45, fy=0.62, fx1=0.5, fy1=0.5,
          exposure=0.6, whip_in=0.3),
    Stock(30.25, 32.1, C_bloom, 1.0, speed=0.8, z0=1.9, z1=1.2, exposure=1.1),
    Stock(31.9, 33.75, C_pour, 2.0, speed=1.0, z0=1.35, z1=1.08, fy=0.45),
]
S_table = R.S_G
S_mont = MontageS(40.3, 42.6, [(T[0], 4.0, 1), (T[3], 0.4, -1), (T[5], 0.6, 1), (T[6], 0.6, -1), (T[2], 2.0, 1),
                               (Stock(0, 3, C_rice, 0.0, z0=1.2, z1=1.1), 1.0, -1), (T[8], 1.2, 1)])
S_close = Stock(56.45, R.DUR, C_soil, 12.0, speed=0.4, z0=1.4, z1=1.3, rack=0, exposure=0.38)
_close_render = S_close.render
S_close.render = lambda tl, pan=(0, 0): cv2.GaussianBlur(_close_render(tl, pan), (0, 0), 5)

R.SHOTS = T + [S_table, S_mont, R.S_I, R.S_J, S_close]


def render_index(i):
    img = R.frame_at(i / FPS)
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes()


if __name__ == '__main__':
    out = sys.argv[1]
    if '--stills' in sys.argv:
        for t in [float(x) for x in sys.argv[sys.argv.index('--stills') + 1].split(',')]:
            cv2.imwrite(os.path.join(out, f's_{t:05.2f}.jpg'), (np.clip(R.frame_at(t), 0, 1) * 255).astype(np.uint8))
        sys.exit()
    from multiprocessing import Pool
    idx = list(range(int(R.DUR * FPS)))
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS),
                           '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for k, buf in enumerate(pool.imap(render_index, idx, chunksize=2)):
            ff.stdin.write(buf)
            if k % 48 == 0: print(f'{k}/{len(idx)}', flush=True)
    ff.stdin.close(); ff.wait()
    print('done', out)
