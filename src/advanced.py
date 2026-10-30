"""Advanced layer: causal inference, regime models, forecasting and statistical rigor.

Four modules, each answering a decision-grade question:

1. ETF causal impact      - did the Jan-2024 US spot-ETF launch change how BTC trades?
2. Volatility regimes     - Markov-switching regimes + GARCH(1,1) forecasts and a VaR backtest
3. Volume forecasting     - next-week hourly volume for staffing / capacity, rolling-origin backtest
4. Rigor + Monte Carlo    - permutation tests, bootstrap CIs, BH correction, block-bootstrap simulation
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import optimize, special, stats
from sklearn.ensemble import HistGradientBoostingRegressor
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

import analysis as A

ETF_LAUNCH = pd.Timestamp("2024-01-11", tz="UTC")  # first trading day of US spot bitcoin ETFs
US_HOURS = range(14, 21)                            # 14:00-20:59 UTC ~ US cash-equity session
RNG_SEED = 7


# =============================================================== 1. ETF causal impact

def weekly_market_structure(daily: pd.DataFrame, hourly: pd.DataFrame, start: str = "2019-01-01") -> pd.DataFrame:
    """Weekly metrics that an ETF could plausibly change."""
    h = hourly[hourly["datetime"] >= start].copy()
    h["week"] = h["datetime"].dt.tz_localize(None).dt.to_period("W-SUN")
    h["weekend"] = h["weekday_num"] >= 5
    h["us_hours"] = h["hour_utc"].isin(US_HOURS) & ~h["weekend"]
    g = h.groupby("week")
    vol = g["volume_usd"].sum()
    d = daily.loc[start:].copy()
    d["week"] = d.index.tz_localize(None).to_period("W-SUN")
    out = pd.DataFrame({
        "realized_vol": d.groupby("week")["realized_vol"].mean() * np.sqrt(365),
        "weekend_share": h[h["weekend"]].groupby("week")["volume_usd"].sum() / vol,
        "us_hours_share": h[h["us_hours"]].groupby("week")["volume_usd"].sum()
                          / h[~h["weekend"]].groupby("week")["volume_usd"].sum(),
        "hours": g.size(),
    })
    out = out[out["hours"] == 168].drop(columns="hours")  # complete weeks only
    out.index = out.index.to_timestamp(how="end").normalize().tz_localize("UTC")
    return out


def interrupted_time_series(y: pd.Series, event: pd.Timestamp = ETF_LAUNCH, pre_years: float = 2.0) -> dict:
    """Segmented regression: y = b0 + b1*t + b2*post + b3*t_since + e, HAC (Newey-West) errors.

    The counterfactual is the pre-period trend extended past the event.
    """
    y = y.loc[event - pd.DateOffset(days=int(365 * pre_years)):].dropna()
    t = np.arange(len(y), dtype=float)
    post = (y.index >= event).astype(float)
    t_since = np.where(post == 1, t - t[post.argmax()], 0.0)
    X = sm.add_constant(np.column_stack([t, post, t_since]))
    fit = sm.OLS(y.to_numpy(), X).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
    counterfactual = fit.params[0] + fit.params[1] * t
    pre_mean = y[post == 0].mean()
    post_mean = y[post == 1].mean()
    return {
        "fit": fit,
        "frame": pd.DataFrame({"actual": y, "fitted": fit.fittedvalues, "counterfactual": counterfactual}, index=y.index),
        "level_shift": fit.params[2], "level_shift_p": fit.pvalues[2],
        "level_shift_ci": tuple(fit.conf_int()[2]),
        "slope_change": fit.params[3], "slope_change_p": fit.pvalues[3],
        "pre_mean": pre_mean, "post_mean": post_mean,
        # average gap between what happened and the extrapolated pre-trend
        "avg_effect_vs_counterfactual": (y[post == 1] - counterfactual[post == 1]).mean(),
    }


def sup_f_break_scan(y: pd.Series, trim: float = 0.15) -> pd.Series:
    """Quandt-Andrews style scan: Chow F-statistic for a mean+trend break at every candidate week.

    The date with the largest F is where the data itself 'wants' the break to be.
    """
    y = y.dropna()
    n = len(y)
    t = np.arange(n, dtype=float)
    X0 = sm.add_constant(t)
    rss0 = sm.OLS(y.to_numpy(), X0).fit().ssr
    k = X0.shape[1]
    out = {}
    for i in range(int(n * trim), int(n * (1 - trim))):
        rss1 = sm.OLS(y.iloc[:i].to_numpy(), X0[:i]).fit().ssr + sm.OLS(y.iloc[i:].to_numpy(), X0[i:]).fit().ssr
        out[y.index[i]] = ((rss0 - rss1) / k) / (rss1 / (n - 2 * k))
    return pd.Series(out, name="chow_F")


def placebo_its(y: pd.Series, n_placebos: int = 40, pre_years: float = 2.0, post_weeks: int = 100) -> pd.DataFrame:
    """In-time placebo test: re-run the ITS at fake event dates that are not the ETF launch.

    If the real level shift is unusual compared with these, it's less likely to be noise.
    """
    y = y.dropna()
    first = y.index[0] + pd.DateOffset(days=int(365 * pre_years))
    last = ETF_LAUNCH - pd.Timedelta(weeks=post_weeks // 2)  # placebo windows overlap the event only partly
    dates = pd.date_range(first, last, periods=n_placebos)
    rows = []
    for d in dates:
        seg = y.loc[:d + pd.Timedelta(weeks=post_weeks)]
        r = interrupted_time_series(seg, event=d, pre_years=pre_years)
        rows.append({"placebo_date": d, "level_shift": r["level_shift"]})
    return pd.DataFrame(rows)


def etf_impact(daily: pd.DataFrame, hourly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    w = weekly_market_structure(daily, hourly)
    rows, details = [], {}
    for col, label in (("realized_vol", "Realized volatility (ann.)"),
                       ("weekend_share", "Weekend share of weekly volume"),
                       ("us_hours_share", "US-session share of weekday volume")):
        its = interrupted_time_series(w[col])
        plc = placebo_its(w[col])
        scan = sup_f_break_scan(w[col])
        placebo_p = (np.abs(plc["level_shift"]) >= abs(its["level_shift"])).mean()
        # Simplest estimator: post minus pre mean, with autocorrelation-robust errors.
        seg = its["frame"]["actual"]
        post = (seg.index >= ETF_LAUNCH).astype(float)
        dm = sm.OLS(seg.to_numpy(), sm.add_constant(post)).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
        rows.append({
            "metric": label,
            "pre_mean": its["pre_mean"], "post_mean": its["post_mean"],
            "mean_diff_p": dm.pvalues[1],
            "level_shift": its["level_shift"], "ci_low": its["level_shift_ci"][0], "ci_high": its["level_shift_ci"][1],
            "hac_p_value": its["level_shift_p"], "placebo_p_value": placebo_p,
            "effect_vs_counterfactual": its["avg_effect_vs_counterfactual"],
            "strongest_break_week": scan.idxmax().date(),
        })
        details[col] = {"its": its, "placebo": plc, "scan": scan}
    return w, pd.DataFrame(rows).set_index("metric"), details


# =============================================================== 2. Volatility regimes & GARCH

def markov_regimes(daily: pd.DataFrame, start: str = A.COHORT_START, k: int = 3) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """3-state Markov-switching model on daily % returns with regime-specific mean and variance."""
    r = daily.loc[start:, "log_return"].dropna() * 100
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mod = MarkovRegression(r.to_numpy(), k_regimes=k, trend="c", switching_variance=True)
        np.random.seed(RNG_SEED)  # search_reps draws random starting values
        res = mod.fit(search_reps=20, disp=False)
    params = dict(zip(mod.param_names, res.params))
    sig = np.array([params[f"sigma2[{i}]"] for i in range(k)])
    order = np.argsort(sig)                                  # 0 = calm, 1 = normal, 2 = stress
    names = ["Calm", "Normal", "Stress"]
    probs = pd.DataFrame(res.smoothed_marginal_probabilities[:, order], index=r.index, columns=names)
    regime = probs.idxmax(axis=1)
    P = res.regime_transition[:, :, 0] if res.regime_transition.ndim == 3 else res.regime_transition
    P = P[np.ix_(order, order)].T                            # rows = from, cols = to
    summary = []
    for i, n in enumerate(names):
        mask = regime == n
        rr = r[mask]
        runs = (mask != mask.shift()).cumsum()[mask]
        summary.append({
            "regime": n,
            "share_of_days": mask.mean(),
            "daily_vol_pct": np.sqrt(sig[order[i]]),
            "ann_vol": np.sqrt(sig[order[i]] * 365) / 100,
            "mean_daily_return_pct": rr.mean(),
            "expected_duration_days": 1 / (1 - P[i, i]),
            "observed_median_run_days": runs.value_counts().median(),
            "share_of_days_2024plus": (regime.loc["2024":] == n).mean(),
        })
    trans = pd.DataFrame(P, index=[f"from {n}" for n in names], columns=[f"to {n}" for n in names])
    out = probs.assign(regime=regime, close=daily["close"].reindex(r.index))
    return out, pd.DataFrame(summary).set_index("regime"), trans


def _garch_nll(params: np.ndarray, r: np.ndarray) -> float:
    omega, alpha, beta, nu = params
    if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 0.99999 or nu <= 2.05:
        return 1e10
    s2 = _garch_filter(r, omega, alpha, beta)
    # Standardised Student-t log-likelihood (variance = s2)
    ll = (special.gammaln((nu + 1) / 2) - special.gammaln(nu / 2) - 0.5 * np.log(np.pi * (nu - 2) * s2)
          - (nu + 1) / 2 * np.log1p(r ** 2 / ((nu - 2) * s2)))
    return -np.sum(ll)


def _garch_filter(r: np.ndarray, omega: float, alpha: float, beta: float) -> np.ndarray:
    s2 = np.empty_like(r)
    s2[0] = r.var()
    for t in range(1, len(r)):
        s2[t] = omega + alpha * r[t - 1] ** 2 + beta * s2[t - 1]
    return s2


def fit_garch_t(r: np.ndarray) -> dict:
    """GARCH(1,1) with Student-t innovations, by maximum likelihood (no `arch` dependency)."""
    v = r.var()
    x0 = np.array([v * 0.05, 0.08, 0.88, 5.0])
    res = optimize.minimize(_garch_nll, x0, args=(r,), method="Nelder-Mead",
                            options={"maxiter": 4000, "xatol": 1e-6, "fatol": 1e-6})
    omega, alpha, beta, nu = res.x
    pers = alpha + beta
    return {"omega": omega, "alpha": alpha, "beta": beta, "nu": nu, "persistence": pers,
            # persistence ~1 (integrated GARCH): shocks never fully decay inside the sample
            "half_life_days": np.log(0.5) / np.log(pers) if pers < 0.9999 else np.inf,
            "converged": res.success}


def volatility_forecast_backtest(daily: pd.DataFrame, test_start: str = "2020-01-01",
                                 train_start: str = "2015-01-01") -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """1-day-ahead volatility forecasts vs realized vol measured from 1-minute data.

    GARCH is re-estimated at the start of every calendar year on all data up to then
    (expanding window); benchmarks are EWMA (RiskMetrics, lambda=0.94) and 30-day historical vol.
    """
    r = daily.loc[train_start:, "log_return"].dropna() * 100
    rv = (daily["realized_vol"] * 100).reindex(r.index)       # realized daily vol in %, the target
    fc = pd.DataFrame(index=r.loc[test_start:].index)
    garch_sig, params_by_year = [], {}
    for year in sorted(set(fc.index.year)):
        train = r.loc[:f"{year - 1}-12-31"].to_numpy()
        p = fit_garch_t(train)
        params_by_year[year] = p
        idx = r.loc[:f"{year}-12-31"]
        s2 = _garch_filter(idx.to_numpy(), p["omega"], p["alpha"], p["beta"])
        # s2[t] is the forecast for day t using information up to t-1
        garch_sig.append(pd.Series(np.sqrt(s2), index=idx.index).loc[str(year)])
    fc["GARCH(1,1)-t"] = pd.concat(garch_sig)
    lam = 0.94
    ewma = (r ** 2).ewm(alpha=1 - lam, adjust=False).mean().shift(1)
    fc["EWMA (RiskMetrics)"] = np.sqrt(ewma).reindex(fc.index)
    fc["30-day historical"] = r.rolling(30).std().shift(1).reindex(fc.index)
    fc["realized"] = rv.reindex(fc.index)
    fc["return"] = r.reindex(fc.index)
    fc = fc.dropna()

    rows = []
    for m in ["GARCH(1,1)-t", "EWMA (RiskMetrics)", "30-day historical"]:
        f2, y2 = fc[m] ** 2, fc["realized"] ** 2
        qlike = (y2 / f2 - np.log(y2 / f2) - 1).mean()       # robust loss for variance forecasts
        rows.append({"model": m, "RMSE_vol_pct": np.sqrt(((fc[m] - fc["realized"]) ** 2).mean()),
                     "QLIKE": qlike, "corr_with_realized": fc[m].corr(fc["realized"])})
    scores = pd.DataFrame(rows).set_index("model")
    return fc, scores, params_by_year


def var_backtest(fc: pd.DataFrame, model: str = "GARCH(1,1)-t", level: float = 0.99, nu: float | None = None) -> dict:
    """Kupiec proportion-of-failures test for a 1-day VaR built from the vol forecast."""
    if nu:
        q = stats.t.ppf(1 - level, nu) * np.sqrt((nu - 2) / nu)
    else:
        q = stats.norm.ppf(1 - level)
    var = q * fc[model]
    hits = (fc["return"] < var)
    n, x, p = len(hits), int(hits.sum()), 1 - level
    phat = x / n
    lr = -2 * (np.log((1 - p) ** (n - x) * p ** x) - np.log((1 - phat) ** (n - x) * phat ** x)) if 0 < x < n else np.nan
    return {"model": model, "level": level, "days": n, "expected_breaches": n * p, "breaches": x,
            "breach_rate": phat, "kupiec_LR": lr, "kupiec_p": 1 - stats.chi2.cdf(lr, 1), "var_series": var}


# =============================================================== 3. Volume forecasting

def hourly_features(hourly: pd.DataFrame, start: str = A.INTRADAY_START) -> pd.DataFrame:
    """Every feature uses data >= 168 hours old, so one model can forecast any hour of the next week."""
    h = hourly[hourly["datetime"] >= start].set_index("datetime")[["volume_usd", "hour_utc", "weekday_num"]].copy()
    h["y"] = np.log1p(h["volume_usd"])
    for k in (1, 2, 3, 4):
        h[f"lag_{168 * k}"] = h["y"].shift(168 * k)
    h["level_7d"] = h["y"].shift(168).rolling(168).mean()       # weekly level as of one week earlier
    h["level_28d"] = h["y"].shift(168).rolling(672).mean()
    h["hour_of_week"] = h["weekday_num"] * 24 + h["hour_utc"]
    return h.dropna()


def volume_forecast_backtest(hourly: pd.DataFrame, test_start: str = "2025-01-06", refit_every_weeks: int = 4) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rolling-origin backtest: each Monday 00:00 UTC, forecast the next 168 hours."""
    f = hourly_features(hourly)
    feats = ["hour_utc", "weekday_num", "hour_of_week", "lag_168", "lag_336", "lag_504", "lag_672", "level_7d", "level_28d"]
    origins = pd.date_range(pd.Timestamp(test_start, tz="UTC"), f.index[-1] - pd.Timedelta(hours=168), freq="7D")
    preds, model = [], None
    for i, o in enumerate(origins):
        if model is None or i % refit_every_weeks == 0:
            tr = f.loc[:o - pd.Timedelta(hours=1)]
            model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                                  random_state=RNG_SEED).fit(tr[feats], tr["y"])
            # Duan smearing: exp(mean log) underestimates the mean, so rescale by the training residuals
            recent = tr.iloc[-24 * 180:]
            smear = np.mean(np.exp(recent["y"] - model.predict(recent[feats])))
        te = f.loc[o:o + pd.Timedelta(hours=167)]
        p = pd.DataFrame({"actual": te["volume_usd"], "week": o}, index=te.index)
        p["Gradient boosting"] = np.expm1(model.predict(te[feats])) * smear
        p["Seasonal naive (last week)"] = np.expm1(te["lag_168"])
        p["4-week seasonal mean"] = np.expm1(te[["lag_168", "lag_336", "lag_504", "lag_672"]].mean(axis=1))
        # Same model, rescaled by how much it under-forecast over the previous 12 weeks (known at the origin).
        past = f.loc[o - pd.Timedelta(weeks=12):o - pd.Timedelta(hours=1)]
        past_fc = np.expm1(past[["lag_168", "lag_336", "lag_504", "lag_672"]].mean(axis=1))
        p["4-week mean, bias-corrected"] = p["4-week seasonal mean"] * past["volume_usd"].sum() / past_fc.sum()
        preds.append(p)
    pr = pd.concat(preds)
    rows = []
    for m in ["Seasonal naive (last week)", "4-week seasonal mean", "4-week mean, bias-corrected", "Gradient boosting"]:
        err = (pr[m] - pr["actual"]).abs()
        wape = err.sum() / pr["actual"].sum()
        # Staffing view: of the 20 busiest hours each week, how many did the forecast flag?
        hit = np.mean([len(set(g.nlargest(20, "actual").index) & set(g.nlargest(20, m).index)) / 20
                       for _, g in pr.groupby("week")])
        day = pr[["actual", m]].groupby(pr.index.floor("D")).sum()
        rows.append({"model": m, "WAPE": wape, "daily_WAPE": (day[m] - day["actual"]).abs().sum() / day["actual"].sum(),
                     "median_APE": (err / pr["actual"]).median(),
                     "bias": (pr[m].sum() - pr["actual"].sum()) / pr["actual"].sum(), "top20_hours_hit_rate": hit})
    scores = pd.DataFrame(rows).set_index("model")
    scores["skill_vs_naive"] = 1 - scores["WAPE"] / scores.loc["Seasonal naive (last week)", "WAPE"]
    return pr, scores


