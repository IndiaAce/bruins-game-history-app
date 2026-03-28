import os
from calendar import monthrange
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─── Constants ───────────────────────────────────────────────────────────────
GOLD  = "#FFB81C"
BLACK = "#000000"
WHITE = "#FFFFFF"
GRAY  = "#F4F4F4"
RED   = "#C8102E"

DAYS_ORDER   = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS_ORDER = [10, 11, 12, 1, 2, 3, 4]
MONTH_ABBR   = {10: "Oct", 11: "Nov", 12: "Dec", 1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
                5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep"}
MONTH_FULL   = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May",
                6: "June", 7: "July", 8: "August", 9: "September",
                10: "October", 11: "November", 12: "December"}

TZ = ZoneInfo("America/New_York")

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Bruins by the Numbers",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
.stApp {{ background-color: {WHITE}; color: {BLACK}; }}
[data-testid="stMetricValue"] {{ color: {BLACK} !important; }}
div[data-testid="metric-container"] {{
    background-color: {GRAY};
    border-left: 4px solid {GOLD};
    padding: 10px 14px;
    border-radius: 6px;
}}
::-webkit-scrollbar {{ width: 8px; }}
::-webkit-scrollbar-thumb {{ background: {GOLD}; border-radius: 4px; }}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
    border-bottom: 3px solid {GOLD};
    font-weight: 600;
}}
</style>
""", unsafe_allow_html=True)


# ─── Data Loading & Cleaning ──────────────────────────────────────────────────
@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv("bruins_game_history.csv")

    # Normalise column names — handle both the old Hockey-Reference CSV export
    # (which has "Unnamed: N" headers) and the new scraper format.
    col_rename = {}
    for c in df.columns:
        if "Unnamed: 2" in c:
            col_rename[c] = "Location"
        elif "Unnamed: 6" in c:
            col_rename[c] = "Result"
        elif "Unnamed: 7" in c:
            col_rename[c] = "OT_SO"
    df = df.rename(columns=col_rename)

    # Old CSV used "Outcome" for the raw W/L/T column
    if "Outcome" in df.columns and "Result" not in df.columns:
        df = df.rename(columns={"Outcome": "Result"})

    # Date
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    # Location
    if "Location" not in df.columns:
        df["Location"] = "Home"
    df["Location"] = df["Location"].fillna("Home").replace({"@": "Away", "": "Home"})

    # Numeric columns
    for col in ["GF", "GA", "W", "L", "T", "OL", "GP"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # Build standardised Outcome from Result + optional OT_SO modifier
    result = df["Result"].fillna("").astype(str) if "Result" in df.columns else pd.Series("", index=df.index)
    ot_so  = df["OT_SO"].fillna("").astype(str) if "OT_SO" in df.columns else pd.Series("", index=df.index)
    raw    = result + ot_so

    def _std(o: str) -> str:
        o = o.strip()
        if "W" in o:
            if "OT" in o: return "Win OT"
            if "SO" in o: return "Win SO"
            return "Win"
        if "L" in o:
            if "OT" in o: return "Loss OT"
            if "SO" in o: return "Loss SO"
            return "Loss"
        if "T" in o:
            return "Tie"
        return "Unknown"

    df["Outcome"]   = raw.apply(_std)
    df["Win"]       = df["Outcome"].apply(lambda x: 1 if "Win" in x else 0)
    df["GoalDiff"]  = (df["GF"] - df["GA"]).astype(float)

    # Temporal features
    df["Month"]     = df["Date"].dt.month
    df["Day"]       = df["Date"].dt.day
    df["MM_DD"]     = df["Date"].dt.strftime("%m-%d")
    df["DayOfWeek"] = df["Date"].dt.day_name()

    # Season column (scraper provides it; old CSV also provides it)
    if "Season" not in df.columns:
        df["Season"] = df["Date"].dt.year.where(df["Date"].dt.month < 9,
                                                df["Date"].dt.year + 1)
    df["Season"] = pd.to_numeric(df["Season"], errors="coerce").astype("Int64")

    keep = ["Season", "GP", "Date", "Month", "Day", "MM_DD", "DayOfWeek",
            "Location", "Opponent", "GF", "GA", "GoalDiff", "Outcome", "Win",
            "W", "L", "T", "OL", "Streak"]
    return df[[c for c in keep if c in df.columns]].reset_index(drop=True)


# ─── Helper Functions ─────────────────────────────────────────────────────────
def win_pct(wins: int, total: int) -> float:
    return round(wins / total * 100, 1) if total > 0 else 0.0

def fmt_record(wins: int, losses: int, ties: int = 0) -> str:
    s = f"{wins}-{losses}"
    if ties:
        s += f"-{ties}"
    return s

def get_record(d: pd.DataFrame) -> dict:
    total  = len(d)
    wins   = int(d["Win"].sum())
    losses = int(d["Outcome"].str.contains("Loss").sum())
    ties   = int((d["Outcome"] == "Tie").sum())
    return {"total": total, "wins": wins, "losses": losses,
            "ties": ties, "win_pct": win_pct(wins, total)}

def _bar_layout(title: str, height: int = 360, **kwargs) -> dict:
    defaults = dict(title=title, plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                    font_color=BLACK, height=height,
                    margin=dict(t=50, b=40, l=50, r=20))
    defaults.update(kwargs)
    return defaults


# ─── Load Data ───────────────────────────────────────────────────────────────
df_all   = load_data()
seasons  = sorted(df_all["Season"].dropna().unique().tolist())

# ─── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.markdown(f"<h2 style='color:{GOLD}; margin-bottom:0;'>Bruins by the Numbers</h2>"
                    f"<p style='color:#888; font-size:0.82rem; margin-top:4px;'>#BringBackJim</p>",
                    unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.subheader("Season Range")
start_s = st.sidebar.selectbox("From", seasons, index=0)
end_s   = st.sidebar.selectbox("To",   seasons, index=len(seasons) - 1)

df = df_all[(df_all["Season"] >= start_s) & (df_all["Season"] <= end_s)].reset_index(drop=True)

st.sidebar.markdown("---")
csv_mtime = os.path.getmtime("bruins_game_history.csv")
csv_date  = datetime.fromtimestamp(csv_mtime).strftime("%b %d, %Y")
st.sidebar.markdown(
    f"<p style='font-size:0.78rem; color:#999;'>"
    f"{len(df_all):,} games &nbsp;·&nbsp; {seasons[0]}–{seasons[-1]}<br>"
    f"Dataset updated: {csv_date}<br>"
    f"<code>python scrape_data.py</code> to refresh"
    f"</p>",
    unsafe_allow_html=True,
)

# ─── Pre-compute Opponent Summary (used in multiple tabs) ─────────────────────
def build_opp_stats(d: pd.DataFrame) -> pd.DataFrame:
    stats = (
        d.groupby("Opponent")
        .apply(lambda g: pd.Series({
            "games":  len(g),
            "wins":   int(g["Win"].sum()),
            "losses": int(g["Outcome"].str.contains("Loss").sum()),
            "ties":   int((g["Outcome"] == "Tie").sum()),
        }), include_groups=False)
        .reset_index()
    )
    stats["WinPct"] = (stats["wins"] / stats["games"] * 100).round(1)
    return stats.sort_values("WinPct", ascending=False).reset_index(drop=True)

opp_stats = build_opp_stats(df)

# ─── Title ───────────────────────────────────────────────────────────────────
st.markdown(
    f"<h1 style='text-align:center; color:{GOLD}; margin-bottom:0;'>"
    f"Boston Bruins Game Day Insights</h1>"
    f"<p style='text-align:center; color:#777; margin-top:4px;'>"
    f"Seasons {start_s}–{end_s} &nbsp;·&nbsp; {len(df):,} games</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

# ─── Tabs ────────────────────────────────────────────────────────────────────
tab_today, tab_explore, tab_rivalries, tab_trends, tab_deep = st.tabs(
    ["Today", "Explore", "Rivalries", "Trends", "Deep Cuts"]
)

# ═══════════════════════════════════════════════════════════════════════════════
# TODAY
# ═══════════════════════════════════════════════════════════════════════════════
with tab_today:
    now      = datetime.now(TZ)
    today    = now.date()
    mm_dd    = today.strftime("%m-%d")
    day_name = today.strftime("%A")

    st.markdown(
        f"<h2 style='text-align:center;'>"
        f"Today is <span style='color:{GOLD}'>{today.strftime('%B %d')}</span>,"
        f" a <span style='color:{GOLD}'>{day_name}</span>"
        f"</h2>",
        unsafe_allow_html=True,
    )

    col_date, col_dow = st.columns(2)

    # --- record on this calendar date ---
    with col_date:
        date_games = df[df["MM_DD"] == mm_dd]
        st.subheader(f"On {today.strftime('%B %d')} historically")
        if date_games.empty:
            st.info("No games on this date in the selected range.")
        else:
            r = get_record(date_games)
            m1, m2, m3 = st.columns(3)
            m1.metric("Record", fmt_record(r["wins"], r["losses"], r["ties"]))
            m2.metric("Win Rate", f"{r['win_pct']}%")
            m3.metric("Games", r["total"])

            with st.expander(f"All {r['total']} games on {today.strftime('%B %d')}"):
                show = date_games.sort_values("Date", ascending=False)[
                    ["Date", "Season", "Location", "Opponent", "GF", "GA", "Outcome"]
                ].copy()
                show["Date"] = show["Date"].dt.strftime("%Y-%m-%d")
                st.dataframe(show, use_container_width=True, hide_index=True)

    # --- record on this day of week ---
    with col_dow:
        dow_games = df[df["DayOfWeek"] == day_name]
        st.subheader(f"On {day_name}s historically")
        if dow_games.empty:
            st.info("No games on this day in the selected range.")
        else:
            r = get_record(dow_games)
            m1, m2, m3 = st.columns(3)
            m1.metric("Record", fmt_record(r["wins"], r["losses"], r["ties"]))
            m2.metric("Win Rate", f"{r['win_pct']}%")
            m3.metric("Games", r["total"])

            # Mini bar chart — highlight today's day
            dow_agg = (
                df.groupby("DayOfWeek")["Win"]
                .agg(["sum", "count"])
                .rename(columns={"sum": "wins", "count": "games"})
                .reset_index()
            )
            dow_agg["WinPct"] = (dow_agg["wins"] / dow_agg["games"] * 100).round(1)
            dow_agg["DayOfWeek"] = pd.Categorical(dow_agg["DayOfWeek"], DAYS_ORDER, ordered=True)
            dow_agg = dow_agg.sort_values("DayOfWeek")

            fig = go.Figure(go.Bar(
                x=dow_agg["DayOfWeek"],
                y=dow_agg["WinPct"],
                marker_color=[GOLD if d == day_name else "#CCCCCC" for d in dow_agg["DayOfWeek"]],
                marker_line_color=BLACK, marker_line_width=0.8,
                hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
            ))
            fig.add_hline(y=50, line_dash="dash", line_color="#999", line_width=1)
            fig.update_layout(**_bar_layout("Win Rate by Day of Week", height=280,
                                            yaxis=dict(range=[0, 100]),
                                            xaxis_title="", yaxis_title="Win %"))
            st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# EXPLORE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_explore:
    st.header("Explore Historical Records")

    left, right = st.columns([1, 2])
    with left:
        by = st.radio("Look up by:", ["Calendar Date", "Day of Week"])
        if by == "Calendar Date":
            months = list(range(1, 13))
            sel_m = st.selectbox("Month", months,
                                 format_func=lambda x: datetime(2020, x, 1).strftime("%B"),
                                 index=9)
            sel_d = st.selectbox("Day", list(range(1, monthrange(2020, sel_m)[1] + 1)))
            lookup_mm_dd = f"{sel_m:02d}-{sel_d:02d}"
            lookup_label = datetime(2020, sel_m, sel_d).strftime("%B %d")
        else:
            sel_dow = st.selectbox("Day", DAYS_ORDER, index=5)

        opp_opts = ["All opponents"] + sorted(df["Opponent"].dropna().unique())
        sel_opp  = st.selectbox("vs.", opp_opts)
        opp_f    = None if sel_opp == "All opponents" else sel_opp

    with right:
        if by == "Calendar Date":
            mask  = df["MM_DD"] == lookup_mm_dd
            label = f"Record on {lookup_label}"
        else:
            mask  = df["DayOfWeek"] == sel_dow
            label = f"Record on {sel_dow}s"
        if opp_f:
            mask  &= df["Opponent"] == opp_f
            label += f" vs {opp_f}"

        games = df[mask].sort_values("Date", ascending=False)
        st.subheader(label)

        if games.empty:
            st.info("No games found for this selection.")
        else:
            r = get_record(games)
            gf_avg = games["GF"].mean()
            ga_avg = games["GA"].mean()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Record",  fmt_record(r["wins"], r["losses"], r["ties"]))
            c2.metric("Win Rate", f"{r['win_pct']}%")
            c3.metric("Games Played", r["total"])
            c4.metric("Avg Score",
                      f"{gf_avg:.1f} – {ga_avg:.1f}" if pd.notna(gf_avg) else "N/A")

            # Outcome pie
            oc = games["Outcome"].value_counts()
            fig_pie = go.Figure(go.Pie(
                labels=oc.index, values=oc.values, hole=0.42,
                marker_colors=[GOLD if "Win" in l else (RED if "Loss" in l else "#888")
                               for l in oc.index],
            ))
            fig_pie.update_layout(
                title="Outcome Breakdown", height=280,
                margin=dict(t=40, b=10, l=10, r=10),
                plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_color=BLACK,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

            with st.expander(f"All {r['total']} games"):
                show = games[["Date", "Season", "Location", "Opponent", "GF", "GA", "Outcome"]].copy()
                show["Date"] = show["Date"].dt.strftime("%Y-%m-%d")
                st.dataframe(show, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# RIVALRIES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_rivalries:
    st.header("Head-to-Head Records")

    # Full opponent bar chart
    fig_all = go.Figure(go.Bar(
        x=opp_stats["Opponent"],
        y=opp_stats["WinPct"],
        marker_color=[GOLD if w >= 50 else RED for w in opp_stats["WinPct"]],
        marker_line_color=BLACK, marker_line_width=0.5,
        customdata=opp_stats[["wins", "losses", "games"]].values,
        hovertemplate=(
            "%{x}<br>Win Rate: %{y:.1f}%<br>"
            "W-L: %{customdata[0]}-%{customdata[1]} (%{customdata[2]} GP)"
            "<extra></extra>"
        ),
    ))
    fig_all.add_hline(y=50, line_dash="dash", line_color="#999", line_width=1)
    fig_all.update_layout(
        **_bar_layout("Win Rate vs Every Opponent  (gold = winning record, red = losing)",
                      height=430, xaxis_tickangle=45,
                      yaxis=dict(range=[0, 100]), yaxis_title="Win %",
                      margin=dict(t=50, b=130, l=50, r=20))
    )
    st.plotly_chart(fig_all, use_container_width=True)

    st.markdown("---")
    st.subheader("Opponent Deep Dive")

    sel_rival   = st.selectbox("Select opponent", sorted(df["Opponent"].dropna().unique()))
    rival_games = df[df["Opponent"] == sel_rival].sort_values("Date", ascending=False)

    if not rival_games.empty:
        home_g = rival_games[rival_games["Location"] == "Home"]
        away_g = rival_games[rival_games["Location"] == "Away"]
        ov, hr, ar = get_record(rival_games), get_record(home_g), get_record(away_g)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Overall**")
            st.metric("Record",  fmt_record(ov["wins"], ov["losses"], ov["ties"]))
            st.metric("Win Rate", f"{ov['win_pct']}%")
            st.metric("Games", ov["total"])
        with c2:
            st.markdown("**At Home**")
            st.metric("Record",  fmt_record(hr["wins"], hr["losses"], hr["ties"]))
            st.metric("Win Rate", f"{hr['win_pct']}%")
            st.metric("Games", hr["total"])
        with c3:
            st.markdown("**On the Road**")
            st.metric("Record",  fmt_record(ar["wins"], ar["losses"], ar["ties"]))
            st.metric("Win Rate", f"{ar['win_pct']}%")
            st.metric("Games", ar["total"])

        # Scoring
        st.markdown("---")
        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("Avg Goals Scored",    f"{rival_games['GF'].mean():.2f}")
        sc2.metric("Avg Goals Allowed",   f"{rival_games['GA'].mean():.2f}")
        sc3.metric("Avg Goal Diff",       f"{rival_games['GoalDiff'].mean():+.2f}")

        # Win rate by day of week vs this opponent
        dow_r = (
            rival_games.groupby("DayOfWeek")["Win"]
            .agg(["sum", "count"])
            .rename(columns={"sum": "wins", "count": "games"})
            .reset_index()
        )
        dow_r["WinPct"] = (dow_r["wins"] / dow_r["games"] * 100).round(1)
        dow_r["DayOfWeek"] = pd.Categorical(dow_r["DayOfWeek"], DAYS_ORDER, ordered=True)
        dow_r = dow_r.sort_values("DayOfWeek")

        fig_dow = go.Figure(go.Bar(
            x=dow_r["DayOfWeek"], y=dow_r["WinPct"],
            marker_color=[GOLD if w >= 50 else RED for w in dow_r["WinPct"]],
            marker_line_color=BLACK, marker_line_width=1,
            customdata=dow_r[["wins", "games"]].values,
            hovertemplate="%{x}: %{y:.1f}%  (%{customdata[0]}W / %{customdata[1]} GP)<extra></extra>",
        ))
        fig_dow.add_hline(y=50, line_dash="dash", line_color="#999", line_width=1)
        fig_dow.update_layout(
            **_bar_layout(f"Win Rate by Day of Week vs {sel_rival}", height=300,
                          yaxis=dict(range=[0, 100]), yaxis_title="Win %")
        )
        st.plotly_chart(fig_dow, use_container_width=True)

        st.subheader(f"Last 10 games vs {sel_rival}")
        last10 = rival_games.head(10)[["Date", "Season", "Location", "GF", "GA", "Outcome"]].copy()
        last10["Date"] = last10["Date"].dt.strftime("%Y-%m-%d")
        st.dataframe(last10, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TRENDS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_trends:
    st.header("Historical Trends")

    season_agg = (
        df.groupby("Season")
        .agg(games=("Win", "count"), wins=("Win", "sum"),
             gf=("GF", "mean"), ga=("GA", "mean"))
        .reset_index()
    )
    season_agg["WinPct"] = (season_agg["wins"] / season_agg["games"] * 100).round(1)

    # Win rate per season
    fig_s = go.Figure(go.Bar(
        x=season_agg["Season"], y=season_agg["WinPct"],
        marker_color=[GOLD if w >= 50 else RED for w in season_agg["WinPct"]],
        marker_line_color=BLACK, marker_line_width=0.5,
        customdata=season_agg["games"].values,
        hovertemplate="%{x}: %{y:.1f}%  (%{customdata} GP)<extra></extra>",
    ))
    fig_s.add_hline(y=50, line_dash="dash", line_color="#999", line_width=1,
                    annotation_text="50 %", annotation_position="right")
    fig_s.update_layout(**_bar_layout("Win Rate by Season", height=380,
                                      xaxis_title="Season (end year)",
                                      yaxis=dict(range=[0, 100]), yaxis_title="Win %"))
    st.plotly_chart(fig_s, use_container_width=True)

    # Goals for / against trend
    fig_g = go.Figure()
    fig_g.add_trace(go.Scatter(
        x=season_agg["Season"], y=season_agg["gf"].round(2),
        name="Goals For", mode="lines+markers",
        line=dict(color=GOLD, width=2.5), marker=dict(size=5),
    ))
    fig_g.add_trace(go.Scatter(
        x=season_agg["Season"], y=season_agg["ga"].round(2),
        name="Goals Against", mode="lines+markers",
        line=dict(color=RED, width=2.5), marker=dict(size=5),
    ))
    fig_g.update_layout(
        **_bar_layout("Average Goals Per Game by Season", height=350,
                      xaxis_title="Season (end year)", yaxis_title="Goals / Game"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_g, use_container_width=True)

    # Monthly win-rate heatmap
    st.subheader("Win Rate Heatmap: Month x Season")
    st.caption("How hot (or cold) are the Bruins in each month of each season?")

    monthly = (
        df.groupby(["Season", "Month"])["Win"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "wins", "count": "games"})
        .reset_index()
    )
    monthly["WinPct"] = (monthly["wins"] / monthly["games"] * 100).round(1)

    pivot = monthly.pivot(index="Season", columns="Month", values="WinPct")
    present = [m for m in MONTHS_ORDER if m in pivot.columns]
    pivot   = pivot[present].rename(columns=MONTH_ABBR)

    fig_heat = px.imshow(
        pivot,
        color_continuous_scale=[[0, RED], [0.5, "#EEEEEE"], [1.0, GOLD]],
        zmin=0, zmax=100,
        labels=dict(color="Win %", x="Month", y="Season"),
        text_auto=".0f",
        aspect="auto",
    )
    fig_heat.update_layout(
        title="Win Rate (%) by Month and Season",
        plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_color=BLACK,
        height=max(320, len(pivot) * 18 + 80),
        margin=dict(t=50, b=30, l=70, r=20),
    )
    st.plotly_chart(fig_heat, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DEEP CUTS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_deep:
    st.header("Deep Cuts")
    st.caption("The stats you didn't know you needed.")

    # ── Home vs Away ──────────────────────────────────────────────────────────
    st.subheader("Home Ice Advantage")
    home_r = get_record(df[df["Location"] == "Home"])
    away_r = get_record(df[df["Location"] == "Away"])
    delta  = home_r["win_pct"] - away_r["win_pct"]

    ha1, ha2, ha3, ha4 = st.columns(4)
    ha1.metric("Home Win Rate", f"{home_r['win_pct']}%",
               delta=f"{delta:+.1f}pp vs Away")
    ha2.metric("Away Win Rate", f"{away_r['win_pct']}%")
    ha3.metric("Home Record", fmt_record(home_r["wins"], home_r["losses"], home_r["ties"]))
    ha4.metric("Away Record", fmt_record(away_r["wins"], away_r["losses"], away_r["ties"]))

    # ── OT / SO ───────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Overtime & Shootout Anxiety")

    ot_w  = int((df["Outcome"] == "Win OT").sum())
    ot_l  = int((df["Outcome"] == "Loss OT").sum())
    so_w  = int((df["Outcome"] == "Win SO").sum())
    so_l  = int((df["Outcome"] == "Loss SO").sum())
    extra = ot_w + ot_l + so_w + so_l
    pct_extra = win_pct(extra, len(df))

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Games to OT/SO", f"{pct_extra:.1f}%", delta=f"{extra} total")
    e2.metric("OT Record", f"{ot_w}-{ot_l}",
              delta=f"{win_pct(ot_w, ot_w + ot_l):.0f}% win" if ot_w + ot_l else None)
    e3.metric("SO Record", f"{so_w}-{so_l}",
              delta=f"{win_pct(so_w, so_w + so_l):.0f}% win" if so_w + so_l else None)
    e4.metric("Combined OT/SO Win Rate",
              f"{win_pct(ot_w + so_w, extra):.1f}%" if extra else "N/A")

    # ── Score Lab ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("The Score Lab — Win Rate by Goals Scored")
    st.caption("Because scoring 1 goal has a different vibe than scoring 6.")

    score_df = df.dropna(subset=["GF"]).copy()
    score_agg = (
        score_df.groupby("GF")["Win"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "wins", "count": "games"})
        .reset_index()
    )
    score_agg = score_agg[score_agg["games"] >= 5]
    score_agg["WinPct"] = (score_agg["wins"] / score_agg["games"] * 100).round(1)
    score_agg["GF"] = score_agg["GF"].astype(int)

    fig_sc = go.Figure(go.Bar(
        x=score_agg["GF"], y=score_agg["WinPct"],
        marker_color=[GOLD if w >= 50 else RED for w in score_agg["WinPct"]],
        marker_line_color=BLACK, marker_line_width=1,
        customdata=score_agg[["wins", "games"]].values,
        hovertemplate="Score %{x}: %{y:.1f}% win rate<br>%{customdata[0]}W / %{customdata[1]} GP<extra></extra>",
    ))
    fig_sc.add_hline(y=50, line_dash="dash", line_color="#999", line_width=1)
    fig_sc.update_layout(**_bar_layout("Win Rate when the Bruins score exactly N goals", height=320,
                                       xaxis_title="Goals Scored", xaxis=dict(dtick=1),
                                       yaxis=dict(range=[0, 105]), yaxis_title="Win %"))
    st.plotly_chart(fig_sc, use_container_width=True)

    if not score_agg.empty:
        magic   = score_agg.loc[score_agg["WinPct"].idxmax()]
        breakeven_idx = (score_agg["WinPct"] - 50).abs().idxmin()
        breakeven = score_agg.loc[breakeven_idx]
        col_sc1, col_sc2 = st.columns(2)
        col_sc1.metric("Magic number (highest win rate)", f"{int(magic['GF'])} goals",
                       delta=f"{magic['WinPct']:.0f}% win rate")
        col_sc2.metric("Break-even number (~50% win rate)", f"{int(breakeven['GF'])} goals",
                       delta=f"{breakeven['WinPct']:.1f}%")

    # ── Blowout Board ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("The Blowout Board")

    bl1, bl2 = st.columns(2)
    with bl1:
        st.markdown("**Biggest Wins**")
        bw = (df[df["Win"] == 1]
              .dropna(subset=["GoalDiff"])
              .nlargest(5, "GoalDiff")
              [["Date", "Season", "Opponent", "GF", "GA", "Location"]]
              .copy())
        bw["Date"] = bw["Date"].dt.strftime("%Y-%m-%d")
        st.dataframe(bw, use_container_width=True, hide_index=True)
    with bl2:
        st.markdown("**Worst Losses**")
        bl = (df[df["Win"] == 0]
              .dropna(subset=["GoalDiff"])
              .nsmallest(5, "GoalDiff")
              [["Date", "Season", "Opponent", "GF", "GA", "Location"]]
              .copy())
        bl["Date"] = bl["Date"].dt.strftime("%Y-%m-%d")
        st.dataframe(bl, use_container_width=True, hide_index=True)

    # ── Best / Worst Month ────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Best and Worst Month (All Time)")

    mo_agg = (
        df.groupby("Month")["Win"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "wins", "count": "games"})
        .reset_index()
    )
    mo_agg["WinPct"]   = (mo_agg["wins"] / mo_agg["games"] * 100).round(1)
    mo_agg["Name"]     = mo_agg["Month"].map(MONTH_FULL)
    mo_agg["SortKey"]  = mo_agg["Month"].apply(lambda m: MONTHS_ORDER.index(m) if m in MONTHS_ORDER else 99)
    mo_agg = mo_agg.sort_values("SortKey")

    fig_mo = go.Figure(go.Bar(
        x=mo_agg["Name"], y=mo_agg["WinPct"],
        marker_color=[GOLD if w >= 50 else RED for w in mo_agg["WinPct"]],
        marker_line_color=BLACK, marker_line_width=1,
        customdata=mo_agg[["wins", "games"]].values,
        hovertemplate="%{x}: %{y:.1f}%  (%{customdata[0]}W / %{customdata[1]} GP)<extra></extra>",
    ))
    fig_mo.add_hline(y=50, line_dash="dash", line_color="#999", line_width=1)
    fig_mo.update_layout(**_bar_layout("Win Rate by Calendar Month", height=320,
                                       xaxis_title="", yaxis=dict(range=[0, 100]), yaxis_title="Win %"))
    st.plotly_chart(fig_mo, use_container_width=True)

    best_mo  = mo_agg.loc[mo_agg["WinPct"].idxmax()]
    worst_mo = mo_agg.loc[mo_agg["WinPct"].idxmin()]
    st.markdown(f"- **Best month:** {best_mo['Name']} — {best_mo['WinPct']:.1f}% win rate over {best_mo['games']} games")
    st.markdown(f"- **Worst month:** {worst_mo['Name']} — {worst_mo['WinPct']:.1f}% win rate over {worst_mo['games']} games")

    # ── Cursed vs Easy Opponents ───────────────────────────────────────────────
    st.markdown("---")
    st.subheader("The Cursed (and Feasted Upon) Opponents")
    st.caption("Min. 20 games played.")

    eligible = opp_stats[opp_stats["games"] >= 20].copy()
    ce1, ce2 = st.columns(2)
    with ce1:
        st.markdown("**Can't figure these teams out**")
        worst5 = eligible.tail(5)[["Opponent", "wins", "losses", "ties", "games", "WinPct"]].copy()
        worst5.columns = ["Opponent", "W", "L", "T", "GP", "Win %"]
        st.dataframe(worst5, use_container_width=True, hide_index=True)
    with ce2:
        st.markdown("**Absolute victims**")
        best5 = eligible.head(5)[["Opponent", "wins", "losses", "ties", "games", "WinPct"]].copy()
        best5.columns = ["Opponent", "W", "L", "T", "GP", "Win %"]
        st.dataframe(best5, use_container_width=True, hide_index=True)

    # ── Birthday Lookup ───────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Your Birthday Record")
    st.caption("Does the universe smile upon you via Bruins results? Let's find out.")

    bd1, bd2 = st.columns([1, 2])
    with bd1:
        bd_month = st.selectbox("Month", list(range(1, 13)),
                                format_func=lambda x: datetime(2020, x, 1).strftime("%B"),
                                key="bd_m")
        bd_day   = st.selectbox("Day", list(range(1, monthrange(2020, bd_month)[1] + 1)),
                                key="bd_d")
        bd_mm_dd = f"{bd_month:02d}-{bd_day:02d}"
        bd_label = datetime(2020, bd_month, bd_day).strftime("%B %d")

    with bd2:
        bd_games = df[df["MM_DD"] == bd_mm_dd]
        if bd_games.empty:
            st.info(f"No Bruins games ever played on {bd_label} in the selected range.")
        else:
            br = get_record(bd_games)
            bm1, bm2, bm3 = st.columns(3)
            bm1.metric("Birthday Record", fmt_record(br["wins"], br["losses"], br["ties"]))
            bm2.metric("Win Rate", f"{br['win_pct']}%")
            bm3.metric("Games Played", br["total"])

            if br["win_pct"] >= 70:
                st.success(f"The Bruins absolutely dominate on {bd_label}. Lucky you.")
            elif br["win_pct"] >= 50:
                st.info(f"The Bruins have a winning record on your birthday. Could be worse.")
            elif br["win_pct"] == 0:
                st.error(f"The Bruins have never won on {bd_label}. We're sorry.")
            else:
                st.warning(f"The Bruins have a losing record on your birthday. Not great.")

            bd_show = bd_games.sort_values("Date", ascending=False)[
                ["Date", "Season", "Opponent", "Location", "GF", "GA", "Outcome"]
            ].copy()
            bd_show["Date"] = bd_show["Date"].dt.strftime("%Y-%m-%d")
            st.dataframe(bd_show, use_container_width=True, hide_index=True)


# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='text-align:center; font-size:0.8rem; color:#aaa;'>"
    "Data: <a href='https://www.hockey-reference.com' target='_blank'>Hockey-Reference.com</a>"
    " · Regular season only · #BringBackJim"
    "</p>",
    unsafe_allow_html=True,
)
