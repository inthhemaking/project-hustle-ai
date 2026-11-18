import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "hustle_ai.db"

st.set_page_config(page_title="Project HUSTLE AI", page_icon="🏀", layout="wide")

GAME_COLUMNS = ["date", "league", "player", "team", "opponent", "metric", "value"]
PROP_COLUMNS = ["game_date", "league", "player", "team", "opponent", "metric", "line", "side", "odds_american"]

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            game_date TEXT,
            league TEXT NOT NULL,
            player TEXT NOT NULL,
            team TEXT,
            opponent TEXT,
            metric TEXT NOT NULL,
            line REAL NOT NULL,
            side TEXT NOT NULL,
            window_n INTEGER NOT NULL,
            sample_size INTEGER NOT NULL,
            projection REAL,
            historical_hit_rate REAL,
            odds_american INTEGER,
            result TEXT DEFAULT 'Pending',
            actual_value REAL
        )
    """)
    conn.commit()
    return conn

def american_to_implied(odds):
    if pd.isna(odds) or odds == 0:
        return None
    odds = float(odds)
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)

def normalize_games(df):
    df = df.copy()
    missing = [c for c in GAME_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError("Game log CSV is missing columns: " + ", ".join(missing))
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["league"] = df["league"].astype(str).str.upper().str.strip()
    df["player"] = df["player"].astype(str).str.strip()
    df["metric"] = df["metric"].astype(str).str.lower().str.strip()
    df = df.dropna(subset=["date", "value"])
    df = df[df["league"].isin(["NBA", "NFL"])]
    return df.sort_values("date", ascending=False)

def normalize_props(df):
    df = df.copy()
    missing = [c for c in PROP_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError("Prop slate CSV is missing columns: " + ", ".join(missing))
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    df["line"] = pd.to_numeric(df["line"], errors="coerce")
    df["odds_american"] = pd.to_numeric(df["odds_american"], errors="coerce")
    df["league"] = df["league"].astype(str).str.upper().str.strip()
    df["player"] = df["player"].astype(str).str.strip()
    df["metric"] = df["metric"].astype(str).str.lower().str.strip()
    df["side"] = df["side"].astype(str).str.title().str.strip()
    df = df.dropna(subset=["line"])
    df = df[df["league"].isin(["NBA", "NFL"]) & df["side"].isin(["Over", "Under"])]
    return df

def estimate(history, line, side, window_n):
    values = history["value"].astype(float).head(window_n)
    n = len(values)
    if n == 0:
        return None
    if side == "Over":
        hits = int((values > line).sum())
    else:
        hits = int((values < line).sum())
    pushes = int((values == line).sum())
    decided = n - pushes
    hit_rate = hits / decided if decided else None
    return {
        "n": n,
        "mean": float(values.mean()),
        "median": float(values.median()),
        "std": float(values.std(ddof=1)) if n > 1 else 0.0,
        "hits": hits,
        "pushes": pushes,
        "decided": decided,
        "hit_rate": hit_rate,
        "values": values.tolist()
    }

def load_saved():
    conn = db()
    df = pd.read_sql_query("SELECT * FROM predictions ORDER BY id DESC", conn)
    conn.close()
    return df

st.title("🏀 Project HUSTLE AI")
st.caption("NBA + NFL sports analytics prototype · Transparent statistics, saved predictions, measurable results")

with st.sidebar:
    st.header("Prototype controls")
    league_filter = st.multiselect("League filter", ["NBA", "NFL"], default=["NBA", "NFL"])
    window_n = st.selectbox("Recent-game window", [5, 10, 20], index=1)
    st.divider()
    st.caption("Prototype v0.1 · CSV-driven · No live odds or injury feed yet")

tab_data, tab_analyze, tab_track, tab_guide = st.tabs(
    ["1 · Data Center", "2 · Prop Analyzer", "3 · Prediction Tracker", "4 · Setup Guide"]
)

with tab_data:
    st.subheader("Import historical player game logs")
    st.write("Upload a CSV containing one row per player per game and per statistic. Keep NBA and NFL rows in the same file if you like.")
    game_file = st.file_uploader("Player game logs CSV", type=["csv"], key="games")
    if game_file:
        try:
            games = normalize_games(pd.read_csv(game_file))
            st.session_state["games"] = games
            st.success(f"Loaded {len(games):,} valid game-stat rows.")
            st.dataframe(games.head(30), use_container_width=True)
        except Exception as e:
            st.error(str(e))
    elif "games" in st.session_state:
            games = st.session_state["games"]
            if games is None:
                games = pd.DataFrame()

        game_count = len(games)

        st.info(f"{game_count:,} game-stat rows currently loaded in this session.")

        if not games.empty:
        st.dataframe(games.head(15), use_container_width=True)
    else:
        st.info("No game statistics loaded yet. Upload your game logs CSV to get started.")
    else:
        st.info("No game logs loaded yet. Download the template from the Setup Guide tab.")

    st.divider()
    st.subheader("Import a prop slate")
    st.write("Each row represents one prop line you want the analyzer to evaluate.")
    prop_file = st.file_uploader("Today's props CSV", type=["csv"], key="props")
    if prop_file:
        try:
            props = normalize_props(pd.read_csv(prop_file))
            st.session_state["props"] = props
            st.success(f"Loaded {len(props):,} prop lines.")
            st.dataframe(props, use_container_width=True)
        except Exception as e:
            st.error(str(e))
    elif "props" in st.session_state:
        st.info(f"{len(st.session_state['props']):,} prop lines currently loaded in this session.")

with tab_analyze:
    st.subheader("Historical prop analysis")
    if "games" not in st.session_state:
        st.warning("Upload player game logs in Data Center first.")
    elif "props" not in st.session_state:
        st.warning("Upload a prop slate in Data Center first.")
    else:
        games = st.session_state["games"]
        props = st.session_state["props"]
        if league_filter:
            props = props[props["league"].isin(league_filter)]
        st.caption("Historical hit rate is descriptive, not a calibrated forecast. It does not account for injuries, role changes, matchup, or market movement.")
        for idx, prop in props.iterrows():
            history = games[
                (games["league"] == prop["league"]) &
                (games["player"].str.casefold() == str(prop["player"]).casefold()) &
                (games["metric"] == prop["metric"])
            ].sort_values("date", ascending=False)
            result = estimate(history, float(prop["line"]), prop["side"], window_n)
            title = f"{prop['player']} · {prop['metric'].replace('_',' ').title()} {prop['side']} {prop['line']:g}"
            with st.expander(title, expanded=(idx == props.index[0])):
                c1, c2, c3, c4 = st.columns(4)
                if result is None:
                    st.error("No matching player history found. Check league, player spelling and metric name.")
                    continue
                c1.metric("Recent sample", f"{result['n']} games")
                c2.metric("Average", f"{result['mean']:.2f}")
                c3.metric("Median", f"{result['median']:.2f}")
                c4.metric("Historical hit rate", "N/A" if result["hit_rate"] is None else f"{result['hit_rate']:.1%}")
                st.write(f"Hits: **{result['hits']}** · Pushes: **{result['pushes']}** · Decided games: **{result['decided']}**")
                implied = american_to_implied(prop.get("odds_american", np.nan))
                if implied is not None:
                    st.write(f"Sportsbook break-even probability before any adjustments: **{implied:.1%}**")
                    if result["hit_rate"] is not None:
                        st.write(f"Historical hit-rate difference vs break-even: **{result['hit_rate'] - implied:+.1%}**")
                st.write("Most recent values:", ", ".join(f"{x:g}" for x in result["values"]))
                if result["n"] < 10:
                    st.warning("Small sample: treat this as preliminary descriptive information, not a reliable edge.")
                if st.button("Save this prediction", key=f"save_{idx}"):
                    conn = db()
                    conn.execute("""
                        INSERT INTO predictions
                        (created_at, game_date, league, player, team, opponent, metric, line, side,
                         window_n, sample_size, projection, historical_hit_rate, odds_american)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        datetime.now(timezone.utc).isoformat(),
                        str(prop["game_date"].date()) if pd.notna(prop["game_date"]) else None,
                        prop["league"], prop["player"], prop.get("team", ""), prop.get("opponent", ""),
                        prop["metric"], float(prop["line"]), prop["side"], window_n, result["n"],
                        result["mean"], result["hit_rate"],
                        int(prop["odds_american"]) if pd.notna(prop["odds_american"]) else None
                    ))
                    conn.commit()
                    conn.close()
                    st.success("Prediction saved to the tracker.")

