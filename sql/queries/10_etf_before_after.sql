-- ETF before/after (2 years either side of 2024-01-11), on complete Monday-Sunday weeks:
-- realized volatility, US-session (14-20 UTC) share of weekday volume, weekend share of volume.
WITH weekly AS (
    SELECT
        week_start,
        date(week_start, '+6 days')                                                         AS week_end,
        COUNT(*)                                                                            AS hours,
        SUM(volume_usd)                                                                     AS vol_all,
        SUM(CASE WHEN is_weekend = 1 THEN volume_usd ELSE 0 END)                            AS vol_weekend,
        SUM(CASE WHEN is_weekend = 0 THEN volume_usd ELSE 0 END)                            AS vol_weekday,
        SUM(CASE WHEN is_weekend = 0 AND hour_utc BETWEEN 14 AND 20 THEN volume_usd ELSE 0 END) AS vol_us
    FROM v_hourly
    GROUP BY week_start
),
weekly_vol AS (
    SELECT week_start, AVG(realized_vol) * sqrt(365) AS realized_vol
    FROM v_daily
    GROUP BY week_start
),
windowed AS (
    SELECT w.*, wv.realized_vol,
           CASE WHEN w.week_end >= '2024-01-11' THEN 'After ETF' ELSE 'Before ETF' END AS period
    FROM weekly w
    JOIN weekly_vol wv USING (week_start)
    WHERE w.hours = 168
      AND w.week_end >= date('2024-01-11', '-730 days')
)
SELECT
    period,
    COUNT(*)                                      AS weeks,
    ROUND(100 * AVG(realized_vol), 1)             AS realized_vol_pct,
    ROUND(100 * AVG(vol_us / vol_weekday), 1)     AS us_session_share_pct,
    ROUND(100 * AVG(vol_weekend / vol_all), 1)    AS weekend_share_pct
FROM windowed
GROUP BY period
ORDER BY period DESC;
