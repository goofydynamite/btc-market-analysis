-- 30-day rolling annualised volatility (sample std via the variance identity),
-- then the share of days spent in each volatility regime by year.
WITH rolling AS (
    SELECT
        date, year, log_return,
        AVG(log_return) OVER w                     AS mean_r,
        AVG(log_return * log_return) OVER w        AS mean_r2,
        COUNT(log_return) OVER w                   AS n
    FROM v_daily
    WINDOW w AS (ORDER BY date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)
),
vol AS (
    SELECT date, year,
           sqrt((mean_r2 - mean_r * mean_r) * n / (n - 1)) * sqrt(365) AS ann_vol_30d
    FROM rolling
    WHERE n = 30
)
SELECT
    year,
    ROUND(100 * AVG(ann_vol_30d), 1)                                AS avg_ann_vol_pct,
    ROUND(100.0 * AVG(ann_vol_30d < 0.40), 1)                       AS calm_days_pct,     -- < 40%
    ROUND(100.0 * AVG(ann_vol_30d BETWEEN 0.40 AND 0.80), 1)        AS normal_days_pct,   -- 40-80%
    ROUND(100.0 * AVG(ann_vol_30d > 0.80), 1)                       AS stressed_days_pct  -- > 80%
FROM vol
GROUP BY year
ORDER BY year;
