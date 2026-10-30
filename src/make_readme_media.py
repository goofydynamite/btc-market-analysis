"""Animated media for the README (reports/media/).

    python src/make_readme_media.py            # header SVG + price GIF
    python src/make_readme_media.py --tour     # also the dashboard tour GIF (needs Microsoft Edge)

GitHub renders animated SVG and GIF in a README but runs no JavaScript, so
everything here is a self-contained file.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image

import analysis as A

MEDIA = A.ROOT / "reports" / "media"
BG, INK, MUTED, GRID = "#0f1620", "#eef2f6", "#8b97a6", "#223041"
BLUE, RED = "#3987e5", "#e5484d"


# ------------------------------------------------------------------ header banner

def header_svg() -> Path:
    daily = A.load_daily()
    w = daily["close"].resample("W").last().loc["2012":]
    y = np.log10(w.to_numpy())
    W, H, x0, x1, y0, y1 = 1200, 300, 640, 1160, 250, 60
    xs = np.linspace(x0, x1, len(y))
    ys = y0 - (y - y.min()) / (y.max() - y.min()) * (y0 - y1)
    path = "M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in zip(xs, ys))
    dq = json.loads((A.PROCESSED / "data_quality.json").read_text())
    stats = [(f"{dq['rows'] / 1e6:.2f}M", "one-minute bars"), ("14 yrs", "of BTC/USD"),
             ("47/47", "SQL checks pass"), ("3", "Tableau views")]
    cards = []
    for i, (v, label) in enumerate(stats):
        cx = 40 + i * 145
        cards.append(
            f'<g class="card" style="animation-delay:{0.6 + i * 0.25:.2f}s">'
            f'<rect x="{cx}" y="172" width="137" height="78" rx="10" fill="#172231" stroke="{GRID}"/>'
            f'<text x="{cx + 14}" y="207" class="v">{v}</text>'
            f'<text x="{cx + 14}" y="232" class="l">{label}</text></g>')
    # the four cards end at x=612, leaving the chart clear from x=640
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Bitcoin Market Intelligence">
<style>
  .t {{ font: 700 40px 'Segoe UI', Helvetica, Arial, sans-serif; fill: {INK}; }}
  .s {{ font: 400 17px 'Segoe UI', Helvetica, Arial, sans-serif; fill: {MUTED}; }}
  .v {{ font: 700 24px 'Segoe UI', Helvetica, Arial, sans-serif; fill: {INK}; }}
  .l {{ font: 400 13px 'Segoe UI', Helvetica, Arial, sans-serif; fill: {MUTED}; }}
  .fade {{ opacity: 0; animation: fade .8s ease-out forwards; }}
  .card {{ opacity: 0; animation: rise .7s ease-out forwards; }}
  .line {{ stroke-dasharray: 3200; stroke-dashoffset: 3200; animation: draw 3.2s ease-in-out .3s forwards; }}
  .dot {{ opacity: 0; animation: fade .4s ease-out 3.4s forwards, pulse 1.6s ease-in-out 3.8s infinite; }}
  @keyframes fade {{ to {{ opacity: 1; }} }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(14px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
  @keyframes pulse {{ 50% {{ opacity: .35; }} }}
  @media (prefers-reduced-motion: reduce) {{ .fade, .card, .dot {{ opacity: 1; animation: none; }} .line {{ stroke-dashoffset: 0; animation: none; }} }}
</style>
<rect width="{W}" height="{H}" rx="18" fill="{BG}"/>
<text x="40" y="78" class="t fade">Bitcoin Market Intelligence</text>
<text x="40" y="112" class="s fade" style="animation-delay:.25s">14 years of minute-level BTC/USD data turned into</text>
<text x="40" y="136" class="s fade" style="animation-delay:.35s">product, risk and operations decisions</text>
{''.join(cards)}
<g opacity=".55">{''.join(f'<line x1="{x0}" x2="{x1}" y1="{yy:.0f}" y2="{yy:.0f}" stroke="{GRID}"/>' for yy in np.linspace(y1, y0, 4))}</g>
<path d="{path}" class="line" fill="none" stroke="{BLUE}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>
<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="5" fill="{BLUE}" class="dot"/>
<text x="{x0}" y="{y0 + 30}" class="l fade" style="animation-delay:3.4s">2012</text>
<text x="{x1}" y="{y0 + 30}" class="l fade" style="animation-delay:3.4s" text-anchor="end">2026 · log scale</text>
</svg>"""
    out = MEDIA / "header.svg"
    out.write_text(svg, encoding="utf-8")
    return out


