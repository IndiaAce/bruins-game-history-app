#!/usr/bin/env python3
"""
Scrape Boston Bruins regular-season game history from Hockey-Reference.com
and save to bruins_game_history.csv.

Usage:
  python scrape_data.py              # All seasons 2000–present
  python scrape_data.py 2024 2025    # Only specific end-years
"""

import sys
import time
import requests
import pandas as pd
from io import StringIO
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Maps Hockey-Reference data-stat attribute names to our column names.
STAT_RENAME = {
    "ranker":        "GP",
    "games":         "GP",
    "date_game":     "Date",
    "game_location": "Location",
    "opp":           "Opponent",
    "opp_name":      "Opponent",
    "goals":         "GF",
    "opp_goals":     "GA",
    "game_result":   "Result",
    "game_outcome":  "Result",
    "overtimes":     "OT_SO",
    "wins":          "W",
    "losses":        "L",
    "ties":          "T",
    "overtime_loss": "OL",
    "losses_ot":     "OL",
    "win_loss_streak": "Streak",
    "game_streak":   "Streak",
    "attendance":    "Att",
}


def scrape_season(year: int) -> pd.DataFrame | None:
    url = f"https://www.hockey-reference.com/teams/BOS/{year}_games.html"
    print(f"  GET {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        print(f"  Request error: {e}")
        return None

    if resp.status_code == 404:
        print(f"  404 — season {year} not available yet")
        return None
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"id": "games"})
    if table is None:
        print(f"  No #games table found")
        return None

    # Extract header names from data-stat attributes
    thead = table.find("thead")
    col_stats = []
    for th in thead.find_all("th"):
        stat = th.get("data-stat", "")
        col_stats.append(stat)

    # Extract data rows (skip rows that are repeated headers or spacers)
    rows = []
    for tr in table.find("tbody").find_all("tr"):
        classes = tr.get("class", [])
        if "thead" in classes or "spacer" in classes:
            continue
        cells = tr.find_all(["td", "th"])
        row = [c.get_text(strip=True) for c in cells]
        if not row:
            continue
        # Skip rows where GP cell is not a number (repeated header rows)
        if row[0] and not row[0].isdigit():
            continue
        rows.append(row)

    if not rows:
        print(f"  No game rows found")
        return None

    # Align columns (table may have fewer cols than header in edge cases)
    n_cols = min(len(col_stats), len(rows[0]))
    df = pd.DataFrame(rows, columns=col_stats[:n_cols])

    # Rename to our standard names
    df = df.rename(columns={k: v for k, v in STAT_RENAME.items() if k in df.columns})

    # Add season end-year
    df["Season"] = year

    # Keep only the columns we care about
    keep = ["Season", "GP", "Date", "Location", "Opponent",
            "GF", "GA", "Result", "OT_SO", "W", "L", "T", "OL", "Streak"]
    df = df[[c for c in keep if c in df.columns]]

    # Drop empty rows (some seasons have a blank row between reg season / playoffs)
    df = df[df["Date"].str.strip().astype(bool)].copy()

    print(f"  {len(df)} games")
    return df


def main() -> None:
    current_year = 2025  # end-year of the current/most-recent season

    if len(sys.argv) > 1:
        years = [int(y) for y in sys.argv[1:]]
    else:
        years = list(range(2000, current_year + 1))

    # 2004-05 season was cancelled (lockout) — no data exists
    years = [y for y in years if y != 2005]

    print(f"Scraping {len(years)} seasons ({years[0]}–{years[-1]})...")
    print("Rate-limited to ~1 request/3 s — grab a coffee.\n")

    frames = []
    for i, year in enumerate(years):
        print(f"[{i+1}/{len(years)}] Season {year}:")
        df = scrape_season(year)
        if df is not None and not df.empty:
            frames.append(df)
        if i < len(years) - 1:
            time.sleep(3)

    if not frames:
        print("\nNo data scraped. Check your connection or try individual seasons.")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)
    out = "bruins_game_history.csv"
    combined.to_csv(out, index=False)

    print(f"\nSaved {len(combined):,} games to {out}")
    print(f"Seasons covered: {combined['Season'].min()}–{combined['Season'].max()}")


if __name__ == "__main__":
    main()
