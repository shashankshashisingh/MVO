# MVO: Mean-Variance Optimizer

A single-page mean-variance optimizer that runs entirely in the browser, plus a script that downloads price history from the FYERS API.

## What it does
- Estimates annualized expected returns and covariance (sample or Ledoit-Wolf) from price or return history.
- Objectives: maximum Sharpe, minimum variance, target return, target volatility, mean-variance utility.
- Per-asset weight bounds, optional short selling, efficient frontier chart, correlation heatmap, and a rebalancing column against current weights.

## Usage
1. Open `index.html` in a browser (it starts on synthetic example data).
2. Enter FYERS symbols, history length and frequency. The page shows a download command.
3. Run it on your computer, then load the `prices.csv` it writes.

```
pip install fyers-apiv3
export FYERS_CLIENT_ID="XXXXXXXX-100" FYERS_SECRET_KEY="..." FYERS_REDIRECT_URI="https://127.0.0.1"
python3 fetch_fyers.py --login          # once per trading day
python3 fetch_fyers.py RELIANCE TCS HDFCBANK INFY --years 5 --freq monthly --out prices.csv
```

Any CSV with a date column and one price (or return) column per asset also works.

## Notes
- FYERS returns daily candles. Weekly and monthly series are built from the last close of each period.
- Whether FYERS prices reflect dividends was not verified, so check before relying on total-return estimates.
- Weights are very sensitive to expected-return estimates. This is an analysis tool, not financial advice.