# ------------------------------------------------------------------ price GIF

def price_gif(frames: int = 70, hold: int = 18) -> Path:
    daily = A.load_daily()
    from advanced import markov_regimes
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        reg, _, _ = markov_regimes(daily)
    w = daily["close"].loc["2014":].resample("W").last()
    stress = reg["Stress"].resample("W").mean().reindex(w.index).fillna(0).to_numpy()
    x = np.arange(len(w))
    yv = np.log10(w.to_numpy())
    pts = np.column_stack([x, yv]).reshape(-1, 1, 2)
    segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
    cmap = LinearSegmentedColormap.from_list("stress", [BLUE, BLUE, RED])

    plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"]})
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=80)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=10)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_xlim(0, len(w) + 70)  # room for the running price label
    ax.set_ylim(yv.min() - 0.15, yv.max() + 0.25)
    ticks = [2, 3, 4, 5]
    ax.set_yticks(ticks, ["$100", "$1K", "$10K", "$100K"])
    years = list(range(2014, 2027, 2))
    ax.set_xticks([int(np.searchsorted(w.index.year, yr)) for yr in years], [str(yr) for yr in years])
    halvings = [h for h in A.HALVINGS if h >= w.index[0]]
    for h in halvings:
        hx = int(np.searchsorted(w.index, h))
        ax.axvline(hx, color=GRID, lw=1, zorder=0)
        ax.text(hx, yv.max() + 0.17, "halving", color=MUTED, fontsize=9, ha="center")
    fig.text(0.07, 0.93, "Bitcoin price, 2014–2026", color=INK, fontsize=15, weight="bold")
    fig.text(0.07, 0.87, "Red = model's stress regime (3-state Markov-switching)", color=MUTED, fontsize=10)
    lc = LineCollection([], linewidths=2.2, cmap=cmap)
    lc.set_clim(0, 1)
    ax.add_collection(lc)
    dot, = ax.plot([], [], "o", color=INK, ms=5)
    label = ax.text(0, 0, "", color=INK, fontsize=10, weight="bold")
    fig.subplots_adjust(left=0.07, right=0.97, bottom=0.1, top=0.82)

    ends = np.linspace(2, len(segs), frames).astype(int)

    def update(i):
        n = ends[min(i, frames - 1)]
        lc.set_segments(segs[:n])
        lc.set_array(stress[:n])
        dot.set_data([x[n]], [yv[n]])
        label.set_position((x[n] + 3, yv[n]))
        label.set_text(f"${w.iloc[n]:,.0f}")
        return lc, dot, label

    anim = FuncAnimation(fig, update, frames=frames + hold, blit=False)
    out = MEDIA / "price_history.gif"
    anim.save(out, writer=PillowWriter(fps=14))
    plt.close(fig)
    return out


# ------------------------------------------------------------------ dashboard tour GIF

EDGE = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]


def dashboard_tour(width: int = 1280, view_h: int = 760, scale: float = 0.6) -> Path:
    edge = next((p for p in EDGE if p.exists()), None) or shutil.which("msedge")
    if not edge:
        raise SystemExit("Microsoft Edge not found; the tour GIF needs a headless browser.")
    page = (A.ROOT / "dashboard" / "index.html").as_uri()
    with tempfile.TemporaryDirectory() as tmp:
        shot = Path(tmp) / "full.png"
        subprocess.run([str(edge), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--virtual-time-budget=9000", "--blink-settings=preferredColorScheme=1",
                        f"--window-size={width},9800", f"--screenshot={shot}", page],
                       check=True, capture_output=True, timeout=180)
        full = Image.open(shot).convert("RGB")
    # trim the empty space under the footer
    arr = np.asarray(full.convert("L"))
    rows = np.where((arr < 235).sum(axis=1) > 5)[0]
    full = full.crop((0, 0, width, min(full.height, int(rows.max()) + 40)))
    stops = np.linspace(0, full.height - view_h, 14).astype(int)
    frames, durations = [], []
    for k, top in enumerate(stops):
        nxt = stops[min(k + 1, len(stops) - 1)]
        for j, t in enumerate(np.linspace(top, nxt, 5)[:-1] if k < len(stops) - 1 else [top]):
            f = full.crop((0, int(t), width, int(t) + view_h))
            frames.append(f.resize((int(width * scale), int(view_h * scale)), Image.LANCZOS))
            durations.append(1400 if j == 0 else 70)
    durations[-1] = 2200
    # One shared palette for every frame; per-frame palettes make GIF frame blending tear.
    sample = Image.new("RGB", (frames[0].width, frames[0].height * 8))
    for k, idx in enumerate(np.linspace(0, len(frames) - 1, 8).astype(int)):
        sample.paste(frames[idx], (0, k * frames[0].height))
    palette = sample.quantize(colors=255, method=Image.MEDIANCUT)
    pal = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    out = MEDIA / "dashboard_tour.gif"
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=durations, loop=0,
                optimize=False, disposal=2)
    return out


