"""Export tidy, Tableau-ready CSVs to tableau/data/ (see tableau/TABLEAU_GUIDE.md).

Each file is one grain (one row per day, per cohort x horizon, ...) with readable
column names, so it drops straight into Tableau Public with no prep.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

import advanced as X
import analysis as A

OUT = A.ROOT / "tableau" / "data"

ERAS = [("2012-2016 Early market", "2012", "2016"), ("2017-2020 Retail boom", "2017", "2020"),
        ("2021-2023 Institutional", "2021", "2023"), ("2024-2026 ETF era", "2024", "2026")]


def _title(col: str) -> str:
    """snake_case -> Title Case, which is what Tableau shows in the Data pane."""
    return col.replace("_", " ").title()


def daily_table(daily: pd.DataFrame, regimes: pd.DataFrame) -> pd.DataFrame:
    c = daily["close"]
    d = pd.DataFrame({
        "Date": daily.index.date,
        "Open": daily["open"], "High": daily["high"], "Low": daily["low"], "Close": c,
        "Volume USD": daily["volume_usd"], "Volume BTC": daily["volume_btc"],
        "Daily Return": daily["pct_return"],
        "All-Time High": c.cummax(),
        "Drawdown": A.drawdown(c),
        "Volatility 30D": A.rolling_volatility(daily, 30),
        "Volatility 90D": A.rolling_volatility(daily, 90),
        "Year": daily["year"], "Weekday": daily["weekday"],
    }, index=daily.index)
    d["Era"] = None
    for name, a, b in ERAS:
        d.loc[a:b, "Era"] = name
    # halving cycle each day belongs to, and days since that halving
    cyc = pd.Series(pd.NaT, index=d.index, dtype="datetime64[ns, UTC]")
    for h in A.HALVINGS:
        cyc[d.index >= h] = h
    d["Halving Cycle"] = cyc.dt.year.astype("Int64").astype(str).replace("<NA>", "Pre-2012 halving")
    d["Days Since Halving"] = (d.index - cyc).dt.days.astype("Int64")
    d["Price vs Halving Day"] = c / c.reindex(cyc.dropna().unique()).reindex(cyc).to_numpy()
    d["Market Regime"] = regimes["regime"].reindex(d.index)
    d["P(Stress)"] = regimes["Stress"].reindex(d.index)
    d["Is ETF Era"] = d.index >= X.ETF_LAUNCH
    return d.reset_index(drop=True)


def heatmap_table(hourly: pd.DataFrame) -> pd.DataFrame:
    hm = A.intraday_heatmaps(hourly)
    vol = hm["volume_index"].stack().rename("Volume Index")
    ret = hm["abs_return_bps"].stack().rename("Avg Abs Move (bps)")
    t = pd.concat([vol, ret], axis=1).reset_index().rename(columns={"weekday": "Weekday", "hour_utc": "Hour UTC"})
    t["Weekday Order"] = t["Weekday"].map({d: i for i, d in enumerate(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])})
    t["Day Type"] = np.where(t["Weekday Order"] >= 5, "Weekend", "Weekday")
    return t


def cohort_table(close: pd.Series) -> pd.DataFrame:
    rows = []
    for h in range(6, 61, 6):
        t = A.dca_vs_lump_sum(close, h).reset_index()
        t["Horizon Months"] = h
        rows.append(t)
    t = pd.concat(rows)
    t["Cohort Start"] = pd.to_datetime(t["cohort"]).dt.date
    t["Cohort Quarter"] = pd.PeriodIndex(t["cohort"], freq="M").asfreq("Q").astype(str)
    return t.rename(columns={"invested": "Invested", "dca_value": "DCA Value", "dca_roi": "DCA ROI",
                             "lump_sum_roi": "Lump Sum ROI", "avg_cost": "Avg Cost",
                             "dca_beats_lump_sum": "DCA Beats Lump Sum"}).drop(columns="cohort")


def etf_table(daily, hourly) -> pd.DataFrame:
    weekly, tab, det = X.etf_impact(daily, hourly)
    labels = {"realized_vol": "Realized volatility", "us_hours_share": "US-session share of weekday volume",
              "weekend_share": "Weekend share of weekly volume"}
    rows = []
    for col, label in labels.items():
        f = det[col]["its"]["frame"]
        r = tab.iloc[[i for i, m in enumerate(tab.index) if m.startswith(label.split()[0])][0]]
        part = pd.DataFrame({"Week": f.index.date, "Metric": label, "Value": f["actual"].to_numpy()})
        part["Period"] = np.where(f.index >= X.ETF_LAUNCH, "After ETF", "Before ETF")
        part["Period Mean"] = np.where(part["Period"] == "After ETF", r.post_mean, r.pre_mean)
        part["HAC p-value"] = r.mean_diff_p
        rows.append(part)
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    daily, hourly = A.load_daily(), A.load_hourly()
    close = daily["close"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        regimes, _, _ = X.markov_regimes(daily)
        mc, fan = X.monte_carlo_plans(daily)

    tables = {
        "btc_daily.csv": daily_table(daily, regimes),
        "trading_heatmap.csv": heatmap_table(hourly),
        "dca_cohorts.csv": cohort_table(close),
        "holding_period_odds.csv": A.holding_period_odds(close).reset_index().rename(columns=_title),
        "crash_events.csv": A.crash_event_study(daily)[0].reset_index().rename(columns=_title)
                              .rename(columns={"Datetime": "Date"}),
        "etf_weekly.csv": etf_table(daily, hourly),
        "monte_carlo_fan.csv": fan.reset_index().assign(Years=lambda f: f["day"] / 365).rename(
            columns={"day": "Day", "p5": "P5", "p25": "P25", "p50": "Median", "p75": "P75", "p95": "P95"}),
        "monte_carlo_summary.csv": mc.reset_index().rename(columns=_title),
    }
    for name, df in tables.items():
        df.to_csv(OUT / name, index=False)
        print(f"{name:28s} {len(df):>6,} rows  {len(df.columns):>2} cols")


if __name__ == "__main__":
    main()
