"""Export analysis results into the self-contained dashboard (dashboard/index.html).

dashboard/template.html holds the page; this script swaps the `/*__DATA__*/null`
placeholder for a JSON blob so the page works offline, on GitHub Pages, or opened
straight from disk.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A

DASH = A.ROOT / "dashboard"


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if math.isnan(x) else round(float(x), 5)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def records(df: pd.DataFrame) -> list[dict]:
    return clean(df.reset_index().astype(object).where(df.reset_index().notna(), None).to_dict("records"))


def build() -> dict:
    daily, hourly = A.load_daily(), A.load_hourly()
    close = daily["close"]
    dd = A.drawdown(close)
    weekly = close.resample("W").last()
    vol30 = A.rolling_volatility(daily, 30)

    cyc = []
    bounds = list(A.HALVINGS) + [close.index[-1]]
    for s, e in zip(bounds[:-1], bounds[1:]):
        seg = close.loc[s:e].iloc[::7]
        cyc.append({"year": s.year, "x": list((seg.index - s).days), "y": clean(list(seg / seg.iloc[0]))})

    hm = A.intraday_heatmaps(hourly)
    since = close.loc[A.COHORT_START:]
    events, crash = A.crash_event_study(daily)
    matrix = A.dca_cohort_matrix(close)

    return clean({
        "asOf": f"{close.index[-1]:%Y-%m-%d}",
        "kpi": {
            "last": close.iloc[-1],
            "ath": close.max(),
            "athDate": f"{close.idxmax():%Y-%m-%d}",
            "drawdown": dd.iloc[-1],
            "vol30": vol30.iloc[-1],
            "volEarly": A.risk_by_era(daily)["ann_volatility"].iloc[0],
            "minutes": json.loads((A.PROCESSED / "data_quality.json").read_text())["rows"],
        },
        "price": {"t": [f"{d:%Y-%m-%d}" for d in weekly.index], "close": list(weekly),
                  "dd": list(dd.reindex(weekly.index, method="ffill"))},
        "cycles": cyc,
        "cycleTable": records(A.halving_cycles(close).assign(
            halving=lambda d: d.halving.astype(str), cycle_peak_date=lambda d: d.cycle_peak_date.astype(str),
            post_peak_low_date=lambda d: d.post_peak_low_date.astype(str)).set_index("halving")),
        "years": records(A.yearly_summary(daily)),
        "eras": records(A.risk_by_era(daily)),
        "volume": {"days": list(hm["volume_index"].index), "z": hm["volume_index"].to_numpy().tolist()},
        "weekday": records(A.weekday_profile(hourly)),
        "holding": records(A.holding_period_odds(close)),
        "dca": records(A.dca_summary(close)),
        "cohorts": {"rows": list(matrix.index), "cols": list(matrix.columns), "z": matrix.to_numpy().tolist()},
        "weekdayDca": records(A.dca_weekday_effect(close)),
        "crash": records(crash),
        "crashEvents": len(events),
        "crash5": records(A.crash_event_study(daily, threshold=-0.05)[1]),
        "crash5Events": len(A.crash_event_study(daily, threshold=-0.05)[0]),
        "crashSince2024": int((daily.loc["2024":, "pct_return"] <= -0.10).sum()),
        # Daily closes since 2014 power the in-page recurring-buy calculator.
        "closes": {"start": f"{since.index[0]:%Y-%m-%d}", "v": list(since.round(2))},
    })


def build_advanced() -> dict:
    import advanced as X
    daily, hourly = A.load_daily(), A.load_hourly()
    weekly, etf, det = X.etf_impact(daily, hourly)
    us = det["us_hours_share"]["its"]["frame"]["actual"]
    regimes, rsum, _ = X.markov_regimes(daily)
    yearly = regimes["regime"].groupby(regimes.index.year).value_counts(normalize=True).unstack().fillna(0)
    fc, vscores, params = X.volatility_forecast_backtest(daily)
    nu = params[max(params)]["nu"]
    var_rows = [{k: v for k, v in X.var_backtest(fc, m, lvl, nu=nu if "GARCH" in m else None).items() if k != "var_series"}
                for lvl in (0.95, 0.99) for m in ["GARCH(1,1)-t", "EWMA (RiskMetrics)", "30-day historical"]]
    preds, fscores = X.volume_forecast_backtest(hourly)
    wk = preds[preds["week"] == preds["week"].unique()[-6]]
    sig = X.significance_tests(daily, hourly)
    mc, fan = X.monte_carlo_plans(daily)
    mc_full, _ = X.monte_carlo_plans(daily, sample_from="2014-01-01")
    return clean({
        "etf": records(etf.assign(strongest_break_week=etf["strongest_break_week"].astype(str))),
        "etfLaunch": f"{X.ETF_LAUNCH:%Y-%m-%d}",
        "usShare": {"t": [f"{d:%Y-%m-%d}" for d in us.index], "v": list(us)},
        "regimeSummary": records(rsum),
        "regimeYears": {"years": list(yearly.index), **{c: list(yearly[c]) for c in ["Calm", "Normal", "Stress"]}},
        "regimeNow": {"date": f"{regimes.index[-1]:%Y-%m-%d}", "regime": regimes["regime"].iloc[-1],
                      **{c: regimes[c].iloc[-1] for c in ["Calm", "Normal", "Stress"]}},
        "volScores": records(vscores),
        "varBacktest": var_rows,
        "garchNu": nu,
        "forecastScores": records(fscores),
        "forecastWeeks": preds["week"].nunique(),
        "forecastWeek": {"t": [f"{d:%a %H:%M}" for d in wk.index], "actual": list(wk["actual"]),
                         "seasonal": list(wk["4-week mean, bias-corrected"]), "gbm": list(wk["Gradient boosting"])},
        "sig": records(sig),
        "mc": records(mc.reset_index().set_index("year")),
        "mcFull": records(mc_full.xs("Weekly plan", level=1)),
        "fan": records(fan),
    })


def main() -> None:
    data = build()
    data["adv"] = build_advanced()
    html = (DASH / "template.html").read_text(encoding="utf-8")
    blob = json.dumps(data, separators=(",", ":")).replace("NaN", "null")
    body = html.replace("/*__DATA__*/null", blob)
    # template.html is a page fragment; wrap it so it works standalone (GitHub Pages / opened from disk).
    out = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
           '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
           'body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n'
           f'</head>\n<body>\n{body}\n</body>\n</html>\n')
    (DASH / "index.html").write_text(out, encoding="utf-8")
    if len(sys.argv) > 1:  # optional: also write the bare fragment (used for publishing)
        Path(sys.argv[1]).write_text(body, encoding="utf-8")
    print(f"dashboard/index.html  ({len(out)/1024:,.0f} KB)")


if __name__ == "__main__":
    main()