# =============================================================== 4. Statistical rigor + Monte Carlo

def permutation_pvalue(observed: float, null: np.ndarray, two_sided: bool = True) -> float:
    if two_sided:
        return (np.sum(np.abs(null) >= abs(observed)) + 1) / (len(null) + 1)
    return (np.sum(null >= observed) + 1) / (len(null) + 1)


def stationary_bootstrap_idx(n: int, size: int, mean_block: int, rng: np.random.Generator,
                             paths: int | None = None) -> np.ndarray:
    """Politis-Romano stationary bootstrap indices (keeps volatility clustering intact).

    Blocks start at random positions and have geometric lengths with mean `mean_block`.
    Returns shape (size,) or (paths, size).
    """
    shape = (paths or 1, size)
    new_block = rng.random(shape) < 1 / mean_block
    new_block[:, 0] = True
    pos = np.broadcast_to(np.arange(size), shape)
    block_start_pos = np.maximum.accumulate(np.where(new_block, pos, 0), axis=1)
    start_value = rng.integers(n, size=shape)
    first_of_block = np.take_along_axis(start_value, block_start_pos, axis=1)
    idx = (first_of_block + pos - block_start_pos) % n
    return idx if paths else idx[0]


def significance_tests(daily: pd.DataFrame, hourly: pd.DataFrame, n_perm: int = 5000) -> pd.DataFrame:
    """Re-test every headline claim from the core analysis, then control the false-discovery rate."""
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    d = daily.loc[A.COHORT_START:]
    r = d["pct_return"].dropna()

    # (a) crash rebound: next-day return after <= -10% days vs random days
    for thr in (-0.10, -0.05):
        ev, _ = A.crash_event_study(daily, threshold=thr)
        nxt = r.shift(-1).dropna()
        obs = nxt.reindex(ev.index).dropna()
        null = np.array([nxt.sample(len(obs), random_state=int(s)).median() - nxt.median()
                         for s in rng.integers(1e9, size=n_perm)])
        diff = obs.median() - nxt.median()
        boot = np.array([np.median(rng.choice(obs.to_numpy(), len(obs))) for _ in range(n_perm)])
        rows.append({"claim": f"Next-day rebound after {thr:.0%} days", "estimate": diff,
                     "ci_low": np.percentile(boot, 2.5) - nxt.median(), "ci_high": np.percentile(boot, 97.5) - nxt.median(),
                     "n": len(obs), "test": "permutation (random days)", "p_value": permutation_pvalue(diff, null)})

    # (b) weekday matters for recurring-buy cost? price relative to its own week's mean, labels shuffled within week
    c = d["close"]
    wk = c.groupby(c.index.tz_localize(None).to_period("W")).transform("mean")
    rel = (c / wk - 1).to_frame("rel").assign(wd=c.index.weekday, wk=c.index.tz_localize(None).to_period("W"))
    rel = rel[rel.groupby("wk")["rel"].transform("size") == 7]
    stat = lambda df: df.groupby("wd")["rel"].mean().pipe(lambda s: s.max() - s.min())
    obs = stat(rel)
    vals = rel["rel"].to_numpy().reshape(-1, 7)
    null = []
    for _ in range(n_perm):
        sh = np.apply_along_axis(rng.permutation, 1, vals)
        m = sh.mean(axis=0)
        null.append(m.max() - m.min())
    rows.append({"claim": "Weekday changes recurring-buy price", "estimate": obs, "ci_low": np.nan, "ci_high": np.nan,
                 "n": len(vals), "test": "permutation within week", "p_value": permutation_pvalue(obs, np.array(null), two_sided=False)})

    # (c) weekend volume lower than weekday (2019+), day labels shuffled within week
    h = hourly[hourly["datetime"] >= A.INTRADAY_START]
    dv = h.groupby(h["datetime"].dt.floor("D"))["volume_usd"].sum()
    dv = np.log(dv[dv > 0])
    frame = dv.to_frame("v").assign(wd=dv.index.weekday, wk=dv.index.tz_localize(None).to_period("W"))
    frame = frame[frame.groupby("wk")["v"].transform("size") == 7].sort_index()
    vals = frame["v"].to_numpy().reshape(-1, 7)
    obs = vals[:, 5:].mean() - vals[:, :5].mean()
    null = [(lambda s: s[:, 5:].mean() - s[:, :5].mean())(np.apply_along_axis(rng.permutation, 1, vals)) for _ in range(2000)]
    rows.append({"claim": "Weekend volume below weekdays (log)", "estimate": np.expm1(obs), "ci_low": np.nan, "ci_high": np.nan,
                 "n": len(vals), "test": "permutation within week", "p_value": permutation_pvalue(obs, np.array(null))})

    # (d) volatility fell: ETF-era vs 2017-2020 daily-return std ratio, stationary-bootstrap CI
    a, b = daily.loc["2017":"2020", "log_return"].dropna().to_numpy(), daily.loc["2024":, "log_return"].dropna().to_numpy()
    ratios = np.array([b[stationary_bootstrap_idx(len(b), len(b), 30, rng)].std() /
                       a[stationary_bootstrap_idx(len(a), len(a), 30, rng)].std() for _ in range(2000)])
    obs = b.std() / a.std()
    rows.append({"claim": "Volatility ratio, 2024+ vs 2017-20", "estimate": obs,
                 "ci_low": np.percentile(ratios, 2.5), "ci_high": np.percentile(ratios, 97.5), "n": len(b),
                 "test": "stationary bootstrap CI", "p_value": (np.sum(ratios >= 1) + 1) / (len(ratios) + 1)})

    # (e) DCA narrows the downside: 10th-percentile 12-month ROI, DCA minus lump sum, cohort bootstrap
    t = A.dca_vs_lump_sum(daily["close"], 12)
    diff = t["dca_roi"].quantile(0.1) - t["lump_sum_roi"].quantile(0.1)
    boot = []
    for _ in range(2000):
        s = t.sample(len(t), replace=True, random_state=int(rng.integers(1e9)))
        boot.append(s["dca_roi"].quantile(0.1) - s["lump_sum_roi"].quantile(0.1))
    boot = np.array(boot)
    rows.append({"claim": "DCA lifts 10th-pct 12m ROI vs lump", "estimate": diff,
                 "ci_low": np.percentile(boot, 2.5), "ci_high": np.percentile(boot, 97.5), "n": len(t),
                 "test": "cohort bootstrap (overlapping)", "p_value": (np.sum(boot <= 0) + 1) / (len(boot) + 1)})

    out = pd.DataFrame(rows).set_index("claim")
    out["p_adjusted_BH"] = multipletests(out["p_value"], method="fdr_bh")[1]
    out["significant_5pct"] = out["p_adjusted_BH"] < 0.05
    return out


