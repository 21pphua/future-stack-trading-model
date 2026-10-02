"""
Thin, mockable wrapper around yfinance -- the only module in this repo that
touches live market data. Every other module takes plain dicts/lists so it
can be unit-tested with synthetic data, independent of network access.

NOTE ON TESTING: this specific module's live calls could NOT be executed
inside the sandbox that built this repo -- that sandbox's outbound network
policy blocks direct calls to Yahoo Finance endpoints AND to the Nasdaq
Trader symbol-directory host used by fetch_full_universe() below (both
confirmed via the proxy's own status endpoint, not guessed). GitHub
Actions' hosted runners have normal, unrestricted outbound internet access,
so this will work there. The functions below follow yfinance's and Nasdaq
Trader's standard, widely-used shapes; quant_scorer.py (the only consumer
of fetch_fundamentals) was tested end-to-end against synthetic data shaped
exactly like what these functions return.
"""
import time


def fetch_daily_bars(ticker, period="9mo", max_retries=2, retry_delay=2.0):
    """
    Returns a list of dicts: date, open, high, low, close, volume
    (oldest -> newest). Not used by the Future-Stack mechanical scan itself
    (that only needs fundamentals, not price history) -- kept here as a
    general-purpose utility in case you want daily bars for something else.
    Returns None (not an exception) if the ticker can't be fetched, so a
    single bad/delisted ticker never kills the whole scan.
    """
    import yfinance as yf

    for attempt in range(max_retries + 1):
        try:
            df = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)
            if df is None or df.empty:
                return None
            rows = []
            for idx, row in df.iterrows():
                rows.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                })
            return rows
        except Exception as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            print(f"  [market_data] WARNING: failed to fetch bars for {ticker}: {e}")
            return None


def fetch_fundamentals(ticker, max_retries=2, retry_delay=2.0):
    """
    Returns a plain dict of the fields quant_scorer.py needs, pulled from
    yfinance's `.info` (best-effort; any individual field can legitimately
    be missing for a given company and quant_scorer.py is written to treat
    a missing field as "insufficient data" for that sub-score rather than
    guessing). Returns None if the ticker can't be fetched at all.
    """
    import yfinance as yf

    fields = [
        "revenueGrowth", "grossMargins", "operatingMargins",
        "freeCashflow", "totalRevenue", "totalCash", "totalDebt",
        "trailingPE", "priceToSalesTrailing12Months", "beta", "debtToEquity",
        "marketCap", "averageDailyVolume10Day", "currentPrice",
        "sector", "industry",
    ]
    for attempt in range(max_retries + 1):
        try:
            info = yf.Ticker(ticker).info or {}
            return {f: info.get(f) for f in fields}
        except Exception as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            print(f"  [market_data] WARNING: failed to fetch fundamentals for {ticker}: {e}")
            return None


# ---------------------------------------------------------------------------
# Broad-market discovery: pull the full list of US-listed tickers, then
# narrow it down to a liquid subset before running the expensive per-ticker
# screen on it.
# ---------------------------------------------------------------------------

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDirectory/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDirectory/otherlisted.txt"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# nasdaqtrader.com will silently reject a request that doesn't look like it
# came from a real browser (no error, just an empty/garbage response) --
# this is the fix for a run that reported n_universe_checked: 0.
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/plain,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _parse_symbol_directory(text, symbol_col, test_issue_col, etf_col):
    """
    Nasdaq Trader's symbol-directory files: pipe-delimited, one header row,
    one 'File Creation Time' footer row to drop. Returns a set of plain
    equity tickers, excluding test issues and ETFs (quant_scorer's
    fundamentals-based categories don't apply meaningfully to a fund).
    """
    lines = [l for l in text.strip().splitlines() if l and not l.startswith("File Creation Time")]
    if not lines:
        return set()
    header = lines[0].split("|")
    rows = [dict(zip(header, line.split("|"))) for line in lines[1:]]
    out = set()
    for row in rows:
        sym = row.get(symbol_col, "").strip()
        if not sym or "$" in sym or "." in sym:
            continue  # warrants/units/preferred share classes use these in this feed
        if row.get(test_issue_col, "N").strip().upper() == "Y":
            continue
        if row.get(etf_col, "N").strip().upper() == "Y":
            continue
        out.add(sym)
    return out


