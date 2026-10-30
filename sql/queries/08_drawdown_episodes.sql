-- Gaps-and-islands: every all-time-high day starts a new "episode"; within each episode find the
-- trough, then the recovery date (= first day of the next episode). Lists bear markets deeper than -50%.
WITH ath AS (
    SELECT date, close,
           MAX(close) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_ath
    FROM v_daily
),
flagged AS (
    SELECT *, close / running_ath - 1 AS drawdown,
           SUM(CASE WHEN close >= running_ath THEN 1 ELSE 0 END)
               OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS episode_id
    FROM ath
),
episodes AS (
    SELECT episode_id,
           MIN(date)          AS peak_date,
           MAX(running_ath)   AS peak_price,
           MIN(drawdown)      AS depth
    FROM flagged
    GROUP BY episode_id
),
troughs AS (
    SELECT f.episode_id, MIN(f.date) AS trough_date, MIN(f.close) AS trough_price
    FROM flagged f
    JOIN episodes e ON e.episode_id = f.episode_id AND f.drawdown = e.depth
    GROUP BY f.episode_id
)
SELECT
    e.peak_date,
    ROUND(e.peak_price, 2)                                                 AS peak_price,
    t.trough_date,
    ROUND(t.trough_price, 2)                                               AS trough_price,
    ROUND(100 * e.depth, 1)                                                AS depth_pct,
    CAST(julianday(t.trough_date) - julianday(e.peak_date) AS INTEGER)     AS days_peak_to_trough,
    nxt.peak_date                                                          AS recovery_date,
    CAST(julianday(COALESCE(nxt.peak_date, (SELECT MAX(date) FROM v_daily))) - julianday(e.peak_date) AS INTEGER)
                                                                           AS days_underwater,
    CASE WHEN nxt.peak_date IS NULL THEN 'still underwater' ELSE 'recovered' END AS status
FROM episodes e
JOIN troughs t USING (episode_id)
LEFT JOIN episodes nxt ON nxt.episode_id = e.episode_id + 1
WHERE e.depth <= -0.5
ORDER BY e.peak_date;
