"""Procedural plates for the Soil hero film mockup. Writes float-free uint8 PNGs into plates/."""
import os, sys
import numpy as np, cv2

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plates')
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)


def vnoise(h, w, cell, seed):
    r = np.random.default_rng(seed)
    gh, gw = h // cell + 3, w // cell + 3
    small = r.random((gh, gw)).astype(np.float32)
    up = cv2.resize(small, (gw * cell, gh * cell), interpolation=cv2.INTER_CUBIC)
    return up[cell:cell + h, cell:cell + w]


def fbm(h, w, cell, octaves, seed, gain=0.5):
    out = np.zeros((h, w), np.float32); amp = 1.0; tot = 0
    for o in range(octaves):
        c = max(2, cell >> o)
        out += amp * vnoise(h, w, c, seed + o * 31); tot += amp; amp *= gain
    return out / tot


def shade(height, albedo, light=(-0.6, -0.5, 0.62), amb=0.32, spec=0.0, shin=24, ao_r=9, ao_k=1.2):
    gy, gx = np.gradient(height)
    n = np.dstack([-gx, -gy, np.ones_like(height)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    L = np.array(light, np.float32); L /= np.linalg.norm(L)
    lam = np.clip((n * L).sum(2), 0, 1)
    ao = np.clip(1 - ao_k * np.clip(cv2.GaussianBlur(height, (0, 0), ao_r) - height, 0, None) / (height.std() + 1e-6) * 0.5, 0.25, 1)
    col = albedo * (amb + (1 - amb) * lam)[..., None] * ao[..., None]
    if spec:
        H = L + np.array([0, 0, 1.0]); H /= np.linalg.norm(H)
        s = np.clip((n * H).sum(2), 0, 1) ** shin
        col = col + spec * s[..., None] * np.array([1.0, 0.92, 0.82])
    return np.clip(col, 0, 1)


def save(name, img, alpha=None):
    img8 = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)[..., ::-1]
    if alpha is not None:
        img8 = np.dstack([img8, (np.clip(alpha, 0, 1) * 255 + 0.5).astype(np.uint8)])
    cv2.imwrite(os.path.join(OUT, name + '.png'), img8)
    print('saved', name, img8.shape, flush=True)


def grains_field(h, w, n, rmin, rmax, palette, weights, seed, quartz=0.03):
    r = np.random.default_rng(seed)
    hgt = np.zeros((h, w), np.float32)
    alb = np.zeros((h, w, 3), np.float32)
    base = np.array(palette[0]) * 0.55
    alb[:] = base
    radii = np.exp(r.uniform(np.log(rmin), np.log(rmax), n))
    order = np.argsort(radii)[::-1]
    pal = np.array(palette, np.float32); wts = np.array(weights) / np.sum(weights)
    for i in order:
        rad = radii[i]; ex = r.uniform(0.65, 1.0); ang = r.uniform(0, np.pi)
        cx, cy = r.uniform(0, w), r.uniform(0, h)
        R = int(rad) + 2
        x0, x1 = int(max(0, cx - R)), int(min(w, cx + R)); y0, y1 = int(max(0, cy - R)), int(min(h, cy + R))
        if x1 <= x0 or y1 <= y0: continue
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        dx, dy = xx - cx, yy - cy
        u = (dx * np.cos(ang) + dy * np.sin(ang)) / rad
        v = (-dx * np.sin(ang) + dy * np.cos(ang)) / (rad * ex)
        d = 1 - u * u - v * v
        m = d > 0
        if not m.any(): continue
        z = np.sqrt(np.clip(d, 0, 1)) * rad * 0.7 + r.uniform(0, rad * 0.4)
        # facets so grains read as crumbs, not marbles
        z *= 1 + 0.18 * np.sin(u * r.uniform(3, 7) + r.uniform(0, 6)) * np.cos(v * r.uniform(3, 7))
        sub = hgt[y0:y1, x0:x1]
        win = m & (z > sub)
        if r.random() < quartz:
            c = np.array([0.82, 0.76, 0.66]) * r.uniform(0.85, 1.05)
        else:
            c = pal[r.choice(len(pal), p=wts)] * r.uniform(0.82, 1.15)
        sub[win] = z[win]
        alb[y0:y1, x0:x1][win] = c
    return hgt, alb


SOIL_PAL = [(0.34, 0.23, 0.15), (0.43, 0.30, 0.20), (0.27, 0.18, 0.12), (0.53, 0.38, 0.25), (0.48, 0.26, 0.16), (0.60, 0.46, 0.31)]
SOIL_W = [3, 3, 2, 1.4, 1, 0.6]


def make_soil():
    h, w = 1800, 3200
    hgt, alb = grains_field(h, w, 16000, 5, 46, SOIL_PAL, SOIL_W, 11)
    hgt += fbm(h, w, 64, 6, 3) * 8 + vnoise(h, w, 2, 5) * 1.5
    alb *= (0.85 + 0.3 * fbm(h, w, 6, 3, 9))[..., None]
    img = shade(hgt, alb, light=(-0.75, -0.45, 0.48), amb=0.22, spec=0.12, shin=18, ao_r=7)
    img = img * np.array([1.06, 1.0, 0.92])
    save('soil', img)
    return img


STRATA = [(0.93, 0.86, 0.75), (0.84, 0.70, 0.52), (0.71, 0.49, 0.31), (0.56, 0.33, 0.21), (0.89, 0.79, 0.64),
          (0.40, 0.27, 0.18), (0.77, 0.56, 0.36), (0.63, 0.40, 0.25), (0.92, 0.83, 0.70), (0.47, 0.30, 0.19),
          (0.82, 0.64, 0.44), (0.31, 0.21, 0.14), (0.68, 0.45, 0.28), (0.86, 0.74, 0.58), (0.36, 0.24, 0.16)]


def strata_bands(h, w, seed=4, nb=15):
    r = np.random.default_rng(seed)
    th = r.uniform(0.6, 1.6, nb); th = th / th.sum() * h * 1.08
    bounds = np.cumsum(th) - h * 0.04
    x = np.arange(w, dtype=np.float32)
    shared = fbm(1, w, 700, 4, seed + 1)[0] * 160 - 80
    idx = np.zeros((h, w), np.int32)
    yy = np.arange(h, dtype=np.float32)[:, None]
    prev = None
    lines = []
    for k, b in enumerate(bounds[:-1]):
        own = fbm(1, w, 380, 4, seed + 10 + k)[0] * 90 - 45
        wave = 30 * np.sin(x / r.uniform(500, 1100) + r.uniform(0, 6))
        yb = b + shared * (0.6 + 0.4 * np.sin(k)) + own + wave
        if prev is not None: yb = np.maximum(yb, prev + 6)
        prev = yb; lines.append(yb)
        idx += (yy > yb[None, :]).astype(np.int32)
    return idx, lines


def make_strata(soil):
    h, w = 2160, 3840
    idx, lines = strata_bands(h, w)
    cols = np.array(STRATA, np.float32)
    img = cols[idx % len(cols)]
    # grain texture from the soil macro so the zoom-out reads as continuous material
    lum = soil.mean(2)
    tile = cv2.resize(lum, (800, 450), interpolation=cv2.INTER_AREA)
    reps = np.tile(tile, (h // 450 + 1, w // 800 + 1))[:h, :w]
    tex = (reps / reps.mean()) ** 0.9
    img = img * (0.72 + 0.28 * tex)[..., None]
    img *= (0.9 + 0.2 * fbm(h, w, 220, 4, 21))[..., None]
    # thin darker seams at band edges
    edge = cv2.Laplacian(idx.astype(np.float32), cv2.CV_32F)
    edge = cv2.GaussianBlur(np.abs(edge), (0, 0), 2.2)
    img *= (1 - 0.35 * np.clip(edge, 0, 1))[..., None]
    # place the soil macro into a dark band (nested zoom target)
    target = None
    for k in range(len(cols)):
        if cols[k].mean() < 0.3:
            ys, xs = np.where(idx[:, 1400:2400] == k)
            if len(ys) > 4000:
                yc = int(np.median(ys)); target = (k, yc); break
    k, yc = target
    rw, rh = 400, 225
    rx, ry = 1920 - rw // 2, yc - rh // 2
    soil_small = cv2.resize(soil, (rw, rh), interpolation=cv2.INTER_AREA)
    quad = np.vstack([np.hstack([soil_small, soil_small[:, ::-1]]), np.hstack([soil_small[::-1], soil_small[::-1, ::-1]])])
    reps = np.tile(quad, (h // (2 * rh) + 3, w // (2 * rw) + 3, 1))
    oy, ox = (2 * rh) - (ry % (2 * rh)), (2 * rw) - (rx % (2 * rw))
    soilfill = reps[oy:oy + h, ox:ox + w]
    m = (idx == k)
    img[m] = soilfill[m]
    save('strata', img)
    np.save(os.path.join(OUT, 'strata_idx.npy'), idx.astype(np.uint8))
    with open(os.path.join(OUT, 'strata_rect.txt'), 'w') as fh:
        fh.write(f'{rx} {ry} {rw} {rh}')


def make_farm():
    h, w = 2160, 3840
    hill = fbm(h, w, 900, 4, 51)
    earth = np.dstack([0.50 + 0 * hill, 0.31 + 0 * hill, 0.20 + 0 * hill]).astype(np.float32)
    earth *= (0.8 + 0.4 * fbm(h, w, 40, 5, 52))[..., None]
    hgt = hill * 400
    alb = earth.copy()
    r = np.random.default_rng(53)
    x = np.arange(w)
    y = 0
    row = 0
    canopy = np.zeros((h, w), np.float32)
    while y < h + 200:
        yrow = y + 70 * np.sin(x / 650 + row * 0.11) + 120 * (hill[np.clip(int(y), 0, h - 1)] - 0.5) * np.sin(x / 1300)
        for xc in range(0, w, 19):
            yc = yrow[xc] + r.normal(0, 2.5)
            rad = r.uniform(9, 14)
            cv2.circle(canopy, (int(xc), int(yc)), int(rad), float(r.uniform(0.7, 1.0)), -1, lineType=cv2.LINE_AA)
        y += 46; row += 1
    for _ in range(60):  # shade trees
        cv2.circle(canopy, (int(r.uniform(0, w)), int(r.uniform(0, h))), int(r.uniform(40, 80)), 1.3, -1, lineType=cv2.LINE_AA)
    canopy = cv2.GaussianBlur(canopy, (0, 0), 2.0)
    leafy = fbm(h, w, 6, 3, 54)
    green = np.array([0.16, 0.27, 0.13], np.float32)
    m = np.clip(canopy, 0, 1)[..., None]
    alb = alb * (1 - m) + green * (0.75 + 0.5 * leafy)[..., None] * m
    hgt = hgt + canopy * 14 + leafy * 3 * canopy
    img = shade(hgt, alb, light=(-0.8, -0.3, 0.5), amb=0.35, ao_r=6, ao_k=1.0)
    img = img * np.array([1.05, 1.0, 0.9])
    save('farm', img)


def bean_maps(L, seed, roast=1.0):
    r = np.random.default_rng(seed)
    a = L / 2; b = L * 0.37
    H, W = int(b * 2 + 8), int(L + 8)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    x = (xx - W / 2) / a; y = (yy - H / 2) / b
    x = x * (1 + 0.05 * y)  # slight asymmetry
    d = 1 - x * x - y * y
    m = np.clip(d * 6, 0, 1)
    z = np.sqrt(np.clip(d, 0, 1)) * b * 0.9
    y0 = 0.12 * np.sin(np.pi * x * 1.3 + r.uniform(-.4, .4)) + r.uniform(-0.04, 0.04)
    crease = np.exp(-((y - y0) / 0.075) ** 2) * np.clip(1 - x * x * 1.1, 0, 1)
    z = z - crease * b * 0.32
    z += (fbm(H, W, max(4, int(L / 18)), 4, seed + 3) - 0.5) * b * 0.05
    base = np.array([0.30, 0.17, 0.09]) * roast * r.uniform(0.85, 1.1)
    alb = np.ones((H, W, 3), np.float32) * base
    alb *= (0.85 + 0.3 * fbm(H, W, max(3, int(L / 10)), 3, seed + 5))[..., None]
    alb *= (1 - 0.6 * crease)[..., None]
    # chaff line in the crease
    alb += (np.exp(-((y - y0) / 0.018) ** 2) * np.clip(1 - x * x * 1.6, 0, 1))[..., None] * np.array([0.25, 0.18, 0.10])
    return z, alb, m


def bean_sprite(L, seed, angle=0.0, roast=1.0, light=(-0.6, -0.55, 0.6)):
    z, alb, m = bean_maps(L, seed, roast)
    H, W = z.shape
    S = int(np.hypot(H, W)) + 4
    pad = lambda arr: cv2.copyMakeBorder(arr, (S - H) // 2, S - H - (S - H) // 2, (S - W) // 2, S - W - (S - W) // 2, cv2.BORDER_CONSTANT, value=0)
    z, m = pad(z), pad(m); alb = pad(alb)
    M = cv2.getRotationMatrix2D((S / 2, S / 2), angle, 1.0)
    z = cv2.warpAffine(z, M, (S, S)); m = cv2.warpAffine(m, M, (S, S)); alb = cv2.warpAffine(alb, M, (S, S))
    col = shade(z, alb, light=light, amb=0.28, spec=0.55, shin=40, ao_r=max(1, L / 60), ao_k=0.6)
    return col.astype(np.float32), m.astype(np.float32)


def paste(dst, col, a, x, y, shadow=None):
    h, w = a.shape
    x0, y0 = int(x - w / 2), int(y - h / 2)
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(dst.shape[1], x0 + w), min(dst.shape[0], y0 + h)
    if X1 <= X0 or Y1 <= Y0: return
    sa = a[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0, None]
    dst[Y0:Y1, X0:X1] = dst[Y0:Y1, X0:X1] * (1 - sa) + col[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0] * sa


def make_beans():
    # hero bean, macro scale
    L = 2600
    col, a = bean_sprite(L, 101, angle=-18, light=(-0.55, -0.6, 0.55))
    save('bean_big', col, a)
    # pile
    h, w = 2160, 3840
    pile = np.ones((h, w, 3), np.float32) * np.array([0.10, 0.06, 0.035])
    r = np.random.default_rng(102)
    sprites = [bean_sprite(150, 200 + i, angle=r.uniform(0, 360), roast=r.uniform(0.75, 1.15)) for i in range(40)]
    occ = np.zeros((h, w), np.float32)
    for layer in range(3):
        for _ in range(1400):
            c, al = sprites[r.integers(len(sprites))]
            x, y = r.uniform(-60, w + 60), r.uniform(-60, h + 60)
            sh = cv2.GaussianBlur(al, (0, 0), 6) * 0.55
            paste(pile, np.zeros_like(c), sh, x + 8, y + 12)
            paste(pile, c, al, x, y)
    # hero bean at centre, same sprite as bean_big scaled
    hero_w = 150 * (col.shape[1] / L)
    hs = int(round(hero_w))
    small = cv2.resize(col, (hs, hs), interpolation=cv2.INTER_AREA); sa = cv2.resize(a, (hs, hs), interpolation=cv2.INTER_AREA)
    paste(pile, np.zeros_like(small), cv2.GaussianBlur(sa, (0, 0), 6) * 0.6, w / 2 + 8, h / 2 + 12)
    paste(pile, small, sa, w / 2, h / 2)
    save('pile', pile)
    with open(os.path.join(OUT, 'pile_hero.txt'), 'w') as fh:
        fh.write(f'{w/2} {h/2} {hs}')
    # small sprites for the roaster drum, several rotations
    os.makedirs(os.path.join(OUT, 'drum'), exist_ok=True)
    for i in range(6):
        for j in range(12):
            c, al = bean_sprite(84, 300 + i, angle=j * 30, roast=0.8 + 0.08 * i)
            save(f'drum/b{i}_{j}', c, al)


def wood(h, w, seed):
    r = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    warp = fbm(h, w, 600, 4, seed) * 260 + 40 * np.sin(xx / 900)
    rings = np.sin((yy + warp) / 70.0 + fbm(h, w, 120, 3, seed + 1) * 3)
    rings = np.sign(rings) * np.abs(rings) ** 0.35
    streak = cv2.resize(r.random((h // 3, max(2, w // 240))).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    fine = cv2.resize(r.random((h // 1, max(2, w // 40))).astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    v = 0.5 + 0.05 * rings + 0.3 * (streak - 0.5) + 0.16 * (fine - 0.5)
    base = np.array([0.66, 0.50, 0.36])
    img = base * (0.72 + 0.5 * v)[..., None]
    img *= (0.9 + 0.2 * fbm(h, w, 700, 3, seed + 3))[..., None]
    return img.astype(np.float32)


def make_crema():
    S = 3000
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    dx, dy = (xx - S / 2) / (S / 2), (yy - S / 2) / (S / 2)
    rad = np.sqrt(dx * dx + dy * dy) + 1e-4; th = np.arctan2(dy, dx)
    # spiral swirl in polar space
    n1 = fbm(S, S, 160, 6, 61); n2 = fbm(S, S, 90, 5, 62)
    sp = np.sin(th * 3 + np.log(rad) * 7 + n1 * 5) * 0.5 + 0.5
    v = 0.55 * sp + 0.45 * n2
    v = np.clip((v - 0.25) * 1.6, 0, 1)
    dark = np.array([0.20, 0.11, 0.06]); light = np.array([0.66, 0.46, 0.28])
    img = dark + (light - dark) * v[..., None] ** 1.3
    # rim of the cup darker crema ring
    img *= (1 - 0.35 * np.clip((rad - 0.82) / 0.18, 0, 1))[..., None]
    fine = fbm(S, S, 4, 2, 63)
    img *= (0.9 + 0.2 * fine)[..., None]
    # tiny bubbles
    r = np.random.default_rng(64)
    bub = np.zeros((S, S), np.float32)
    for _ in range(2500):
        cv2.circle(bub, (int(r.uniform(0, S)), int(r.uniform(0, S))), int(r.uniform(2, 7)), 1.0, 1, lineType=cv2.LINE_AA)
    img = img + bub[..., None] * 0.08
    a = np.clip((1 - rad) * 200, 0, 1)
    save('crema', img, a)


def make_table_and_cup():
    h, w = 2160, 3840
    tbl = wood(h, w, 71)
    # ring stain: the cup's usual place
    stain = np.zeros((h, w), np.float32)
    cv2.circle(stain, (2240, 1150), 300, 1.0, 10, lineType=cv2.LINE_AA)
    stain = cv2.GaussianBlur(stain, (0, 0), 4)
    tbl *= (1 - 0.18 * stain)[..., None]
    # notebook and a sprig as props
    note = np.zeros((h, w), np.float32)
    cv2.rectangle(note, (700, 520), (1450, 1520), 1.0, -1)
    nb = cv2.GaussianBlur(note, (0, 0), 3)
    shadow = cv2.GaussianBlur(np.roll(np.roll(note, 30, 0), 24, 1), (0, 0), 26)
    tbl *= (1 - 0.45 * shadow)[..., None]
    paper = np.array([0.90, 0.86, 0.78]) * (0.93 + 0.1 * fbm(h, w, 8, 3, 72))[..., None]
    lines = (np.sin(np.arange(h) / 7.0) > 0.985).astype(np.float32)[:, None] * np.ones((1, w))
    paper = paper * (1 - 0.15 * lines[..., None])
    tbl = tbl * (1 - nb[..., None]) + paper * nb[..., None]
    # light falloff, window light from top left
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    lightf = 1.15 - 0.45 * np.clip(np.hypot((xx - 600) / w, (yy - 200) / h), 0, 1)
    tbl *= lightf[..., None]
    save('table', tbl)
    # cup sprite (top view): saucer, cup wall, coffee with crema (crema drawn live on top)
    S = 1100
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    d = np.hypot(xx - S / 2, yy - S / 2)
    cup = np.zeros((S, S, 3), np.float32); a = np.zeros((S, S), np.float32)
    sauc = np.clip((520 - d), 0, 1); a = np.maximum(a, sauc)
    cer = np.array([0.93, 0.91, 0.87])
    cup[:] = cer * (0.86 + 0.12 * np.clip((d - 330) / 190, 0, 1))[..., None]
    cupwall = np.clip(372 - d, 0, 1)
    cup = cup * (1 - 0.2 * np.exp(-((d - 372) / 10) ** 2))[..., None]  # contact shadow
    rim = np.exp(-((d - 350) / 9) ** 2)
    cup += rim[..., None] * 0.07
    inner = np.clip(318 - d, 0, 1)
    cup = cup * (1 - inner[..., None]) + np.array([0.18, 0.10, 0.06]) * inner[..., None]
    # handle
    handle = np.zeros((S, S), np.float32)
    cv2.ellipse(handle, (int(S / 2 + 400), int(S / 2)), (85, 30), 0, 0, 360, 1.0, -1, lineType=cv2.LINE_AA)
    handle *= (d > 360)
    cup = cup * (1 - handle[..., None]) + cer * 0.95 * handle[..., None]
    a = np.clip(a + handle, 0, 1)
    # soft drop shadow baked separately
    sh = cv2.GaussianBlur(a, (0, 0), 22)
    save('cup', cup, a)
    save('cup_shadow', np.zeros((S, S, 3)), sh * 0.55)
    # wide plate used for the crema zoom-out: table with cup at centre
    tw = wood(h, w, 74) * lightf[..., None]
    cx, cy = w // 2, h // 2
    paste(tw, np.zeros((S, S, 3), np.float32), sh * 0.55, cx + 30, cy + 40)
    paste(tw, cup, a, cx, cy)
    save('table_cup', tw)


def make_pourover():
    h, w = 2160, 3840
    tbl = wood(h, w, 81)
    S = 1500
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    d = np.hypot(xx - S / 2, yy - S / 2)
    a = np.clip(700 - d, 0, 1)
    cer = np.array([0.95, 0.93, 0.90])
    rings = 0.92 + 0.06 * np.sin(d / 14) * (d > 330)
    col = cer * rings[..., None] * (0.82 + 0.18 * np.clip((d - 300) / 400, 0, 1))[..., None]
    sh = cv2.GaussianBlur(a, (0, 0), 30) * 0.5
    paste(tbl, np.zeros((S, S, 3), np.float32), sh, w / 2 + 40, h / 2 + 50)
    paste(tbl, col, a, w / 2, h / 2)
    save('pourover', tbl)


def make_kraft():
    h, w = 1800, 3200
    base = np.array([0.66, 0.50, 0.34])
    img = np.ones((h, w, 3), np.float32) * base
    img *= (0.85 + 0.3 * fbm(h, w, 120, 5, 91))[..., None]
    r = np.random.default_rng(92)
    fib = np.zeros((h, w), np.float32)
    for _ in range(26000):
        x, y = r.uniform(0, w), r.uniform(0, h); L = r.uniform(10, 60); ang = r.uniform(0, np.pi)
        x2, y2 = x + L * np.cos(ang), y + L * np.sin(ang)
        cv2.line(fib, (int(x), int(y)), (int(x2), int(y2)), float(r.choice([-1, 1]) * r.uniform(0.3, 1)), 1, lineType=cv2.LINE_AA)
    fib = cv2.GaussianBlur(fib, (0, 0), 0.8)
    hgt = fbm(h, w, 30, 4, 93) * 6 + fib * 1.5
    img = img * (1 + 0.12 * fib)[..., None]
    img = shade(hgt, img, light=(-0.7, -0.4, 0.55), amb=0.55, ao_r=4, ao_k=0.4)
    save('kraft', img)
    return img


def make_bag(kraft):
    h, w = 2160, 3840
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    bg = np.array([0.78, 0.70, 0.60]) * (0.9 + 0.15 * fbm(h, w, 200, 5, 95))[..., None]
    bg *= (1.1 - 0.5 * np.clip(np.hypot((xx - 1500) / w, (yy - 500) / h), 0, 1))[..., None]
    # floor line
    floor = (yy > 1750).astype(np.float32)
    bg = bg * (1 - 0.12 * floor[..., None])
    bx0, bx1, by0, by1 = 1470, 2370, 380, 1820
    mask = np.zeros((h, w), np.float32)
    cv2.rectangle(mask, (bx0, by0), (bx1, by1), 1.0, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), 1.2)
    tile = cv2.resize(kraft, (800, 450), interpolation=cv2.INTER_AREA)
    tex = np.tile(tile, (h // 450 + 1, w // 800 + 1, 1))[:h, :w]
    u = (xx - bx0) / (bx1 - bx0)
    shading = 0.78 + 0.32 * np.clip(np.sin(np.clip(u, 0, 1) * np.pi), 0, 1) ** 0.6
    shading *= (0.95 + 0.1 * fbm(h, w, 90, 3, 96) * (np.sin(xx / 37) * 0.5 + 0.5))
    crimp = (yy < by0 + 120).astype(np.float32) * (0.85 + 0.15 * np.sin(yy / 6))
    shading = shading * np.where(yy < by0 + 120, crimp, 1)
    bag = tex * shading[..., None]
    sh = cv2.GaussianBlur(np.roll(mask, 60, 1), (0, 0), 60) * 0.5
    img = bg * (1 - sh[..., None])
    img = img * (1 - mask[..., None]) + bag * mask[..., None]
    # label from the text pass
    lab = cv2.imread(os.path.join(os.path.dirname(OUT), 'text', 'label.png'), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255
    la = lab[..., 3]
    ys, xs = np.where(la > 0.05)
    crop = lab[ys.min() - 40:ys.max() + 40, xs.min() - 80:xs.max() + 80]
    lw = 640; lh = int(crop.shape[0] * lw / crop.shape[1])
    crop = cv2.resize(crop, (lw, lh), interpolation=cv2.INTER_AREA)
    lx, ly = (bx0 + bx1) // 2 - lw // 2, 980
    card = np.array([0.93, 0.89, 0.81]) * (0.95 + 0.06 * fbm(lh + 80, lw + 80, 20, 3, 97))[..., None]
    img[ly - 40:ly + lh + 40, lx - 40:lx + lw + 40] = card
    ink = crop[..., :3][..., ::-1]; ia = crop[..., 3:4]
    img[ly:ly + lh, lx:lx + lw] = img[ly:ly + lh, lx:lx + lw] * (1 - ia) + ink * ia
    # nested macro region on the upper body of the bag
    rw, rh = 360, 202
    rx, ry = (bx0 + bx1) // 2 - rw // 2, 600
    ks = cv2.resize(kraft, (rw, rh), interpolation=cv2.INTER_AREA) * shading[ry:ry + rh, rx:rx + rw, None]
    yy2, xx2 = np.mgrid[0:rh, 0:rw].astype(np.float32)
    f = np.minimum(np.minimum(xx2, rw - 1 - xx2) / (rw * 0.2), np.minimum(yy2, rh - 1 - yy2) / (rh * 0.2))
    a = np.clip(f, 0, 1)[..., None]
    img[ry:ry + rh, rx:rx + rw] = img[ry:ry + rh, rx:rx + rw] * (1 - a) + ks * a
    save('bag', img)
    with open(os.path.join(OUT, 'bag_rect.txt'), 'w') as fh:
        fh.write(f'{rx} {ry} {rw} {rh}')


if __name__ == '__main__':
    which = sys.argv[1:] or ['soil', 'farm', 'beans', 'crema', 'table', 'pour', 'kraft']
    if 'soil' in which:
        soil = make_soil(); make_strata(soil)
    if 'farm' in which: make_farm()
    if 'beans' in which: make_beans()
    if 'crema' in which: make_crema()
    if 'table' in which: make_table_and_cup()
    if 'pour' in which: make_pourover()
    if 'kraft' in which:
        k = make_kraft(); make_bag(k)
