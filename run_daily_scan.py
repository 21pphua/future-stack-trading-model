#!/usr/bin/env python3
"""
Orchestrator -- the script the GitHub Actions workflow actually runs.

This repo is the Future-Stack Trading Model, and only the Future-Stack
Trading Model. Candidate selection is driven entirely by Future-Stack's own
mechanical scorecard (quant_scorer.py) -- a stock is "picked" because its
financial ratios score well against the Future-Stack v2.7 rubric, full
stop. There is no technical/price-pattern system (momentum, breakout, SAR,
or anything else) anywhere in this repo -- just conviction, built from the
scorecard's financial-ratio categories.

1. Scores every ticker in universe.csv (your curated, thematically-tagged
   watchlist) against the Future-Stack mechanical rubric (quant_scorer.py),
   using fundamentals pulled via market_data.py.
2. UNLESS --no-broad-scan is passed, also does the same thing across the
   broad US equity market: pulls the full list of US-listed tickers, narrows
   it to a liquid subset (plain price/dollar-volume floor -- not a trading
   signal, just a "can you actually trade this" filter), then scores each
   survivor the same way. This is what finds names you never put on your
   watchlist -- universe.csv alone only ever re-checks names you already
   picked.
3. A ticker is only surfaced as a "candidate" in the report if its
   Future-Stack mechanical score clears a configurable bar (see
   --min-quant-pct / --broad-min-quant-pct below). Your curated watchlist
   defaults to showing everything (you picked those names for a reason);
   the broad market defaults to a real bar, since otherwise a liquid-enough
   universe is thousands of names.
4. Builds the portfolio status report from holdings.csv + red_flags.csv
   (portfolio_report.py).
5. Writes two output files:
     - report.md           human-readable, used as the GitHub Issue body.
     - results/latest.json  machine-readable snapshot of the same run,
                            timestamped, meant to be committed back to the
                            repo so something OUTSIDE this run (e.g. a
                            Claude artifact dashboard reading the raw file
                            from GitHub) can pick up the latest results
                            without needing any API key of its own.

Every number in the output is traceable to a specific rule in
quant_scorer.py / portfolio_report.py -- nothing here is an LLM guess, and
nothing here is a technical/price-pattern signal from a different system.
"""
import argparse
import datetime
import json
import os
import sys
import time

import market_data
import quant_scorer
import portfolio_report

GOLDEN_RULE = ("Golden Rule: every score above measures structural quality/risk. "
               "It is never a buy or sell signal, and this scan recommends nothing.")


def load_universe(path):
    import csv
    with open(path, newline="") as f:
        return [(row["ticker"].strip().upper(), row["theme"].strip())
                for row in csv.DictReader(f) if row.get("ticker")]


def _quant_pct(quant):
    """Mechanical score achieved as a fraction of what was actually
    measurable for this ticker (same denominator the dashboard's progress
    bar uses) -- the one and only bar for "is this worth surfacing"."""
    cap = quant.get("quant_cap_achieved") or 0
    if cap <= 0:
        return 0.0
    return quant["quant_total"] / cap


def run_scan(universe_path, sleep_between=0.3, limit=None, min_quant_pct=0.0):
    """
    Scores every ticker in your curated watchlist against the Future-Stack
    mechanical rubric. Default min_quant_pct=0.0 means every curated name
    shows up in the report (you picked this list on purpose); raise it if
    you'd rather only see your watchlist names that are currently scoring
    well.
    """
    universe = load_universe(universe_path)
    if limit:
        universe = universe[:limit]

    candidates = []
    errors = []
    for ticker, theme in universe:
        fundamentals = market_data.fetch_fundamentals(ticker)
        time.sleep(sleep_between)
        if fundamentals is None:
            errors.append(ticker)
            continue
        quant = quant_scorer.auto_score_quantitative(ticker, fundamentals)
        if _quant_pct(quant) < min_quant_pct:
            continue
        candidates.append({"ticker": ticker, "theme": theme, "quant": quant, "source": "curated"})

    candidates.sort(key=lambda c: c["quant"]["quant_total"], reverse=True)
    return candidates, errors


