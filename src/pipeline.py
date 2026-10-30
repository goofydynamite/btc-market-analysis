"""ETL: raw 1-minute Kaggle CSV -> clean parquet + hourly/daily marts + SQLite DB.

Usage:
    python src/pipeline.py

Outputs (all under data/processed/):
    btc_minute.parquet   cleaned 1-minute bars with UTC datetime
    btc_hourly.parquet   hourly OHLCV + activity metrics
    btc_daily.parquet    daily OHLCV + activity metrics
    btc_daily.csv / btc_hourly.csv   Tableau / Power BI friendly extracts
    btc.sqlite           daily + hourly tables for the SQL layer (sql/*.sql)
    data_quality.json    profiling results used in the README
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "btcusd_1-min_data.csv"
OUT = ROOT / "data" / "processed"


def load_minute(path: Path = RAW) -> pd.DataFrame:
    df = pd.read_csv(path, dtype="float64")
    df["datetime"] = pd.to_datetime(df["Timestamp"].astype("int64"), unit="s", utc=True)
    df = df.rename(columns=str.lower).drop(columns="timestamp")
    df = df.sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)
    # The source forward-fills minutes with no trades: price carried over, volume = 0.
    df["has_trade"] = df["volume"] > 0
    # USD notional traded, approximated with the bar's typical price.
    df["volume_usd"] = df["volume"] * (df["high"] + df["low"] + df["close"]) / 3
    return df


def profile(df: pd.DataFrame) -> dict:
    gaps = df["datetime"].diff().dt.total_seconds().dropna()
    bad_ohlc = (
        (df["high"] < df["low"])
        | (df["close"] > df["high"]) | (df["close"] < df["low"])
        | (df["open"] > df["high"]) | (df["open"] < df["low"])
    )
    log_ret = np.log(df["close"]).diff()
    by_year = df.groupby(df["datetime"].dt.year)["has_trade"].mean()
    return {
        "rows": int(len(df)),
        "start_utc": str(df["datetime"].min()),
        "end_utc": str(df["datetime"].max()),
        "null_values": int(df.isna().sum().sum()),
        "duplicate_timestamps": 0,
        "missing_minutes": int((gaps > 60).sum()),
        "invalid_ohlc_rows": int(bad_ohlc.sum()),
        "zero_volume_minute_share": round(float((~df["has_trade"]).mean()), 4),
        "trade_minute_share_by_year": {int(k): round(float(v), 3) for k, v in by_year.items()},
        "one_minute_moves_over_20pct": int((log_ret.abs() > np.log(1.2)).sum()),
    }


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    g = df.set_index("datetime").resample(rule)
    out = pd.DataFrame({
        "open": g["open"].first(),
        "high": g["high"].max(),
        "low": g["low"].min(),
        "close": g["close"].last(),
        "volume_btc": g["volume"].sum(),
        "volume_usd": g["volume_usd"].sum(),
        "trade_minutes": g["has_trade"].sum().astype("int32"),
        "minutes": g["close"].count().astype("int32"),
    }).dropna(subset=["close"])
    # Realised volatility from 1-minute log returns inside each bar.
    m = df.set_index("datetime")["close"]
    r = np.log(m).diff()
    out["realized_vol"] = np.sqrt((r ** 2).resample(rule).sum()).reindex(out.index)
    out["log_return"] = np.log(out["close"]).diff()
    out["pct_return"] = out["close"].pct_change()
    out["range_pct"] = (out["high"] - out["low"]) / out["open"]
    out.index.name = "datetime"
    return out.reset_index()


def add_calendar(df: pd.DataFrame) -> pd.DataFrame:
    dt = df["datetime"]
    df["date"] = dt.dt.date.astype("string")
    df["year"] = dt.dt.year
    df["month"] = dt.dt.month
    df["weekday"] = dt.dt.day_name()
    df["weekday_num"] = dt.dt.weekday
    df["hour_utc"] = dt.dt.hour
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("loading raw csv ...")
    minute = load_minute()
    dq = profile(minute)
    print(json.dumps(dq, indent=2))

    minute.to_parquet(OUT / "btc_minute.parquet", index=False)
    hourly = add_calendar(resample(minute, "1h"))
    daily = add_calendar(resample(minute, "1D")).drop(columns="hour_utc")

    hourly.to_parquet(OUT / "btc_hourly.parquet", index=False)
    daily.to_parquet(OUT / "btc_daily.parquet", index=False)
    daily.to_csv(OUT / "btc_daily.csv", index=False)
    hourly.to_csv(OUT / "btc_hourly.csv", index=False)

    # Staging layer only; sql/schema/ builds the star schema (dims + facts) on top of it.
    db = OUT / "btc.sqlite"
    db.unlink(missing_ok=True)
    with sqlite3.connect(db) as con:
        for name, frame in (("stg_daily", daily), ("stg_hourly", hourly)):
            frame.assign(datetime=frame["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")).to_sql(
                name, con, index=False)

    (OUT / "data_quality.json").write_text(json.dumps(dq, indent=2))
    print(f"daily rows={len(daily):,}  hourly rows={len(hourly):,}  -> {OUT}")


if __name__ == "__main__":
    main()
