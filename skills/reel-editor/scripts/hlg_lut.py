#!/usr/bin/env python3
"""Writes a 3D LUT (.cube) for iPhone HLG (BT.2020) -> SDR BT.709, optionally with a grade.
Usage:  .venv/bin/python <skill-dir>/scripts/hlg_lut.py <out.cube> [--grade] [--exposure 0.48]
ffmpeg:  -vf "scale=in_color_matrix=bt2020:in_range=tv,format=gbrpf32le,lut3d=<out.cube>:interp=tetrahedral,
              scale=out_color_matrix=bt709:out_range=tv,format=yuv420p"
Path: HLG inverse OETF -> OOTF (1000 nit, gamma 1.2) -> reference white 203 nit = 1.0 -> soft shoulder
     (on luminance, colour ratios preserved) -> gamut 2020->709 -> BT.1886 encoding (1/2.4).
--grade adds the brand-film look: gentle S-curve, neutral to cool highlights, shadows towards blue, saturation +6 %.
--wb r,g,b: white balance as a factor on linear light (e.g. 0.95,1,1.06 = cooler).
"""
import sys
import numpy as np

N = 65
a, b, c = 0.17883277, 0.28466892, 0.55991073
M2020_709 = np.array([[1.6605, -0.5876, -0.0728], [-0.1246, 1.1329, -0.0083], [-0.0182, -0.1006, 1.1187]])
Y2020 = np.array([0.2627, 0.6780, 0.0593])
Y709 = np.array([0.2126, 0.7152, 0.0722])


def hlg_inv(e):
    return np.where(e <= 0.5, e * e / 3, (np.exp((e - c) / a) + b) / 12)


def shoulder(l, k=0.55):
    # linear up to k, above that soft towards 1 (continuous slope)
    return np.where(l <= k, l, k + (1 - k) * (1 - np.exp(-(l - k) / (1 - k))))


def grade(v):
    """v: SDR-Signal 0..1 (BT.1886-kodiert). Dezenter Werbefilm-Look."""
    y = v @ Y709
    # S-Kurve um 0.45 (Kontrast +8 %), Schwarz leicht angehoben (Film-Look)
    s = 0.45 + (y - 0.45) * 1.08
    s = 0.015 + s * 0.985
    v = v + (s - y)[..., None]
    # split toning: shadows slightly cool, highlights slightly warm
    sh = np.clip(1 - y / 0.45, 0, 1)[..., None]
    hi = np.clip((y - 0.55) / 0.45, 0, 1)[..., None]
    v = v + sh * np.array([-0.010, -0.002, 0.012]) + hi * np.array([-0.004, 0.0, 0.006])
    # saturation +6 %
    y2 = (v @ Y709)[..., None]
    return y2 + (v - y2) * 1.06


def main():
    out, do_grade = sys.argv[1], "--grade" in sys.argv
    g = np.linspace(0, 1, N)
    # .cube: R varies fastest
    B, G, R = np.meshgrid(g, g, g, indexing="ij")
    e = np.stack([R, G, B], -1).reshape(-1, 3)
    E = hlg_inv(e)  # scene light 0..1
    ys = np.clip(E @ Y2020, 1e-9, None)
    Fd = E * (ys ** 0.2)[:, None]  # display light, 1.0 = 1000 nit
    expo = float(sys.argv[sys.argv.index("--exposure") + 1]) if "--exposure" in sys.argv else 0.48
    L = Fd * (1000 / 203) * expo  # reference white = expo (0.52 = rich, highlights not blown out)
    lum = np.clip(L @ Y2020, 1e-9, None)
    L = L * (shoulder(lum) / lum)[:, None]
    rgb = L @ M2020_709.T
    if "--wb" in sys.argv:
        rgb = rgb * np.array([float(x) for x in sys.argv[sys.argv.index("--wb") + 1].split(",")])
    # outside 709: pull towards grey instead of hard clipping
    yl = (rgb @ Y709)[:, None]
    neg = np.clip(-rgb.min(1, keepdims=True), 0, None)
    t = np.clip(neg / np.clip(yl + neg, 1e-9, None), 0, 1)
    rgb = rgb + (yl - rgb) * t
    v = np.clip(rgb, 0, 1) ** (1 / 2.4)
    if do_grade:
        v = grade(v)
    v = np.clip(v, 0, 1)
    with open(out, "w") as f:
        f.write(f'TITLE "HLG to SDR{" graded" if do_grade else ""}"\nLUT_3D_SIZE {N}\n')
        np.savetxt(f, v, fmt="%.6f")
    print(out, N, "grade" if do_grade else "neutral")


if __name__ == "__main__":
    main()
