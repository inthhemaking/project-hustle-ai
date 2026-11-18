from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "hustle_tracker.db"

st.set_page_config(
    page_title="Project HUSTLE AI",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Styling ----------
st.markdown(
    """
    <style>
      .stApp { background: #0b0e14; color: #f4f6fb; }
      [data-testid="stSidebar"] { background: #111722; }
      .hero {
        padding: 1.35rem 1.5rem; border: 1px solid #273246;
        border-radius: 18px; background: linear-gradient(120deg,#151e2d,#10141d);
        margin-bottom: 1rem;
      }
      .hero h1 { margin: 0; letter-spacing: .04em; }
      .hero p { color: #aab6c8; margin: .35rem 0 0 0; }
      .metric-card {
        padding: 1rem; border-radius: 14px; border: 1px solid #293448;
        background: #121a26; min-height: 105px;
      }
      .muted { color: #9ba9bd; font-size: .88rem; }
      div[data-testid="stDataFrame"] { border: 1px solid #273246; border-radius: 12px; }
      .small-note { color: #aab6c8; font-size: .82rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Helpers ----------
NBA_MARKETS = [
    "points", "rebounds", "assists", "threes", "steals", "blocks",
    "turnovers", "pra", "points_rebounds", "points_assists", "rebounds_assists",
]
NFL_MARKETS = [
    "pass_yards", "rush_yards", "rec_yards", "receptions",
    "pass_tds", "rush_tds", "rec_tds", "completions",
]
ALL_MARKETS = sorted(set(NBA_MARKETS + NFL_MARKETS))

def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    out.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in out.columns
    ]
    return out

def safe_read_csv(upload) -> pd.DataFrame:
    if upload is None:
        return pd.DataFrame()
    try:
        return clean_columns(pd.read_csv(upload))
    except Exception as exc:
        st.error(f"Could not read that CSV: {exc}")
        return pd.DataFrame()

def normalize_logs(df: pd.DataFrame) -> pd.DataFrame:
    """Accept wide game-log CSVs or long CSVs with stat/value columns."""
    df = clean_columns(df)
    if df.empty:
        return pd.DataFrame()
    if "player" not in df.columns:
        return pd.DataFrame()

    if "date" not in df.columns:
        df["date"] = ""
    if "sport" not in df.columns:
        df["sport"] = "NBA"

    if {"stat", "value"}.issubset(df.columns):
        idx = [c for c in ["date", "sport", "player", "team", "opponent"] if c in df.columns]
        try:
            wide = df.pivot_table(
                index=idx, columns="stat", values="value", aggfunc="first"
            ).reset_index()
            wide.columns.name = None
            df = wide
        except Exception:
            return pd.DataFrame()

    for col in ["team", "opponent", "sport"]:
        if col not in df.columns:
            df[col] = ""
    df["player"] = df["player"].astype(str).str.strip()
    df["sport"] = df["sport"].astype(str).str.upper().str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in df.columns:
        if col not in {"date", "player", "team", "opponent", "sport"}:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[df["player"].ne("")].copy()

def normalize_props(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_columns(df)
    if df.empty:
        return pd.DataFrame()
    required = {"player", "market", "line"}
    if not required.issubset(df.columns):
        return pd.DataFrame()
    for col in ["team", "opponent", "sport", "odds", "game_date"]:
        if col not in df.columns:
            df[col] = ""
    df["player"] = df["player"].astype(str).str.strip()
    df["market"] = df["market"].astype(str).str.lower().str.strip()
    df["line"] = pd.to_numeric(df["line"], errors="coerce")
    df["odds"] = df["odds"].replace("", pd.NA)
    df["odds"] = pd.to_numeric(df["odds"], errors="coerce")
    df["sport"] = df["sport"].astype(str).str.upper().str.strip()
    return df.dropna(subset=["line"]).copy()

def get_market_value(row: pd.Series, market: str) -> Optional[float]:
    market = market.lower()
    if market in row.index and pd.notna(row[market]):
        return float(row[market])
    combos = {
        "pra": ["points", "rebounds", "assists"],
        "points_rebounds": ["points", "rebounds"],
        "points_assists": ["points", "assists"],
        "rebounds_assists": ["rebounds", "assists"],
    }
    if market in combos:
        vals = [row.get(c) for c in combos[market]]
        if all(pd.notna(v) for v in vals):
            return float(sum(vals))
    return None

def american_implied_probability(odds) -> Optional[float]:
    if pd.isna(odds):
        return None
    odds = float(odds)
    if odds == 0:
        return None
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)

def analyze_prop(prop: pd.Series, logs: pd.DataFrame) -> dict:
    player = str(prop["player"]).strip().casefold()
    market = str(prop["market"]).strip().lower()
    sport = str(prop.get("sport", "")).upper()
    sample = logs[logs["player"].str.casefold().eq(player)].copy()
    if sport and sport not in {"", "NAN"}:
        sample = sample[sample["sport"].eq(sport)]
    sample["market_value"] = sample.apply(lambda r: get_market_value(r, market), axis=1)
    sample = sample.dropna(subset=["market_value"]).sort_values("date", ascending=False)
    line = float(prop["line"])
    vals = sample["market_value"]
    row = {
        "player": prop["player"],
        "team": prop.get("team", ""),
        "opponent": prop.get("opponent", ""),
        "market": market.replace("_", " ").title(),
        "line": line,
        "games": int(len(vals)),
        "last_5_avg": round(vals.head(5).mean(), 2) if len(vals) else None,
        "last_10_avg": round(vals.head(10).mean(), 2) if len(vals) else None,
        "last_20_avg": round(vals.head(20).mean(), 2) if len(vals) else None,
        "last_5_hit": round((vals.head(5) > line).mean() * 100, 1) if len(vals) else None,
        "last_10_hit": round((vals.head(10) > line).mean() * 100, 1) if len(vals) else None,
        "last_20_hit": round((vals.head(20) > line).mean() * 100, 1) if len(vals) else None,
        "median": round(vals.median(), 2) if len(vals) else None,
        "odds": prop.get("odds", None),
        "implied_prob": american_implied_probability(prop.get("odds", None)),
    }
    row["historical_hit_rate"] = round((vals > line).mean() * 100, 1) if len(vals) else None
    return row

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS picks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                sport TEXT, player TEXT, market TEXT, line REAL,
                odds REAL, side TEXT, result TEXT, notes TEXT
            )"""
        )
        conn.commit()

def load_picks() -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM picks ORDER BY id DESC", conn)

def add_pick(sport, player, market, line, odds, side, notes):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO picks (sport, player, market, line, odds, side, notes) VALUES (?,?,?,?,?,?,?)",
            (sport, player, market, float(line), None if pd.isna(odds) else float(odds), side, notes),
        )
        conn.commit()

