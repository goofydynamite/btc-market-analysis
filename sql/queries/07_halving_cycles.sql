-- Halving-cycle scorecard (joins the cycle dimension): price at the halving, the cycle peak
-- (highest close within 730 days of the halving), days to peak, and the bear-market low after it.
WITH cycle_days AS (
    SELECT c.cycle_key, c.cycle_label, c.halving_date, v.date, v.close,
           julianday(v.date) - julianday(c.halving_date) AS days_in
    FROM v_daily v
    JOIN dim_halving_cycle c USING (cycle_key)
    WHERE c.cycle_key > 0
),
peak AS (
    SELECT cycle_key, date AS peak_date, close AS peak_close
    FROM (
        SELECT cycle_key, date, close,
               ROW_NUMBER() OVER (PARTITION BY cycle_key ORDER BY close DESC, date) AS rn
        FROM cycle_days
        WHERE days_in <= 730
    )
    WHERE rn = 1
),
post_peak_low AS (
    SELECT p.cycle_key, MIN(cd.close) AS low_close
    FROM peak p
    JOIN cycle_days cd ON cd.cycle_key = p.cycle_key AND cd.date >= p.peak_date
    GROUP BY p.cycle_key
),
halving_price AS (
    SELECT cycle_key, close AS halving_close FROM cycle_days WHERE days_in = 0
)
SELECT
    c.cycle_label,
    c.halving_date,
    ROUND(h.halving_close, 2)                                             AS price_at_halving,
    p.peak_date,
    ROUND(p.peak_close, 2)                                                AS cycle_peak,
    CAST(julianday(p.peak_date) - julianday(c.halving_date) AS INTEGER)   AS days_to_peak,
    ROUND(p.peak_close / h.halving_close, 1)                              AS halving_to_peak_x,
    ROUND(100.0 * (l.low_close / p.peak_close - 1), 1)                    AS post_peak_drawdown_pct
FROM dim_halving_cycle c
JOIN halving_price h  USING (cycle_key)
JOIN peak p           USING (cycle_key)
JOIN post_peak_low l  USING (cycle_key)
ORDER BY c.cycle_key;
