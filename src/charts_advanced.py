"""Charts for the advanced layer (reports/figures/1x_*.png). Shares styling with charts.py."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

import advanced as X
from charts import AXIS, BLUE_RAMP, INK, INK_2, MUTED, SERIES, SURFACE, _save, _subtitle, usd

REGIME_COLORS = {"Calm": BLUE_RAMP[0], "Normal": BLUE_RAMP[3], "Stress": SERIES[7]}
REGIME_ALPHA = 0.5
ETF_LABELS = {"realized_vol": "Realized volatility (ann.)", "weekend_share": "Weekend share of weekly volume",
              "us_hours_share": "US-session share of weekday volume"}


def etf_its(weekly: pd.DataFrame, table: pd.DataFrame, details: dict):
    specs = [("realized_vol", "Realized volatility (annualised)", lambda v, _: f"{v:.0%}"),
             ("us_hours_share", "US-session share of weekday volume", lambda v, _: f"{v:.0%}"),
             ("weekend_share", "Weekend share of weekly volume", lambda v, _: f"{v:.0%}")]
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    for ax, (col, title, fmt) in zip(axes, specs):
        f = details[col]["its"]["frame"]
        row = table.loc[ETF_LABELS[col]]
        ax.plot(f.index, f["actual"], color=SERIES[0], lw=1.1, alpha=0.9)
        pre, post = f.index < X.ETF_LAUNCH, f.index >= X.ETF_LAUNCH
        ax.hlines(row.pre_mean, f.index[pre][0], f.index[pre][-1], color=INK, lw=2)
        ax.hlines(row.post_mean, f.index[post][0], f.index[post][-1], color=INK, lw=2)
        ax.axvline(X.ETF_LAUNCH, color=SERIES[1], lw=1.5)
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(fmt))
        ax.grid(axis="x", visible=False)
        verdict = "significant" if row.mean_diff_p < 0.05 else "not significant"
        ax.set_title(title, fontsize=11.5, pad=6)
        ax.text(0.995, 0.96, f"mean {row.pre_mean:.1%} → {row.post_mean:.1%}  ·  p = {row.mean_diff_p:.3f} ({verdict})"
                f"  ·  data-chosen break: {row.strongest_break_week:%b %Y}",
                transform=ax.transAxes, ha="right", va="top", fontsize=9, color=INK_2,
                bbox=dict(fc=SURFACE, ec="none", pad=2))
    axes[-1].text(X.ETF_LAUNCH, axes[-1].get_ylim()[0], " ETF launch", color=INK_2, fontsize=9, va="bottom")
    fig.suptitle("Did the January 2024 spot-ETF launch change how Bitcoin trades?", x=0.125, ha="left",
                 fontsize=13, fontweight="semibold", y=0.995)
    fig.text(0.125, 0.955, "Weekly metrics, 2 years before vs after. Black bars = period means; p-values use "
             "autocorrelation-robust (HAC) errors", color=INK_2, fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return _save(fig, "10_etf_impact.png")


def break_scan(details: dict):
    fig, ax = plt.subplots(figsize=(11, 3.8))
    for i, (col, name) in enumerate((("realized_vol", "Realized volatility"), ("us_hours_share", "US-session share"),
                                     ("weekend_share", "Weekend share"))):
        s = details[col]["scan"]
        ax.plot(s.index, s, color=SERIES[i], lw=1.8, label=name)
        ax.scatter([s.idxmax()], [s.max()], s=40, color=SERIES[i], edgecolor=SURFACE, lw=2, zorder=3)
    ax.axvline(X.ETF_LAUNCH, color=AXIS, lw=1.5)
    ax.text(X.ETF_LAUNCH, ax.get_ylim()[1] * 0.97, " ETF launch", color=INK_2, fontsize=9, va="top")
    ax.legend(loc="upper left")
    ax.set_ylabel("Chow F-statistic")
    ax.grid(axis="x", visible=False)
    ax.set_title("Where does the data itself put the break?")
    _subtitle(ax, "Structural-break scan (Quandt–Andrews): F-statistic for a break at each week; dots mark the maximum")
    return _save(fig, "11_break_scan.png")


def regimes(reg: pd.DataFrame, summary: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 4.6))
    c = reg["close"]
    ax.plot(c.index, c, color=INK, lw=1.1, zorder=3)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(usd))
    runs = (reg["regime"] != reg["regime"].shift()).cumsum()
    for _, seg in reg.groupby(runs):
        ax.axvspan(seg.index[0], seg.index[-1] + pd.Timedelta(days=1), color=REGIME_COLORS[seg["regime"].iloc[0]],
                   alpha=REGIME_ALPHA, lw=0)
    handles = [Patch(color=col, alpha=REGIME_ALPHA,
                     label=f"{n}: {summary.loc[n, 'ann_vol']:.0%} vol, {summary.loc[n, 'share_of_days']:.0%} of days")
               for n, col in REGIME_COLORS.items()]
    ax.legend(handles=handles, loc="lower right", frameon=True, facecolor=SURFACE, edgecolor="none", framealpha=0.95)
    ax.grid(axis="x", visible=False)
    ax.set_title("Three volatility regimes, and stress has almost disappeared since 2024")
    _subtitle(ax, "3-state Markov-switching model on daily returns (2014–2026); background = most likely regime")
    return _save(fig, "12_volatility_regimes.png")


def garch_var(fc: pd.DataFrame, var99: pd.Series, breaches: int, expected: float, normal_breaches: int):
    fig, axes = plt.subplots(2, 1, figsize=(11, 7.4), sharex=True, gridspec_kw={"height_ratios": [1, 1.2]})
    ax = axes[0]
    rv = fc["realized"].rolling(7).mean()
    ax.plot(rv.index, rv, color=AXIS, lw=1.4, label="Realized (1-min data, 7d avg)")
    ax.plot(fc.index, fc["GARCH(1,1)-t"], color=SERIES[0], lw=1.4, label="GARCH(1,1)-t forecast")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_ylabel("daily vol")
    ax.legend(loc="upper right", ncol=2)
    ax.grid(axis="x", visible=False)
    ax.set_title("GARCH tracks realized volatility and gets the 1-in-100-day loss right")
    _subtitle(ax, "One-day-ahead forecasts, re-estimated yearly on an expanding window (out-of-sample 2020–2026)")
    ax = axes[1]
    r = fc["return"]
    hit = r < var99
    ax.scatter(r.index[~hit], r[~hit], s=4, color=MUTED, alpha=0.5, lw=0)
    ax.plot(var99.index, var99, color=SERIES[0], lw=1.3, label="99% VaR (GARCH-t)")
    ax.scatter(r.index[hit], r[hit], s=28, color=SERIES[7], edgecolor=SURFACE, lw=1.5, zorder=3,
               label=f"Breaches: {breaches} (expected {expected:.0f})")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_ylabel("daily return")
    lo = -30
    ax.set_ylim(lo, 22)
    worst = r.idxmin()
    if r.min() < lo:  # March 2020 crash sits off the scale; label it instead of squashing the panel
        ax.annotate(f"{worst:%b %Y}: {r.min():.0f}% ↓", (worst, lo), xytext=(6, 6), textcoords="offset points",
                    fontsize=8.5, color=INK_2)
    ax.legend(loc="upper left", ncol=2)
    ax.text(0.995, 0.04, f"A normal-distribution EWMA VaR breached {normal_breaches} times",
            transform=ax.transAxes, ha="right", fontsize=9, color=INK_2)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    return _save(fig, "13_garch_var_backtest.png")


def volume_week(pr: pd.DataFrame, scores: pd.DataFrame):
    wk = pr["week"].unique()[-6]
    g = pr[pr["week"] == wk]
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(g.index, g["actual"] / 1e6, color=AXIS, lw=2, label="Actual")
    ax.plot(g.index, g["4-week seasonal mean"] / 1e6, color=SERIES[0], lw=1.8, label="4-week seasonal mean")
    ax.plot(g.index, g["Gradient boosting"] / 1e6, color=SERIES[1], lw=1.4, label="Gradient boosting")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:.0f}M"))
    ax.legend(loc="upper right", ncol=3)
    ax.grid(axis="x", visible=False)
    s = scores
    ax.set_title("Forecasts catch the shape of the week, not the size of the spikes")
    _subtitle(ax, f"Hourly USD volume, one example week. Backtest over {pr['week'].nunique()} weeks: "
                  f"top-20 busiest hours found {s.loc['4-week seasonal mean', 'top20_hours_hit_rate']:.0%} "
                  f"of the time (chance = 12%)")
    return _save(fig, "14_volume_forecast.png")


def monte_carlo_fan(fan: pd.DataFrame, summary: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 4.4))
    x = fan.index / 365
    ax.fill_between(x, fan["p5"], fan["p95"], color=SERIES[0], alpha=0.12, lw=0, label="5th–95th percentile")
    ax.fill_between(x, fan["p25"], fan["p75"], color=SERIES[0], alpha=0.25, lw=0, label="25th–75th percentile")
    ax.plot(x, fan["p50"], color=SERIES[0], lw=2, label="Median")
    ax.axhline(0, color=AXIS, lw=1)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    ax.set_xlabel("Years on a weekly plan")
    floor = fan["p5"].min() - 0.75
    for yr in range(1, 5):
        p = summary.loc[(yr, "Weekly plan"), "prob_loss"]
        ax.text(yr, floor + 0.08, f"{p:.0%} chance of a loss", ha="center" if yr < 4 else "right",
                va="bottom", fontsize=8.5, color=INK_2)
    ax.set_ylim(floor, fan["p95"].max() * 1.05)
    ax.set_xticks(range(5))
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)
    ax.set_title("Simulated outcomes for a weekly plan: still a 1-in-4 chance of a loss after four years")
    _subtitle(ax, "10,000 stationary-block-bootstrap paths of post-2021 daily returns (mean block 30 days)")
    return _save(fig, "15_monte_carlo_plan.png")


def make_all() -> dict:
    import analysis as A
    daily, hourly = A.load_daily(), A.load_hourly()
    weekly, table, details = X.etf_impact(daily, hourly)
    reg, rsum, trans = X.markov_regimes(daily)
    fc, vscores, params = X.volatility_forecast_backtest(daily)
    nu = params[max(params)]["nu"]
    vb = X.var_backtest(fc, "GARCH(1,1)-t", 0.99, nu=nu)
    vb_norm = X.var_backtest(fc, "EWMA (RiskMetrics)", 0.99)
    pr, fscores = X.volume_forecast_backtest(hourly)
    mc, fan = X.monte_carlo_plans(daily)
    paths = [etf_its(weekly, table, details), break_scan(details), regimes(reg, rsum),
             garch_var(fc, vb["var_series"], vb["breaches"], vb["expected_breaches"], vb_norm["breaches"]),
             volume_week(pr, fscores), monte_carlo_fan(fan, mc)]
    plt.close("all")
    return {"paths": paths}


if __name__ == "__main__":
    for p in make_all()["paths"]:
        print(p)
