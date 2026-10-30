"""Static matplotlib charts for the README / notebook (saved to reports/figures/)."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

import analysis as A

FIG_DIR = A.ROOT / "reports" / "figures"

# Colour palette. The categorical order keeps neighbouring series distinguishable for colour-blind readers.
SURFACE = "#fcfcfb"
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIVERGING = LinearSegmentedColormap.from_list(
    "red_gray_blue", ["#b52f2f", "#e34948", "#f0efec", "#3987e5", "#104281"])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 10.5,
    "text.color": INK, "axes.labelcolor": INK_2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": AXIS, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.titlesize": 13, "axes.titleweight": "semibold", "axes.titlelocation": "left",
    "axes.titlepad": 22, "lines.linewidth": 2, "lines.solid_capstyle": "round",
    "legend.frameon": False, "figure.dpi": 110, "axes.axisbelow": True,
})


def _subtitle(ax, text: str) -> None:
    ax.text(0, 1.02, text, transform=ax.transAxes, color=INK_2, fontsize=10, va="bottom")


def _save(fig, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    return path


def usd(x, _=None) -> str:
    if x >= 1000:
        return f"${x/1000:,.0f}K"
    return f"${x:,.0f}" if x >= 1 else f"${x:.2f}"


# ------------------------------------------------------------------------------

def price_history(daily: pd.DataFrame):
    c = daily["close"]
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.plot(c.index, c, color=SERIES[0], lw=1.6)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(usd))
    for h in A.HALVINGS:
        ax.axvline(h, color=AXIS, lw=1, zorder=0)
        ax.text(h, c.max() * 1.6, "halving", color=MUTED, fontsize=8.5, ha="center")
    for _, ep in A.halving_cycles(c).iterrows():
        d, p = pd.Timestamp(ep.cycle_peak_date, tz="UTC"), ep.cycle_peak
        ax.scatter([d], [p], s=40, color=SERIES[0], edgecolor=SURFACE, lw=2, zorder=3)
        ax.annotate(usd(p), (d, p), xytext=(0, 8), textcoords="offset points", ha="center",
                    fontsize=9, color=INK_2)
    ax.set_ylim(top=c.max() * 3)
    ax.set_title("Bitcoin price, 2012–2026 (log scale)")
    _subtitle(ax, f"Daily close in USD, \\${c.iloc[0]:,.0f} → \\${c.iloc[-1]:,.0f}. Each dot marks a cycle peak")
    ax.grid(axis="x", visible=False)
    return _save(fig, "01_price_history.png")


def halving_cycles_indexed(daily: pd.DataFrame):
    c = daily["close"]
    fig, ax = plt.subplots(figsize=(11, 4.8))
    bounds = list(A.HALVINGS) + [c.index[-1]]
    for i, (s, e) in enumerate(zip(bounds[:-1], bounds[1:])):
        seg = c.loc[s:e]
        x = (seg.index - s).days
        y = seg / seg.iloc[0]
        ax.plot(x, y, color=SERIES[i], lw=1.8, label=f"{s.year} halving")
        ax.annotate(f"{s.year}", (x[-1], y.iloc[-1]), xytext=(5, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK_2)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:g}×"))
    ax.axhline(1, color=AXIS, lw=1)
    ax.set_xlabel("Days since halving")
    ax.legend(loc="lower right", ncol=2)
    ax.set_title("Every halving cycle has peaked ~12–18 months later, with smaller gains each time")
    _subtitle(ax, "Price indexed to 1× on halving day")
    return _save(fig, "02_halving_cycles.png")


def underwater(daily: pd.DataFrame):
    dd = A.drawdown(daily["close"])
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.fill_between(dd.index, dd, 0, color=SERIES[7], alpha=0.12, lw=0)
    ax.plot(dd.index, dd, color=SERIES[7], lw=1.2)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1))
    ep = A.drawdown_episodes(daily["close"])
    for _, r in ep.iterrows():
        t = pd.Timestamp(r.trough_date, tz="UTC")
        ax.annotate(f"{r.depth:.0%}", (t, r.depth), xytext=(0, -12), textcoords="offset points",
                    ha="center", fontsize=8.5, color=INK_2)
    ax.set_ylim(-1, 0.05)
    ax.set_title("Drawdown from all-time high")
    _subtitle(ax, "Six bear markets deeper than 50%; holders were underwater for up to 3.2 years")
    ax.grid(axis="x", visible=False)
    return _save(fig, "03_drawdowns.png")


def volatility(daily: pd.DataFrame):
    v = A.rolling_volatility(daily, 90)
    era = A.risk_by_era(daily)
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(v.index, v, color=SERIES[0], lw=1.4)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    spans = [("2012", "2016"), ("2017", "2020"), ("2021", "2023"), ("2024", "2026")]
    for (a, b), (name, row) in zip(spans, era.iterrows()):
        x0, x1 = pd.Timestamp(f"{a}-01-01", tz="UTC"), pd.Timestamp(f"{b}-12-31", tz="UTC")
        x1 = min(x1, v.index[-1])
        ax.hlines(row.ann_volatility, x0, x1, color=INK, lw=1.5)
        ax.text(x0 + (x1 - x0) / 2, 2.1, f"{name.split(' ', 1)[1]}\navg {row.ann_volatility:.0%}",
                ha="center", va="top", fontsize=9, color=INK_2)
    ax.set_title("Volatility has roughly halved since the early market")
    _subtitle(ax, "Annualised 90-day rolling volatility; black bars = era average")
    ax.grid(axis="x", visible=False)
    return _save(fig, "04_volatility.png")


def liquidity_heatmap(hourly: pd.DataFrame):
    v = A.intraday_heatmaps(hourly)["volume_index"]
    fig, ax = plt.subplots(figsize=(11, 3.8))
    cmap = LinearSegmentedColormap.from_list("blue", BLUE_RAMP)
    im = ax.imshow(v.values, aspect="auto", cmap=cmap)
    ax.set_xticks(range(24), [f"{h:02d}" for h in range(24)])
    ax.set_yticks(range(7), [d[:3] for d in v.index])
    ax.grid(False)
    ax.set_xlabel("Hour (UTC)")
    hi = np.unravel_index(np.nanargmax(v.values), v.shape)
    lo = np.unravel_index(np.nanargmin(v.values), v.shape)
    for (r, c_), col in ((hi, "white"), (lo, INK)):
        ax.text(c_, r, f"{v.values[r, c_]:.1f}×", ha="center", va="center", fontsize=8.5, color=col)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=MUTED)
    cb.set_label("× average hour", color=INK_2)
    ax.set_title("Trading peaks at 13–16 UTC on weekdays and halves on weekends")
    _subtitle(ax, "Median USD volume per hour, indexed to the average hour of the week (2019–2026)")
    return _save(fig, "05_liquidity_heatmap.png")


def holding_odds(daily: pd.DataFrame):
    t = A.holding_period_odds(daily["close"])
    fig, ax = plt.subplots(figsize=(11, 4))
    x = np.arange(len(t))
    ax.bar(x, t["prob_profit"], width=0.55, color=SERIES[0])
    for i, p in enumerate(t["prob_profit"]):
        label = f"{p:.1%}" if 0.99 < p < 1 else f"{p:.0%}"
        ax.text(i, p + 0.02, label, ha="center", fontsize=9.5, color=INK)
    ax.axhline(0.5, color=AXIS, lw=1)
    ax.set_xticks(x, t.index)
    ax.set_ylim(0, 1.1)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    ax.grid(axis="x", visible=False)
    ax.set_title("The odds of being in profit rise sharply with holding time")
    _subtitle(ax, f"Share of all buy days since 2014 that were in profit after each holding period "
                  f"({t['buy_days_tested'].iloc[0]:,} buy days)")
    return _save(fig, "06_holding_period_odds.png")


def dca_vs_lump(daily: pd.DataFrame):
    c = daily["close"]
    horizons = [12, 24, 36, 48]
    fig, ax = plt.subplots(figsize=(11, 4.4))
    for i, h in enumerate(horizons):
        t = A.dca_vs_lump_sum(c, h)
        for j, (col, color, name) in enumerate(((t["dca_roi"], SERIES[0], "Weekly recurring buy"),
                                                (t["lump_sum_roi"], SERIES[1], "Lump sum on day 1"))):
            pos = i * 3 + j
            q10, q25, q50, q75, q90 = np.log1p(col).quantile([.1, .25, .5, .75, .9])
            ax.vlines(pos, q10, q90, color=color, lw=2)
            ax.add_patch(plt.Rectangle((pos - 0.3, q25), 0.6, q75 - q25, color=color, alpha=0.25, lw=0))
            ax.hlines(q50, pos - 0.3, pos + 0.3, color=color, lw=3)
            if i == 0:
                ax.plot([], [], color=color, lw=6, alpha=0.6, label=name)
    ticks = [-0.5, 0, 1, 3, 10]
    ax.set_yticks(np.log1p(ticks), [f"{t:+.0%}" for t in ticks])
    ax.axhline(0, color=AXIS, lw=1)
    ax.set_xticks([i * 3 + 0.5 for i in range(len(horizons))], [f"{h} months" for h in horizons])
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left")
    ax.set_title("Recurring buys give up upside in exchange for a much narrower range of outcomes")
    _subtitle(ax, "ROI by monthly start cohort since 2014: box = middle 50%, line = 10th–90th pct, bar = median")
    return _save(fig, "07_dca_vs_lump_sum.png")


def dca_cohort_heatmap(daily: pd.DataFrame):
    m = A.dca_cohort_matrix(daily["close"])
    z = np.log1p(m)
    fig, ax = plt.subplots(figsize=(11, 8))
    im = ax.imshow(z.values, aspect="auto", cmap=DIVERGING,
                   norm=TwoSlopeNorm(vcenter=0, vmin=np.log1p(-0.7), vmax=np.nanmax(z.values)))
    ax.set_xticks(range(m.shape[1]), [f"{c}m" for c in m.columns])
    ax.set_yticks(range(0, len(m), 2), m.index[::2])
    ax.grid(False)
    ax.set_xlabel("Months of weekly recurring buys")
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
    ticks = [-0.5, 0, 1, 3, 10]
    cb.set_ticks(np.log1p(ticks), labels=[f"{t:+.0%}" for t in ticks])
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=MUTED)
    ax.set_title("Recurring-buy ROI by start cohort: red = losing money, blue = profit", pad=28)
    _subtitle(ax, "Each row is a customer cohort starting a weekly $100 plan in that quarter")
    return _save(fig, "08_dca_cohort_heatmap.png")


def crash_rebound(daily: pd.DataFrame):
    _, s = A.crash_event_study(daily)
    s = s.loc[[1, 7, 30, 90]]
    fig, ax = plt.subplots(figsize=(11, 4))
    x = np.arange(len(s))
    w = 0.32
    for j, (col, color, name) in enumerate((("after_crash_median", SERIES[0], "After a −10% day"),
                                            ("baseline_median", SERIES[1], "Any day (baseline)"))):
        ax.bar(x + (j - 0.5) * (w + 0.03), s[col], width=w, color=color, label=name)
        for i, v in enumerate(s[col]):
            ax.text(i + (j - 0.5) * (w + 0.03), v + 0.002, f"{v:+.1%}", ha="center", fontsize=9, color=INK)
    ax.set_xticks(x, [f"Next {d} day{'s' if d > 1 else ''}" for d in s.index])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    ax.axhline(0, color=AXIS, lw=1)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left")
    ax.set_title("Selling on a crash day usually means missing the rebound")
    _subtitle(ax, f"Median forward return after the {int(s['events'].iloc[0])} one-day drops of 10%+ since 2014")
    return _save(fig, "09_crash_rebound.png")


def make_all() -> list[Path]:
    daily, hourly = A.load_daily(), A.load_hourly()
    paths = [price_history(daily), halving_cycles_indexed(daily), underwater(daily), volatility(daily),
             liquidity_heatmap(hourly), holding_odds(daily), dca_vs_lump(daily),
             dca_cohort_heatmap(daily), crash_rebound(daily)]
    plt.close("all")
    return paths


if __name__ == "__main__":
    for p in make_all():
        print(p)
