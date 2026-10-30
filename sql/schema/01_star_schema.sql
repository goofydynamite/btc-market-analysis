-- Star schema built from the staging tables (stg_daily, stg_hourly) written by src/pipeline.py.
--
--   dim_date ──┐                     ┌── dim_halving_cycle
--              ├── fact_daily_price ─┘
--              └── fact_hourly_trading
--
-- Grain: fact_daily_price = one row per UTC day; fact_hourly_trading = one row per UTC hour.

DROP VIEW  IF EXISTS v_daily;
DROP VIEW  IF EXISTS v_hourly;
DROP TABLE IF EXISTS fact_hourly_trading;
DROP TABLE IF EXISTS fact_daily_price;
DROP TABLE IF EXISTS dim_halving_cycle;
DROP TABLE IF EXISTS dim_date;

-- ---------------------------------------------------------------- dimensions
CREATE TABLE dim_date (
    date_key      INTEGER PRIMARY KEY,      -- yyyymmdd
    date          TEXT    NOT NULL UNIQUE,  -- ISO yyyy-mm-dd
    year          INTEGER NOT NULL,
    quarter       INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    year_month    TEXT    NOT NULL,         -- yyyy-mm
    week_start    TEXT    NOT NULL,         -- Monday of the ISO week
    weekday_num   INTEGER NOT NULL,         -- 0 = Monday ... 6 = Sunday
    weekday_name  TEXT    NOT NULL,
    is_weekend    INTEGER NOT NULL,
    era           TEXT    NOT NULL,
    is_etf_era    INTEGER NOT NULL          -- on/after first US spot-ETF trading day
);

INSERT INTO dim_date
SELECT
    CAST(strftime('%Y%m%d', date) AS INTEGER),
    date,
    CAST(strftime('%Y', date) AS INTEGER),
    (CAST(strftime('%m', date) AS INTEGER) + 2) / 3,
    CAST(strftime('%m', date) AS INTEGER),
    strftime('%Y-%m', date),
    date(date, '-' || ((CAST(strftime('%w', date) AS INTEGER) + 6) % 7) || ' days'),
    (CAST(strftime('%w', date) AS INTEGER) + 6) % 7,
    weekday,
    CASE WHEN strftime('%w', date) IN ('0', '6') THEN 1 ELSE 0 END,
    CASE
        WHEN date < '2017-01-01' THEN '2012-2016 Early market'
        WHEN date < '2021-01-01' THEN '2017-2020 Retail boom'
        WHEN date < '2024-01-01' THEN '2021-2023 Institutional'
        ELSE '2024-2026 ETF era'
    END,
    CASE WHEN date >= '2024-01-11' THEN 1 ELSE 0 END
FROM stg_daily;

CREATE TABLE dim_halving_cycle (
    cycle_key          INTEGER PRIMARY KEY,
    cycle_label        TEXT NOT NULL,
    halving_date       TEXT NOT NULL,
    next_halving_date  TEXT                 -- NULL for the current cycle
);

INSERT INTO dim_halving_cycle VALUES
    (0, 'Pre-2012 halving', '2012-01-01', '2012-11-28'),
    (1, '2012 cycle',       '2012-11-28', '2016-07-09'),
    (2, '2016 cycle',       '2016-07-09', '2020-05-11'),
    (3, '2020 cycle',       '2020-05-11', '2024-04-20'),
    (4, '2024 cycle',       '2024-04-20', NULL);

-- ---------------------------------------------------------------- facts
CREATE TABLE fact_daily_price (
    date_key       INTEGER PRIMARY KEY REFERENCES dim_date(date_key),
    cycle_key      INTEGER NOT NULL    REFERENCES dim_halving_cycle(cycle_key),
    open           REAL NOT NULL,
    high           REAL NOT NULL,
    low            REAL NOT NULL,
    close          REAL NOT NULL,
    volume_usd     REAL NOT NULL,
    volume_btc     REAL NOT NULL,
    trade_minutes  INTEGER NOT NULL,
    realized_vol   REAL,                   -- sqrt(sum of squared 1-minute log returns)
    log_return     REAL,
    pct_return     REAL
);

INSERT INTO fact_daily_price
SELECT
    CAST(strftime('%Y%m%d', s.date) AS INTEGER),
    (SELECT MAX(c.cycle_key) FROM dim_halving_cycle c WHERE c.halving_date <= s.date),
    s.open, s.high, s.low, s.close, s.volume_usd, s.volume_btc, s.trade_minutes,
    s.realized_vol, s.log_return, s.pct_return
FROM stg_daily s;

CREATE TABLE fact_hourly_trading (
    datetime_utc   TEXT    PRIMARY KEY,
    date_key       INTEGER NOT NULL REFERENCES dim_date(date_key),
    hour_utc       INTEGER NOT NULL,
    close          REAL    NOT NULL,
    volume_usd     REAL    NOT NULL,
    trade_minutes  INTEGER NOT NULL,
    log_return     REAL
);

INSERT INTO fact_hourly_trading
SELECT datetime, CAST(strftime('%Y%m%d', datetime) AS INTEGER), hour_utc, close, volume_usd, trade_minutes, log_return
FROM stg_hourly;

CREATE INDEX ix_fact_daily_cycle   ON fact_daily_price(cycle_key);
CREATE INDEX ix_fact_hourly_date   ON fact_hourly_trading(date_key);

-- ---------------------------------------------------------------- analyst-friendly views
CREATE VIEW v_daily AS
SELECT d.date, d.year, d.quarter, d.month, d.year_month, d.week_start, d.weekday_num,
       d.weekday_name AS weekday, d.is_weekend, d.era, d.is_etf_era,
       c.cycle_key, c.cycle_label, c.halving_date,
       f.open, f.high, f.low, f.close, f.volume_usd, f.volume_btc, f.trade_minutes,
       f.realized_vol, f.log_return, f.pct_return
FROM fact_daily_price f
JOIN dim_date d           USING (date_key)
JOIN dim_halving_cycle c  USING (cycle_key);

CREATE VIEW v_hourly AS
SELECT h.datetime_utc AS datetime, d.date, d.year, d.week_start, d.weekday_num, d.weekday_name AS weekday,
       d.is_weekend, d.is_etf_era, h.hour_utc, h.close, h.volume_usd, h.trade_minutes, h.log_return
FROM fact_hourly_trading h
JOIN dim_date d USING (date_key);