def _fetch_sec_ticker_fallback(max_retries=2, retry_delay=2.0):
    """
    Fallback source if Nasdaq Trader's symbol directory can't be reached at
    all: the SEC's own free, public company-ticker list. It doesn't carry
    Nasdaq Trader's ETF/test-issue flags, so this is a strictly cruder list
    (a handful of ETFs may slip through), but it's a reliable second source
    so one blocked/down host doesn't take broad-market discovery to zero.
    The SEC asks callers to identify themselves with a real User-Agent
    (name + contact) in its fair-use policy -- that's what the header below
    is for, not a bot-block workaround.
    """
    import requests

    headers = dict(_BROWSER_HEADERS)
    headers["User-Agent"] = "trading-system-bot/1.0 (github.com/21pphua/trading-system-bot)"
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(SEC_TICKERS_URL, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            tickers = {
                row["ticker"].strip().upper() for row in data.values()
                if row.get("ticker") and "$" not in row["ticker"] and "." not in row["ticker"]
            }
            return sorted(tickers)
        except Exception as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            print(f"  [market_data] WARNING: SEC ticker-list fallback also failed: {e}")
            return None


def fetch_full_universe(max_retries=2, retry_delay=2.0):
    """
    Downloads Nasdaq Trader's two public, free, no-key symbol-directory
    files (NASDAQ-listed + everything else: NYSE, NYSE American, ARCA, ...)
    and returns a sorted list of plain equity tickers -- no ETFs, no test
    issues, no warrant/unit/preferred-class suffixes. This is the standard
    free source for "every US-listed ticker symbol"; there is no official
    API key needed. If BOTH Nasdaq Trader files fail (e.g. a blocked/garbage
    response), falls back to the SEC's public ticker list before giving up
    entirely. Returns None only if that fallback also fails.
    """
    import requests

    tickers = set()
    got_any = False
    for url, sym_col, test_col, etf_col in [
        (NASDAQ_LISTED_URL, "Symbol", "Test Issue", "ETF"),
        (OTHER_LISTED_URL, "ACT Symbol", "Test Issue", "ETF"),
    ]:
        for attempt in range(max_retries + 1):
            try:
                resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=30)
                resp.raise_for_status()
                parsed = _parse_symbol_directory(resp.text, sym_col, test_col, etf_col)
                if not parsed:
                    raise ValueError("response parsed to zero tickers -- likely a blocked/garbage response, not a real empty list")
                tickers |= parsed
                got_any = True
                break
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    continue
                print(f"  [market_data] WARNING: failed to fetch {url}: {e}")

    if got_any:
        return sorted(tickers)

    print("  [market_data] Nasdaq Trader unreachable/blocked this run -- falling back to the SEC ticker list.")
    return _fetch_sec_ticker_fallback(max_retries=max_retries, retry_delay=retry_delay)


def bulk_liquidity_filter(tickers, batch_size=150, min_price=3.0,
                           min_avg_dollar_vol=5_000_000, pause_between_batches=1.5):
    """
    Cheap first pass over a large ticker list: pulls ~1 month of daily bars
    for many tickers per network call (yfinance's bulk download, far fewer
    round trips than one Ticker().history() per symbol) and keeps only
    names clearing a basic price/liquidity floor. Returns a sorted list of
    tickers that passed -- meant to run BEFORE the full 9-month fetch so
    the expensive per-ticker screen only runs on a liquid subset.
    A batch that errors is skipped (logged), never silently treated as
    "all failed tickers are illiquid".
    """
    import yfinance as yf

    passed = []
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        try:
            df = yf.download(batch, period="1mo", interval="1d", group_by="ticker",
                              threads=True, progress=False, auto_adjust=False)
        except Exception as e:
            print(f"  [market_data] WARNING: liquidity batch {i}-{i+len(batch)} failed: {e}")
            time.sleep(pause_between_batches)
            continue

        for t in batch:
            try:
                sub = df[t] if len(batch) > 1 else df
                closes = sub["Close"].dropna()
                vols = sub["Volume"].dropna()
                if closes.empty or vols.empty:
                    continue
                last_price = float(closes.iloc[-1])
                avg_dollar_vol = float((closes * vols).dropna().mean())
                if last_price >= min_price and avg_dollar_vol >= min_avg_dollar_vol:
                    passed.append(t)
            except Exception:
                continue  # this one ticker's slice was malformed -- skip, don't crash the batch
        time.sleep(pause_between_batches)

    return sorted(passed)


def fetch_daily_bars_bulk(tickers, period="9mo", batch_size=100, pause_between_batches=1.5):
    """
    Same idea as bulk_liquidity_filter but returns full OHLCV bars (the
    shape fetch_daily_bars() returns for one ticker) for many tickers at
    once. Returns a dict {ticker: bars_list_or_None}.
    """
    import yfinance as yf

    out = {}
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        try:
            df = yf.download(batch, period=period, interval="1d", group_by="ticker",
                              threads=True, progress=False, auto_adjust=False)
        except Exception as e:
            print(f"  [market_data] WARNING: bulk bars batch {i}-{i+len(batch)} failed: {e}")
            for t in batch:
                out[t] = None
            time.sleep(pause_between_batches)
            continue

        for t in batch:
            try:
                sub = df[t] if len(batch) > 1 else df
                sub = sub.dropna(subset=["Close"])
                if sub.empty:
                    out[t] = None
                    continue
                rows = []
                for idx, row in sub.iterrows():
                    rows.append({
                        "date": idx.strftime("%Y-%m-%d"),
                        "open": float(row["Open"]), "high": float(row["High"]),
                        "low": float(row["Low"]), "close": float(row["Close"]),
                        "volume": float(row["Volume"]),
                    })
                out[t] = rows
            except Exception:
                out[t] = None
        time.sleep(pause_between_batches)

    return out
