-- Crash event study: one-day drops of 10%+ since 2014, de-clustered (a drop within 7 days of the
-- previous qualifying drop is the same event), then how often the next day / next 30 days were up.
WITH px AS (
    SELECT date, close, pct_return,
           LEAD(close, 1)  OVER (ORDER BY date) / close - 1 AS fwd_1d,
           LEAD(close, 30) OVER (ORDER BY date) / close - 1 AS fwd_30d
    FROM v_daily
    WHERE date >= '2014-01-01'
),
candidates AS (
    SELECT *, LAG(date) OVER (ORDER BY date) AS prev_candidate
    FROM px
    WHERE pct_return <= -0.10
),
events AS (
    SELECT *
    FROM candidates
    WHERE prev_candidate IS NULL OR julianday(date) - julianday(prev_candidate) > 7
)
SELECT
    COUNT(*)                                                                     AS events,
    ROUND(100.0 * AVG(fwd_1d > 0), 1)                                            AS next_day_up_pct,
    ROUND(100.0 * (SELECT AVG(fwd_1d > 0) FROM px WHERE fwd_1d IS NOT NULL), 1)  AS baseline_next_day_up_pct,
    ROUND(100.0 * AVG(fwd_30d > 0), 1)                                           AS next_30d_up_pct,
    ROUND(100.0 * (SELECT AVG(fwd_30d > 0) FROM px WHERE fwd_30d IS NOT NULL), 1) AS baseline_30d_up_pct,
    SUM(date >= '2024-01-01')                                                    AS events_since_2024
FROM events;
