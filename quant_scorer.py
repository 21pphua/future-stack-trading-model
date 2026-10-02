"""
Mechanical, partial Future-Stack scorer.

Peter chose the free/mechanical-only path: this auto-scores ONLY the
Future-Stack v2.7 categories that are honestly derivable from raw numbers.
It never guesses at the qualitative ones -- those need an actual read of
the business (moat, management, sector thesis, proof points) that no
threshold on a financial ratio can substitute for. Calling that out loudly
is the whole point of doing this mechanically instead of faking it.

Quantitative categories auto-scored here (cap 47 of the rubric's 100):
  Revenue Quality & Growth        /12  -- trailing revenue growth rate
  Margin Path / Unit Economics    /10  -- operating margin level
  FCF & Balance Sheet             /12  -- FCF margin + net cash/debt position
  Valuation                        /8  -- P/S (or P/E when sane) vs. simple bands
  Macro / Rate Sensitivity          /5  -- beta + leverage as a rate-sensitivity proxy

Left for manual/qualitative review (cap 53 of the rubric's 100):
  Structural Sector Future        /10
  Future-Stack Role                /7
  Durable Moat                    /14
  Management & Capital Allocation   /8
  Proof / Milestone Quality       /14

Every threshold below is a simple, documented, retunable rule -- not a
black box. Treat the output as a rough first-pass filter, not a verdict.
"""
from future_stack_model import CATEGORIES

QUANT_CATEGORIES = [
    "Revenue Quality & Growth",
    "Margin Path / Unit Economics",
    "FCF & Balance Sheet",
    "Valuation",
    "Macro / Rate Sensitivity",
]
QUANT_CAPS = {name: cap for name, cap in CATEGORIES if name in QUANT_CATEGORIES}
QUANT_CAP_TOTAL = sum(QUANT_CAPS.values())  # 47

QUALITATIVE_CATEGORIES = [(name, cap) for name, cap in CATEGORIES if name not in QUANT_CATEGORIES]
QUALITATIVE_CAP_TOTAL = sum(cap for _, cap in QUALITATIVE_CATEGORIES)  # 53
assert QUANT_CAP_TOTAL + QUALITATIVE_CAP_TOTAL == 100


def _na(reason):
    return {"score": None, "reason": reason}


def score_revenue_growth(f):
    g = f.get("revenueGrowth")
    if g is None:
        return _na("revenueGrowth not reported")
    if g >= 0.40:
        s = 12
    elif g >= 0.25:
        s = 10
    elif g >= 0.15:
        s = 8
    elif g >= 0.08:
        s = 6
    elif g >= 0:
        s = 4
    else:
        s = 2
    return {"score": s, "reason": f"trailing revenue growth {g:.1%}"}


def score_margin_path(f):
    m = f.get("operatingMargins")
    if m is None:
        return _na("operatingMargins not reported")
    if m >= 0.25:
        s = 10
    elif m >= 0.15:
        s = 8
    elif m >= 0.05:
        s = 6
    elif m >= 0:
        s = 4
    elif m >= -0.15:
        s = 2
    else:
        s = 1
    return {"score": s, "reason": f"operating margin {m:.1%}"}


def score_fcf_balance_sheet(f):
    fcf = f.get("freeCashflow")
    rev = f.get("totalRevenue")
    cash = f.get("totalCash")
    debt = f.get("totalDebt")
    if fcf is None or not rev:
        return _na("freeCashflow/totalRevenue not reported")
    fcf_margin = fcf / rev
    net_cash_position = (cash or 0) - (debt or 0) >= 0
    if fcf_margin >= 0.20 and net_cash_position:
        s = 12
    elif fcf_margin >= 0.10:
        s = 9
    elif fcf_margin >= 0:
        s = 6
    elif net_cash_position:
        s = 4
    else:
        s = 2
    return {"score": s, "reason": f"FCF margin {fcf_margin:.1%}, "
                                  f"{'net cash' if net_cash_position else 'net debt'} position"}


