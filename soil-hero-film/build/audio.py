"""Temp sound bed for the mockup: ambient pad, texture, whooshes and spot effects, synced to render.py timings."""
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 48000
DUR = 61.5
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(3)
L = np.zeros(N); R = np.zeros(N)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], 'band', fs=SR, output='sos'), x)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, 'low', fs=SR, output='sos'), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, 'high', fs=SR, output='sos'), x)


def env(t0, a, s_, r, peak=1.0):
    e = np.zeros(N)
    i0 = int(t0 * SR)
    n_a, n_s, n_r = int(a * SR), int(s_ * SR), int(r * SR)
    seg = np.concatenate([np.linspace(0, 1, n_a) ** 2, np.ones(n_s), np.linspace(1, 0, n_r) ** 2]) * peak
    i1 = min(N, i0 + len(seg))
    e[i0:i1] = seg[:i1 - i0]
    return e


def add(x, gain=1.0, pan=0.0):
    global L, R
    L += x * gain * (1 - pan) / 1.0
    R += x * gain * (1 + pan) / 1.0


def smoothstep(x):
    x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)


# pad: D minor colour, slow movement
pad_env = smoothstep(t / 4) * (0.55 + 0.25 * smoothstep((t - 40) / 8)) * (1 - 0.6 * smoothstep((t - 56.3) / 0.6)) * (1 - smoothstep((t - 60.3) / 1.2))
for f, g, pan in [(73.42, 0.5, -0.2), (110.0, 0.35, 0.2), (146.83, 0.22, -0.3), (174.61, 0.12, 0.35), (220.0, 0.08, 0)]:
    for det in (-0.25, 0.25):
        trem = 1 + 0.15 * np.sin(2 * np.pi * (0.07 + 0.03 * det) * t + f)
        add(np.sin(2 * np.pi * (f + det) * t) * trem * pad_env, g * 0.06, pan + det)
# close chord, brighter
close_env = smoothstep((t - 56.6) / 1.5) * (1 - smoothstep((t - 60.2) / 1.3))
for f, g in [(146.83, 0.3), (220.0, 0.25), (293.66, 0.18), (349.23, 0.1)]:
    add(np.sin(2 * np.pi * f * t) * close_env, g * 0.05, 0)

# earth bed
brown = np.cumsum(rng.normal(0, 1, N)); brown = hp(brown, 20); brown /= np.abs(brown).max()
add(lp(brown, 300) * smoothstep(t / 3) * (1 - smoothstep((t - 60) / 1.5)), 0.08)

# grain crackle under the soil macro
imp = (rng.random(N) < 0.0009) * rng.normal(0, 1, N)
crack = bp(imp, 1800, 7000) * env(0.2, 1.5, 6.5, 2.0)
add(crack, 0.5, -0.2); add(np.roll(crack, 400), 0.4, 0.2)


def whoosh(tc, dur=0.6, gain=0.35, pan=0.0):
    i0 = int((tc - dur / 2) * SR); n = int(dur * SR)
    if i0 < 0: return
    noise = rng.normal(0, 1, n)
    u = np.linspace(0, 1, n)
    e = np.sin(np.pi * u) ** 3
    lo = bp(noise, 150, 900) * (1 - u); hi = bp(noise, 900, 6000) * u
    x = (lo * 1.4 + hi) * e
    seg = np.zeros(N); seg[i0:i0 + n] = x[:max(0, min(n, N - i0))]
    add(seg, gain * (1 - pan * 0.5), pan)
    add(seg * 0, 0)


for tc in (13.17, 17.27, 22.47, 25.87, 42.52):
    whoosh(tc, 0.7, 0.4)
seg = (42.6 - 40.3) / 7
for i in range(7):
    whoosh(40.3 + seg * (i + 0.5), 0.3, 0.25, pan=0.6 if i % 2 else -0.6)
for k in range(15):
    whoosh(46.0 + 0.11 * k + 0.25, 0.45, 0.12, pan=0.5 if k % 2 else -0.5)

# roaster: rumble plus bean rattle
e_d = env(22.4, 0.3, 3.0, 0.4)
add(lp(rng.normal(0, 1, N), 140) * e_d * (1 + 0.3 * np.sin(2 * np.pi * 0.55 * t)), 0.5)
rat = (rng.random(N) < 0.006) * rng.normal(0, 1, N)
add(bp(rat, 1500, 5000) * e_d, 0.6, -0.15); add(bp(np.roll(rat, 900), 1500, 5000) * e_d, 0.5, 0.15)

# pour
e_p = env(30.3, 0.5, 2.6, 0.5)
water = bp(rng.normal(0, 1, N), 350, 2600) * (0.7 + 0.3 * lp(rng.normal(0, 1, N), 9) * 6)
add(water * e_p, 0.12)

# cup lands on its usual place
tl = 34.95; i0 = int(tl * SR); n = int(0.6 * SR); u = np.arange(n) / SR
thud = np.sin(2 * np.pi * 85 * u) * np.exp(-u * 22)
tick = (np.sin(2 * np.pi * 3150 * u) + 0.6 * np.sin(2 * np.pi * 5230 * u)) * np.exp(-u * 45)
x = np.zeros(N); x[i0:i0 + n] = thud * 0.6 + tick * 0.18
add(x, 1.0)
# slide before landing
e_s = env(34.0, 0.2, 0.55, 0.25)
add(bp(rng.normal(0, 1, N), 2000, 6000) * e_s, 0.05, 0.4)

# kashida rise
e_k = env(27.0, 0.3, 1.4, 0.6)
ph = np.cumsum(2 * np.pi * (220 + 110 * smoothstep((t - 27.0) / 1.7)) / SR)
add(np.sin(ph) * e_k, 0.035)

# riser and boom for the reveal
e_r = np.clip((t - 46.0) / 2.4, 0, 1) ** 2 * (t < 48.4)
add(hp(rng.normal(0, 1, N), 2500) * e_r, 0.10)
ph = np.cumsum(2 * np.pi * (180 + 520 * np.clip((t - 46.0) / 2.4, 0, 1) ** 2) / SR)
add(np.sin(ph) * e_r, 0.03)
i0 = int(48.4 * SR); n = int(3.0 * SR); u = np.arange(n) / SR
boom = np.sin(2 * np.pi * np.cumsum(60 - 22 * (1 - np.exp(-u * 3))) / SR) * np.exp(-u * 1.6)
burst = lp(rng.normal(0, 1, n), 400) * np.exp(-u * 4)
x = np.zeros(N); x[i0:i0 + n] = boom * 0.8 + burst * 0.4
add(x, 1.0)
# soft bell at the close
i0 = int(57.0 * SR); n = int(4.0 * SR); u = np.arange(n) / SR
bell = (np.sin(2 * np.pi * 587.3 * u) + 0.4 * np.sin(2 * np.pi * 1174.7 * u) + 0.2 * np.sin(2 * np.pi * 1761 * u)) * np.exp(-u * 1.4)
x = np.zeros(N); x[i0:i0 + n] = bell
add(x, 0.05)

mix = np.stack([L, R], 1)
mix *= np.clip(t / 0.6, 0, 1)[:, None] * np.clip((DUR - t) / 0.8, 0, 1)[:, None]
mix = np.tanh(mix / np.abs(mix).max() * 1.4) / np.tanh(1.4) * 0.89
wavfile.write('audio.wav', SR, (mix * 32767).astype(np.int16))
print('audio ok', mix.shape)