def update_pick_result(pick_id, result):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE picks SET result=? WHERE id=?", (result, int(pick_id)))
        conn.commit()

# ---------- App state ----------
if "logs" not in st.session_state:
    st.session_state.logs = pd.DataFrame()
if "props" not in st.session_state:
    st.session_state.props = pd.DataFrame()

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## 🏀 HUSTLE AI")
    st.caption("Sports research workspace")
    sport_filter = st.selectbox("Sport workspace", ["NBA", "NFL"])
    st.divider()
    st.markdown("### Load your data")
    logs_file = st.file_uploader(
        "Player game logs (CSV)", type=["csv"], key="logs_upload",
        help="Upload one row per player per game. Use the included template."
    )
    if logs_file is not None:
        new_logs = normalize_logs(safe_read_csv(logs_file))
        if not new_logs.empty:
            st.session_state.logs = new_logs
            st.success(f"Loaded {len(new_logs):,} game rows.")
        else:
            st.error("The game-log CSV needs a player column and numeric stat columns.")
    props_file = st.file_uploader(
        "Today's prop slate (CSV)", type=["csv"], key="props_upload",
        help="Required columns: player, market, line. Optional: team, opponent, sport, odds."
    )
    if props_file is not None:
        new_props = normalize_props(safe_read_csv(props_file))
        if not new_props.empty:
            st.session_state.props = new_props
            st.success(f"Loaded {len(new_props):,} props.")
        else:
            st.error("The prop CSV needs player, market, and line columns.")
    if st.button("Clear uploaded data", use_container_width=True):
        st.session_state.logs = pd.DataFrame()
        st.session_state.props = pd.DataFrame()
        st.rerun()
    st.divider()
    st.caption("No live sportsbook, injury, or stats feed is connected in this prototype.")

logs = st.session_state.logs.copy()
props = st.session_state.props.copy()
if logs.empty:
    filtered_logs = pd.DataFrame()
else:
    filtered_logs = logs[logs["sport"].isin([sport_filter, ""])].copy()

if props.empty:
    filtered_props = pd.DataFrame()
else:
    filtered_props = props[(props["sport"].isin([sport_filter, ""])) | (props["sport"].eq("NAN"))].copy()

