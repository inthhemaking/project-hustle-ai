from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "hustle_tracker.db"
BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
WEB_BASE = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ProjectHustleAI/1.0)"}

st.set_page_config(page_title="Project HUSTLE AI", page_icon="🏀", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
.stApp{background:#080d16;color:#edf2fa}.block-container{padding-top:1.2rem;max-width:1400px}
[data-testid="stSidebar"]{background:#101827}.hero{padding:1.35rem 1.5rem;border:1px solid #25344b;border-radius:18px;background:linear-gradient(115deg,#14243a,#101722);margin-bottom:1rem}
.hero h1{letter-spacing:.07em;margin:0;font-size:2rem}.hero p{color:#aab9cc;margin:.35rem 0 0}
[data-testid="stMetric"]{background:#111c2b;border:1px solid #25344b;padding:13px;border-radius:13px}
div[data-testid="stDataFrame"]{border:1px solid #25344b;border-radius:12px}
.stButton>button{border-radius:10px}.muted{color:#9aabc1}
@media(max-width:700px){.block-container{padding-left:.8rem;padding-right:.8rem}.hero h1{font-size:1.55rem}}
</style>
""", unsafe_allow_html=True)

# ---------------- ESPN transport ----------------
def fetch_json(url: str, params: dict | None = None) -> dict:
    response = requests.get(url, params=params, headers=HEADERS, timeout=15)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("ESPN returned an unexpected response format.")
    return payload

@st.cache_data(ttl=90, show_spinner=False)
def get_scoreboard(day: str | None = None) -> dict:
    params = {"dates": day} if day else None
    return fetch_json(f"{BASE}/scoreboard", params)

@st.cache_data(ttl=3600, show_spinner=False)
def get_standings() -> dict:
    return fetch_json("https://site.api.espn.com/apis/v2/sports/basketball/nba/standings")

@st.cache_data(ttl=1800, show_spinner=False)
def get_injuries() -> dict:
    return fetch_json(f"{BASE}/injuries")

@st.cache_data(ttl=1800, show_spinner=False)
def search_players(query: str) -> list[dict]:
    urls = [
        ("https://site.api.espn.com/apis/site/v2/sports/search", {"query": query, "limit": 20, "type": "player"}),
        ("https://site.web.api.espn.com/apis/search/v2", {"query": query, "limit": 20, "sport": "basketball", "league": "nba"}),
    ]
    for url, params in urls:
        try:
            data = fetch_json(url, params)
            found: list[dict] = []
            def walk(obj: Any):
                if isinstance(obj, dict):
                    ident = obj.get("id") or obj.get("uid")
                    name = obj.get("displayName") or obj.get("fullName") or obj.get("name")
                    typ = str(obj.get("type", "")).lower()
                    if ident and name and ("athlete" in typ or "player" in typ or "position" in obj or "team" in obj):
                        pid = str(ident).split("/")[-1]
                        if pid.isdigit():
                            found.append({"id": pid, "name": name, "team": (obj.get("team") or {}).get("abbreviation", ""), "position": (obj.get("position") or {}).get("abbreviation", "")})
                    for value in obj.values(): walk(value)
                elif isinstance(obj, list):
                    for value in obj: walk(value)
            walk(data)
            unique = {p["id"]: p for p in found}
            if unique:
                return list(unique.values())[:20]
        except Exception:
            continue
    return []

@st.cache_data(ttl=1800, show_spinner=False)
def get_athlete_overview(player_id: str) -> dict:
    return fetch_json(f"{WEB_BASE}/athletes/{player_id}/overview")

@st.cache_data(ttl=1800, show_spinner=False)
def get_athlete_stats(player_id: str) -> dict:
    return fetch_json(f"{WEB_BASE}/athletes/{player_id}/stats")

@st.cache_data(ttl=900, show_spinner=False)
def get_gamelog(player_id: str, season: int) -> dict:
    return fetch_json(f"{WEB_BASE}/athletes/{player_id}/gamelog", {"season": season, "seasontype": 2})

@st.cache_data(ttl=600, show_spinner=False)
def get_game_summary(event_id: str) -> dict:
    return fetch_json(f"{BASE}/summary", {"event": event_id})

# ---------------- Data parsing ----------------
def walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)

def scoreboard_rows(data: dict) -> list[dict]:
    rows = []
    for event in data.get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        teams = comp.get("competitors", [])
        home = next((x for x in teams if x.get("homeAway") == "home"), {})
        away = next((x for x in teams if x.get("homeAway") == "away"), {})
        status = (event.get("status") or {}).get("type") or (comp.get("status") or {}).get("type") or {}
        rows.append({"Game": event.get("name", "Matchup"), "Away": (away.get("team") or {}).get("displayName", "Away"), "Away score": away.get("score", "—"), "Home": (home.get("team") or {}).get("displayName", "Home"), "Home score": home.get("score", "—"), "Status": status.get("shortDetail") or status.get("description") or "Scheduled", "Start (local display)": event.get("date", ""), "Event ID": event.get("id", "")})
    return rows

def parse_gamelog(data: dict) -> pd.DataFrame:
    labels = data.get("labels") or data.get("names") or []
    records = []
    for obj in walk_dicts(data):
        # ESPN v3 commonly nests one game per event, with stats as a list.
        if not (obj.get("id") and (obj.get("date") or obj.get("gameDate") or obj.get("eventDate"))):
            continue
        stats = obj.get("stats") or obj.get("statistics")
        if not isinstance(stats, (list, dict)):
            continue
        row = {"Date": obj.get("date") or obj.get("gameDate") or obj.get("eventDate"), "Opponent": "", "Home/Away": obj.get("homeAway", "")}
        opponent = obj.get("opponent")
        if isinstance(opponent, dict): row["Opponent"] = opponent.get("abbreviation") or opponent.get("displayName") or opponent.get("name", "")
        elif opponent: row["Opponent"] = str(opponent)
        if isinstance(stats, dict):
            for k, v in stats.items():
                if isinstance(v, (str, int, float)): row[str(k).lower()] = v
        else:
            for i, value in enumerate(stats):
                key = labels[i] if i < len(labels) else f"stat_{i}"
                row[str(key).lower()] = value
        records.append(row)
    if not records:
        # Some ESPN responses store event rows in a category.events list.
        for obj in walk_dicts(data):
            events = obj.get("events")
            if isinstance(events, list):
                for event in events:
                    if isinstance(event, dict) and (event.get("stats") or event.get("statistics")):
                        row = {"Date": event.get("date") or event.get("eventDate"), "Opponent": event.get("opponent", "")}
                        stats = event.get("stats") or event.get("statistics")
                        if isinstance(stats, dict): row.update(stats)
                        elif isinstance(stats, list):
                            for i, v in enumerate(stats): row[labels[i] if i < len(labels) else f"stat_{i}"] = v
                        records.append(row)
    df = pd.DataFrame(records)
    if df.empty: return df
    df = df.drop_duplicates().copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in df.columns:
        if col not in {"Date", "Opponent", "Home/Away"}:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Date"]).sort_values("Date", ascending=False).reset_index(drop=True)

def stat_column(df: pd.DataFrame, market: str) -> pd.Series | None:
    aliases = {"Points": ["points", "pts"], "Rebounds": ["rebounds", "reb", "totalrebounds"], "Assists": ["assists", "ast"], "3-pointers made": ["threepointersmade", "3pm", "threepointfieldgoalsmade", "3pt"], "Steals": ["steals", "stl"], "Blocks": ["blocks", "blk"], "PRA": ["pra"]}
    normalized = {re.sub(r"[^a-z0-9]", "", str(c).lower()): c for c in df.columns}
    for alias in aliases[market]:
        if alias in normalized: return pd.to_numeric(df[normalized[alias]], errors="coerce")
    if market == "PRA":
        component_aliases = [["points", "pts"], ["rebounds", "reb", "totalrebounds"], ["assists", "ast"]]
        component_columns = []
        for aliases_for_stat in component_aliases:
            match = next((normalized[a] for a in aliases_for_stat if a in normalized), None)
            if match is None:
                return None
            component_columns.append(pd.to_numeric(df[match], errors="coerce"))
        return component_columns[0] + component_columns[1] + component_columns[2]
    return None

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS picks (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, player TEXT, market TEXT, line REAL, side TEXT, opponent TEXT, result TEXT DEFAULT 'Pending', notes TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS parlays (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, name TEXT, legs_json TEXT, result TEXT DEFAULT 'Pending')")
        conn.commit()

def load_picks() -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn: return pd.read_sql_query("SELECT * FROM picks ORDER BY id DESC", conn)

def add_pick(player: str, market: str, line: float, side: str, opponent: str, notes: str):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO picks(player,market,line,side,opponent,notes) VALUES(?,?,?,?,?,?)", (player, market, float(line), side, opponent, notes))
        conn.commit()

def set_result(pick_id: int, result: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE picks SET result=? WHERE id=?", (result, int(pick_id)))
        conn.commit()

def save_parlay(name: str, legs: list[dict]):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO parlays(name,legs_json) VALUES(?,?)", (name, json.dumps(legs)))
        conn.commit()

def load_parlays() -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM parlays ORDER BY id DESC", conn)

def set_parlay_result(parlay_id: int, result: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE parlays SET result=? WHERE id=?", (result, int(parlay_id)))
        conn.commit()

# ---------------- Interface ----------------
st.markdown('<div class="hero"><h1>PROJECT HUSTLE AI</h1><p>Research the numbers. Understand the matchup. Track your process.</p></div>', unsafe_allow_html=True)
with st.sidebar:
    st.markdown("## 🏀 HUSTLE AI")
    st.caption("NBA research workspace")
    st.info("NBA is active. NFL expansion is planned for a later release.")
    st.caption("Data: ESPN public endpoints • No paid API key")

pages = st.tabs(["🏠 Dashboard", "🔎 Player Research", "🚑 Injury Center", "📊 Prop Analyzer", "⚔️ Matchups", "🧾 Picks & Parlays"])

# Dashboard
with pages[0]:
    left, right = st.columns([3, 1])
    with left: st.subheader("NBA scoreboard")
    with right: selected_day = st.date_input("Game date", value=date.today(), label_visibility="collapsed")
    try:
        with st.spinner("Loading NBA games..."):
            board = get_scoreboard(selected_day.strftime("%Y%m%d"))
        games = scoreboard_rows(board)
        if games:
            live = sum("in progress" in str(g["Status"]).lower() or "quarter" in str(g["Status"]).lower() or "half" in str(g["Status"]).lower() for g in games)
            a,b,c = st.columns(3); a.metric("Games", len(games)); b.metric("Live", live); c.metric("Season", (board.get("leagues") or [{}])[0].get("season", {}).get("displayName", "NBA"))
            st.dataframe(pd.DataFrame(games).drop(columns=["Event ID"]), use_container_width=True, hide_index=True)
            with st.expander("Game details / box score"):
                ids = {f"{g['Game']} • {g['Event ID']}": g["Event ID"] for g in games if g["Event ID"]}
                if ids:
                    chosen = st.selectbox("Choose a game", list(ids))
                    if st.button("Load game summary"):
                        try:
                            summary = get_game_summary(ids[chosen])
                            st.json(summary.get("boxscore", summary), expanded=False)
                        except Exception as exc: st.warning(f"Game summary unavailable: {exc}")
        else: st.info("No NBA games are listed for this date. Try another date.")
    except Exception as exc:
        st.error(f"The ESPN scoreboard is temporarily unavailable. Details: {exc}")
    st.caption("Scores and schedules are supplied by ESPN. Refresh or change the date if the feed is delayed.")
    try:
        with st.expander("League standings"):
            standings = get_standings()
            entries = []
            for obj in walk_dicts(standings):
                if obj.get("team") and isinstance(obj.get("stats"), list):
                    team = obj["team"]
                    row = {"Team": team.get("displayName", team.get("name", ""))}
                    for s in obj["stats"]:
                        if isinstance(s, dict) and s.get("name") in {"wins", "losses", "winPercent", "streak"}:
                            row[s.get("name")] = s.get("displayValue") or s.get("value")
                    if len(row) > 1: entries.append(row)
            if entries: st.dataframe(pd.DataFrame(entries).drop_duplicates(), use_container_width=True, hide_index=True)
            else: st.info("Standings feed responded, but its current structure could not be normalized.")
    except Exception as exc: st.info(f"Standings are unavailable right now: {exc}")

# Player search helper shared across tabs

def player_picker(key: str):
    query = st.text_input("Search NBA player", placeholder="Type a player name...", key=f"query_{key}")
    if len(query.strip()) < 3:
        st.caption("Enter at least 3 letters to search ESPN's player directory.")
        return None
    with st.spinner("Searching ESPN..."):
        players = search_players(query.strip())
    if not players:
        st.warning("No player results found. ESPN search may be temporarily unavailable; try the player's full name.")
        return None
    labels = [f"{p['name']}" + (f" — {p['team']}" if p.get("team") else "") for p in players]
    selected = st.selectbox("Select player", range(len(players)), format_func=lambda i: labels[i], key=f"pickplayer_{key}")
    return players[selected]

# Player research
with pages[1]:
    st.subheader("Player research")
    player = player_picker("research")
    if player:
        st.markdown(f"### {player['name']}")
        st.caption(f"ESPN athlete ID: {player['id']} • Team/position information depends on ESPN search results")
        season = st.selectbox("Season", [2027, 2026, 2025, 2024], index=0, key="research_season")
        try:
            overview = get_athlete_overview(player["id"])
            with st.expander("Player overview", expanded=True): st.json(overview, expanded=False)
        except Exception as exc: st.info(f"Player overview unavailable: {exc}")
        try:
            stats = get_athlete_stats(player["id"])
            with st.expander("Season statistics", expanded=True): st.json(stats, expanded=False)
        except Exception as exc: st.info(f"Season statistics unavailable: {exc}")
        try:
            log = parse_gamelog(get_gamelog(player["id"], season))
            if not log.empty:
                st.markdown("#### Recent game log")
                st.dataframe(log.head(20), use_container_width=True, hide_index=True)
                for market in ["Points", "Rebounds", "Assists"]:
                    values = stat_column(log, market)
                    if values is not None:
                        vals = values.dropna()
                        st.metric(f"{market} • last 5 / 10 / 20", " / ".join(f"{vals.head(n).mean():.1f}" if len(vals.head(n)) else "—" for n in [5,10,20]))
            else: st.warning("ESPN returned a game-log response, but its format did not contain recognizable game rows. No averages were fabricated.")
        except Exception as exc: st.warning(f"Game log unavailable: {exc}")

# Injury center
with pages[2]:
    st.subheader("NBA injury center")
    st.caption("Public ESPN injury feed. Reports may be incomplete, delayed, or changed by teams.")
    if st.button("Refresh injury feed"): get_injuries.clear()
    try:
        injury_data = get_injuries()
        entries = []
        for team_group in injury_data.get("injuries", []):
            team = team_group.get("team", {})
            for injury in team_group.get("injuries", []):
                athlete = injury.get("athlete", {})
                entries.append({"Player": athlete.get("displayName", "Unknown"), "Team": team.get("displayName", team.get("abbreviation", "Unknown")), "Status": injury.get("status", "Not specified"), "Injury": (injury.get("type") or {}).get("name", "Not specified"), "Details": injury.get("details", ""), "Report date": injury.get("date", "")})
        if entries: st.dataframe(pd.DataFrame(entries), use_container_width=True, hide_index=True)
        else: st.info("ESPN's injury endpoint responded, but no injury entries were present in its current response.")
        st.caption("Source: ESPN public NBA injury endpoint. Last retrieved: " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    except Exception as exc: st.error(f"Injury feed unavailable. No player statuses will be inferred. Details: {exc}")

# Prop analyzer
with pages[3]:
    st.subheader("Player prop analyzer")
    st.caption("Enter the line from your sportsbook. ESPN does not provide a complete sportsbook prop board here.")
    player = player_picker("prop")
    if player:
        col1,col2,col3 = st.columns([1.3,1,1])
        with col1: market = st.selectbox("Stat market", ["Points", "Rebounds", "Assists", "3-pointers made", "Steals", "Blocks", "PRA"])
        with col2: line = st.number_input("Prop line", min_value=0.0, max_value=300.0, value=20.5, step=0.5)
        with col3: season = st.selectbox("Season", [2027, 2026, 2025, 2024], key="prop_season")
        if st.button("Analyze player prop", type="primary", use_container_width=True):
            st.session_state["active_prop"] = {"player": player, "market": market, "line": line, "season": season}
        prop = st.session_state.get("active_prop")
        if prop and prop["player"]["id"] == player["id"]:
            try:
                log = parse_gamelog(get_gamelog(player["id"], prop["season"]))
                values = stat_column(log, prop["market"]) if not log.empty else None
                if values is None:
                    st.warning("The selected statistic was not available in the returned game log. Try another market or check back later.")
                else:
                    valid = pd.DataFrame({"Date": log["Date"], "Opponent": log.get("Opponent", ""), "Result": values}).dropna(subset=["Result"]).sort_values("Date", ascending=False)
                    valid["Outcome"] = valid["Result"].apply(lambda x: "Over" if x > prop["line"] else ("Under" if x < prop["line"] else "Push"))
                    metrics = []
                    for n in [5,10,20]:
                        sample = valid.head(n)
                        metrics.append((n, len(sample), sample["Result"].mean() if len(sample) else None, (sample["Result"] > prop["line"]).mean()*100 if len(sample) else None, (sample["Result"] < prop["line"]).mean()*100 if len(sample) else None))
                    total = len(valid); over = int((valid["Result"] > prop["line"]).sum()); under = int((valid["Result"] < prop["line"]).sum()); push = int((valid["Result"] == prop["line"]).sum())
                    a,b,c,d = st.columns(4); a.metric("Games in sample", total); b.metric("Over", f"{over}/{total}" if total else "—"); c.metric("Under", f"{under}/{total}" if total else "—"); d.metric("Push", push)
                    st.markdown("#### Recent sample breakdown")
                    st.dataframe(pd.DataFrame([{"Sample":f"Last {n}","Games":count,"Average":round(avg,2) if avg is not None else "—","Over %":round(o,1) if o is not None else "—","Under %":round(u,1) if u is not None else "—"} for n,count,avg,o,u in metrics]), use_container_width=True, hide_index=True)
                    st.markdown("#### Game-by-game results")
                    st.dataframe(valid.head(20), use_container_width=True, hide_index=True)
                    st.caption("Hit rates are historical frequencies in the displayed sample, not predictions or calibrated probabilities. Pushes are excluded from over/under percentages.")
                    side = st.radio("Save which side?", ["Over", "Under"], horizontal=True, key="save_side")
                    notes = st.text_input("Notes (optional)", key="prop_notes")
                    if st.button("Save pick to tracker"):
                        add_pick(prop["player"]["name"], prop["market"], prop["line"], side, "", notes)
                        st.success("Pick saved in this app's local tracker.")
            except Exception as exc: st.error(f"Unable to analyze this player right now: {exc}")

# Matchups
with pages[4]:
    st.subheader("Matchup research")
    st.caption("Start with the live ESPN schedule. Team defensive ranks and matchup ratings are not fabricated.")
    try:
        games = scoreboard_rows(get_scoreboard())
        if games:
            labels = [f"{g['Away']} at {g['Home']} • {g['Status']}" for g in games]
            choice = st.selectbox("Today's matchup", range(len(games)), format_func=lambda i: labels[i])
            game = games[choice]
            st.markdown(f"### {game['Away']} at {game['Home']}")
            st.write(f"**Status:** {game['Status']}  ")
            st.write(f"**Score:** {game['Away score']} – {game['Home score']}")
            if st.button("Load available matchup / box score data"):
                try: st.json(get_game_summary(game["Event ID"]), expanded=False)
                except Exception as exc: st.info(f"Game detail feed unavailable: {exc}")
        else: st.info("No games on the current scoreboard. Choose another date on the Dashboard.")
    except Exception as exc: st.warning(f"Matchup schedule unavailable: {exc}")

# Tracker
with pages[5]:
    st.subheader("Pick tracker & parlay workspace")
    picks = load_picks()
    if picks.empty: st.info("No saved picks yet. Analyze a player prop and save it to begin.")
    else:
        wins = int((picks["result"] == "Win").sum()); losses = int((picks["result"] == "Loss").sum()); pending = int((picks["result"] == "Pending").sum())
        a,b,c,d = st.columns(4); a.metric("Saved picks", len(picks)); b.metric("Wins", wins); c.metric("Losses", losses); d.metric("Pending", pending)
        st.dataframe(picks, use_container_width=True, hide_index=True)
        st.markdown("#### Settle a pick")
        pending_rows = picks[picks["result"] == "Pending"]
        if not pending_rows.empty:
            chosen = st.selectbox("Pick", pending_rows["id"].tolist(), format_func=lambda x: f"#{x} — {pending_rows.loc[pending_rows.id.eq(x),'player'].iloc[0]} {pending_rows.loc[pending_rows.id.eq(x),'market'].iloc[0]}")
            result = st.selectbox("Result", ["Win", "Loss", "Push", "Void"])
            if st.button("Save result"): set_result(chosen, result); st.success("Result updated."); st.rerun()
        st.markdown("#### Build a parlay (workspace only)")
        open_picks = picks[picks["result"] == "Pending"]
        if len(open_picks) >= 2:
            chosen_ids = st.multiselect("Select legs", open_picks["id"].tolist(), format_func=lambda x: f"#{x} {open_picks.loc[open_picks.id.eq(x),'player'].iloc[0]} — {open_picks.loc[open_picks.id.eq(x),'market'].iloc[0]} {open_picks.loc[open_picks.id.eq(x),'side'].iloc[0]}")
            if chosen_ids:
                st.write(f"Parlay legs selected: **{len(chosen_ids)}**. This is a saved-pick grouping, not an odds calculator or guarantee.")
                parlay_name = st.text_input("Parlay name", value=f"HUSTLE slip {datetime.now().strftime('%m/%d')}")
                if st.button("Save parlay"):
                    legs = open_picks[open_picks["id"].isin(chosen_ids)][["id", "player", "market", "line", "side"]].to_dict("records")
                    save_parlay(parlay_name.strip() or "My parlay", legs)
                    st.success("Parlay saved to your tracker.")
                    st.rerun()
        else: st.caption("Save at least two pending picks to assemble a parlay grouping.")
    parlays = load_parlays()
    if not parlays.empty:
        st.markdown("#### Saved parlays")
        display_parlays = parlays.copy()
        display_parlays["Legs"] = display_parlays["legs_json"].apply(lambda x: len(json.loads(x)) if x else 0)
        st.dataframe(display_parlays[["id", "created_at", "name", "Legs", "result"]], use_container_width=True, hide_index=True)
        pending_parlays = parlays[parlays["result"] == "Pending"]
        if not pending_parlays.empty:
            selected_parlay = st.selectbox("Parlay to settle", pending_parlays["id"].tolist(), format_func=lambda x: f"#{x} — {pending_parlays.loc[pending_parlays.id.eq(x),'name'].iloc[0]}")
            parlay_result = st.selectbox("Parlay result", ["Win", "Loss", "Push", "Void"], key="parlay_result")
            if st.button("Save parlay result"):
                set_parlay_result(selected_parlay, parlay_result)
                st.success("Parlay result updated.")
                st.rerun()
    st.warning("Streamlit Community Cloud's local SQLite storage may reset after app restarts or redeployments. This tracker is convenient for a prototype, not guaranteed permanent storage.")

st.divider()
st.caption("PROJECT HUSTLE AI • NBA FIRST • ESPN public data • Research tool only — no guarantees, sportsbook lines, or betting advice.")
