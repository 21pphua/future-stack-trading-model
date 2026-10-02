#!/usr/bin/env python3
"""Generates the Future-Stack Scan dashboard artifact HTML, embedding a
results/latest.json snapshot as seed data.

Usage: python3 build_dashboard.py [input_json] [output_html]
  input_json  defaults to "latest.json" in the current directory
  output_html defaults to "dashboard.html" in the current directory

This file is meant to live in the trading-system-bot repo (so a future
Claude session -- including an unattended scheduled refresh -- can fetch it
straight from raw.githubusercontent.com alongside results/latest.json and
regenerate the dashboard without needing anything from this original
session's local disk).
"""
import argparse
import json


def build(input_path="latest.json", output_path="dashboard.html"):
    with open(input_path) as f:
        DATA = json.load(f)

    SEED_JSON = json.dumps(DATA, separators=(',', ':'))

    QUANT_CATS = [
        ("Revenue Quality & Growth", 12),
        ("Margin Path / Unit Economics", 10),
        ("FCF & Balance Sheet", 12),
        ("Valuation", 8),
        ("Macro / Rate Sensitivity", 5),
    ]
    QUAL_CATS = [
        ("Structural Sector Future", 10),
        ("Future-Stack Role", 7),
        ("Durable Moat", 14),
        ("Management & Capital Allocation", 8),
        ("Proof / Milestone Quality", 14),
    ]
    QUANT_CATS_JSON = json.dumps(QUANT_CATS)
    QUAL_CATS_JSON = json.dumps(QUAL_CATS)

    GRADE_BANDS_JSON = json.dumps([
        [92, "A+"], [86, "A"], [80, "A-"], [74, "B+"],
        [68, "B"], [60, "C+"], [50, "C"], [0, "Reject"],
    ])

    HTML = r"""<title>Future-Stack Scan</title>
<style>
:root {
  /* layout: sticky compact header, scrollable two-column body (candidates list + portfolio rail) collapsing to one column under 860px */
  --bg: #eef1ee;
  --surface: #ffffff;
  --surface-2: #e4e9e4;
  --border: #d2dad2;
  --fg: #16201a;
  --muted: #5c6b63;
  --accent: #1f6f5c;
  --accent-fg: #ffffff;
  --good: #2f7d4f;
  --warn: #9a6b0a;
  --bad: #ad3b3b;
  --font-display: 'IBM Plex Sans', system-ui, sans-serif;
  --font-body: 'IBM Plex Sans', system-ui, sans-serif;
  --font-mono: 'IBM Plex Mono', ui-monospace, 'SFMono-Regular', Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #111613;
    --surface: #181f1a;
    --surface-2: #202923;
    --border: #2b352e;
    --fg: #e6ece7;
    --muted: #93a79b;
    --accent: #52d3ae;
    --accent-fg: #0a1a15;
    --good: #5fcf86;
    --warn: #e3ab49;
    --bad: #e2726e;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #111613;
  --surface: #181f1a;
  --surface-2: #202923;
  --border: #2b352e;
  --fg: #e6ece7;
  --muted: #93a79b;
  --accent: #52d3ae;
  --accent-fg: #0a1a15;
  --good: #5fcf86;
  --warn: #e3ab49;
  --bad: #e2726e;
  color-scheme: dark;
}

* { box-sizing: border-box; }
body {
  background: var(--bg);
  color: var(--fg);
  font-family: var(--font-body);
  padding-inline: 16px;
  padding-block: 20px;
  max-width: 1100px;
  margin: 0 auto;
}
h1, h2, h3 { font-family: var(--font-display); text-wrap: balance; margin: 0; }
.mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
a { color: var(--accent); }

header.top {
  position: sticky;
  top: env(safe-area-inset-top, 0px);
  background: var(--bg);
  padding-block: 10px;
  margin-bottom: 18px;
  border-bottom: 1px solid var(--border);
  z-index: 5;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
header.top h1 { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.01em; }
header.top .asof { color: var(--muted); font-size: 0.85rem; }

.golden-rule {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 0.82rem;
  color: var(--muted);
  margin-bottom: 20px;
}
.golden-rule strong { color: var(--fg); }

.layout { display: grid; grid-template-columns: 1.6fr 1fr; gap: 20px; align-items: start; }
@media (max-width: 860px) { .layout { grid-template-columns: 1fr; } }

section.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  min-width: 0;
}
section.panel > h2 {
  font-size: 1.05rem;
  margin-bottom: 4px;
}
.panel .sub { color: var(--muted); font-size: 0.82rem; margin-bottom: 14px; }

.candidate {
  border: 1px solid var(--border);
  border-radius: 10px;
  margin-bottom: 8px;
  overflow: hidden;
}
.candidate > summary {
  list-style: none;
  cursor: pointer;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.candidate > summary::-webkit-details-marker { display: none; }
.candidate > summary::before {
  content: "+";
  font-family: var(--font-mono);
  color: var(--muted);
  width: 1em;
  flex-shrink: 0;
}
.candidate[open] > summary::before { content: "\2212"; }
.c-ticker { font-family: var(--font-mono); font-weight: 700; min-width: 4.5em; flex-shrink: 0; }
.c-theme { color: var(--muted); font-size: 0.82rem; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.c-bar-wrap { width: 120px; flex-shrink: 0; display: flex; align-items: center; gap: 6px; }
.c-bar-track { flex: 1; height: 6px; border-radius: 3px; background: var(--surface-2); overflow: hidden; }
.c-bar-fill { height: 100%; background: var(--accent); border-radius: 3px; }
.c-score { font-family: var(--font-mono); font-size: 0.82rem; color: var(--muted); flex-shrink: 0; width: 4.2em; text-align: right; }

.candidate .detail { padding: 4px 14px 14px; border-top: 1px solid var(--border); }
.trigger-line { font-size: 0.82rem; color: var(--muted); margin: 8px 0; }
.subscore-grid { display: grid; grid-template-columns: 1fr auto; gap: 3px 10px; font-size: 0.85rem; margin: 10px 0; }
.subscore-grid .name { min-width: 0; }
.subscore-grid .val { font-family: var(--font-mono); text-align: right; white-space: nowrap; }

.pending-box {
  background: var(--surface-2);
  border-radius: 8px;
  padding: 10px 12px;
  margin-top: 10px;
}
.pending-box .label { font-size: 0.78rem; color: var(--muted); margin-bottom: 6px; }
.pending-chip {
  display: inline-block;
  font-size: 0.76rem;
  font-family: var(--font-mono);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 2px 8px;
  margin: 2px 4px 2px 0;
}

button.run-btn {
  font-family: var(--font-body);
  font-size: 0.85rem;
  font-weight: 600;
  background: var(--accent);
  color: var(--accent-fg);
  border: none;
  border-radius: 7px;
  padding: 8px 14px;
  cursor: pointer;
  margin-top: 10px;
}
button.run-btn:disabled { opacity: 0.6; cursor: default; }
.run-status { font-size: 0.8rem; color: var(--muted); margin-top: 8px; }
.run-status.err { color: var(--bad); }

.qual-result { margin-top: 12px; border-top: 1px dashed var(--border); padding-top: 12px; }
.qual-result .assess { font-size: 0.88rem; line-height: 1.5; margin: 10px 0; }
.total-line { display: flex; align-items: baseline; gap: 10px; font-size: 0.95rem; margin-top: 10px; flex-wrap: wrap; }
.total-line .grade {
  font-family: var(--font-mono);
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--surface-2);
}
.confidence { font-size: 0.78rem; color: var(--warn); margin-top: 6px; }

.theme-row { display: flex; align-items: center; gap: 8px; font-size: 0.82rem; margin-bottom: 6px; }
.theme-row .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.theme-row .bar-track { width: 90px; height: 6px; border-radius: 3px; background: var(--surface-2); overflow: hidden; flex-shrink: 0; }
.theme-row .bar-fill { height: 100%; background: var(--accent); }
.theme-row .pct { font-family: var(--font-mono); width: 3.4em; text-align: right; flex-shrink: 0; }

.stat-row { display: flex; justify-content: space-between; font-size: 0.85rem; padding: 5px 0; border-bottom: 1px solid var(--border); }
.stat-row:last-child { border-bottom: none; }
.stat-row .v { font-family: var(--font-mono); }

.flag { border-left: 3px solid var(--warn); padding: 6px 10px; margin-bottom: 8px; font-size: 0.82rem; background: var(--surface-2); border-radius: 0 6px 6px 0; }
.flag .t { font-family: var(--font-mono); font-weight: 700; }
.flag .status { color: var(--muted); }

.errors-note { color: var(--muted); font-size: 0.78rem; margin-top: 10px; }
.suggested-note { font-size: 0.76rem; color: var(--muted); margin-top: 8px; }
</style>

<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">

<header class="top">
  <h1>Future-Stack Scan</h1>
  <span class="asof" id="asof-label"></span>
</header>

<div class="golden-rule">
  <strong>Golden Rule:</strong> every score on this page measures structural quality or risk. It is never a buy or sell signal, and this page recommends nothing. The mechanical scores come from plain price/volume/financial-ratio math. Anything Claude fills in on request is a reasoned read from general knowledge, not fresh, verified research &mdash; treat it the same as any other first-pass take in this project: useful for narrowing attention, not for relying on without checking.
</div>

<div class="layout">
  <section class="panel">
    <h2>Scan Candidates</h2>
    <div class="sub" id="candidates-sub"></div>
    <div id="candidates-list"></div>
    <div class="errors-note" id="errors-note"></div>
  </section>

  <div>
    <section class="panel">
      <h2>Your Portfolio</h2>
      <div class="sub" id="portfolio-sub"></div>
      <div id="portfolio-stats"></div>
      <div style="margin-top:14px;" id="theme-weights"></div>
      <div class="suggested-note" id="suggested-note"></div>
    </section>

    <section class="panel">
      <h2>Open Red Flags</h2>
      <div id="flags-list"></div>
    </section>
  </div>
</div>

<script>
const SEED = __SEED_JSON__;
const QUANT_CATS = __QUANT_CATS_JSON__;
const QUAL_CATS = __QUAL_CATS_JSON__;
const GRADE_BANDS = __GRADE_BANDS_JSON__;
const QUANT_CAP = QUANT_CATS.reduce((s,c)=>s+c[1],0);
const QUAL_CAP = QUAL_CATS.reduce((s,c)=>s+c[1],0);

function grade(total) {
  for (const [min, g] of GRADE_BANDS) { if (total >= min) return g; }
  return "Reject";
}
function esc(s) {
  return String(s==null?'':s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

const qualResults = {}; // ticker -> {scores, assessment, confidence_note, scoredAt}

let db = null, sample = null;
(async () => {
  try { db = await window.claude?.use?.('db'); } catch (e) { db = null; }
  try { sample = await window.claude?.use?.('sample'); } catch (e) { sample = null; }
  if (db) {
    try {
      const snap = await db.collection('qualitative_scores').get();
      for (const doc of snap.docs) {
        if (doc.exists) {
          const data = doc.data();
          if (data && data.scores) qualResults[doc.id] = data;
        }
      }
    } catch (e) { /* empty store or unavailable -- fine, just render without it */ }
  }
  render();
})();

function buildPrompt(cand) {
  const quantLines = QUANT_CATS.map(([name, cap]) => {
    const d = cand.quant.quant_details[name];
    const scoreTxt = d.score == null ? 'N/A' : `${d.score}/${cap}`;
    return `- ${name} (${scoreTxt}): ${d.reason}`;
  }).join('\n');
  const qualLines = QUAL_CATS.map(([name, cap]) => `- ${name} (cap ${cap})`).join('\n');
  return `You are scoring ${cand.ticker} (theme: ${cand.theme}) against 5 specific categories from the Future-Stack v2.7 rubric. These 5 categories require qualitative judgment about the business, not financial-ratio math.

Known mechanical (already-scored, for context only -- do not re-score these) categories:
${quantLines}

Score ONLY these 5 categories, each from 0 up to its cap:
${qualLines}

Rules:
- Never invent a specific forward price target, probability of success, or valuation multiple.
- If you are not confident about a category for this specific company, say so in that category's reason and give a conservative score rather than guessing high.
- Keep each reason to one sentence.
- The assessment should be 2-3 sentences, plain language, and must not be investment advice.

Respond with ONLY this JSON shape, no other text:
{"scores":{"Structural Sector Future":{"score":N,"reason":"..."},"Future-Stack Role":{"score":N,"reason":"..."},"Durable Moat":{"score":N,"reason":"..."},"Management & Capital Allocation":{"score":N,"reason":"..."},"Proof / Milestone Quality":{"score":N,"reason":"..."}},"assessment":"...","confidence_note":"..."}`;
}

async function runScorecard(ticker) {
  const statusEl = document.getElementById('status-' + ticker);
  const btn = document.getElementById('btn-' + ticker);
  if (!sample) {
    statusEl.textContent = "Claude isn't available on this view right now.";
    statusEl.classList.add('err');
    return;
  }
  btn.disabled = true;
  statusEl.classList.remove('err');
  statusEl.textContent = 'Asking Claude…';
  const cand = SEED.candidates.find(c => c.ticker === ticker);
  try {
    const result = await sample.json(buildPrompt(cand), {cache: false, modelTier: 'default'});
    const parsed = result && result.scores ? result : null;
    if (!parsed) throw new Error('unexpected response shape');
    // Clamp any out-of-range score defensively rather than trusting it blindly.
    for (const [name, cap] of QUAL_CATS) {
      const entry = parsed.scores[name];
      if (entry && typeof entry.score === 'number') {
        entry.score = Math.max(0, Math.min(cap, Math.round(entry.score)));
      }
    }
    const record = {scores: parsed.scores, assessment: parsed.assessment || '', confidence_note: parsed.confidence_note || '', scoredAt: new Date().toISOString()};
    qualResults[ticker] = record;
    if (db) {
      try { await db.doc('qualitative_scores/' + ticker).set(record); } catch (e) { /* non-fatal: still shown this session */ }
    }
    statusEl.textContent = '';
    render();
  } catch (e) {
    const code = e && e.code;
    if (code === 'not_granted') statusEl.textContent = "You'll need to allow Claude access on this page to use this.";
    else if (code === 'rate_limited') statusEl.textContent = 'Rate-limited -- try again in a moment.';
    else if (code === 'invalid_json') statusEl.textContent = "Claude's reply wasn't valid JSON -- try again.";
    else if (code === 'refused') statusEl.textContent = 'Claude declined this one -- try again or skip it.';
    else statusEl.textContent = "Couldn't get a scorecard just now -- try again.";
    statusEl.classList.add('err');
    btn.disabled = false;
  }
}
window.runScorecard = runScorecard;

function candidateDetail(cand) {
  const quantRows = QUANT_CATS.map(([name, cap]) => {
    const d = cand.quant.quant_details[name];
    const v = d.score == null ? 'N/A' : `${d.score}/${cap}`;
    return `<div class="name">${esc(name)}</div><div class="val mono">${v}</div>`;
  }).join('');

  const qr = qualResults[cand.ticker];
  let qualBlock;
  if (qr) {
    const qualRows = QUAL_CATS.map(([name, cap]) => {
      const e = qr.scores[name] || {};
      return `<div class="name">${esc(name)} &mdash; <span style="color:var(--muted)">${esc(e.reason||'')}</span></div><div class="val mono">${e.score ?? '-'}/${cap}</div>`;
    }).join('');
    const qualTotal = QUAL_CATS.reduce((s,[name]) => s + (qr.scores[name]?.score || 0), 0);
    const combinedTotal = cand.quant.quant_total + qualTotal;
    qualBlock = `
      <div class="qual-result">
        <div class="subscore-grid">${qualRows}</div>
        <div class="assess">${esc(qr.assessment)}</div>
        ${qr.confidence_note ? `<div class="confidence">${esc(qr.confidence_note)}</div>` : ''}
        <div class="total-line">
          <span>Full Future-Stack score:</span>
          <span class="mono">${combinedTotal}/100</span>
          <span class="grade">${esc(grade(combinedTotal))}</span>
        </div>
        <button class="run-btn" id="btn-${esc(cand.ticker)}" onclick="runScorecard('${esc(cand.ticker)}')">Re-run</button>
        <div class="run-status" id="status-${esc(cand.ticker)}"></div>
      </div>`;
  } else {
    const chips = QUAL_CATS.map(([name, cap]) => `<span class="pending-chip">${esc(name)} /${cap}</span>`).join('');
    qualBlock = `
      <div class="pending-box">
        <div class="label">Still needs qualitative review (${QUAL_CAP} pts):</div>
        ${chips}
      </div>
      <button class="run-btn" id="btn-${esc(cand.ticker)}" onclick="runScorecard('${esc(cand.ticker)}')">Run full scorecard with Claude</button>
      <div class="run-status" id="status-${esc(cand.ticker)}"></div>`;
  }

  // Older snapshots (before candidates were selected purely by Future-Stack
  // mechanical score) may still carry a "hits" field describing a
  // price-pattern trigger -- render it if present for backward
  // compatibility, but new snapshots won't have one at all.
  const triggerLine = (cand.hits && cand.hits.length)
    ? `<div class="trigger-line">${cand.hits.map(h => {
        if (h.trigger === 'momentum') return `Momentum: +${(h.return*100).toFixed(1)}% over ${h.lookback_days} trading days (avg $${Math.round(h.avg_dollar_volume).toLocaleString()}/day volume)`;
        if (h.trigger === 'breakout_setup') return `Breakout setup: ${h.date}, close ${h.close.toFixed(2)}, checklist ${h.checklist_score}`;
        return h.trigger;
      }).join(' &middot; ')}</div>`
    : '';

  return `
    ${triggerLine}
    <div class="subscore-grid">${quantRows}</div>
    ${qualBlock}
  `;
}

function render() {
  document.getElementById('asof-label').textContent = 'as of ' + SEED.as_of;
  document.getElementById('candidates-sub').textContent = SEED.candidates.length + ' names cleared the Future-Stack mechanical bar';

  const list = document.getElementById('candidates-list');
  list.innerHTML = SEED.candidates.map(cand => {
    const pct = Math.round(100 * cand.quant.quant_total / cand.quant.quant_cap_achieved);
    const scored = !!qualResults[cand.ticker];
    return `<details class="candidate">
      <summary>
        <span class="c-ticker">${esc(cand.ticker)}</span>
        <span class="c-theme">${esc(cand.theme)}</span>
        <span class="c-bar-wrap"><span class="c-bar-track"><span class="c-bar-fill" style="width:${pct}%"></span></span></span>
        <span class="c-score">${cand.quant.quant_total}/${cand.quant.quant_cap_achieved}${scored ? ' ✓' : ''}</span>
      </summary>
      <div class="detail">${candidateDetail(cand)}</div>
    </details>`;
  }).join('');

  if (SEED.scan_errors && SEED.scan_errors.length) {
    document.getElementById('errors-note').textContent = `Could not fetch data for: ${SEED.scan_errors.join(', ')} (skipped, not scored as zero).`;
  }

  const pr = SEED.portfolio_report;
  if (pr && pr.holdings_analysis) {
    const a = pr.holdings_analysis;
    document.getElementById('portfolio-sub').textContent = `${pr.n_holdings} positions, $${Math.round(a.total_value).toLocaleString()} total`;
    document.getElementById('portfolio-stats').innerHTML = `
      <div class="stat-row"><span>Largest position</span><span class="v">${esc(a.top_ticker)} &middot; ${(a.top_weight*100).toFixed(1)}%</span></div>
      <div class="stat-row"><span>Effective # of positions (HHI)</span><span class="v">${a.effective_n_positions.toFixed(1)}</span></div>
      <div class="stat-row"><span>Themes represented</span><span class="v">${a.n_themes}</span></div>
      <div class="stat-row"><span>Largest theme</span><span class="v">${esc(a.largest_theme)} &middot; ${(a.largest_theme_weight*100).toFixed(1)}%</span></div>
      <div class="stat-row"><span>Suggested concentration score</span><span class="v">${a.suggested_concentration_score}/15</span></div>
      <div class="stat-row"><span>Suggested diversification score</span><span class="v">${a.suggested_diversification_score}/20</span></div>
    `;
    document.getElementById('theme-weights').innerHTML = Object.entries(a.theme_weights).map(([name, w]) => `
      <div class="theme-row">
        <span class="name">${esc(name)}</span>
        <span class="bar-track"><span class="bar-fill" style="width:${Math.round(w*100)}%"></span></span>
        <span class="pct">${(w*100).toFixed(1)}%</span>
      </div>
    `).join('');
    document.getElementById('suggested-note').textContent = "These two sub-scores are data-derived suggestions, not a full Portfolio Construction Score — Quality mix, Leverage, Known-flags severity, and Thematic conviction still need your judgment call.";
  }

  const flags = (pr && pr.open_flags) || [];
  document.getElementById('flags-list').innerHTML = flags.length ? flags.map(f => `
    <div class="flag">
      <div><span class="t">${esc(f.Ticker)}</span> &mdash; ${esc(f.Flag)}</div>
      <div class="status">${esc(f.Status)} &middot; last checked ${esc(f['Last Checked'])}</div>
    </div>
  `).join('') : '<div style="color:var(--muted); font-size:0.85rem;">No open flags on file.</div>';
}
render();
</script>
"""

    HTML = HTML.replace("__SEED_JSON__", SEED_JSON)
    HTML = HTML.replace("__QUANT_CATS_JSON__", QUANT_CATS_JSON)
    HTML = HTML.replace("__QUAL_CATS_JSON__", QUAL_CATS_JSON)
    HTML = HTML.replace("__GRADE_BANDS_JSON__", GRADE_BANDS_JSON)

    with open(output_path, 'w') as f:
        f.write(HTML)

    print(f"Wrote {output_path} ({len(HTML)} bytes)")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", nargs="?", default="latest.json",
                    help="Path to a results/latest.json snapshot (default: latest.json)")
    p.add_argument("output", nargs="?", default="dashboard.html",
                    help="Path to write the generated dashboard HTML (default: dashboard.html)")
    args = p.parse_args()
    build(args.input, args.output)


if __name__ == "__main__":
    main()
