-- Product / ops question: which hours of the week are busiest (staff support,
-- send campaigns) and quietest (schedule maintenance)? 2019+ only, when the
-- order book is liquid enough that hourly volume is meaningful.
WITH by_slot AS (
    SELECT weekday, weekday_num, hour_utc, AVG(volume_usd) AS avg_usd_volume
    FROM v_hourly
    WHERE datetime >= '2019-01-01'
    GROUP BY weekday, weekday_num, hour_utc
),
indexed AS (
    SELECT *,
           avg_usd_volume / AVG(avg_usd_volume) OVER () AS vs_avg_hour,
           RANK() OVER (ORDER BY avg_usd_volume DESC)   AS busiest_rank,
           RANK() OVER (ORDER BY avg_usd_volume ASC)    AS quietest_rank
    FROM by_slot
)
SELECT
    CASE WHEN busiest_rank <= 5 THEN 'busiest' ELSE 'quietest' END AS slot_type,
    weekday,
    printf('%02d:00 UTC', hour_utc)            AS hour,
    ROUND(avg_usd_volume / 1e6, 2)             AS avg_usd_volume_m,
    ROUND(vs_avg_hour, 2)                      AS vs_avg_hour
FROM indexed
WHERE busiest_rank <= 5 OR quietest_rank <= 5
ORDER BY slot_type, vs_avg_hour DESC;
