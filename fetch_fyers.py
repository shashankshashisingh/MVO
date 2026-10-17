#!/usr/bin/env python3
"""Download daily price history from the FYERS API (v3) and save a CSV for the optimizer.

One-time setup
    pip install fyers-apiv3
    export FYERS_CLIENT_ID="XXXXXXXX-100"        # your app ID from myapi.fyers.in
    export FYERS_SECRET_KEY="..."                 # your app secret
    export FYERS_REDIRECT_URI="https://127.0.0.1" # must match the app's redirect URL

Each trading day
    python3 fetch_fyers.py --login                # opens a login URL, you paste back the redirected URL
    python3 fetch_fyers.py RELIANCE TCS HDFCBANK --years 5 --freq monthly --out prices.csv

Symbols: a plain name such as RELIANCE becomes NSE:RELIANCE-EQ. Anything containing a colon
is sent as written (e.g. NSE:NIFTYBEES-EQ, NSE:NIFTY50-INDEX, BSE:SENSEX-INDEX).

FYERS returns daily candles; weekly and monthly series are built here from the last close of each
period. Prices are as FYERS reports them, so check whether dividends are reflected before relying
on total-return estimates.
Load the CSV in the optimizer under "Load the prices file" (type: Prices).
"""
import argparse, csv, json, os, sys, time, urllib.parse
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
CHUNK_DAYS = 365          # conservative window for daily candles
PAUSE = 0.4               # seconds between requests, to stay under the rate limit
TOKEN_FILE = os.path.expanduser("~/.fyers_token.json")


def normalize(sym):
    s = sym.strip().upper()
    return s if ":" in s else f"NSE:{s}-EQ"


def period_key(d, freq):
    if freq == "monthly":
        return d.strftime("%Y-%m")
    if freq == "weekly":
        return (d - timedelta(days=d.weekday())).isoformat()
    return d.isoformat()


def get_daily(fy, symbol, start, end, pause=PAUSE):
    """Return {date: close} for [start, end], requesting at most CHUNK_DAYS per call."""
    out = {}
    cur = start
    while cur <= end:
        stop = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        resp = fy.history(data={
            "symbol": symbol, "resolution": "1D", "date_format": "1",
            "range_from": cur.isoformat(), "range_to": stop.isoformat(), "cont_flag": "1",
        })
        if not isinstance(resp, dict) or resp.get("s") != "ok":
            msg = (resp or {}).get("message") if isinstance(resp, dict) else str(resp)
            raise RuntimeError(f"{symbol}: {msg or 'request failed'}")
        for c in resp.get("candles") or []:
            d = datetime.fromtimestamp(c[0], tz=timezone.utc).astimezone(IST).date()
            if c[4] and c[4] > 0:
                out[d] = float(c[4])          # duplicates: the later candle wins
        cur = stop + timedelta(days=1)
        if cur <= end:
            time.sleep(pause)
    return out


def resample(daily, freq, today=None):
    """Last close of each period. The still-forming week or month is dropped."""
    if freq == "daily":
        return {d.isoformat(): p for d, p in sorted(daily.items())}
    today = today or datetime.now(IST).date()
    now_key = period_key(today, freq)
    last = {}
    for d in sorted(daily):
        last[period_key(d, freq)] = daily[d]
    last.pop(now_key, None)
    return last


def write_csv(series, path):
    keys = sorted(set.intersection(*(set(s) for s in series.values())))
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Date"] + list(series))
        for k in keys:
            w.writerow([k] + [round(series[t][k], 6) for t in series])
    return len(keys)


# ---------- authentication ----------
def login():
    from fyers_apiv3 import fyersModel
    cid, secret, redirect = (os.environ.get(k) for k in ("FYERS_CLIENT_ID", "FYERS_SECRET_KEY", "FYERS_REDIRECT_URI"))
    if not (cid and secret and redirect):
        sys.exit("Set FYERS_CLIENT_ID, FYERS_SECRET_KEY and FYERS_REDIRECT_URI first (see the top of this file).")
    sess = fyersModel.SessionModel(client_id=cid, secret_key=secret, redirect_uri=redirect,
                                   response_type="code", grant_type="authorization_code", state="mvo")
    print("Open this URL, log in, then copy the full address you are redirected to:\n")
    print(sess.generate_authcode(), "\n")
    pasted = input("Paste the redirected URL (or just the auth_code value): ").strip()
    code = pasted
    if "auth_code=" in pasted:
        code = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query).get("auth_code", [""])[0]
    sess.set_token(code)
    resp = sess.generate_token()
    token = resp.get("access_token")
    if not token:
        sys.exit(f"Login failed: {resp.get('message') or resp}")
    with open(TOKEN_FILE, "w") as f:
        json.dump({"client_id": cid, "token": token, "date": date.today().isoformat()}, f)
    os.chmod(TOKEN_FILE, 0o600)
    print(f"Token saved to {TOKEN_FILE}. It is valid for today only.")


def load_token():
    cid = os.environ.get("FYERS_CLIENT_ID", "")
    token = os.environ.get("FYERS_ACCESS_TOKEN", "")
    if cid and token:
        return cid, token
    try:
        with open(TOKEN_FILE) as f:
            t = json.load(f)
        if t.get("date") != date.today().isoformat():
            sys.exit("The saved token is from an earlier day. Run: python3 fetch_fyers.py --login")
        return t["client_id"], t["token"]
    except FileNotFoundError:
        sys.exit("No token found. Run: python3 fetch_fyers.py --login")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("symbols", nargs="*")
    ap.add_argument("--login", action="store_true", help="get today's access token")
    ap.add_argument("--years", type=float, default=5)
    ap.add_argument("--freq", choices=["daily", "weekly", "monthly"], default="monthly")
    ap.add_argument("--out", default="prices.csv")
    a = ap.parse_args()
    if a.login:
        return login()
    if len(a.symbols) < 2:
        sys.exit("Give at least two symbols, or use --login.")
    from fyers_apiv3 import fyersModel
    cid, token = load_token()
    fy = fyersModel.FyersModel(client_id=cid, token=token, is_async=False, log_path="")
    end = datetime.now(IST).date()
    start = end - timedelta(days=int(a.years * 365.25))
    series, failed = {}, []
    for raw in dict.fromkeys(normalize(s) for s in a.symbols):
        try:
            daily = get_daily(fy, raw, start, end)
            series[raw] = resample(daily, a.freq)
            print(f"ok    {raw}: {len(daily)} daily candles -> {len(series[raw])} {a.freq} prices")
        except Exception as e:
            failed.append(raw)
            print(f"FAIL  {e}", file=sys.stderr)
        time.sleep(PAUSE)
    if len(series) < 2:
        sys.exit("Need at least two symbols with data.")
    n = write_csv(series, a.out)
    print(f"Wrote {n} rows x {len(series)} symbols to {a.out}" + (f" (left out: {', '.join(failed)})" if failed else ""))


if __name__ == "__main__":
    main()