with tab_track:
    st.subheader("Prediction performance tracker")
    saved = load_saved()
    if saved.empty:
        st.info("No predictions saved yet. Analyze a prop and select 'Save this prediction'.")
    else:
        total = len(saved)
        settled = saved[saved["result"].isin(["Win", "Loss", "Push"])]
        wins = int((settled["result"] == "Win").sum())
        losses = int((settled["result"] == "Loss").sum())
        pushes = int((settled["result"] == "Push").sum())
        a, b, c, d = st.columns(4)
        a.metric("Saved predictions", total)
        b.metric("Settled", len(settled))
        c.metric("Wins / losses", f"{wins} / {losses}")
        d.metric("Win rate (decided)", f"{wins/(wins+losses):.1%}" if wins + losses else "N/A")
        st.caption("This is a simple count-based tracker. ROI requires recording actual stake and payout/odds and is not calculated in v0.1.")
        st.dataframe(saved, use_container_width=True)
        st.markdown("#### Settle a prediction")
        pending = saved[saved["result"] == "Pending"]
        if not pending.empty:
            labels = {int(r.id): f"#{r.id} · {r.league} · {r.player} · {r.metric} {r.side} {r.line}" for r in pending.itertuples()}
            chosen = st.selectbox("Choose a pending prediction", list(labels.keys()), format_func=lambda x: labels[x])
            r = pending[pending["id"] == chosen].iloc[0]
            actual = st.number_input("Actual player statistic", min_value=0.0, value=0.0, step=1.0)
            if st.button("Save actual result"):
                if actual == r["line"]:
                    outcome = "Push"
                elif (r["side"] == "Over" and actual > r["line"]) or (r["side"] == "Under" and actual < r["line"]):
                    outcome = "Win"
                else:
                    outcome = "Loss"
                conn = db()
                conn.execute("UPDATE predictions SET result=?, actual_value=? WHERE id=?", (outcome, float(actual), int(chosen)))
                conn.commit()
                conn.close()
                st.success(f"Prediction #{chosen} settled as {outcome}. Refresh the page to update totals.")
        else:
            st.success("All saved predictions have been settled.")

