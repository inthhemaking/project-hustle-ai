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
SEARCH_BASE = "https://site.web.api.espn.com/apis/search/v2"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ProjectHustleAI/2.0)"}

st.set_page_config(page_title="Project HUSTLE AI", page_icon="🏀", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
.stApp{background:#080d16;color:#edf2fa}.block-container{padding-top:1rem;max-width:1400px}
.hero{padding:1.3rem 1.4rem;border:1px solid #25344b;border-radius:18px;background:linear-gradient(115deg,#14243a,#101722);margin-bottom:1rem}
.hero h1{letter-spacing:.07em;margin:0;font-size:2rem}.hero p{color:#aab9cc;margin:.35rem 0 0}
[data-testid="stMetric"]{background:#111c2b;border:1px solid #25344b;padding:12px;border-radius:13px}
[data-testid="stDataFrame"]{border:1px solid #25344b;border-radius:12px}
.stButton>button{border-radius:10px;min-height:2.6rem}
@media(max-width:700px){.block-container{padding-left:.8rem;padding-right:.8rem}.hero h1{font-size:1.5rem}}
</style>
""", unsafe_allow_html=True)

# ---------------- ESPN data access ----------------
def fetch_json(url: str, params: dict | None = None) -> dict:
    response = requests.get(url, params=params, headers=HEADERS, timeout=18)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("ESPN returned an unexpected response format.")
    return payload

@st.cache_data(ttl=90, show_spinner=False)
def get_scoreboard(day: str | None = None) -> dict:
    return fetch_json(f"{BASE}/scoreboard", {"dates": day} if day else None)

@st.cache_data(ttl=3600, show_spinner=False)
def get_standings() -> dict:
    return fetch_json("https://site.api.espn.com/apis/v2/sports/basketball/nba/standings")

@st.cache_data(ttl=1800, show_spinner=False)
def get_injuries() -> dict:
    return fetch_json(f"{BASE}/injuries")

@st.cache_data(ttl=1800, show_spinner=False)
def get_teams() -> list[dict]:
    """Normalize ESPN's nested teams response into a unique team list."""
    data = fetch_json(f"{BASE}/teams", {"limit": 100})
    found: dict[str, dict] = {}
    for node in walk_dicts(data):
        # The endpoint commonly wraps each team in a {"team": {...}} object.
        team = node.get("team") if isinstance(node.get("team"), dict) else node
        if not isinstance(team, dict):
            continue
        tid = team.get("id")
        abbr = team.get("abbreviation") or team.get("abbr")
        name = team.get("displayName") or team.get("name")
        if tid and abbr and name:
            found[str(tid)] = {"id": str(tid), "name": name, "abbr": abbr}
    return sorted(found.values(), key=lambda item: item["abbr"])

@st.cache_data(ttl=1800, show_spinner=False)
def get_roster(team_id: str) -> list[dict]:
    """Read flat or grouped ESPN roster payloads without assuming one schema."""
    data = fetch_json(f"{BASE}/teams/{team_id}/roster")
    roster: dict[str, dict] = {}
    team_obj = data.get("team") if isinstance(data.get("team"), dict) else {}
    team_abbr = team_obj.get("abbreviation", "")
    for athlete in walk_dicts(data):
        pid = athlete.get("id")
        name = athlete.get("displayName") or athlete.get("fullName") or athlete.get("name")
        # Require a plausible athlete object; this avoids indexing team IDs.
        if not pid or not name or not str(pid).isdigit():
            continue
        pos = athlete.get("position") or {}
        position = pos.get("abbreviation", "") if isinstance(pos, dict) else str(pos)
        roster[str(pid)] = {"id": str(pid), "name": name, "team": team_abbr, "position": position}
    return list(roster.values())

@st.cache_data(ttl=900, show_spinner=False)
def search_players(query: str) -> list[dict]:
    """Search ESPN's player index, then try every team roster independently.

    ESPN's search endpoint requires type=player for reliable player-only results.
    A failed roster request for one franchise must not stop the other teams.
    """
    q = query.strip().lower()
    if not q:
        return []
    found: dict[str, dict] = {}
    search_errors: list[str] = []
    # ESPN search has changed its nesting and filters over time. Try explicit
    # player typing first, then a sport-scoped variant; normalize nested results.
    search_variants = [
        {"region": "us", "lang": "en", "query": query, "limit": 50, "type": "player", "sport": "basketball", "league": "nba"},
        {"region": "us", "lang": "en", "query": query, "limit": 50, "type": "player", "sport": "basketball"},
    ]
    for params in search_variants:
        try:
            data = fetch_json(SEARCH_BASE, params)
            for node in walk_dicts(data):
                ident = node.get("id") or node.get("uid") or node.get("guid")
                name = node.get("displayName") or node.get("fullName") or node.get("name")
                typ = str(node.get("type", "")).lower()
                # ESPN UIDs can be URI-like or s:40~l:46~a:1234.
                pid = str(ident or "").rstrip("/").split("/")[-1]
                if "~a:" in pid:
                    pid = pid.rsplit("~a:", 1)[-1]
                if ident and name and pid.isdigit() and ("athlete" in typ or "player" in typ or node.get("position") is not None):
                    team = node.get("team") or {}
                    pos = node.get("position") or {}
                    found[pid] = {
                        "id": pid,
                        "name": name,
                        "team": team.get("abbreviation", "") if isinstance(team, dict) else "",
                        "position": pos.get("abbreviation", "") if isinstance(pos, dict) else "",
                    }
            if found:
                break
        except Exception as exc:
            search_errors.append(str(exc)[:180])

    # Roster fallback: isolate failures per team so one unavailable roster
    # cannot abort the entire league search.
    if not found:
        try:
            teams = get_teams()
        except Exception as exc:
            teams = []
            search_errors.append(f"Teams feed: {str(exc)[:160]}")
        for team in teams:
            try:
                for player in get_roster(team["id"]):
                    if q in player["name"].lower():
                        player["team"] = player.get("team") or team["abbr"]
                        found[player["id"]] = player
            except Exception as exc:
                # Continue searching other franchises if one roster fails.
                search_errors.append(f"{team.get('abbr', team['id'])}: {str(exc)[:100]}")
    results = sorted(found.values(), key=lambda player: player["name"].lower())
    return results[:30]

@st.cache_data(ttl=1800, show_spinner=False)
def get_athlete_overview(player_id: str) -> dict:
    return fetch_json(f"{WEB_BASE}/athletes/{player_id}/overview")

@st.cache_data(ttl=1800, show_spinner=False)
def get_athlete_stats(player_id: str, season: int) -> dict:
    return fetch_json(f"{WEB_BASE}/athletes/{player_id}/stats", {"season": season, "seasontype": 2})

@st.cache_data(ttl=900, show_spinner=False)
def get_gamelog(player_id: str, season: int) -> dict:
    return fetch_json(f"{WEB_BASE}/athletes/{player_id}/gamelog", {"season": season, "seasontype": 2})

@st.cache_data(ttl=600, show_spinner=False)
def get_game_summary(event_id: str) -> dict:
    return fetch_json(f"{BASE}/summary", {"event": event_id})

# ---------------- Parsing and calculations ----------------
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
        rows.append({"Game": event.get("name", "Matchup"), "Away": (away.get("team") or {}).get("displayName", "Away"), "Away score": away.get("score", "—"), "Home": (home.get("team") or {}).get("displayName", "Home"), "Home score": home.get("score", "—"), "Status": status.get("shortDetail") or status.get("description") or "Scheduled", "Start": event.get("date", ""), "Event ID": event.get("id", "")})
    return rows

def _stat_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"--", "-", "—"}:
        return None
    # ESPN shooting stats are often represented as made-attempted; props need made.
    if re.fullmatch(r"\d+\s*[-/]\s*\d+", text):
        text = re.split(r"[-/]", text)[0].strip()
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None

def parse_gamelog(data: dict) -> pd.DataFrame:
    labels = data.get("names") or data.get("labels") or []
    records: list[dict] = []
    events = data.get("events", [])
    if isinstance(events, dict):
        events = list(events.values())
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        raw_stats = event.get("stats") or event.get("statistics") or []
        row: dict[str, Any] = {"Date": event.get("date") or event.get("eventDate"), "Result": event.get("gameResult") or event.get("result", ""), "Home/Away": event.get("homeAway", "")}
        opponent = event.get("opponent") or event.get("opponentDisplayName") or ""
        row["Opponent"] = (opponent.get("displayName") or opponent.get("abbreviation") or opponent.get("name", "")) if isinstance(opponent, dict) else opponent
        if isinstance(raw_stats, dict):
            row.update(raw_stats)
        elif isinstance(raw_stats, list):
            # ESPN game-log event arrays commonly omit DATE/OPP/RESULT, so align
            # a shorter stats array with the trailing stat names, not index zero.
            keys = labels[-len(raw_stats):] if labels and len(raw_stats) < len(labels) else labels
            for idx, value in enumerate(raw_stats):
                key = keys[idx] if idx < len(keys) else f"stat_{idx}"
                row[str(key)] = value
        records.append(row)
    # Alternate nested event format used by some ESPN responses.
    if not records:
        for node in walk_dicts(data):
            evs = node.get("events")
            if isinstance(evs, list) and evs is not events:
                for event in evs:
                    if isinstance(event, dict) and (event.get("stats") or event.get("statistics")):
                        records.append(event)
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "Date" not in df.columns:
        date_col = next((c for c in df.columns if str(c).lower() in {"date", "eventdate"}), None)
        if date_col:
            df["Date"] = df[date_col]
    df["Date"] = pd.to_datetime(df.get("Date"), errors="coerce", utc=True)
    if "Opponent" not in df:
        df["Opponent"] = ""
    if "Result" not in df:
        df["Result"] = ""
    # Normalize ESPN names/labels to stable market columns.
    aliases = {
        "points": {"points", "pts"}, "rebounds": {"rebounds", "reb", "totalrebounds"},
        "assists": {"assists", "ast"}, "threepointsmade": {"threepointsmade", "threepointersmade", "3pm", "3pt", "threepointfieldgoalsmade"},
        "steals": {"steals", "stl"}, "blocks": {"blocks", "blk"}, "minutes": {"minutes", "min"}
    }
    rename = {}
    for col in df.columns:
        normalized = re.sub(r"[^a-z0-9]", "", str(col).lower())
        for target, names in aliases.items():
            if normalized in names:
                rename[col] = target
                break
    df = df.rename(columns=rename)
    for col in df.columns:
        if col not in {"Date", "Opponent", "Result", "Home/Away"}:
            df[col] = df[col].map(_stat_number)
    df = df.dropna(subset=["Date"]).sort_values("Date", ascending=False).drop_duplicates(subset=["Date", "Opponent"], keep="first").reset_index(drop=True)
    return df

def stat_series(df: pd.DataFrame, market: str) -> pd.Series | None:
    mapping = {"Points": "points", "Rebounds": "rebounds", "Assists": "assists", "3-pointers made": "threepointsmade", "Steals": "steals", "Blocks": "blocks"}
    if market == "PRA":
        if not all(c in df.columns for c in ["points", "rebounds", "assists"]):
            return None
        return df["points"] + df["rebounds"] + df["assists"]
    col = mapping.get(market)
    return pd.to_numeric(df[col], errors="coerce") if col in df.columns else None

def show_recent_averages(log: pd.DataFrame):
    markets = [("Points", "points"), ("Rebounds", "rebounds"), ("Assists", "assists")]
    cols = st.columns(3)
    for col, (label, field) in zip(cols, markets):
        vals = log[field].dropna() if field in log else pd.Series(dtype=float)
        col.metric(f"{label} L5 / L10 / L20", " / ".join(f"{vals.head(n).mean():.1f}" if len(vals.head(n)) else "—" for n in (5, 10, 20)))

def player_picker(key: str):
    query = st.text_input("Search NBA player", placeholder="Try LeBron James or Stephen Curry", key=f"player_query_{key}")
    if len(query.strip()) < 3:
        st.caption("Enter at least 3 letters. Search uses ESPN's player directory with team-roster fallback.")
        return None
    with st.spinner("Searching ESPN player directory..."):
        players = search_players(query.strip())
    if not players:
        st.warning("No player results returned by ESPN. The search now tries ESPN's player-only search and team rosters; if it still fails, the public feed may be blocking or changing its response.")
        with st.expander("Player search troubleshooting"):
            st.write("Try a shorter search such as Curry, Durant, or Giannis. If all searches fail, ESPN's public player directory is currently unavailable to this app.")
        return None
    labels = [f"{p['name']}" + (f" — {p['team']}" if p.get("team") else "") for p in players]
    selected = st.selectbox("Select player", range(len(players)), format_func=lambda i: labels[i], key=f"player_select_{key}")
    return players[selected]

# ---------------- Pick tracker database ----------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS picks (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, player TEXT, market TEXT, line REAL, side TEXT, opponent TEXT, result TEXT DEFAULT 'Pending', notes TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS parlays (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, name TEXT, legs_json TEXT, result TEXT DEFAULT 'Pending')")
        conn.commit()

def load_picks() -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM picks ORDER BY id DESC", conn)

def add_pick(player: str, market: str, line: float, side: str, opponent: str, notes: str):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO picks(player,market,line,side,opponent,notes) VALUES(?,?,?,?,?,?)", (player, market, float(line), side, opponent, notes))
        conn.commit()

def set_pick_result(pick_id: int, result: str):
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

# ---------------- Main interface ----------------
st.markdown('<div class="hero"><h1>PROJECT HUSTLE AI</h1><p>Research the numbers. Understand the matchup. Track your process.</p></div>', unsafe_allow_html=True)
sections = ["Dashboard", "Player Research", "Injury Center", "Prop Analyzer", "Matchup Research", "Pick Tracker & Parlays"]
section = st.selectbox("Navigate HUSTLE AI", sections, key="main_navigation")
st.caption("NBA analytics workspace • ESPN public data • No paid API key • Data availability can vary")

if section == "Dashboard":
    st.subheader("NBA scoreboard")
    selected_day = st.date_input("Game date", value=date.today())
    try:
        with st.spinner("Loading NBA games..."):
            board = get_scoreboard(selected_day.strftime("%Y%m%d"))
        games = scoreboard_rows(board)
        if games:
            live = sum(any(term in str(g["Status"]).lower() for term in ["in progress", "quarter", "half"]) for g in games)
            a, b, c = st.columns(3)
            a.metric("Games", len(games)); b.metric("Live", live); c.metric("Season", (board.get("leagues") or [{}])[0].get("season", {}).get("displayName", "NBA"))
            st.dataframe(pd.DataFrame(games).drop(columns=["Event ID"]), use_container_width=True, hide_index=True)
            with st.expander("Game details / box score"):
                ids = {f"{g['Game']} • {g['Event ID']}": g["Event ID"] for g in games if g["Event ID"]}
                if ids:
                    chosen = st.selectbox("Choose a game", list(ids))
                    if st.button("Load game summary"):
                        try: st.json(get_game_summary(ids[chosen]), expanded=False)
                        except Exception as exc: st.warning(f"Game summary unavailable: {exc}")
        else:
            st.info("No NBA games are listed for this date. Try another date.")
    except Exception as exc:
        st.error(f"ESPN scoreboard unavailable: {exc}")
    with st.expander("League standings"):
        try:
            data = get_standings(); rows = []
            for node in walk_dicts(data):
                team = node.get("team")
                stats = node.get("stats")
                if isinstance(team, dict) and isinstance(stats, list):
                    row = {"Team": team.get("displayName") or team.get("name", "")}
                    for stat in stats:
                        if isinstance(stat, dict) and stat.get("name") in {"wins", "losses", "winPercent", "streak"}:
                            row[stat["name"]] = stat.get("displayValue") or stat.get("value")
                    if len(row) > 1: rows.append(row)
            if rows: st.dataframe(pd.DataFrame(rows).drop_duplicates(), use_container_width=True, hide_index=True)
            else: st.info("Standings returned, but the response format could not be normalized.")
        except Exception as exc: st.info(f"Standings unavailable: {exc}")

elif section == "Player Research":
    st.subheader("Player research & game logs")
    player = player_picker("research")
    if player:
        st.markdown(f"### {player['name']}")
        st.caption(f"ESPN athlete ID: {player['id']} • {player.get('team', '')} {player.get('position', '')}")
        season = st.selectbox("Season", [2027,  2026, 2025, 2024, 2023], index=0, key="research_season")
        try:
            overview = get_athlete_overview(player["id"])
            stats_obj = overview.get("statistics", {})
            if stats_obj.get("labels") and stats_obj.get("displayValues"):
                st.markdown("#### Season snapshot")
                st.dataframe(pd.DataFrame([stats_obj["displayValues"]], columns=stats_obj["labels"]), use_container_width=True, hide_index=True)
            with st.expander("ESPN player overview details"): st.json(overview, expanded=False)
        except Exception as exc: st.info(f"Player overview unavailable: {exc}")
        try:
            stats = get_athlete_stats(player["id"], season)
            categories = stats.get("categories", [])
            stat_rows = []
            for cat in categories:
                labels = cat.get("labels", []); totals = cat.get("totals", [])
                for label, value in zip(labels, totals): stat_rows.append({"Category": cat.get("displayName", cat.get("name", "Stats")), "Statistic": label, "Value": value})
            if stat_rows:
                st.markdown("#### Season statistics")
                st.dataframe(pd.DataFrame(stat_rows), use_container_width=True, hide_index=True)
            else:
                st.caption("Season statistics were not supplied in the current ESPN response.")
        except Exception as exc: st.info(f"Season statistics unavailable: {exc}")
        try:
            log = parse_gamelog(get_gamelog(player["id"], season))
            if not log.empty:
                st.markdown("#### Recent game logs")
                show_recent_averages(log)
                st.dataframe(log.head(20), use_container_width=True, hide_index=True)
            else:
                st.warning("ESPN did not return recognizable game rows for this season. Try a previous season or check back later.")
        except Exception as exc: st.warning(f"Game logs unavailable: {exc}")

elif section == "Injury Center":
    st.subheader("NBA injury center")
    st.caption("Public ESPN injury information can be incomplete or delayed. No statuses are inferred.")
    if st.button("Refresh injury feed"): get_injuries.clear()
    try:
        data = get_injuries(); rows = []
        groups = data.get("injuries", [])
        for group in groups:
            team = group.get("team", {})
            for injury in group.get("injuries", []):
                athlete = injury.get("athlete", {})
                rows.append({"Player": athlete.get("displayName", "Unknown"), "Team": team.get("displayName") or team.get("abbreviation", "Unknown"), "Status": injury.get("status", "Not specified"), "Injury": (injury.get("type") or {}).get("name", "Not specified"), "Details": injury.get("details", ""), "Report date": injury.get("date", "")})
        if rows: st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else: st.info("No injury entries were present in ESPN's current response.")
        st.caption(f"Source: ESPN public injury endpoint • Retrieved {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    except Exception as exc: st.error(f"Injury feed unavailable: {exc}")

elif section == "Prop Analyzer":
    st.subheader("Player prop analyzer")
    st.caption("Enter a line from your sportsbook. ESPN does not provide a complete sportsbook prop board.")
    player = player_picker("prop")
    if player:
        col1, col2, col3 = st.columns([1.3, 1, 1])
        with col1: market = st.selectbox("Stat market", ["Points", "Rebounds", "Assists", "3-pointers made", "Steals", "Blocks", "PRA"])
        with col2: line = st.number_input("Prop line", min_value=0.0, max_value=300.0, value=20.5, step=0.5)
        with col3: season = st.selectbox("Season", [2027, 2026, 2025, 2024, 2023], key="prop_season")
        if st.button("Analyze player prop", type="primary", use_container_width=True):
            st.session_state["active_prop"] = {"player": player, "market": market, "line": line, "season": season}
        prop = st.session_state.get("active_prop")
        if prop and prop["player"]["id"] == player["id"]:
            try:
                log = parse_gamelog(get_gamelog(player["id"], prop["season"]))
                values = stat_series(log, prop["market"]) if not log.empty else None
                if values is None:
                    st.warning(f"ESPN did not supply the {prop['market']} stat in this game-log response. No hit rate was calculated.")
                else:
                    valid = pd.DataFrame({"Date": log["Date"], "Opponent": log["Opponent"], "Result": values}).dropna(subset=["Result"]).sort_values("Date", ascending=False)
                    valid["Outcome"] = valid["Result"].apply(lambda x: "Over" if x > prop["line"] else ("Under" if x < prop["line"] else "Push"))
                    total = len(valid); over = int((valid["Result"] > prop["line"]).sum()); under = int((valid["Result"] < prop["line"]).sum()); push = int((valid["Result"] == prop["line"]).sum())
                    a,b,c,d = st.columns(4); a.metric("Games", total); b.metric("Over", f"{over}/{total}" if total else "—"); c.metric("Under", f"{under}/{total}" if total else "—"); d.metric("Push", push)
                    rows = []
                    for n in [5, 10, 20]:
                        sample = valid.head(n); count = len(sample)
                        rows.append({"Sample": f"Last {n}", "Games": count, "Average": round(sample["Result"].mean(), 2) if count else "—", "Over %": round((sample["Result"] > prop["line"]).mean()*100, 1) if count else "—", "Under %": round((sample["Result"] < prop["line"]).mean()*100, 1) if count else "—"})
                    st.markdown("#### Recent sample breakdown")
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    st.markdown("#### Game-by-game results")
                    st.dataframe(valid.head(20), use_container_width=True, hide_index=True)
                    st.caption("Historical frequencies only; not predictions or calibrated probabilities. Pushes are excluded from over/under rates.")
                    side = st.radio("Save which side?", ["Over", "Under"], horizontal=True, key="save_side")
                    notes = st.text_input("Notes (optional)", key="prop_notes")
                    if st.button("Save pick to tracker"):
                        add_pick(prop["player"]["name"], prop["market"], prop["line"], side, "", notes)
                        st.success("Pick saved in this app's local tracker. Open Pick Tracker & Parlays from the navigation menu.")
            except Exception as exc: st.error(f"Unable to analyze this player: {exc}")

elif section == "Matchup Research":
    st.subheader("Matchup research")
    st.caption("Schedule and box-score information only; defensive rankings are not fabricated.")
    try:
        games = scoreboard_rows(get_scoreboard())
        if games:
            labels = [f"{g['Away']} at {g['Home']} • {g['Status']}" for g in games]
            selected = st.selectbox("Today's matchup", range(len(games)), format_func=lambda i: labels[i])
            game = games[selected]
            st.markdown(f"### {game['Away']} at {game['Home']}")
            st.write(f"**Status:** {game['Status']}  ")
            st.write(f"**Score:** {game['Away score']} – {game['Home score']}")
            if st.button("Load matchup / box score"):
                try: st.json(get_game_summary(game["Event ID"]), expanded=False)
                except Exception as exc: st.info(f"Game details unavailable: {exc}")
        else: st.info("No games on today's scoreboard. Check Dashboard to select another date.")
    except Exception as exc: st.warning(f"Matchup schedule unavailable: {exc}")

elif section == "Pick Tracker & Parlays":
    st.subheader("Pick tracker & parlay workspace")
    picks = load_picks()
    if picks.empty:
        st.info("No saved picks yet. Analyze a player prop and select Save pick to tracker.")
    else:
        wins = int((picks["result"] == "Win").sum()); losses = int((picks["result"] == "Loss").sum()); pending = int((picks["result"] == "Pending").sum())
        a,b,c,d = st.columns(4); a.metric("Saved picks", len(picks)); b.metric("Wins", wins); c.metric("Losses", losses); d.metric("Pending", pending)
        st.dataframe(picks, use_container_width=True, hide_index=True)
        pending_rows = picks[picks["result"] == "Pending"]
        if not pending_rows.empty:
            st.markdown("#### Settle a pick")
            chosen = st.selectbox("Pick", pending_rows["id"].tolist(), format_func=lambda x: f"#{x} — {pending_rows.loc[pending_rows.id.eq(x), 'player'].iloc[0]} {pending_rows.loc[pending_rows.id.eq(x), 'market'].iloc[0]}")
            result = st.selectbox("Result", ["Win", "Loss", "Push", "Void"])
            if st.button("Save pick result"):
                set_pick_result(chosen, result); st.success("Pick result updated."); st.rerun()
        st.markdown("#### Build a parlay")
        pending_rows = picks[picks["result"] == "Pending"]
        if len(pending_rows) >= 2:
            chosen_ids = st.multiselect("Select parlay legs", pending_rows["id"].tolist(), format_func=lambda x: f"#{x} {pending_rows.loc[pending_rows.id.eq(x), 'player'].iloc[0]} — {pending_rows.loc[pending_rows.id.eq(x), 'market'].iloc[0]}")
            if chosen_ids:
                parlay_name = st.text_input("Parlay name", value=f"HUSTLE slip {datetime.now().strftime('%m/%d')}")
                if st.button("Save parlay"):
                    legs = pending_rows[pending_rows["id"].isin(chosen_ids)][["id", "player", "market", "line", "side"]].to_dict("records")
                    save_parlay(parlay_name.strip() or "My parlay", legs); st.success("Parlay saved."); st.rerun()
        else:
            st.caption("Save at least two pending picks to build a parlay.")
    parlays = load_parlays()
    if not parlays.empty:
        st.markdown("#### Saved parlays")
        view = parlays.copy(); view["Legs"] = view["legs_json"].apply(lambda x: len(json.loads(x)) if x else 0)
        st.dataframe(view[["id", "created_at", "name", "Legs", "result"]], use_container_width=True, hide_index=True)
        pending_parlays = parlays[parlays["result"] == "Pending"]
        if not pending_parlays.empty:
            pid = st.selectbox("Parlay to settle", pending_parlays["id"].tolist(), format_func=lambda x: f"#{x} — {pending_parlays.loc[pending_parlays.id.eq(x), 'name'].iloc[0]}")
            result = st.selectbox("Parlay result", ["Win", "Loss", "Push", "Void"], key="parlay_result")
            if st.button("Save parlay result"):
                set_parlay_result(pid, result); st.success("Parlay result updated."); st.rerun()
    st.warning("Important: SQLite on Streamlit Community Cloud is local storage and may reset after restarts or redeployments. Use this tracker as a prototype until we add a free persistent database.")

st.divider()
st.caption("PROJECT HUSTLE AI • NBA FIRST • ESPN public data • Research tool only — no guaranteed outcomes.")
