"""Reusable analysis functions for the BTC market case study.

Every function takes the daily / hourly marts produced by pipeline.py and
returns a tidy DataFrame, so the notebook, the dashboard export and the
tests all compute numbers the same way.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

HALVINGS = pd.to_datetime(["2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20"], utc=True)

# Before 2017 a third or more of minutes had no trades (see data_quality.json),
# so intraday liquidity questions use the mature-market window only.
INTRADAY_START = "2019-01-01"
# Cohort / holding-period analysis starts once daily prices are continuous and liquid.
COHORT_START = "2014-01-01"


def load_daily() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "btc_daily.parquet").set_index("datetime")


def load_hourly() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "btc_hourly.parquet")


# ---------------------------------------------------------------- market overview

def yearly_summary(daily: pd.DataFrame) -> pd.DataFrame:
    g = daily.groupby("year")
    out = pd.DataFrame({
        "open": g["open"].first(),
        "close": g["close"].last(),
        "high": g["high"].max(),
        "low": g["low"].min(),
        "return": g["close"].last() / g["open"].first() - 1,
        "ann_volatility": g["log_return"].std() * np.sqrt(365),
        "max_drawdown": g["close"].apply(lambda s: (s / s.cummax() - 1).min()),
        "usd_volume_bn": g["volume_usd"].sum() / 1e9,
        "days_up_pct": g["pct_return"].apply(lambda s: (s > 0).mean()),
    })
    out["partial_year"] = g.size() < 365
    return out


def drawdown(close: pd.Series) -> pd.Series:
    return close / close.cummax() - 1


def drawdown_episodes(close: pd.Series, min_depth: float = -0.5) -> pd.DataFrame:
    """Peak -> trough -> recovery episodes deeper than `min_depth`."""
    dd = drawdown(close)
    peak_id = (dd == 0).cumsum()
    rows = []
    for _, seg in dd.groupby(peak_id):
        depth = seg.min()
        if depth > min_depth:
            continue
        peak_date = seg.index[0]
        trough_date = seg.idxmin()
        after = close.loc[trough_date:]
        recovered = after[after >= close.loc[peak_date]]
        recovery_date = recovered.index[0] if len(recovered) else pd.NaT
        rows.append({
            "peak_date": peak_date.date(),
            "peak_price": close.loc[peak_date],
            "trough_date": trough_date.date(),
            "trough_price": close.loc[trough_date],
            "depth": depth,
            "days_peak_to_trough": (trough_date - peak_date).days,
            "recovery_date": recovery_date.date() if pd.notna(recovery_date) else None,
            "days_underwater": ((recovery_date if pd.notna(recovery_date) else close.index[-1]) - peak_date).days,
            "recovered": pd.notna(recovery_date),
        })
    return pd.DataFrame(rows)


def halving_cycles(close: pd.Series, peak_window_days: int = 730) -> pd.DataFrame:
    """Run-up from each halving to its cycle peak, then the bear market that follows.

    Cycle peak = highest close within `peak_window_days` of the halving (a plain
    halving-to-halving max would pick the 2024 pre-halving rally for the 2020 cycle).
    The post-peak low is measured up to the next halving, or the end of the data.
    """
    rows = []
    bounds = list(HALVINGS) + [close.index[-1] + pd.Timedelta(days=1)]
    for start, end in zip(bounds[:-1], bounds[1:]):
        seg = close.loc[start:end - pd.Timedelta(days=1)]
        window = seg.loc[:start + pd.Timedelta(days=peak_window_days)]
        peak_date = window.idxmax()
        post = seg.loc[peak_date:]
        rows.append({
            "halving": start.date(),
            "price_at_halving": seg.iloc[0],
            "cycle_peak_date": peak_date.date(),
            "cycle_peak": window.max(),
            "days_halving_to_peak": (peak_date - start).days,
            "halving_to_peak_multiple": window.max() / seg.iloc[0],
            "post_peak_low_date": post.idxmin().date(),
            "post_peak_low": post.min(),
            "post_peak_drawdown": post.min() / window.max() - 1,
            "cycle_complete": end <= close.index[-1],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- risk

def risk_by_era(daily: pd.DataFrame) -> pd.DataFrame:
    eras = {
        "2012-2016 early market": ("2012", "2016"),
        "2017-2020 retail boom": ("2017", "2020"),
        "2021-2023 institutional": ("2021", "2023"),
        "2024-2026 ETF era": ("2024", "2026"),
    }
    rows = []
    for name, (a, b) in eras.items():
        r = daily.loc[a:b, "pct_return"].dropna()
        var95, var99 = r.quantile(0.05), r.quantile(0.01)
        rows.append({
            "era": name,
            "days": len(r),
            "ann_volatility": r.std() * np.sqrt(365),
            "VaR_95": var95,
            "CVaR_95": r[r <= var95].mean(),
            "VaR_99": var99,
            "days_abs_move_gt_5pct": (r.abs() > 0.05).mean(),
            "days_abs_move_gt_10pct": (r.abs() > 0.10).mean(),
            "worst_day": r.min(),
            "best_day": r.max(),
        })
    return pd.DataFrame(rows).set_index("era")


def rolling_volatility(daily: pd.DataFrame, window: int = 30) -> pd.Series:
    return daily["log_return"].rolling(window).std() * np.sqrt(365)


# ---------------------------------------------------------------- when does the market trade

def intraday_heatmaps(hourly: pd.DataFrame, start: str = INTRADAY_START) -> dict[str, pd.DataFrame]:
    h = hourly[hourly["datetime"] >= start].copy()
    h["abs_return"] = h["log_return"].abs()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def pivot(col: str, agg: str) -> pd.DataFrame:
        p = h.pivot_table(index="weekday", columns="hour_utc", values=col, aggfunc=agg)
        return p.reindex(order)

    vol = pivot("volume_usd", "median")
    return {
        # Indexed so 1.0 = the average hour of the week; robust to the multi-year price level shift.
        "volume_index": vol / vol.to_numpy().mean(),
        "abs_return_bps": pivot("abs_return", "mean") * 1e4,
    }


def weekday_profile(hourly: pd.DataFrame, start: str = INTRADAY_START) -> pd.DataFrame:
    h = hourly[hourly["datetime"] >= start]
    day = h.groupby(h["datetime"].dt.floor("D")).agg(volume_usd=("volume_usd", "sum"),
                                                      weekday=("weekday", "first"))
    day["abs_return"] = (h.groupby(h["datetime"].dt.floor("D"))["log_return"].sum()).abs()
    out = day.groupby("weekday").agg(median_volume_usd=("volume_usd", "median"),
                                     mean_abs_return=("abs_return", "mean"))
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    out = out.reindex(order)
    out["volume_vs_weekday_avg"] = out["median_volume_usd"] / out["median_volume_usd"].iloc[:5].mean()
    return out


# ---------------------------------------------------------------- holding period & DCA

def holding_period_odds(close: pd.Series, start: str = COHORT_START,
                        horizons: dict[str, int] | None = None) -> pd.DataFrame:
    """For every possible buy day, the return after holding N days."""
    horizons = horizons or {"1 day": 1, "1 week": 7, "1 month": 30, "3 months": 91,
                            "6 months": 182, "1 year": 365, "2 years": 730,
                            "3 years": 1095, "4 years": 1461}
    c = close.loc[start:]
    rows = []
    for label, n in horizons.items():
        fwd = (c.shift(-n) / c - 1).dropna()
        rows.append({
            "horizon": label,
            "days": n,
            "buy_days_tested": len(fwd),
            "prob_profit": (fwd > 0).mean(),
            "prob_loss_gt_50pct": (fwd < -0.5).mean(),
            "p10_return": fwd.quantile(0.10),
            "median_return": fwd.median(),
            "p90_return": fwd.quantile(0.90),
        })
    return pd.DataFrame(rows).set_index("horizon")


def dca_vs_lump_sum(close: pd.Series, horizon_months: int, amount_per_buy: float = 100.0,
                    every_days: int = 7, start: str = COHORT_START) -> pd.DataFrame:
    """One row per monthly start cohort: weekly recurring buy vs investing the same total on day 1."""
    c = close.loc[start:]
    last = c.index[-1]
    rows = []
    for cohort_start in pd.date_range(c.index[0], last, freq="MS"):
        end = cohort_start + pd.DateOffset(months=horizon_months)
        if end > last:
            break
        buy_dates = pd.date_range(cohort_start, end - pd.Timedelta(days=1), freq=f"{every_days}D")
        prices = c.reindex(buy_dates).dropna()
        coins = (amount_per_buy / prices).sum()
        invested = amount_per_buy * len(prices)
        end_price = c.loc[:end].iloc[-1]
        dca_value = coins * end_price
        lump_value = invested * end_price / prices.iloc[0]
        rows.append({
            "cohort": cohort_start.strftime("%Y-%m"),
            "invested": invested,
            "dca_value": dca_value,
            "dca_roi": dca_value / invested - 1,
            "lump_sum_roi": lump_value / invested - 1,
            "avg_cost": invested / coins,
        })
    out = pd.DataFrame(rows).set_index("cohort")
    out["dca_beats_lump_sum"] = out["dca_roi"] > out["lump_sum_roi"]
    return out


def dca_summary(close: pd.Series, horizons=(12, 24, 36, 48)) -> pd.DataFrame:
    rows = []
    for h in horizons:
        t = dca_vs_lump_sum(close, h)
        rows.append({
            "horizon_months": h,
            "cohorts": len(t),
            "dca_prob_profit": (t["dca_roi"] > 0).mean(),
            "lump_prob_profit": (t["lump_sum_roi"] > 0).mean(),
            "dca_median_roi": t["dca_roi"].median(),
            "lump_median_roi": t["lump_sum_roi"].median(),
            "dca_worst_roi": t["dca_roi"].min(),
            "lump_worst_roi": t["lump_sum_roi"].min(),
            "dca_roi_iqr": t["dca_roi"].quantile(0.75) - t["dca_roi"].quantile(0.25),
            "lump_roi_iqr": t["lump_sum_roi"].quantile(0.75) - t["lump_sum_roi"].quantile(0.25),
            "share_dca_beats_lump": t["dca_beats_lump_sum"].mean(),
        })
    return pd.DataFrame(rows).set_index("horizon_months")


def dca_cohort_matrix(close: pd.Series, horizons=range(6, 61, 6)) -> pd.DataFrame:
    """Quarterly start cohorts x holding months -> weekly-DCA ROI (the cohort heatmap)."""
    cols = {}
    for h in horizons:
        t = dca_vs_lump_sum(close, h)["dca_roi"]
        t.index = pd.PeriodIndex(t.index, freq="M").asfreq("Q").astype(str)
        cols[h] = t.groupby(level=0).first()  # first month of each quarter
    return pd.DataFrame(cols)


def dca_weekday_effect(close: pd.Series, start: str = "2018-01-01") -> pd.DataFrame:
    """Does the day of the week a recurring buy runs on change the average cost?"""
    c = close.loc[start:]
    rows = []
    for wd, name in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]):
        p = c[c.index.weekday == wd]
        rows.append({"weekday": name, "buys": len(p), "avg_cost": len(p) / (1 / p).sum()})
    out = pd.DataFrame(rows).set_index("weekday")
    out["vs_best_day"] = out["avg_cost"] / out["avg_cost"].min() - 1
    return out


# ---------------------------------------------------------------- crash behaviour

def crash_event_study(daily: pd.DataFrame, threshold: float = -0.10, cooldown_days: int = 7,
                      start: str = COHORT_START, horizons=(1, 7, 30, 90, 365)) -> tuple[pd.DataFrame, pd.DataFrame]:
    """What happens after a large one-day drop, vs. the unconditional baseline?

    Events closer than `cooldown_days` to a previous event are merged so one
    crash doesn't get counted several times.
    """
    d = daily.loc[start:]
    c = d["close"]
    candidates = d.index[d["pct_return"] <= threshold]
    events, last = [], None
    for t in candidates:
        if last is None or (t - last).days > cooldown_days:
            events.append(t)
        last = t
    ev = pd.DataFrame({"drop": d.loc[events, "pct_return"], "close": c.loc[events]})
    summary = []
    for n in horizons:
        fwd_all = (c.shift(-n) / c - 1)
        fwd = fwd_all.loc[events].dropna()
        ev[f"fwd_{n}d"] = fwd_all.loc[events]
        summary.append({
            "horizon_days": n,
            "events": len(fwd),
            "after_crash_median": fwd.median(),
            "after_crash_prob_up": (fwd > 0).mean(),
            "baseline_median": fwd_all.dropna().median(),
            "baseline_prob_up": (fwd_all.dropna() > 0).mean(),
        })
    return ev, pd.DataFrame(summary).set_index("horizon_days")
