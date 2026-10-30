-- Recurring-buy cohort analysis in pure SQL: a customer starts on the 1st of each month (2014+)
-- and buys $100 every 7 days for N months, vs investing the same total on day 1 (lump sum).
WITH horizons(months) AS (
    VALUES (12), (24), (36), (48)
),
cohorts AS (
    SELECT h.months, v.date AS cohort_start, date(v.date, '+' || h.months || ' months') AS cohort_end
    FROM v_daily v
    CROSS JOIN horizons h
    WHERE v.date >= '2014-01-01'
      AND substr(v.date, 9, 2) = '01'
      AND date(v.date, '+' || h.months || ' months') <= (SELECT MAX(date) FROM v_daily)
),
buys AS (                                     -- one row per weekly $100 purchase
    SELECT c.months, c.cohort_start, c.cohort_end, v.close
    FROM cohorts c
    JOIN v_daily v
      ON v.date >= c.cohort_start
     AND v.date <  c.cohort_end
     AND CAST(julianday(v.date) - julianday(c.cohort_start) AS INTEGER) % 7 = 0
),
cohort_result AS (
    SELECT b.months, b.cohort_start,
           100.0 * COUNT(*)        AS invested,
           SUM(100.0 / b.close)    AS coins,
           (SELECT close FROM v_daily WHERE date = b.cohort_start)                             AS first_price,
           (SELECT close FROM v_daily WHERE date <= b.cohort_end ORDER BY date DESC LIMIT 1)   AS end_price
    FROM buys b
    GROUP BY b.months, b.cohort_start
),
roi AS (
    SELECT months, cohort_start,
           coins * end_price / invested - 1   AS dca_roi,
           end_price / first_price - 1        AS lump_roi
    FROM cohort_result
)
SELECT
    months                                           AS horizon_months,
    COUNT(*)                                         AS cohorts,
    ROUND(100.0 * AVG(dca_roi  > 0), 1)              AS dca_in_profit_pct,
    ROUND(100.0 * AVG(lump_roi > 0), 1)              AS lump_in_profit_pct,
    ROUND(100 * MIN(dca_roi), 1)                     AS dca_worst_pct,
    ROUND(100 * MIN(lump_roi), 1)                    AS lump_worst_pct,
    ROUND(100.0 * AVG(dca_roi > lump_roi), 1)        AS dca_beats_lump_pct
FROM roi
GROUP BY months
ORDER BY months;
