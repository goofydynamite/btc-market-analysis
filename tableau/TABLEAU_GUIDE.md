# Tableau build notes: Bitcoin Market Intelligence

How the workbook [`Bitcoin Market Intelligence.twb`](Bitcoin%20Market%20Intelligence.twb) is put together, so it can be rebuilt or extended. All data comes from the CSVs in [`data/`](data/), which `src/export_tableau.py` writes from the same pipeline as the notebooks and the HTML dashboard. The numbers match across all three.

Published version: [Tableau Public](https://public.tableau.com/app/profile/deepti.singh.kushwaha/viz/bitcoinanalysis_17932796615520/RecurringBuyDecision)

| Dashboard | Audience | Sheets |
|---|---|---|
| Market Overview | Strategy / Risk | KPIs, Price by Regime, Drawdown, Annualised volatility by year |
| When the Market Trades | Operations / Growth | Trading Heatmap, Weekday vs Weekend, ETF US Session |
| Recurring Buy Decision | Product | Cohort Heatmap, Holding Odds, Monte Carlo |

All dashboards are 1200 × 900 with floating layout.

---

## Data sources

One data source per CSV, no joins.

| File | Grain | Used in |
|---|---|---|
| `btc_daily.csv` | 1 row per day (5,393) | Market Overview |
| `trading_heatmap.csv` | weekday × hour (168) | When the Market Trades |
| `etf_weekly.csv` | week × metric (741) | When the Market Trades |
| `dca_cohorts.csv` | start month × horizon (1,210) | Recurring Buy Decision |
| `holding_period_odds.csv` | horizon (9) | Recurring Buy Decision |
| `monte_carlo_fan.csv` | month of plan (48) | Recurring Buy Decision |

`Hour UTC` and `Horizon Months` are converted to discrete dimensions. Ratio fields (`Drawdown`, `Prob Profit`, `Value`, the percentile fields) use a percentage number format.

[`Preferences.tps`](Preferences.tps) holds the colour palettes. Copy it to `Documents\My Tableau Public Repository\` to use them.

---

## Market Overview (`btc_daily`)

**Calculated fields**

```text
Latest Date     { FIXED : MAX([Date]) }
Last Close      { FIXED : MAX(IF [Date] = [Latest Date] THEN [Close] END) }
From ATH        { FIXED : MAX(IF [Date] = [Latest Date] THEN [Drawdown] END) }
Vol 30D Now     { FIXED : MAX(IF [Date] = [Latest Date] THEN [Volatility 30D] END) }
Stress Now      { FIXED : MAX(IF [Date] = [Latest Date] THEN [P(Stress)] END) }
Annualised Vol  STDEV([Daily Return]) * SQRT(365)
```

The FIXED level-of-detail expressions return the latest value for the whole dataset, so the KPI tiles are unaffected by filters on the view.

- **KPIs:** Measure Names on Columns, Measure Values (MAX of the four LOD fields) on Text. Grey pane shading with thick white column dividers makes the four cells read as tiles.
- **Price by Regime:** exact Date (continuous) × Close on a log axis, filtered to 2014+. Colour is `P(Stress)` on a red-blue diverging palette centred at 0.5. A continuous colour keeps it a single line; colouring by the `Market Regime` dimension would split it into segments. `Market Regime` is on the tooltip.
- **Drawdown:** area chart of Drawdown, axis fixed −100% to 0%.
- **Annualised volatility by year:** bars of `Annualised Vol` by discrete Year, with labels.

## When the Market Trades

- **Trading Heatmap** (`trading_heatmap`): Hour UTC × Weekday, square marks coloured by `Volume Index` (blue sequential). Weekday is sorted by `Weekday Order`.
- **Weekday vs Weekend:** AVG(`Volume Index`) by `Day Type`.
- **ETF US Session** (`etf_weekly`): filtered to "US-session share of weekday volume". Week (exact, continuous) × Measure Values (`Value`, `Period Mean`) on one shared axis, coloured by `Period`, with Measure Names on Detail. Each period shows its weekly series and its mean line.

## Recurring Buy Decision

```text
ROI colour (log)   LN(1 + AVG([Dca Roi]))
```

Returns range from about −70% to +1,500%, so a linear colour scale would make every loss look the same. The log transform keeps 0 at 0 and spreads out the losses.

- **Cohort Heatmap** (`dca_cohorts`): YEAR(Cohort Start) × Horizon Months, coloured by `ROI colour (log)` on a red-blue diverging palette centred at 0.
- **Holding Odds** (`holding_period_odds`): Prob Profit by Horizon, sorted by Days.
- **Monte Carlo** (`monte_carlo_fan`): Years × Measure Values for the five percentile fields (renamed Worst 5% of paths, Lower quartile, Median, Upper quartile, Best 5% of paths), shaded from light to dark blue with the median darkest.

---

## Possible extensions

- A `p_Strategy` parameter (Recurring buy / Lump sum) that swaps the cohort heatmap between `Dca Roi` and `Lump Sum ROI`.
- A parameter action that sets the holding horizon by clicking a heatmap column, driving a KPI tile with the share of cohorts in profit.
- Filter and highlight actions on Market Overview, for example clicking a year in the volatility chart to zoom the price and drawdown charts.
