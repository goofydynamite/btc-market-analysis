-- Tail-risk monitor: how often does BTC move more than 5% / 10% in a day?
SELECT
    year,
    COUNT(*)                                             AS days,
    SUM(pct_return <= -0.10)                             AS crash_days_10pct,
    SUM(pct_return >=  0.10)                             AS rally_days_10pct,
    ROUND(100.0 * AVG(ABS(pct_return) > 0.05), 1)        AS days_moving_5pct_plus,
    ROUND(100 * MIN(pct_return), 1)                      AS worst_day_pct,
    ROUND(100 * MAX(pct_return), 1)                      AS best_day_pct
FROM v_daily
WHERE pct_return IS NOT NULL
GROUP BY year
ORDER BY year;