# ------------------------------------------------------------------ animated charts

FIGURES = A.ROOT / "reports" / "figures"


# How each chart reveals: "grow" = bars rise from the baseline, "sweep" = soft fade
# across (heatmaps), "draw" = lines/areas draw left to right with a soft leading edge.
CHART_STYLE = {
    "06_holding_period_odds": "grow", "07_dca_vs_lump_sum": "grow", "09_crash_rebound": "grow",
    "04_volatility": "draw", "05_liquidity_heatmap": "sweep", "08_dca_cohort_heatmap": "sweep",
}


def _ease(t: float) -> float:
    return 3 * t * t - 2 * t * t * t          # smoothstep ease-in-out


def animate_chart(png: Path, width: int = 900, frames: int = 34, hold_ms: int = 3800) -> Path:
    """Animated reveal of a static chart. The title, subtitle and axes are visible from frame 1."""
    img = Image.open(png).convert("RGB")
    img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    w, h = img.size
    style = CHART_STYLE.get(png.stem, "draw")
    bg = Image.new("RGB", img.size, img.getpixel((2, 2)))
    title_h, axis_w, axis_h = int(h * 0.13), int(w * 0.09), int(h * 0.11)
    feather = 70 if style == "sweep" else 28
    xs, ys = np.arange(w)[None, :], np.arange(h)[:, None]
    always = np.zeros((h, w), bool)
    always[:title_h, :] = True                # title and subtitle
    always[:, :axis_w] = True                 # y-axis ticks
    if style == "grow":
        always[h - axis_h:, :] = True         # x-axis labels stay put while bars rise
    # One palette for every frame (from the finished chart) so frames don't flicker.
    palette = img.quantize(colors=255, method=Image.MEDIANCUT)
    out_frames = []
    for k in range(frames + 1):
        t = _ease(k / frames)
        if style == "grow":
            top = (h - axis_h) - t * (h - axis_h - title_h + feather)
            alpha = np.clip((ys - top) / feather, 0, 1) * np.ones((1, w))
        else:
            edge = axis_w + t * (w - axis_w + feather)
            alpha = np.clip((edge - xs) / feather, 0, 1) * np.ones((h, 1))
        alpha = np.where(always, 1.0, alpha)
        mask = Image.fromarray((alpha * 255).astype(np.uint8), "L")
        f = Image.composite(img, bg, mask)
        out_frames.append(f.quantize(palette=palette, dither=Image.Dither.NONE))
    durations = [55] * frames + [hold_ms]
    out = MEDIA / "charts" / f"{png.stem}.gif"
    out.parent.mkdir(parents=True, exist_ok=True)
    out_frames[0].save(out, save_all=True, append_images=out_frames[1:], duration=durations,
                       loop=0, optimize=True, disposal=1)
    return out


def animate_all_charts() -> list[Path]:
    return [animate_chart(p) for p in sorted(FIGURES.glob("*.png"))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tour", action="store_true", help="also record the dashboard tour (needs Edge)")
    args = ap.parse_args()
    MEDIA.mkdir(parents=True, exist_ok=True)
    paths = [header_svg(), price_gif(), *animate_all_charts()]
    if args.tour:
        paths.append(dashboard_tour())
    for p in paths:
        print(f"{p.relative_to(A.ROOT)}  {p.stat().st_size / 1024:,.0f} KB")


if __name__ == "__main__":
    main()