def score_valuation(f):
    pe = f.get("trailingPE")
    ps = f.get("priceToSalesTrailing12Months")
    metric_used, value = None, None
    if pe is not None and pe > 0:
        metric_used, value = "P/E", pe
        bands = [(15, 8), (25, 6), (40, 4), (70, 2)]
    elif ps is not None:
        metric_used, value = "P/S", ps
        bands = [(3, 8), (6, 6), (10, 4), (20, 2)]
    else:
        return _na("neither trailingPE nor priceToSalesTrailing12Months reported")
    s = 1
    for threshold, score in bands:
        if value <= threshold:
            s = score
            break
    return {"score": s, "reason": f"{metric_used} = {value:.1f}"}


def score_macro_rate_sensitivity(f):
    beta = f.get("beta")
    dte = f.get("debtToEquity")
    if beta is None and dte is None:
        return _na("neither beta nor debtToEquity reported")
    beta = beta if beta is not None else 1.0
    dte = dte if dte is not None else 0.0
    # debtToEquity from yfinance is typically a percentage-like number (e.g. 45.2 = 0.452x) -- normalize.
    dte_ratio = dte / 100 if dte > 5 else dte
    if beta < 1.2 and dte_ratio < 0.5:
        s = 5
    elif beta < 1.8 and dte_ratio < 1.5:
        s = 3
    else:
        s = 1
    return {"score": s, "reason": f"beta {beta:.2f}, debt/equity ~{dte_ratio:.2f}x"}


SCORERS = {
    "Revenue Quality & Growth": score_revenue_growth,
    "Margin Path / Unit Economics": score_margin_path,
    "FCF & Balance Sheet": score_fcf_balance_sheet,
    "Valuation": score_valuation,
    "Macro / Rate Sensitivity": score_macro_rate_sensitivity,
}


def auto_score_quantitative(ticker, fundamentals):
    """
    fundamentals: dict as returned by market_data.fetch_fundamentals().
    Returns a dict: per-category {score, reason} (score is None when data
    was missing -- NOT zero, so a missing field is visibly distinct from a
    genuinely bad score), a quant_total (sum of the ones that resolved),
    a quant_cap_achieved (sum of caps for categories that actually scored,
    so a name with gappy data isn't unfairly compared against the full 47),
    and the qualitative categories left as pending.
    """
    details = {name: fn(fundamentals) for name, fn in SCORERS.items()}
    resolved = {k: v for k, v in details.items() if v["score"] is not None}
    quant_total = sum(v["score"] for v in resolved.values())
    quant_cap_achieved = sum(QUANT_CAPS[k] for k in resolved)
    missing = [k for k, v in details.items() if v["score"] is None]
    return {
        "ticker": ticker.strip().upper(),
        "quant_details": details,
        "quant_total": quant_total,
        "quant_cap_achieved": quant_cap_achieved,
        "quant_cap_full": QUANT_CAP_TOTAL,
        "missing_data_categories": missing,
        "qualitative_pending": QUALITATIVE_CATEGORIES,
        "qualitative_cap_total": QUALITATIVE_CAP_TOTAL,
    }


def format_quant_result(result):
    lines = [f"{result['ticker']} -- mechanical partial score: "
             f"{result['quant_total']}/{result['quant_cap_achieved']} "
             f"(of a possible {result['quant_cap_full']}-pt quantitative subset)"]
    for name in QUANT_CATEGORIES:
        d = result["quant_details"][name]
        cap = QUANT_CAPS[name]
        if d["score"] is None:
            lines.append(f"  {name:<32} N/A/{cap}   ({d['reason']})")
        else:
            lines.append(f"  {name:<32} {d['score']:>3}/{cap}   ({d['reason']})")
    if result["missing_data_categories"]:
        lines.append(f"  (missing data for: {', '.join(result['missing_data_categories'])} "
                      f"-- excluded from the achieved-cap denominator above, not scored as zero)")
    lines.append(f"  STILL NEEDS YOUR MANUAL REVIEW ({result['qualitative_cap_total']} pts, not auto-scored):")
    for name, cap in result["qualitative_pending"]:
        lines.append(f"    {name} /{cap}")
    return "\n".join(lines)
