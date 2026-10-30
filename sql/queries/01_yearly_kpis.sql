-- Yearly KPI table: return, range, traded volume and share of up days.
-- Window functions pick the first open / last close of each year.
WITH ordered AS (
    SELECT
        year,
        date,
        close,
        volume_usd,
        FIRST_VALUE(open) OVER (PARTITION BY year ORDER BY date) AS year_open,
        LAST_VALUE(close) OVER (PARTITION BY year ORDER BY date
                                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS year_close,
        close > LAG(close) OVER (ORDER BY date) AS is_up_day
    FROM v_daily
)
SELECT
    year,
    ROUND(MIN(year_open), 2)                              AS open_usd,
    ROUND(MIN(year_close), 2)                             AS close_usd,
    ROUND(100.0 * (MIN(year_close) / MIN(year_open) - 1), 1) AS return_pct,
    ROUND(SUM(volume_usd) / 1e9, 2)                       AS usd_volume_bn,
    ROUND(100.0 * AVG(is_up_day), 1)                      AS up_days_pct,
    COUNT(*)                                              AS trading_days
FROM ordered
GROUP BY year
ORDER BY year;