def run_broad_scan(exclude_tickers, min_price=3.0, min_avg_dollar_vol=5_000_000,
                    max_universe=None, liquidity_batch_size=150, min_quant_pct=0.55,
                    max_liquid=None, sleep_between=0.2):
    """
    The broad-market discovery pass: full ticker list -> liquidity
    pre-filter (a basic "can you actually trade this" floor, not a scoring
    signal) -> Future-Stack mechanical score on each survivor, on names NOT
    already in the curated universe.csv (no point double-scanning those).
    Theme is taken from the ticker's own sector/industry when available,
    since there's no hand-picked theme tag for a name nobody chose.

    min_quant_pct is a real bar here (default 0.55 = the name needs to
    clear 55% of its achievable mechanical points) -- otherwise every
    liquid-enough ticker in the market would show up, which is thousands
    of names, not a useful "candidates" list.

    max_liquid caps how many liquidity-cleared tickers actually get a
    (slower) fundamentals fetch + score -- a safety valve for a quick
    manual test, separate from max_universe (which caps the pool before
    the liquidity filter even runs).

    Returns (candidates, errors, n_universe, n_liquid) -- the last two are
    reported so a failed/empty broad scan is visible, not silently blank.
    """
    full_universe = market_data.fetch_full_universe()
    if full_universe is None:
        print("  [run_broad_scan] WARNING: could not fetch the broad ticker list at all -- "
              "skipping the broad scan this run, curated watchlist results are unaffected.")
        return [], [], 0, 0

    candidates_pool = [t for t in full_universe if t not in exclude_tickers]
    if max_universe:
        candidates_pool = candidates_pool[:max_universe]
    n_universe = len(candidates_pool)
    print(f"  [run_broad_scan] {n_universe} tickers to liquidity-check (after excluding your watchlist)")

    liquid = market_data.bulk_liquidity_filter(
        candidates_pool, batch_size=liquidity_batch_size,
        min_price=min_price, min_avg_dollar_vol=min_avg_dollar_vol,
    )
    if max_liquid:
        liquid = liquid[:max_liquid]
    n_liquid = len(liquid)
    print(f"  [run_broad_scan] {n_liquid} tickers cleared the liquidity floor "
          f"(price >= ${min_price}, avg dollar volume >= ${min_avg_dollar_vol:,.0f}) "
          f"-- scoring each against the Future-Stack mechanical rubric now")

    candidates = []
    errors = []
    for ticker in liquid:
        fundamentals = market_data.fetch_fundamentals(ticker)
        time.sleep(sleep_between)
        if fundamentals is None:
            errors.append(ticker)
            continue
        quant = quant_scorer.auto_score_quantitative(ticker, fundamentals)
        if _quant_pct(quant) < min_quant_pct:
            continue
        theme = fundamentals.get("sector") or fundamentals.get("industry") or "Broad Scan"
        candidates.append({"ticker": ticker, "theme": theme, "quant": quant, "source": "broad_scan"})

    candidates.sort(key=lambda c: c["quant"]["quant_total"], reverse=True)
    return candidates, errors, n_universe, n_liquid


