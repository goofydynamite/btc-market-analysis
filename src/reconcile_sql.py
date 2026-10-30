"""Reconcile the SQL layer against the Python analysis: same question, two independent
implementations, results must agree. Writes reports/sql_reconciliation.md and exits non-zero
on any mismatch, so it can gate a CI run.
"""
from __future__ import annotations

import sqlite3
import sys
import warnings

import pandas as pd

import advanced as X
import analysis as A
from run_sql import DB, ROOT, run_queries, to_markdown

TOL = 0.051  # SQL rounds to 1 decimal place (in %), so allow half a unit plus float noise


def checks(sql: dict[str, pd.DataFrame]) -> list[dict]:
    daily, hourly = A.load_daily(), A.load_hourly()
    close = daily["close"]
    out = []

    def add(area, metric, sql_value, py_value, tol=TOL):
        out.append({"area": area, "metric": metric, "sql": sql_value, "python": round(float(py_value), 4),
                    "match": abs(float(sql_value) - float(py_value)) <= tol})

    hc_sql, hc_py = sql["07_halving_cycles.sql"], A.halving_cycles(close)
    for (_, s), (_, p) in zip(hc_sql.iterrows(), hc_py.iterrows()):
        yr = s.halving_date[:4]
        add("Halving cycles", f"{yr} days to peak", s.days_to_peak, p.days_halving_to_peak, 0)
        add("Halving cycles", f"{yr} post-peak drawdown %", s.post_peak_drawdown_pct, 100 * p.post_peak_drawdown)

    dd_sql, dd_py = sql["08_drawdown_episodes.sql"], A.drawdown_episodes(close)
    add("Drawdown episodes", "episodes deeper than -50%", len(dd_sql), len(dd_py), 0)
    for (_, s), (_, p) in zip(dd_sql.iterrows(), dd_py.iterrows()):
        add("Drawdown episodes", f"{s.peak_date} depth %", s.depth_pct, 100 * p.depth)
        add("Drawdown episodes", f"{s.peak_date} days underwater", s.days_underwater, p.days_underwater, 0)

    dca_sql, dca_py = sql["09_dca_cohorts.sql"].set_index("horizon_months"), A.dca_summary(close)
    for h in dca_sql.index:
        s, p = dca_sql.loc[h], dca_py.loc[h]
        add("DCA cohorts", f"{h}m cohorts", s.cohorts, p.cohorts, 0)
        add("DCA cohorts", f"{h}m DCA in profit %", s.dca_in_profit_pct, 100 * p.dca_prob_profit)
        add("DCA cohorts", f"{h}m DCA worst %", s.dca_worst_pct, 100 * p.dca_worst_roi)
        add("DCA cohorts", f"{h}m DCA beats lump %", s.dca_beats_lump_pct, 100 * p.share_dca_beats_lump)

    etf_sql = sql["10_etf_before_after.sql"].set_index("period")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, etf_py, _ = X.etf_impact(daily, hourly)
    for col, label in (("realized_vol_pct", "Realized volatility (ann.)"),
                       ("us_session_share_pct", "US-session share of weekday volume"),
                       ("weekend_share_pct", "Weekend share of weekly volume")):
        add("ETF before/after", f"{label}, before", etf_sql.loc["Before ETF", col], 100 * etf_py.loc[label, "pre_mean"])
        add("ETF before/after", f"{label}, after", etf_sql.loc["After ETF", col], 100 * etf_py.loc[label, "post_mean"])

    cr_sql = sql["11_crash_rebound.sql"].iloc[0]
    events, cr_py = A.crash_event_study(daily)
    add("Crash rebound", "events", cr_sql.events, len(events), 0)
    add("Crash rebound", "next day up %", cr_sql.next_day_up_pct, 100 * cr_py.loc[1, "after_crash_prob_up"])
    add("Crash rebound", "next 30d up %", cr_sql.next_30d_up_pct, 100 * cr_py.loc[30, "after_crash_prob_up"])
    add("Crash rebound", "baseline next day up %", cr_sql.baseline_next_day_up_pct, 100 * cr_py.loc[1, "baseline_prob_up"])
    return out


def main() -> int:
    with sqlite3.connect(DB) as con:
        sql = run_queries(con)
    res = pd.DataFrame(checks(sql))
    passed = int(res["match"].sum())
    res["match"] = res["match"].map({True: "pass", False: "FAIL"})
    text = ["# SQL ↔ Python reconciliation\n",
            "Every headline number is computed twice: once in SQL (`sql/queries/`) and once in pandas "
            "(`src/analysis.py`, `src/advanced.py`). They must agree to within SQL's rounding.\n",
            f"**{passed} / {len(res)} checks match.**\n", to_markdown(res), ""]
    (ROOT / "reports" / "sql_reconciliation.md").write_text("\n".join(text), encoding="utf-8")
    print(f"{passed}/{len(res)} checks match")
    if passed < len(res):
        print(res[res["match"] == "FAIL"].to_string())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
