# SQL ↔ Python reconciliation

Every headline number is computed twice: once in SQL (`sql/queries/`) and once in pandas (`src/analysis.py`, `src/advanced.py`). They must agree to within SQL's rounding.

**47 / 47 checks match.**

| area | metric | sql | python | match |
|---|---|---|---|---|
| Halving cycles | 2012 days to peak | 371.0 | 371.0 | pass |
| Halving cycles | 2012 post-peak drawdown % | -84.9 | -84.8579 | pass |
| Halving cycles | 2016 days to peak | 525.0 | 525.0 | pass |
| Halving cycles | 2016 post-peak drawdown % | -83.4 | -83.4293 | pass |
| Halving cycles | 2020 days to peak | 546.0 | 546.0 | pass |
| Halving cycles | 2020 post-peak drawdown % | -76.7 | -76.6634 | pass |
| Halving cycles | 2024 days to peak | 534.0 | 534.0 | pass |
| Halving cycles | 2024 post-peak drawdown % | -53.1 | -53.077 | pass |
| Drawdown episodes | episodes deeper than -50% | 6.0 | 6.0 | pass |
| Drawdown episodes | 2013-04-09 depth % | -71.0 | -71.0306 | pass |
| Drawdown episodes | 2013-04-09 days underwater | 210.0 | 210.0 | pass |
| Drawdown episodes | 2013-12-04 depth % | -84.9 | -84.8579 | pass |
| Drawdown episodes | 2013-12-04 days underwater | 1177.0 | 1177.0 | pass |
| Drawdown episodes | 2017-12-16 depth % | -83.4 | -83.4293 | pass |
| Drawdown episodes | 2017-12-16 days underwater | 1080.0 | 1080.0 | pass |
| Drawdown episodes | 2021-04-13 depth % | -53.1 | -53.1396 | pass |
| Drawdown episodes | 2021-04-13 days underwater | 189.0 | 189.0 | pass |
| Drawdown episodes | 2021-11-08 depth % | -76.7 | -76.6634 | pass |
| Drawdown episodes | 2021-11-08 days underwater | 847.0 | 847.0 | pass |
| Drawdown episodes | 2025-10-06 depth % | -53.1 | -53.077 | pass |
| Drawdown episodes | 2025-10-06 days underwater | 365.0 | 365.0 | pass |
| DCA cohorts | 12m cohorts | 142.0 | 142.0 | pass |
| DCA cohorts | 12m DCA in profit % | 71.8 | 71.831 | pass |
| DCA cohorts | 12m DCA worst % | -51.5 | -51.4679 | pass |
| DCA cohorts | 12m DCA beats lump % | 35.9 | 35.9155 | pass |
| DCA cohorts | 24m cohorts | 130.0 | 130.0 | pass |
| DCA cohorts | 24m DCA in profit % | 81.5 | 81.5385 | pass |
| DCA cohorts | 24m DCA worst % | -48.1 | -48.1269 | pass |
| DCA cohorts | 24m DCA beats lump % | 29.2 | 29.2308 | pass |
| DCA cohorts | 36m cohorts | 118.0 | 118.0 | pass |
| DCA cohorts | 36m DCA in profit % | 95.8 | 95.7627 | pass |
| DCA cohorts | 36m DCA worst % | -10.0 | -9.9902 | pass |
| DCA cohorts | 36m DCA beats lump % | 25.4 | 25.4237 | pass |
| DCA cohorts | 48m cohorts | 106.0 | 106.0 | pass |
| DCA cohorts | 48m DCA in profit % | 100.0 | 100.0 | pass |
| DCA cohorts | 48m DCA worst % | 34.3 | 34.2677 | pass |
| DCA cohorts | 48m DCA beats lump % | 19.8 | 19.8113 | pass |
| ETF before/after | Realized volatility (ann.), before | 49.1 | 49.0988 | pass |
| ETF before/after | Realized volatility (ann.), after | 43.6 | 43.6318 | pass |
| ETF before/after | US-session share of weekday volume, before | 41.7 | 41.6975 | pass |
| ETF before/after | US-session share of weekday volume, after | 45.8 | 45.8365 | pass |
| ETF before/after | Weekend share of weekly volume, before | 15.1 | 15.1123 | pass |
| ETF before/after | Weekend share of weekly volume, after | 14.8 | 14.7586 | pass |
| Crash rebound | events | 37.0 | 37.0 | pass |
| Crash rebound | next day up % | 67.6 | 67.5676 | pass |
| Crash rebound | next 30d up % | 62.2 | 62.1622 | pass |
| Crash rebound | baseline next day up % | 51.6 | 51.5769 | pass |
