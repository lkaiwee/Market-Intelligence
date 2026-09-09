# Research suite 7.6–8.4

All pages use the existing owner-token API, Render service and Neon database. No paid feed or broker connection is required. Existing holdings and refresh schedules remain in place. New database tables are additive and created during API startup.

| Version | Page | Working features | Inputs and source |
| --- | --- | --- | --- |
| 7.6 | Macro Surprises | Saved release records, actual-minus-consensus, relative surprise, standardized surprise against strictly earlier records; edit and delete | User-recorded actuals, consensus and sources, release time, reporting period and units. No automatic consensus feed is configured. |
| 7.7 | Risk & Position Sizing | Holding/sector concentration, account exposures, planned stop risk; long/short quantity constrained by risk, allocation and available capital | Existing holdings and stored closes, explicit cash/equity and stops; optional labelled ATR estimates. |
| 7.8 | Market Regime | Risk-on / neutral / risk-off / unknown, SPY trend, realized volatility and universe breadth with coverage | Completed daily prices; SMA50/200, 20-return volatility and configured stock universe. App-defined thresholds are shown. |
| 7.9 | Technical Setups | Breakout, trend pullback, volatility compression and oversold recovery scans, per-rule evidence, relative strength and planning levels | Completed stored OHLCV, prior-bar highs/volumes, SPY comparison. No signal probability is claimed. |
| 8.0 | Fair Value | Equity cash-flow DCF, bear/base/bull scenarios, discount/terminal-growth sensitivity, margin of safety and earnings multiple scenario | Real statement cache and stored fundamentals, visible model assumptions and optional verified overrides. |
| 8.1 | Earnings Quality | Annual statement refresh/cache; cash conversion, accruals, FCF, liquidity, leverage, share dilution and coverage-aware checklist | Yahoo annual income, balance sheet and cash flow joined by exact fiscal date. Unknown data stays unavailable. |
| 8.2 | Stress & Correlation | Correlation matrix, SPY beta, historical volatility/VaR/expected shortfall, uniform/beta/holding-specific shocks | Current holdings, aligned historical daily price returns and explicit cash/scenario inputs. Minimum 60 observations. |
| 8.3 | Trade Journal | Persistent open/closed long/short trades, fees, stops, thesis and tags; realized P&L, R, win rate, profit factor, monthly/tag summaries and drawdown | User-entered independent trade lots. Journal entries do not modify portfolio holdings. |
| 8.4 | Backtesting | SMA trend, channel breakout and RSI reversion strategies; next-open fills, fees/slippage, ATR stops and optional R targets, equity curve, trade ledger and CSV export | Stored daily price history (normally about two years), simulation dates/capital/parameters. No external trade execution. |

## Workflow

1. Use **System** to refresh daily and screener prices. Add new tickers in **Stock Universe** or refresh a stock directly before scanning or backtesting it.
2. Use **Market Regime** and **Technical Setups** to inspect the completed session. Stale/short price histories are identified in the results.
3. In **Earnings Quality**, enter a ticker and refresh annual statements. **Fair Value** can then use the cached cash flow, currency and share count. Review assumptions and reporting dates before interpreting values.
4. Enter account equity or cash in **Risk & Position Sizing**. Empty account fields are not replaced with an invented balance. Stops and scenario shocks are planning inputs.
5. Record genuine trades in **Trade Journal**. For partial exits, record separate lots and allocate the fees. Performance uses closed trades; the P&L curve is not an account NAV curve.
6. In **Macro Surprises**, record the actual and consensus in matching units and reporting periods with attribution. A surprise's sign alone does not imply a market direction. Editable historical records are not a point-in-time vintage dataset.
7. In **Backtesting**, choose a strategy and cost assumptions. Signals at close execute at the following available open. Open positions stay marked at the final close. Warm-up periods and the actual simulation interval are reported.

## Model boundaries

- Price-return analytics exclude dividends. Yahoo historical data can be corrected; the app does not archive point-in-time corporate-action or constituent vintages.
- DCF treats CFO minus capex as a levered equity cash-flow proxy under zero net borrowing, discounted at the cost of equity. It does not subtract debt or add cash again. Currency mismatches require explicit conversion/overrides.
- Historical stress uses today's weights, not historical account performance. Correlations can change, and VaR/expected shortfall do not cap future losses.
- Backtests are daily, long-only and use whole shares without leverage. Costs apply per fill. Daily-bar ambiguity uses an adverse stop-first ordering after observable opening gaps. There is no liquidity/market-impact, tax, delisting or fundamental vintage model.
- Free Render can sleep, GitHub scheduled refreshes may start late, and Yahoo statement availability varies by company. No artificial records or paid data subscriptions are installed.

## Validation

Backend regression tests cover authentication, route registration, data gaps, persistent record validation, calculation fixtures, completed sessions, and backtest causality/execution. GitHub Actions runs them on Python 3.11. The Pages workflow builds and type-checks all frontend routes.

Run locally from `backend`: `python -m unittest discover -s tests -v`.

Primary references: [yfinance price history](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html), [next-bar execution](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/), [equity valuation](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/background/valintro.htm). Formula details and source labels also appear in each page.
