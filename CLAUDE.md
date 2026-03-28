# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the app locally:**
```
streamlit run bruins_app.py --server.enableCORS false --server.enableXsrfProtection false
```
Runs on port 8501. Uses Python 3.11 (see `.devcontainer/devcontainer.json`).

**Install dependencies:**
```
pip install -r requirements.txt
```

**Refresh the dataset** (scrapes all seasons 2000–present from Hockey-Reference):
```
python scrape_data.py
```
Or for specific seasons only: `python scrape_data.py 2024 2025`. Rate-limited to ~1 req/3 s. The 2004-05 season (lockout) is automatically skipped.

There are no tests or linting configurations.

## Architecture

`bruins_app.py` is a **single-file Streamlit app** organised into five tabs. All data loading, transformation, and rendering lives there.

**Data source:** `bruins_game_history.csv` — the app supports both the original Hockey-Reference export format (unnamed columns) and the new scraper format (named columns). `load_data()` normalises both into the same schema.

**Normalised schema** (post-load):
- `Season` (Int64, end-year e.g. 2000 = 1999-2000)
- `Date` (datetime), `Month`, `Day`, `MM_DD` (string `%m-%d`), `DayOfWeek`
- `Location` (Home / Away), `Opponent`
- `GF`, `GA`, `GoalDiff` (float)
- `Outcome` (standardised: Win / Win OT / Win SO / Loss / Loss OT / Loss SO / Tie)
- `Win` (int 0/1)

**Key helpers:** `get_record(df)` returns a dict of total/wins/losses/ties/win_pct for any filtered DataFrame. `build_opp_stats(df)` pre-computes the per-opponent summary table (computed once before tabs, reused in Rivalries and Deep Cuts).

**Tab layout:**
1. **Today** — historical record on today's calendar date + day of week, with a bar chart highlighting the current day
2. **Explore** — look up any date or day-of-week, optional opponent filter; shows outcome pie + game list
3. **Rivalries** — win rate bar chart vs all opponents; detailed drill-down per opponent (home/away split, scoring, day-of-week chart, last 10 games)
4. **Trends** — season win-rate bar chart, goals for/against line chart, month×season win-rate heatmap
5. **Deep Cuts** — home/away comparison, OT/SO record, score lab (win rate by goals scored), blowout board, best/worst month, cursed/easy opponents, birthday lookup

**Timezone:** `ZoneInfo('America/New_York')` for current date — prevents off-by-one errors.

**Styling:** CSS injected via `st.markdown()`. Colors: gold `#FFB81C`, red `#C8102E`. Metric cards styled with left gold border. `@st.cache_data` on `load_data()`.

**Deployment:** Live at https://bruins-best-days.streamlit.app (Streamlit Cloud, auto-deploys from `main`).
