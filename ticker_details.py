#!/usr/bin/env python3
"""
Post-scan step for the dashboard's expanded ticker view.

Reads results/latest.json (written by run_daily_scan.py) and, for every
candidate in it, writes results/tickers/<TICKER>.json with:
  - profile   name, exchange, country, sector, industry, business summary
  - stats     the raw inputs behind the mechanical scorecard (growth,
              operating margin, FCF margin, net cash, P/E, P/S, beta, D/E)
              plus market cap, price, 52-week range, average volume
  - bars      ~1 year of daily OHLCV (oldest -> newest)
  - news      latest headlines (title, publisher, time, url)
  - insiders  recent insider transactions

Purely descriptive data -- nothing here is scored or interpreted. A ticker
that fails is logged and skipped; it never stops the run. Files for
tickers no longer in the scan are removed so the folder mirrors latest.json.

Usage (after run_daily_scan.py):
    python3 ticker_details.py
"""
import argparse
import datetime
import glob
import json
import math
import os
import time


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _str(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    s = str(v).strip()
    return s or None


def _bars(t, period):
    df = t.history(period=period, interval="1d", auto_adjust=False)
    if df is None or df.empty:
        return []
    out = []
    for idx, r in df.iterrows():
        c = _num(r["Close"])
        if c is None:
            continue
        out.append({
            "d": idx.strftime("%Y-%m-%d"),
            "o": round(_num(r["Open"]) or c, 4),
            "h": round(_num(r["High"]) or c, 4),
            "l": round(_num(r["Low"]) or c, 4),
            "c": round(c, 4),
            "v": int(_num(r["Volume"]) or 0),
        })
    return out


def _stats(info):
    fcf, rev = _num(info.get("freeCashflow")), _num(info.get("totalRevenue"))
    cash, debt = _num(info.get("totalCash")), _num(info.get("totalDebt"))
    dte = _num(info.get("debtToEquity"))
    if dte is not None and dte > 5:  # same normalization as quant_scorer.py
        dte = dte / 100
    return {
        "price": _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice")),
        "marketCap": _num(info.get("marketCap")),
        "revenueGrowth": _num(info.get("revenueGrowth")),
        "operatingMargins": _num(info.get("operatingMargins")),
        "fcfMargin": (fcf / rev) if fcf is not None and rev else None,
        "netCash": ((cash or 0) - (debt or 0)) if cash is not None or debt is not None else None,
        "trailingPE": _num(info.get("trailingPE")),
        "priceToSales": _num(info.get("priceToSalesTrailing12Months")),
        "beta": _num(info.get("beta")),
        "debtToEquity": dte,
        "fiftyTwoWeekLow": _num(info.get("fiftyTwoWeekLow")),
        "fiftyTwoWeekHigh": _num(info.get("fiftyTwoWeekHigh")),
        "avgVolume": _num(info.get("averageVolume")) or _num(info.get("averageDailyVolume10Day")),
    }


def _profile(info):
    return {
        "name": _str(info.get("longName")) or _str(info.get("shortName")),
        "exchange": _str(info.get("fullExchangeName")) or _str(info.get("exchange")),
        "country": _str(info.get("country")),
        "sector": _str(info.get("sector")),
        "industry": _str(info.get("industry")),
        "website": _str(info.get("website")),
        "summary": _str(info.get("longBusinessSummary")),
    }


def _news(t, n):
    """Handles both yfinance news shapes (flat legacy items and the newer
    {"content": {...}} items)."""
    try:
        items = t.news or []
    except Exception:
        return []
    out = []
    for item in items:
        c = item.get("content") or item
        title = _str(c.get("title"))
        if not title:
            continue
        prov = c.get("provider")
        publisher = (prov.get("displayName") if isinstance(prov, dict) else None) or c.get("publisher")
        url = ((c.get("canonicalUrl") or {}).get("url")
               or (c.get("clickThroughUrl") or {}).get("url")
               or c.get("link"))
        when = c.get("pubDate") or c.get("displayTime")
        if not when and c.get("providerPublishTime"):
            when = datetime.datetime.utcfromtimestamp(c["providerPublishTime"]).isoformat() + "Z"
        out.append({"time": when, "title": title, "publisher": _str(publisher), "url": _str(url)})
        if len(out) >= n:
            break
    return out


def _insiders(t, n):
    try:
        df = t.insider_transactions
    except Exception:
        return []
    if df is None or getattr(df, "empty", True):
        return []
    out = []
    for _, r in df.head(n).iterrows():
        d = r.get("Start Date")
        out.append({
            "date": d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else _str(d),
            "insider": _str(r.get("Insider")),
            "position": _str(r.get("Position")),
            "transaction": _str(r.get("Transaction")) or _str(r.get("Text")),
            "shares": _num(r.get("Shares")),
            "value": _num(r.get("Value")),
            "url": _str(r.get("URL")),
        })
    return out


def fetch_details(ticker, period="1y", n_news=10, n_insiders=15):
    import yfinance as yf
    t = yf.Ticker(ticker)
    info = t.info or {}
    return {
        "ticker": ticker,
        "generated_at_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "profile": _profile(info),
        "stats": _stats(info),
        "bars": _bars(t, period),
        "news": _news(t, n_news),
        "insiders": _insiders(t, n_insiders),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in-json", default="results/latest.json")
    p.add_argument("--out-dir", default="results/tickers")
    p.add_argument("--period", default="1y")
    p.add_argument("--news", type=int, default=10)
    p.add_argument("--insiders", type=int, default=15)
    p.add_argument("--sleep", type=float, default=0.4)
    p.add_argument("--retries", type=int, default=2)
    args = p.parse_args()

    with open(args.in_json) as f:
        snap = json.load(f)
    tickers = [c["ticker"] for c in snap.get("candidates", [])]
    os.makedirs(args.out_dir, exist_ok=True)

    keep = set(tickers)
    for path in glob.glob(os.path.join(args.out_dir, "*.json")):
        if os.path.splitext(os.path.basename(path))[0] not in keep:
            os.remove(path)

    ok, failed = 0, []
    for i, tk in enumerate(tickers, 1):
        for attempt in range(args.retries + 1):
            try:
                data = fetch_details(tk, args.period, args.news, args.insiders)
                with open(os.path.join(args.out_dir, f"{tk}.json"), "w") as f:
                    json.dump(data, f, separators=(",", ":"), default=str)
                ok += 1
                break
            except Exception as e:
                if attempt < args.retries:
                    time.sleep(2.0)
                    continue
                print(f"  [ticker_details] WARNING: {tk} failed: {e}")
                failed.append(tk)
        time.sleep(args.sleep)
        if i % 25 == 0:
            print(f"  [ticker_details] {i}/{len(tickers)}")

    print(f"Wrote {ok} ticker files to {args.out_dir}" + (f"; failed: {', '.join(failed)}" if failed else ""))


if __name__ == "__main__":
    main()