# ---------- Header ----------
st.markdown(
    """
    <div class="hero">
      <h1>PROJECT HUSTLE AI</h1>
      <p>Research the numbers. Track the process. Never confuse historical trends with guarantees.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_overview, tab_analyzer, tab_tracker, tab_guide = st.tabs(
    ["Overview", "Prop Analyzer", "Pick Tracker", "Data Guide"]
)

with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Game-log rows", f"{len(filtered_logs):,}")
    with c2:
        st.metric("Props loaded", f"{len(filtered_props):,}")
    with c3:
        st.metric("Sport", sport_filter)
    with c4:
        st.metric("Tracked picks", f"{len(load_picks()):,}")
    st.subheader("Workspace status")
    if filtered_logs.empty:
        st.info("No game logs loaded for this sport yet. Upload a game-log CSV from the sidebar to unlock historical analysis.")
    else:
        st.success(f"{len(filtered_logs):,} game-log rows are ready for analysis.")
        st.dataframe(filtered_logs.head(12), use_container_width=True, hide_index=True)
    if filtered_props.empty:
        st.info("No prop slate loaded yet. Upload a prop-slate CSV to compare lines against player history.")
    else:
        st.write("Current prop slate")
        st.dataframe(filtered_props, use_container_width=True, hide_index=True)

with tab_analyzer:
    st.subheader(f"{sport_filter} player prop analyzer")
    st.caption("Hit rates are historical frequencies from the uploaded sample, not forward-looking guarantees.")
    if filtered_props.empty:
        st.info("Upload a prop-slate CSV in the sidebar to populate the analyzer.")
    elif filtered_logs.empty:
        st.warning("Your prop slate is loaded, but there are no matching game logs yet. Upload player game logs to calculate trends.")
        st.dataframe(filtered_props, use_container_width=True, hide_index=True)
    else:
        results = [analyze_prop(row, filtered_logs) for _, row in filtered_props.iterrows()]
        analysis_df = pd.DataFrame(results)
        if "last_10_hit" in analysis_df:
            analysis_df = analysis_df.sort_values(
                "last_10_hit", ascending=False, na_position="last"
            )
        display_cols = [
            "player", "team", "opponent", "market", "line", "games",
            "last_5_avg", "last_10_avg", "last_20_avg", "median",
            "last_5_hit", "last_10_hit", "last_20_hit", "historical_hit_rate",
            "odds", "implied_prob",
        ]
        st.dataframe(
            analysis_df[[c for c in display_cols if c in analysis_df.columns]],
            use_container_width=True, hide_index=True,
        )
        st.download_button(
            "Download analysis CSV",
            analysis_df.to_csv(index=False).encode("utf-8"),
            file_name="hustle_ai_prop_analysis.csv",
            mime="text/csv",
        )
        st.divider()
        st.markdown("#### Add a prop to your tracker")
        choice_labels = [
            f"{r['player']} — {r['market']} {r['line']}"
            for _, r in analysis_df.iterrows()
        ]
        selected_label = st.selectbox("Select a prop", choice_labels)
        selected_idx = choice_labels.index(selected_label)
        selected = analysis_df.iloc[selected_idx]
        side = st.radio("Side", ["Over", "Under"], horizontal=True)
        notes = st.text_input("Notes (optional)", placeholder="Matchup, role, injury context, etc.")
        if st.button("Add pick to tracker", type="primary"):
            add_pick(
                sport_filter, selected["player"], selected["market"],
                selected["line"], selected.get("odds"), side, notes
            )
            st.success("Pick added to your tracker.")

with tab_tracker:
    st.subheader("Pick tracker")
    picks = load_picks()
    if picks.empty:
        st.info("No picks tracked yet. Add one from the Prop Analyzer tab.")
    else:
        st.dataframe(picks, use_container_width=True, hide_index=True)
        st.markdown("#### Settle a pick")
        unsettled = picks[picks["result"].isna() | picks["result"].eq("")]
        if not unsettled.empty:
            selected_pick = st.selectbox(
                "Pick to settle",
                unsettled["id"].tolist(),
                format_func=lambda x: f"#{x} — {unsettled.loc[unsettled['id'].eq(x), 'player'].iloc[0]} ({unsettled.loc[unsettled['id'].eq(x), 'side'].iloc[0]})",
            )
            result = st.selectbox("Result", ["Win", "Loss", "Push", "Void"])
            if st.button("Save result"):
                update_pick_result(selected_pick, result)
                st.success("Result saved.")
                st.rerun()
        else:
            st.caption("All tracked picks have a result recorded.")
        st.download_button(
            "Download pick history",
            picks.to_csv(index=False).encode("utf-8"),
            file_name="hustle_ai_pick_history.csv",
            mime="text/csv",
        )

with tab_guide:
    st.subheader("CSV format")
    st.markdown(
        """
        **Game logs:** one row per player per game. Include `player`, `date`, `sport`,
        and one or more stat columns. Column names should match the markets below.
        """
    )
    st.code(
        "date,sport,player,team,opponent,points,rebounds,assists,threes\n"
        "2026-11-01,NBA,Example Player,ABC,XYZ,24,8,6,3\n"
        "2026-11-03,NBA,Example Player,ABC,QRS,19,10,4,2",
        language="csv",
    )
    st.markdown("**Prop slate:** one row per prop.")
    st.code(
        "sport,player,team,opponent,market,line,odds\n"
        "NBA,Example Player,ABC,XYZ,points,22.5,-110\n"
        "NBA,Example Player,ABC,XYZ,rebounds,7.5,+105\n"
        "NFL,Example Player,ABC,XYZ,rec_yards,64.5,-115",
        language="csv",
    )
    st.markdown("**Supported markets**")
    st.write("NBA:", ", ".join(NBA_MARKETS))
    st.write("NFL:", ", ".join(NFL_MARKETS))
    st.warning(
        "This prototype does not fetch live statistics, injuries, starting lineups, "
        "or sportsbook odds. Upload verified data before relying on any analysis. "
        "Historical hit rates are descriptive and do not guarantee future outcomes."
    )

st.divider()
st.caption(
    "Project HUSTLE AI • Prototype • Data is user-supplied. "
    "Streamlit Community Cloud local files may reset; use a persistent database before offering paid accounts."
)
