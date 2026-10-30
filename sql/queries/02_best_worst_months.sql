-- Month-over-month returns, ranked: the 5 best and 5 worst months on record.
WITH month_end AS (
    SELECT
        substr(date, 1, 7) AS month,
        close,
        ROW_NUMBER() OVER (PARTITION BY substr(date, 1, 7) ORDER BY date DESC) AS rn
    FROM v_daily
),
monthly AS (
    SELECT month, close,
           close / LAG(close) OVER (ORDER BY month) - 1 AS monthly_return
    FROM month_end
    WHERE rn = 1
),
ranked AS (
    SELECT month, close, monthly_return,
           RANK() OVER (ORDER BY monthly_return DESC) AS best_rank,
           RANK() OVER (ORDER BY monthly_return ASC)  AS worst_rank
    FROM monthly
    WHERE monthly_return IS NOT NULL
)
SELECT
    CASE WHEN best_rank <= 5 THEN 'best' ELSE 'worst' END AS bucket,
    month,
    ROUND(close, 2)                   AS month_close_usd,
    ROUND(100.0 * monthly_return, 1)  AS return_pct
FROM ranked
WHERE best_rank <= 5 OR worst_rank <= 5
ORDER BY bucket, return_pct DESC;
