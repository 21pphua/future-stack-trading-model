# Future-Stack Trading Model

This repo is the **Future-Stack Trading Model**, full stop. Every candidate
it surfaces is picked and ranked purely by the mechanical half of the
Future-Stack v2.7 scorecard -- conviction, FUD-discount buys, long-term
holds. There is no technical/price-pattern trading system of any kind in
here (no momentum screen, no breakout pattern, no SAR logic) -- just the
scorecard's financial-ratio categories deciding what gets surfaced.

Two mechanical engines, one GitHub repo, running on a schedule:

1. **Future-Stack mechanical scorer** -- scores your curated watchlist
   (`universe.csv`) AND, by default, the whole US equity market against the
   *mechanical, partial* version of the Future-Stack v2.7 rubric, using
   nothing but financial ratios (revenue growth, margins, FCF, valuation,
   beta/leverage). A name only shows up as a "candidate" if its mechanical
   score clears a bar you control (see below) -- there's no price-chart
   pattern involved in picking or ranking anything.
2. **Portfolio report** -- analyzes your actual holdings (`holdings.csv`)
   for concentration/diversification, and surfaces currently open items
   from your Red Flag Log (`red_flags.csv`).

## Broad-market discovery (new)

`universe.csv` alone only ever re-checks names you already picked -- it
can't surface a stock you've never heard of. By default, every run now
ALSO does this: pulls the full list of US-listed stocks from Nasdaq
Trader's free public symbol directory (falling back automatically to the
SEC's public ticker list if Nasdaq Trader can't be reached that day -- no
API key or signup for either), excludes names already on your watchlist,
narrows that down to a liquid subset (price >= $3, average daily dollar
volume >= $5M by default -- both adjustable via `--broad-min-price` /
`--broad-min-dollar-vol`; this is just a "can you actually trade this"
floor, not a scoring signal), and scores every survivor against the exact
same Future-Stack mechanical rubric used for your watchlist. Only names
clearing `--broad-min-quant-pct` (default 55% of their achievable points)
show up in the report, tagged "(discovered)", with their theme taken from
the company's own sector/industry since nobody hand-picked one.

This is the heaviest part of the run -- every liquidity-cleared ticker gets
its own fundamentals fetch and a full Future-Stack score, not just a
pre-filtered handful, so expect anywhere from 20 minutes to well over an
hour depending on how many tickers clear the liquidity floor and how the
data source is behaving that day. Controls:
- `--no-broad-scan` skips this entirely and only re-checks `universe.csv`
  (the original, fast behavior).
- `--broad-max N` caps how many non-watchlist tickers it even considers,
  before the liquidity filter runs (useful for a quick manual test -- the
  "Run workflow" button on GitHub has a `broad_max` field for exactly
  this).
- `--broad-max-liquid N` caps how many liquidity-cleared tickers actually
  get scored -- a second safety valve, since scoring (one fundamentals
  fetch per ticker) is the slower step.
- `--broad-min-quant-pct 0.X` raises or lowers the "worth surfacing" bar
  for the broad pass; `--min-quant-pct 0.X` does the same for your
  curated watchlist (default 0.0 there, so every watchlist name always
  shows up).
- If the ticker-list fetch fails outright for the day (both Nasdaq Trader
  and the SEC fallback), the run logs a warning and simply skips the
  broad pass that day -- your curated watchlist results are never
  affected by it failing.

Every run opens a GitHub Issue with the results and commits a machine-readable
snapshot to `results/latest.json`.

## Setup (no API keys, no secrets)

1. Create a new GitHub repo and push everything in this folder to it.
2. Edit `holdings.csv` with your real positions (ticker, dollar value, theme).
   The shipped version is a placeholder.
3. Edit `universe.csv` if you want to add/remove names from the scan list
   (it ships with ~190 liquid names across AI infra, defense, nuclear/grid,
   cybersecurity, biotech, fintech, and more).
4. Enable GitHub Actions on the repo (Settings -> Actions -> allow). That's
   it -- `daily_scan.yml` runs on its own schedule (weekdays, ~4:30-5:30pm
   ET) and also has a manual "Run workflow" button in the Actions tab.

Nothing here needs an Anthropic API key, a GitHub personal access token, a
Slack/Discord webhook, or any paid data service -- it's open-source
(`yfinance`) data and GitHub's own built-in `GITHUB_TOKEN`.

## IMPORTANT: what "mechanical-only" scoring actually means

This was a deliberate choice (zero cost, zero API key) over having an LLM
do the scoring. The tradeoff: **this bot only scores the ~47 of 100
Future-Stack points that are honestly computable from raw numbers** --
revenue growth, margins, free cash flow/balance sheet, valuation, and a
beta/leverage proxy for rate sensitivity. It leaves the other 53 points
(Structural Sector Future, Future-Stack Role, Durable Moat, Management &
Capital Allocation, Proof/Milestone Quality) explicitly unscored and
flagged "needs manual review" in every report -- because those require an
actual read of the business that no financial-ratio threshold can replace.
Every candidate the scanner surfaces is a research lead, not a graded
stock. If you'd rather have the full rubric auto-filled (quantitative +
qualitative) by having an LLM do the qualitative read too, that's the
other path we discussed -- it needs an Anthropic API key in the repo's
secrets and has a small per-run cost; ask and this can be swapped in.

## Files

| File | What it does |
|---|---|
| `universe.csv` | The scan list (ticker, theme). Edit freely. |
| `holdings.csv` | Your real portfolio (ticker, value, theme). Edit before relying on it. |
| `red_flags.csv` | Red Flag Log, seeded from this session's prior research. |
| `market_data.py` | The only module that touches `yfinance`, the Nasdaq Trader symbol directory, or the SEC ticker-list fallback; everything else takes plain data so it's independently testable. |
| `quant_scorer.py` | The mechanical partial Future-Stack scorer -- the one and only thing that decides what counts as a candidate. |
| `portfolio_report.py` | Holdings concentration/diversification analysis + open-flags summary. |
| `red_flags_store.py` | CSV-based add/list/resolve for the Red Flag Log (repo-native; the xlsx version from earlier in this session is for your local tracker). |
| `run_daily_scan.py` | Orchestrates all of the above; what the workflow actually runs. |
| `future_stack_model.py` / `portfolio_management_system.py` | The original rubric engines, unchanged, reused as libraries here. |
| `dashboard/build_dashboard.py` | Generates the Claude dashboard artifact HTML from a `results/latest.json` snapshot. Not run by the workflow itself -- used to refresh the separate Claude dashboard. |

## Golden Rule (unchanged from the rest of this project)

A score measures structural quality/risk. It is never a buy or sell signal,
and nothing in this repo recommends or executes a trade.
