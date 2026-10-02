"""
Portfolio status report -- the "portfolio management system" half of this
repo. Reuses the exact scoring/analysis functions already built and tested
in portfolio_management_system.py (same rubric, same category names), just
pointed at repo-native CSV inputs instead of the local xlsx tracker.

What's auto-computed here (objective, from your holdings.csv):
  - Diversification across uncorrelated themes -- suggested sub-score
  - Single-position concentration risk          -- suggested sub-score
  via the HHI/theme-weight math in portfolio_management_system.analyze_holdings().

What's NOT auto-computed (these stay your judgment call, same as always):
  Quality/stability mix, Leverage/instrument-risk, Known open red flags
  (score), Thematic conviction quality. This report surfaces the currently
  OPEN red flags from red_flags.csv so you have that input in front of you,
  but it doesn't convert "N open flags" into a score for you -- how much an
  open flag should cost the portfolio is exactly the kind of judgment call
  this whole project has been careful not to automate away.
"""
import csv

from portfolio_management_system import analyze_holdings, format_holdings_analysis
import red_flags_store


def load_holdings(path):
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            # tolerate the template's leading '#'-commented instruction rows
            if not row.get("ticker") or row["ticker"].strip().startswith("#"):
                continue
            rows.append({
                "ticker": row["ticker"].strip().upper(),
                "value": float(row["value"]),
                "theme": row["theme"].strip(),
            })
    return rows


def generate(holdings_path, red_flags_path):
    holdings = load_holdings(holdings_path)
    if not holdings:
        return {"error": f"No holdings found in {holdings_path} -- edit it with your real positions."}

    analysis = analyze_holdings(holdings)
    open_flags = [r for r in red_flags_store.list_flags(red_flags_path)
                  if "resolved" not in (r.get("Status") or "").lower()]

    return {"holdings_analysis": analysis, "open_flags": open_flags, "n_holdings": len(holdings)}


def format_report(report):
    if "error" in report:
        return report["error"]
    lines = [format_holdings_analysis(report["holdings_analysis"]), ""]
    if report["open_flags"]:
        lines.append(f"Open red flags ({len(report['open_flags'])}):")
        for f in report["open_flags"]:
            lines.append(f"  [{f['Ticker']}] {f['Flag']} -- {f['Status']} "
                          f"(last checked {f['Last Checked']})")
    else:
        lines.append("No open red flags on file.")
    lines.append("")
    lines.append("Quality/stability mix, Leverage, Known-flags SCORE, and Thematic conviction "
                  "quality are not auto-scored here -- those stay a judgment call. Ask Claude "
                  "to log a full 7-category Portfolio Construction Score against these holdings.")
    return "\n".join(lines)