with tab_guide:
    st.subheader("How to get the prototype running")
    st.markdown("""
    **You need a computer for the initial setup** (Windows, Mac or Linux). The app is mobile-friendly once hosted.

    1. Install Python 3.10 or newer.
    2. Put `app.py` and `requirements.txt` in the same folder.
    3. Open Terminal / Command Prompt in that folder.
    4. Run `pip install -r requirements.txt`.
    5. Run `streamlit run app.py`.
    6. Open the local address Streamlit prints.

    **CSV rules**
    - Use the provided game-log template and prop-slate template.
    - Use consistent player names and metric labels between files.
    - Use `NBA` or `NFL` in the league column.
    - Examples of metrics: `points`, `rebounds`, `assists`, `passing_yards`, `rushing_yards`, `receptions`.
    - For game logs, `value` is the actual statistic from that game.
    - For props, `side` must be `Over` or `Under`; American odds are optional.

    **Current limitations**
    - No live sportsbook odds, injury feed, starting lineup feed or automatic data refresh.
    - No machine-learning model has been trained yet.
    - Historical hit rates are not calibrated probabilities and do not prove future profitability.
    - Predictions are saved locally in a SQLite database beside the app.
    """)
    st.download_button("Download game-log CSV template",
                       "date,league,player,team,opponent,metric,value\n",
                       file_name="game_logs_template.csv", mime="text/csv")
    st.download_button("Download prop-slate CSV template",
                       "game_date,league,player,team,opponent,metric,line,side,odds_american\n",
                       file_name="prop_slate_template.csv", mime="text/csv")

st.divider()
st.caption("Project HUSTLE AI v0.1 · Research and educational analytics only · No guarantee of outcomes")
