# MVO: Mean-Variance Optimizer

A mean-variance optimizer that runs in the browser, with price history pulled from the FYERS API through a small serverless function on Vercel. Nothing runs on your own computer.

## What it does
- Estimates annualized expected returns and covariance (sample or Ledoit-Wolf) from price or return history.
- Objectives: maximum Sharpe, minimum variance, target return, target volatility, mean-variance utility.
- Per-asset weight bounds, optional short selling, efficient frontier chart, correlation heatmap, and a rebalancing column against current weights.
- Loads data from FYERS (daily candles, resampled to weekly or monthly), or from any CSV with a date column and one price (or return) column per asset.

## How it fits together
- `index.html` is the whole app.
- `api/fyers.js` is a Vercel function with three actions: `config` (builds the FYERS login URL), `token` (exchanges the login code for an access token using your app secret) and `history` (forwards a daily-candle request). The secret stays on the server. The access token lives in the browser tab for the day and is sent with each history request, never stored on the server.
- `fetch_fyers.py` is an optional command-line alternative that writes a prices CSV.

## Set up (once)
1. Create an app at [myapi.fyers.in](https://myapi.fyers.in) and note the app ID and secret.
2. Import this repo into Vercel (Add New, Project). Vercel serves `index.html` and deploys `api/fyers.js` automatically.
3. In the Vercel project, add environment variables `FYERS_CLIENT_ID` (the app ID) and `FYERS_SECRET_KEY`, then redeploy.
4. In the FYERS app settings, set the redirect URL to your site address with a trailing slash, for example `https://mvo.vercel.app/`. To use a different address, set `FYERS_REDIRECT_URI` in Vercel to match.

## Each trading day
Open the site, click **Log in with FYERS**, sign in, and you land back on the page connected. Enter symbols and click **Fetch from FYERS**. A plain name such as `RELIANCE` means `NSE:RELIANCE-EQ`.

Daily prices are saved in your browser. Adding a symbol and clicking Fetch requests only the new symbol; changing the frequency requests nothing; a longer history or a new trading day requests only the missing days. **Re-fetch all listed symbols** ignores the saved data. Today's candle is left out until the next day so a half-finished day never gets saved.

## Notes
- FYERS tokens last one trading day, so one login click per day is needed.
- Weekly and monthly prices are the last close of each period. Whether FYERS prices reflect dividends was not verified, so check before relying on total-return estimates.
- Weights are very sensitive to expected-return estimates. This is an analysis tool, not financial advice.