def monte_carlo_plans(daily: pd.DataFrame, years: int = 4, n_paths: int = 10000, weekly_amount: float = 100.0,
                      sample_from: str = "2021-01-01", mean_block: int = 30) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate customer outcomes for a weekly plan vs a lump sum by stationary block bootstrap of daily returns.

    Sampling from the post-2021 regime reflects today's lower volatility; the bootstrap keeps
    multi-week trends and volatility clusters that i.i.d. sampling would destroy.
    """
    rng = np.random.default_rng(RNG_SEED)
    r = daily.loc[sample_from:, "log_return"].dropna().to_numpy()
    days = years * 365
    buy_days = np.arange(0, days, 7)
    invested = weekly_amount * len(buy_days)
    price = np.empty((n_paths, days))
    for chunk in range(0, n_paths, 2000):                            # chunked to keep memory modest
        k = min(2000, n_paths - chunk)
        idx = stationary_bootstrap_idx(len(r), days, mean_block, rng, paths=k)
        price[chunk:chunk + k] = np.exp(np.cumsum(r[idx], axis=1))   # price relative to day 0
    # value of DCA at the end of each year, and lump sum (all invested on day 0)
    rows, fan = [], []
    for yr in range(1, years + 1):
        end = yr * 365 - 1
        b = buy_days[buy_days <= end]
        coins = (weekly_amount / price[:, b]).sum(axis=1)
        inv = weekly_amount * len(b)
        dca_roi = coins * price[:, end] / inv - 1
        lump_roi = price[:, end] - 1
        for name, roi in (("Weekly plan", dca_roi), ("Lump sum", lump_roi)):
            rows.append({"year": yr, "strategy": name, "prob_loss": (roi < 0).mean(),
                         "prob_loss_gt_30pct": (roi < -0.3).mean(), "p5": np.percentile(roi, 5),
                         "median": np.median(roi), "p95": np.percentile(roi, 95),
                         "expected_shortfall_5pct": roi[roi <= np.percentile(roi, 5)].mean()})
    for day in range(30, days + 1, 30):
        end = day - 1
        b = buy_days[buy_days <= end]
        coins = (weekly_amount / price[:, b]).sum(axis=1)
        roi = coins * price[:, end] / (weekly_amount * len(b)) - 1
        fan.append({"day": day, **{f"p{q}": np.percentile(roi, q) for q in (5, 25, 50, 75, 95)}})
    summary = pd.DataFrame(rows).set_index(["year", "strategy"])
    return summary, pd.DataFrame(fan).set_index("day")