def format_markdown(candidates, errors, port_report, as_of, broad_stats=None, broad_min_quant_pct=0.55):
    lines = [f"# Daily Scan -- {as_of}", ""]
    lines.append("_Future-Stack Trading Model only -- candidates are picked purely by the "
                  "Future-Stack mechanical scorecard below. No separate technical/price-pattern "
                  "system (momentum, breakout, SAR, or otherwise) is used anywhere in this repo._")

    if broad_stats:
        n_universe, n_liquid = broad_stats
        if n_universe:
            lines.append(f"\n_Broad scan: {n_universe} market tickers checked, {n_liquid} cleared the "
                          f"liquidity floor and were scored against the Future-Stack mechanical rubric; "
                          f"only those clearing {broad_min_quant_pct:.0%} of their achievable points are "
                          f"listed below._")
        else:
            lines.append("\n_Broad scan: could not fetch the market-wide ticker list this run -- "
                          "see job log. Curated watchlist results below are unaffected._")

    lines.append("\n## Candidates")
    if not candidates:
        lines.append("\nNo candidates cleared the Future-Stack mechanical bar today.")
    else:
        for c in candidates:
            tag = " (discovered)" if c.get("source") == "broad_scan" else ""
            pct = _quant_pct(c["quant"])
            lines.append(f"\n### {c['ticker']} -- {c['theme']}{tag}")
            lines.append(f"Future-Stack mechanical score: {c['quant']['quant_total']}/"
                          f"{c['quant']['quant_cap_achieved']} ({pct:.0%} of achievable)")
            lines.append("```")
            lines.append(quant_scorer.format_quant_result(c["quant"]))
            lines.append("```")

    if errors:
        lines.append(f"\n_Could not fetch data for: {', '.join(errors)} (skipped, not scored as zero)._")

    lines.append("\n## Your Portfolio")
    lines.append(portfolio_report.format_report(port_report))

    lines.append(f"\n---\n{GOLDEN_RULE}")
    lines.append("\nThis scan is 100% mechanical (financial-ratio thresholds, plus a basic "
                  "price/liquidity floor for the broad-market pass) -- it does not judge moat, "
                  "management, proof points, or sector thesis. Treat every candidate above as a "
                  "research lead, not a conclusion.")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--universe", default="universe.csv")
    p.add_argument("--holdings", default="holdings.csv")
    p.add_argument("--red-flags", default="red_flags.csv")
    p.add_argument("--out-md", default="report.md")
    p.add_argument("--out-json", default="results/latest.json")
    p.add_argument("--limit", type=int, default=None, help="Cap the curated universe size (useful for a quick test run).")
    p.add_argument("--min-quant-pct", type=float, default=0.0,
                    help="Only show curated watchlist names scoring at least this fraction of their achievable Future-Stack points (default 0.0 = show all).")
    p.add_argument("--no-broad-scan", action="store_true",
                    help="Skip the market-wide discovery pass and only re-check universe.csv (fast, old behavior).")
    p.add_argument("--broad-max", type=int, default=None,
                    help="Cap how many non-watchlist tickers the broad scan even considers, before the liquidity filter (safety valve for a quick manual test).")
    p.add_argument("--broad-max-liquid", type=int, default=None,
                    help="Cap how many liquidity-cleared tickers actually get scored in the broad pass (a second safety valve, since scoring is the slower step).")
    p.add_argument("--broad-min-price", type=float, default=3.0)
    p.add_argument("--broad-min-dollar-vol", type=float, default=5_000_000)
    p.add_argument("--broad-min-quant-pct", type=float, default=0.55,
                    help="Only surface broad-market names scoring at least this fraction of their achievable Future-Stack points (default 0.55).")
    args = p.parse_args()

    as_of = datetime.date.today().isoformat()
    candidates, errors = run_scan(args.universe, limit=args.limit, min_quant_pct=args.min_quant_pct)

    broad_stats = None
    if not args.no_broad_scan:
        curated_tickers = {t for t, _ in load_universe(args.universe)}
        broad_candidates, broad_errors, n_universe, n_liquid = run_broad_scan(
            curated_tickers, min_price=args.broad_min_price,
            min_avg_dollar_vol=args.broad_min_dollar_vol, max_universe=args.broad_max,
            max_liquid=args.broad_max_liquid, min_quant_pct=args.broad_min_quant_pct,
        )
        candidates = candidates + broad_candidates
        candidates.sort(key=lambda c: c["quant"]["quant_total"], reverse=True)
        errors = errors + broad_errors
        broad_stats = (n_universe, n_liquid)

    port_report = portfolio_report.generate(args.holdings, args.red_flags)

    md = format_markdown(candidates, errors, port_report, as_of, broad_stats=broad_stats,
                          broad_min_quant_pct=args.broad_min_quant_pct)
    with open(args.out_md, "w") as f:
        f.write(md)
    print(f"Wrote {args.out_md}")

    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    snapshot = {
        "as_of": as_of,
        "generated_at_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "candidates": candidates,
        "scan_errors": errors,
        "broad_scan_stats": {"n_universe_checked": broad_stats[0], "n_liquid": broad_stats[1]} if broad_stats else None,
        "portfolio_report": port_report,
    }
    with open(args.out_json, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)
    print(f"Wrote {args.out_json}")


if __name__ == "__main__":
    main()
