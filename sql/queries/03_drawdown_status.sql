-- Running all-time high and drawdown per day, then: how many days did the
-- market spend in each drawdown bucket, and where are we today?
WITH ath AS (
    SELECT date, close,
           MAX(close) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_ath
    FROM v_daily
),
dd AS (
    SELECT date, close, running_ath, close / running_ath - 1 AS drawdown
    FROM ath
)
SELECT
    CASE
        WHEN drawdown >= -0.10 THEN '0 to -10%'
        WHEN drawdown >= -0.30 THEN '-10 to -30%'
        WHEN drawdown >= -0.50 THEN '-30 to -50%'
        WHEN drawdown >= -0.70 THEN '-50 to -70%'
        ELSE 'below -70%'
    END                                                   AS drawdown_bucket,
    COUNT(*)                                              AS days,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM dd), 1) AS share_of_days_pct,
    MAX(CASE WHEN date = (SELECT MAX(date) FROM dd) THEN 'current' END) AS today
FROM dd
GROUP BY drawdown_bucket
ORDER BY MIN(drawdown) DESC;
