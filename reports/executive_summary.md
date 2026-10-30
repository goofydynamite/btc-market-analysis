# Executive summary: Bitcoin market intelligence for the 2027 roadmap

**To:** Product, Risk, Operations and Growth leads
**From:** Data Analytics
**Data:** 7.76M one-minute BTC/USD bars, January 2012 to October 2026 (Bitstamp via Kaggle)

## Bottom line

Bitcoin has become a calmer asset (volatility 91% → 47%) whose cycles still repeat in timing but no longer in size. The calming started in 2022, before the spot ETFs. For our customers, **how long they hold and how they buy** matter far more than **when** they buy. That points the roadmap toward recurring buys and toward helping people stay invested, not toward timing tools.

## Decisions requested

1. **Make weekly Recurring Buy the default onboarding path.** It doesn't earn more than investing everything on day 1 (lump sum wins in 64–80% of start months). But it cut the worst 12-month outcome from −72% to −51%, and it narrows the range of results by about 60%. Fewer customers having a terrible first year should mean better retention. *Measure:* share of new users on a plan and 12-month retention.
2. **Drop the "best day to buy" feature request.** Across 8+ years, the weekday a plan runs on changes the average cost by 0.6% at most.
3. **Deprioritise the crash-day cool-down prompt.** After the 37 one-day drops of 10%+ since 2014, the next day was up 68% of the time, versus 52% normally. But there has been only one such day since 2024, and at a −5% trigger the rebound disappears (127 events). The feature would almost never fire. Revisit if 90-day volatility returns above 80%.
4. **Move maintenance to Saturday 03:00 UTC and staff support peaks Mon–Fri 13:00–17:00 UTC.** Volume at the quietest hour is about 0.3× average; at the busiest it is 2.9×.
5. **Compute VaR with a fat-tailed GARCH model and add a stress-regime alert.** In an out-of-sample backtest (2020–26), the 99% VaR from GARCH-t was breached 25 times against 25 expected. The normal-distribution EWMA method was breached 51 times. A Markov-switching model flags stress regimes, which last about 13 days once they start.
6. **Don't show customers historical "99.7% of 3-year holds were profitable" odds.** A Monte Carlo using today's return profile puts the chance of a loss after four years on a weekly plan at about 26%. Show a simulated range of outcomes instead. It's more honest and still favours recurring buys: in bad scenarios the plan loses 59% against 80% for a lump sum.
7. **Shift operations and campaign coverage toward US hours.** Since the spot-ETF launch, the US-session share of weekday volume rose from 41.7% to 45.8% (p = 0.002).
8. **Staff with a bias-corrected 4-week seasonal volume forecast.** A gradient-boosting model was no more accurate.

## What not to conclude

- "The next cycle will be like the last." Gains fell from 93× to 2× across four cycles, and four cycles is too few to forecast from.
- "Buy the dip." Crash-day rebounds are short-lived, and one year later crash-day buyers did worse than average.
- "ETFs made Bitcoin safer." Volatility did fall (to 0.57× its 2017–20 level), but the structural break was in August 2022, 17 months before the ETF launch.
- Any of this as investment advice. All customer-facing copy needs compliance review.
