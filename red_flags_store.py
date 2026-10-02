"""
CSV-based Red Flag Log -- the repo-native equivalent of the xlsx-based
functions in portfolio_management_system.py (same columns, same behavior:
add/list/resolve), rebuilt against a plain CSV instead of a workbook.

Why a separate store instead of reusing the xlsx one here: an automated
GitHub Action committing binary .xlsx diffs back into git on a schedule is
exactly the kind of thing that produces unreadable diffs and merge
conflicts. A CSV is plain text, diffs cleanly, and is trivial for the
Action to read/update/commit. If you also keep a local xlsx tracker (the
one from earlier in this session), treat this CSV as the source of truth
for the automated repo and copy entries over by hand when you touch both.
"""
import csv
import datetime
import os

FIELDNAMES = ["Flag", "Ticker", "Status", "Last Checked", "Finding / Notes", "Source"]


def _read_all(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _write_all(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows)


def list_flags(path, ticker=None, status_contains=None):
    rows = _read_all(path)
    out = []
    for r in rows:
        if ticker and r["Ticker"].strip().upper() != ticker.strip().upper():
            continue
        if status_contains and status_contains.lower() not in (r["Status"] or "").lower():
            continue
        out.append(r)
    return out


def add_flag(path, flag, ticker, status, notes="", source="", last_checked=None):
    rows = _read_all(path)
    last_checked = last_checked or datetime.date.today().isoformat()
    rows.append({
        "Flag": flag, "Ticker": ticker.strip().upper(), "Status": status,
        "Last Checked": last_checked, "Finding / Notes": notes, "Source": source,
    })
    _write_all(path, rows)
    return len(rows)


def resolve_flag(path, ticker, match, new_status, notes_append="", last_checked=None):
    rows = _read_all(path)
    last_checked = last_checked or datetime.date.today().isoformat()
    updated = 0
    for r in rows:
        if r["Ticker"].strip().upper() != ticker.strip().upper():
            continue
        haystack = (r["Flag"] or "") + " " + (r["Finding / Notes"] or "")
        if match.lower() not in haystack.lower():
            continue
        r["Status"] = new_status
        r["Last Checked"] = last_checked
        if notes_append:
            prior = r["Finding / Notes"] or ""
            r["Finding / Notes"] = (prior + " | " if prior else "") + f"[{last_checked}] {notes_append}"
        updated += 1
    if updated == 0:
        raise RuntimeError(f"No red_flags.csv row found for ticker={ticker!r} matching text {match!r}")
    _write_all(path, rows)
    return updated
