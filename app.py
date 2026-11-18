from __future__ import annotations

import html
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
:root {
  --h-bg:#080e18; --h-panel:#111c2b; --h-panel2:#172438;
  --h-border:#263952; --h-text:#f4f7fc; --h-muted:#aebbd0;
  --h-green:#55e6a5; --h-blue:#65a9ff;
}
.stApp {background:radial-gradient(ellipse at 50% -15%,#1a3150 0%,#0b1422 42%,var(--h-bg) 78%);color:var(--h-text)}
.block-container {max-width:1180px;padding:1rem 1.1rem 3.5rem}
header[data-testid="stHeader"] {background:rgba(8,14,24,.88)}
.hero {position:relative;overflow:hidden;padding:1.45rem 1.5rem;border:1px solid #294363;border-radius:22px;background:linear-gradient(115deg,#142b45 0%,#101b2c 58%,#102b2b 100%);margin:0 0 1rem;box-shadow:0 16px 42px rgba(0,0,0,.25)}
.hero:after {content:"";position:absolute;width:190px;height:190px;right:-65px;top:-85px;border:28px solid rgba(85,230,165,.10);border-radius:50%}
.hero h1 {letter-spacing:.07em;margin:0;font-size:2rem;line-height:1.15;font-weight:850;color:#f6f9ff}
.hero p {color:#c1d0e2;margin:.55rem 0 0;font-size:.98rem}
.hero-kicker {font-size:.68rem;letter-spacing:.19em;font-weight:800;color:var(--h-green);margin-bottom:.45rem}
h1,h2,h3 {letter-spacing:-.025em;color:var(--h-text)}
h2 {margin-top:.4rem;font-size:1.5rem}
h3 {font-size:1.15rem}
p, label, .stMarkdown {color:var(--h-text)}
[data-testid="stCaptionContainer"],.caption {color:var(--h-muted)}
[data-testid="stMetric"] {background:linear-gradient(145deg,#152338,#101a29);border:1px solid var(--h-border);padding:15px 16px;border-radius:17px;min-height:94px;box-shadow:0 8px 22px rgba(0,0,0,.13)}
[data-testid="stMetricLabel"] {color:var(--h-muted);font-size:.82rem;font-weight:650}
[data-testid="stMetricValue"] {color:var(--h-text);font-size:1.65rem;font-weight:750}
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,[data-testid="stSelectbox"] [role="combobox"],[data-testid="stDateInput"] input {min-height:3rem;border-radius:12px;background:#111d2d;border:1px solid #30445f;color:#f4f7fc}
[data-testid="stTextInput"] label,[data-testid="stNumberInput"] label,[data-testid="stSelectbox"] label,[data-testid="stRadio"] label,[data-testid="stDateInput"] label {color:#dce6f3;font-weight:650}
.stButton>button,[data-testid="stDownloadButton"] button {border-radius:13px;min-height:3rem;font-weight:750;border:1px solid #39785f;background:linear-gradient(110deg,#1b805c,#176b55);color:white;box-shadow:0 7px 18px rgba(22,130,91,.16);transition:transform .15s ease,filter .15s ease}
.stButton>button:hover,[data-testid="stDownloadButton"] button:hover {filter:brightness(1.12);transform:translateY(-1px)}
[data-testid="stAlert"],[data-testid="stExpander"] {border-radius:14px}
[data-testid="stExpander"] {border:1px solid var(--h-border);background:rgba(17,28,43,.72)}
hr {border-color:var(--h-border)}
[data-testid="stDataFrame"],[data-testid="stTable"] {border:1px solid var(--h-border);border-radius:14px;overflow:hidden}
.hustle-game {background:linear-gradient(145deg,#142238,#101a29);border:1px solid #2b405c;border-radius:16px;padding:13px 14px;margin:.45rem 0;box-shadow:0 7px 18px rgba(0,0,0,.13)}
.hustle-game-top {display:flex;justify-content:space-between;gap:10px;color:#aebbd0;font-size:.78rem;margin-bottom:9px}
.hustle-game-grid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}
.hustle-stat {background:#0c1522;border-radius:10px;padding:9px 7px;text-align:center;min-width:0}
.hustle-stat strong {display:block;color:#f4f7fc;font-size:1.08rem;line-height:1.2}
.hustle-stat span {display:block;color:#9eacc1;font-size:.65rem;letter-spacing:.07em;margin-top:4px}
.hustle-result {font-weight:800;color:var(--h-green)}
.hustle-box-player {background:linear-gradient(145deg,#142238,#101a29);border:1px solid #2b405c;border-radius:13px;padding:11px 12px;margin:8px 0}
.hustle-box-player-name {font-weight:800;color:#f4f7fc;font-size:.95rem;margin-bottom:9px}
.hustle-box-stats {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
.hustle-box-stat {background:#0b1523;border-radius:8px;padding:7px 4px;text-align:center;min-width:0}
.hustle-box-stat b {display:block;color:#f4f7fc;font-size:.9rem;overflow-wrap:anywhere}
.hustle-box-stat span {display:block;color:#9eacc1;font-size:.62rem;letter-spacing:.04em;margin-top:3px}
.hustle-nav-label {color:#55e6a5;font-size:.72rem;font-weight:800;letter-spacing:.14em;margin:.35rem 0}
@media(max-width:760px) {
 .block-container {padding:.55rem .65rem 2.3rem}
 .hero {padding:1.05rem 1rem;border-radius:17px;margin-bottom:.8rem}
 .hero h1 {font-size:1.48rem;letter-spacing:.045em}
 .hero p {font-size:.86rem;line-height:1.4;max-width:95%}
 h2 {font-size:1.28rem !important} h3 {font-size:1.05rem !important}
 [data-testid="stHorizontalBlock"] {flex-wrap:wrap;gap:.5rem}
 [data-testid="column"] {min-width:calc(50% - .3rem) !important;flex:1 1 calc(50% - .3rem) !important}
 [data-testid="stMetric"] {min-height:82px;padding:10px 11px;border-radius:14px}
 [data-testid="stMetricLabel"] {font-size:.72rem}
 [data-testid="stMetricValue"] {font-size:1.25rem}
 .stButton>button,[data-testid="stDownloadButton"] button {width:100%;min-height:3.05rem}
 [data-testid="stDataFrame"] {max-width:100%;overflow-x:auto}
 [data-testid="stDataFrame"] iframe {max-width:100%}
 [data-testid="stSelectbox"],[data-testid="stTextInput"],[data-testid="stNumberInput"],[data-testid="stDateInput"] {width:100%}
 [data-testid="stRadio"]>div {flex-wrap:wrap;gap:.4rem}
 .hustle-game {padding:11px;border-radius:14px}
 .hustle-game-grid {grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}
 .hustle-stat {padding:8px 3px}
 .hustle-stat strong {font-size:1rem}
 .hustle-stat span {font-size:.58rem;letter-spacing:.03em}
 .hustle-box-stats {grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}
 .hustle-box-player {padding:10px}
}
@media(max-width:390px) {
 [data-testid="column"] {min-width:100% !important;flex:1 1 100% !important}
 .hustle-game-grid {grid-template-columns:repeat(2,minmax(0,1fr))}
}

.hustle-prop-hero {background:linear-gradient(135deg,#142b45,#102b2b);border:1px solid #34516e;border-radius:20px;padding:18px;margin:8px 0 16px;box-shadow:0 12px 30px rgba(0,0,0,.2)}
.hustle-prop-kicker {color:#55e6a5;font-size:.7rem;font-weight:850;letter-spacing:.13em}
.hustle-prop-player {color:#f4f7fc;font-size:1.15rem;font-weight:800;margin-top:6px}
.hustle-prop-record {color:#f4f7fc;font-size:1.05rem;font-weight:800;margin:15px 0 10px}
.hustle-prop-record span {color:#8fa2ba;padding:0 5px}
.hustle-prop-bar {height:10px;border-radius:20px;background:#263952;overflow:hidden}
.hustle-prop-bar div {height:100%;background:linear-gradient(90deg,#55e6a5,#2eae80);border-radius:20px}
.hustle-prop-split {display:flex;justify-content:space-between;color:#dce6f3;font-size:.75rem;font-weight:800;margin-top:8px}
.hustle-prop-foot {color:#aebbd0;font-size:.72rem;margin-top:9px}
.hustle-sample-card {background:linear-gradient(145deg,#15263c,#101a29);border:1px solid #2b405c;border-radius:15px;padding:12px 10px;margin:5px 0;text-align:center;min-height:126px}
.hustle-sample-label {color:#55e6a5;font-size:.67rem;font-weight:850;letter-spacing:.1em}
.hustle-sample-average {color:#f4f7fc;font-size:1.65rem;font-weight:850;line-height:1.35;margin-top:4px}
.hustle-sample-caption {color:#aebbd0;font-size:.61rem;line-height:1.4}
.hustle-sample-hit {color:#55e6a5;font-size:.85rem;font-weight:850;margin:5px 0 2px}
.hustle-prop-game {display:flex;align-items:center;justify-content:space-between;gap:12px;background:#111c2b;border:1px solid #263952;border-radius:12px;padding:11px 13px;margin:6px 0}
.hustle-prop-game>div:first-child {min-width:0}
.hustle-prop-game strong {display:block;color:#f4f7fc;font-size:.9rem}
.hustle-prop-game span {display:block;color:#aebbd0;font-size:.72rem;margin-top:3px;overflow-wrap:anywhere}
.hustle-prop-game-result {text-align:right;flex-shrink:0}
.hustle-prop-game-result strong {font-size:1.1rem}
@media(max-width:600px) {
 .hustle-prop-hero {padding:15px;border-radius:16px}
 .hustle-sample-card {padding:10px 5px;min-height:116px}
 .hustle-sample-average {font-size:1.4rem}
 .hustle-prop-game {padding:10px}
}

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
    # ESPN sometimes supplies minutes as MM:SS; convert to decimal minutes.
    if re.fullmatch(r"\d{1,3}:\d{2}", text):
        minutes, seconds = text.split(":", 1)
        return float(minutes) + float(seconds) / 60.0
    # ESPN shooting stats are often represented as made-attempted; props need made.
    if re.fullmatch(r"\d+\s*[-/]\s*\d+", text):
        text = re.split(r"[-/]", text)[0].strip()
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None

def parse_gamelog(data: dict) -> pd.DataFrame:
    """Normalize ESPN Web API v3 game logs.

    ESPN's current response stores game metadata in an ``events`` dictionary,
    while the actual stat rows are nested under
    ``seasonTypes[].categories[].events[]``. Older/alternate responses may
    still provide a flat events list, so both shapes are supported.
    """
    labels = data.get("names") or data.get("labels") or data.get("displayNames") or []
    metadata = data.get("events", {})
    records: list[dict[str, Any]] = []

    def metadata_for(event_id: Any) -> dict:
        if isinstance(metadata, dict):
            item = metadata.get(str(event_id), {})
            return item if isinstance(item, dict) else {}
        if isinstance(metadata, list):
            return next((x for x in metadata if isinstance(x, dict) and str(x.get("id")) == str(event_id)), {})
        return {}

    def append_stat_event(stat_event: dict):
        raw_stats = stat_event.get("stats") or stat_event.get("statistics") or []
        event_id = stat_event.get("eventId") or stat_event.get("id")
        meta = metadata_for(event_id)
        # Some variants put all event metadata directly on the stat row.
        merged = {**meta, **stat_event}
        row: dict[str, Any] = {
            "Date": merged.get("date") or merged.get("gameDate") or merged.get("eventDate"),
            "Result": merged.get("gameResult") or merged.get("result", ""),
            "Home/Away": merged.get("homeAway") or merged.get("home_away", ""),
        }
        opponent = merged.get("opponent") or merged.get("opponentDisplayName") or merged.get("opponent_display_name") or ""
        row["Opponent"] = (opponent.get("displayName") or opponent.get("abbreviation") or opponent.get("name", "")) if isinstance(opponent, dict) else opponent
        if isinstance(raw_stats, dict):
            row.update(raw_stats)
        elif isinstance(raw_stats, list):
            # ESPN responses are inconsistent: some label arrays contain only
            # stat fields (MIN, FG, 3PT...), while others also include the
            # metadata fields DATE, OPP and RESULT. The stats array excludes
            # those three metadata values, so align from the right when needed.
            stat_labels = labels
            if len(labels) - len(raw_stats) in (1, 2, 3):
                stat_labels = labels[len(labels) - len(raw_stats):]
            for idx, value in enumerate(raw_stats):
                key = stat_labels[idx] if idx < len(stat_labels) else f"stat_{idx}"
                row[str(key)] = value
        if row.get("Date") or any(k not in {"Date", "Result", "Home/Away", "Opponent"} for k in row):
            records.append(row)

    # Current ESPN Web API v3 layout: seasonTypes -> categories -> events.
    season_types = data.get("seasonTypes", [])
    if isinstance(season_types, list):
        for season_type in season_types:
            if not isinstance(season_type, dict):
                continue
            for category in season_type.get("categories", []) or []:
                if not isinstance(category, dict):
                    continue
                for stat_event in category.get("events", []) or []:
                    if isinstance(stat_event, dict):
                        append_stat_event(stat_event)

    # Older/alternate layout: events is a flat list of rows with inline stats.
    if not records:
        flat_events = metadata if isinstance(metadata, list) else []
        for event in flat_events:
            if isinstance(event, dict) and (event.get("stats") or event.get("statistics")):
                append_stat_event(event)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    # Normalize ESPN labels/names to stable market columns.
    aliases = {
        "points": {"points", "pts"},
        "rebounds": {"rebounds", "reb", "totalrebounds"},
        "assists": {"assists", "ast"},
        "threepointsmade": {"threepointsmade", "threepointersmade", "3pm", "3pt", "threepointfieldgoalsmade", "threepointfieldgoalsmade"},
        "steals": {"steals", "stl"},
        "blocks": {"blocks", "blk"},
        "minutes": {"minutes", "min"},
    }
    rename = {}
    for col in df.columns:
        normalized = re.sub(r"[^a-z0-9]", "", str(col).lower())
        for target, names in aliases.items():
            if normalized in names:
                rename[col] = target
                break
    df = df.rename(columns=rename)
    df["Date"] = pd.to_datetime(df.get("Date"), errors="coerce", utc=True)
    for col in df.columns:
        if col not in {"Date", "Opponent", "Result", "Home/Away"}:
            df[col] = df[col].map(_stat_number)
    if "Opponent" not in df:
        df["Opponent"] = ""
    if "Result" not in df:
        df["Result"] = ""
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

def render_game_cards(log: pd.DataFrame, limit: int = 20):
    """Render compact game cards instead of a wide, clipped table on phones."""
    if log.empty:
        st.info("No game rows are available for this player and season.")
        return
    fields = [("PTS", "points"), ("REB", "rebounds"), ("AST", "assists"), ("MIN", "minutes")]
    for _, row in log.head(limit).iterrows():
        dt = row.get("Date")
        date_label = dt.strftime("%b %d, %Y") if pd.notna(dt) else "Date unavailable"
        opponent = str(row.get("Opponent") or "Opponent unavailable")
        result = str(row.get("Result") or "")
        cells = []
        for label, field in fields:
            value = row.get(field)
            display = f"{value:.0f}" if pd.notna(value) and field == "minutes" else (f"{value:.1f}" if pd.notna(value) else "—")
            cells.append(f'<div class="hustle-stat"><strong>{display}</strong><span>{label}</span></div>')
        st.markdown(
            f'<div class="hustle-game"><div class="hustle-game-top"><span>{date_label} · {opponent}</span><span class="hustle-result">{result}</span></div><div class="hustle-game-grid">{"".join(cells)}</div></div>',
            unsafe_allow_html=True,
        )

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



def render_game_summary(summary: dict):
    """Render ESPN game summary as readable matchup cards and box-score tables.

    Never expose the raw ESPN JSON payload in the public interface.
    """
    header = summary.get("header") or {}
    competition = (header.get("competitions") or [{}])[0]
    competitors = competition.get("competitors") or []
    if competitors:
        st.markdown("#### Final score / game status")
        score_cols = st.columns(len(competitors))
        for col, team in zip(score_cols, competitors):
            team_obj = team.get("team") or {}
            col.metric(team_obj.get("displayName") or team_obj.get("abbreviation") or "Team", team.get("score", "—"), "Winner" if team.get("winner") else None)

    leaders = summary.get("leaders") or []
    leader_cards = []
    for team_group in leaders:
        team = team_group.get("team") or {}
        team_name = team.get("displayName") or team.get("abbreviation") or "Team"
        for category in team_group.get("leaders") or []:
            category_name = category.get("displayName") or category.get("name") or "Leader"
            top = (category.get("leaders") or [{}])[0]
            athlete = top.get("athlete") or {}
            athlete_name = athlete.get("displayName") or athlete.get("fullName") or "Player"
            value = top.get("displayValue") or top.get("value") or "—"
            leader_cards.append((team_name, category_name, athlete_name, value))

    if leader_cards:
        st.markdown("#### Game leaders")
        for start in range(0, len(leader_cards), 2):
            cols = st.columns(2)
            for col, item in zip(cols, leader_cards[start:start + 2]):
                team_name, category_name, athlete_name, value = item
                with col:
                    st.markdown(f'<div class="hustle-game"><div class="hustle-game-top"><span>{team_name}</span><span>{category_name}</span></div><strong style="font-size:1rem;color:#f4f7fc">{athlete_name}</strong><div style="font-size:1.35rem;font-weight:800;color:#55e6a5;margin-top:.3rem">{value}</div></div>', unsafe_allow_html=True)

    boxscore = summary.get("boxscore") or {}
    player_groups = boxscore.get("players") or []
    if player_groups:
        st.markdown("#### Team box scores")
    for index, group in enumerate(player_groups):
        team = group.get("team") or {}
        team_name = team.get("displayName") or team.get("abbreviation") or "Team"
        with st.expander(f"{team_name} player statistics", expanded=(index == 0)):
            found_rows = False
            for stat_group in group.get("statistics") or []:
                labels = stat_group.get("labels") or stat_group.get("keys") or []
                player_cards = []
                for entry in stat_group.get("athletes") or []:
                    athlete = entry.get("athlete") or {}
                    player_name = athlete.get("displayName") or athlete.get("fullName") or "Player"
                    values = entry.get("stats") or []
                    stat_items = []
                    for idx, value in enumerate(values):
                        label = str(labels[idx] if idx < len(labels) else f"Stat {idx + 1}")
                        stat_items.append((label, str(value)))
                    if stat_items:
                        player_cards.append((player_name, stat_items))
                if player_cards:
                    found_rows = True
                    group_name = stat_group.get("name") or stat_group.get("displayName")
                    if group_name:
                        st.caption(str(group_name).replace("_", " ").title())
                    for player_name, stat_items in player_cards:
                        stat_html = "".join(
                            f'<div class="hustle-box-stat"><b>{html.escape(value)}</b><span>{html.escape(label)}</span></div>'
                            for label, value in stat_items
                        )
                        st.markdown(
                            f'<div class="hustle-box-player"><div class="hustle-box-player-name">{html.escape(player_name)}</div><div class="hustle-box-stats">{stat_html}</div></div>',
                            unsafe_allow_html=True,
                        )
            if not found_rows:
                st.info("ESPN did not include player-level box-score rows for this team.")

    if not leader_cards and not player_groups:
        st.info("ESPN returned the game summary, but did not include readable player leaders or box-score statistics for this game.")
        game_info = summary.get("gameInfo") or {}
        venue = game_info.get("venue") or {}
        if venue.get("fullName"):
            st.caption(f"Venue: {venue['fullName']}")
        st.caption("Raw technical data is hidden to keep the matchup page clean.")


# ---------------- Pick tracker database ----------------
def init_db():
    """Create tracker tables and safely migrate older SQLite schemas in place.

    Existing picks are preserved. Each missing column is added only when needed,
    so redeployments do not require deleting the user's database.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS picks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            player TEXT, market TEXT, line REAL, side TEXT,
            opponent TEXT, result TEXT DEFAULT 'Pending', notes TEXT
        )""")
        existing = {row[1] for row in conn.execute("PRAGMA table_info(picks)").fetchall()}
        migrations = {
            "created_at": "TEXT",
            "player": "TEXT",
            "market": "TEXT",
            "line": "REAL",
            "side": "TEXT",
            "opponent": "TEXT",
            "result": "TEXT DEFAULT 'Pending'",
            "notes": "TEXT",
        }
        for column, declaration in migrations.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE picks ADD COLUMN {column} {declaration}")
        if "created_at" not in existing:
            conn.execute("UPDATE picks SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        conn.execute("""CREATE TABLE IF NOT EXISTS parlays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            name TEXT, legs_json TEXT, result TEXT DEFAULT 'Pending'
        )""")
        parlay_columns = {row[1] for row in conn.execute("PRAGMA table_info(parlays)").fetchall()}
        parlay_migrations = {
            "created_at": "TEXT",
            "name": "TEXT",
            "legs_json": "TEXT",
            "result": "TEXT DEFAULT 'Pending'",
        }
        for column, declaration in parlay_migrations.items():
            if column not in parlay_columns:
                conn.execute(f"ALTER TABLE parlays ADD COLUMN {column} {declaration}")
        if "created_at" not in parlay_columns:
            conn.execute("UPDATE parlays SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
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
st.markdown('<div class="hero"><div class="hero-kicker">NBA ANALYTICS · BUILT TO COMPETE</div><h1>PROJECT HUSTLE AI</h1><p>Research the numbers. Read the matchup. Make your data-driven decisions.</p></div>', unsafe_allow_html=True)
sections = ["Dashboard", "Player Research", "Injury Center", "Prop Analyzer", "Matchup Research", "Pick Tracker & Parlays"]
section = st.selectbox("Where do you want to go?", sections, key="main_navigation", help="Choose a workspace. On phones, this menu is easier to use than a row of tabs.")
st.markdown('<div class="hustle-nav-label">YOUR WORKSPACE</div>', unsafe_allow_html=True)

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
                    if st.button("Load game summary", use_container_width=True):
                        try:
                            with st.spinner("Loading game details..."):
                                summary = get_game_summary(ids[chosen])
                            render_game_summary(summary)
                        except Exception as exc:
                            st.warning(f"Game summary unavailable: {exc}")
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
                render_game_cards(log.head(20))
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
    st.subheader("Prop Lab")
    st.caption("Build a player prop analysis from actual ESPN game logs. Enter the line shown by your sportsbook.")
    player = player_picker("prop")
    if player:
        st.markdown(
            f'<div class="hustle-game"><div class="hustle-game-top"><span>PLAYER SELECTED</span><span>{html.escape(str(player.get("team", "NBA")))}</span></div><strong style="font-size:1.25rem;color:#f4f7fc">{html.escape(player["name"])}</strong><div style="color:#aebbd0;font-size:.8rem;margin-top:4px">Choose a market and set your line below.</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("#### Build your prop")
        market = st.selectbox("Stat market", ["Points", "Rebounds", "Assists", "3-pointers made", "Steals", "Blocks", "PRA"], key="prop_market")
        c1, c2 = st.columns(2)
        with c1:
            line = st.number_input("Prop line", min_value=0.0, max_value=300.0, value=20.5, step=0.5, key="prop_line")
        with c2:
            season = st.selectbox("NBA season", [2027, 2026, 2025, 2024, 2023], key="prop_season")
        analyze = st.button("Analyze prop", type="primary", use_container_width=True)
        if analyze:
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
                    valid["Result"] = pd.to_numeric(valid["Result"], errors="coerce")
                    valid = valid.dropna(subset=["Result"]).copy()
                    valid["Outcome"] = valid["Result"].apply(lambda x: "Over" if x > prop["line"] else ("Under" if x < prop["line"] else "Push"))
                    total = len(valid)
                    over = int((valid["Result"] > prop["line"]).sum())
                    under = int((valid["Result"] < prop["line"]).sum())
                    push = int((valid["Result"] == prop["line"]).sum())
                    decided = over + under
                    over_pct = (over / decided * 100) if decided else 0
                    under_pct = (under / decided * 100) if decided else 0
                    st.markdown("#### Historical results")
                    st.markdown(
                        f'<div class="hustle-prop-hero"><div class="hustle-prop-kicker">{html.escape(prop["market"].upper())} · LINE {prop["line"]:g}</div><div class="hustle-prop-player">{html.escape(prop["player"]["name"])}</div><div class="hustle-prop-record">{over} OVER <span>·</span> {under} UNDER <span>·</span> {push} PUSH</div><div class="hustle-prop-bar"><div style="width:{over_pct:.2f}%"></div></div><div class="hustle-prop-split"><span>OVER {over_pct:.1f}%</span><span>UNDER {under_pct:.1f}%</span></div><div class="hustle-prop-foot">{total} games in sample · {decided} non-push results</div></div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("#### Recent performance")
                    sample_cols = st.columns(3)
                    for col, n in zip(sample_cols, [5, 10, 20]):
                        sample = valid.head(n)
                        count = len(sample)
                        avg = sample["Result"].mean() if count else None
                        sample_over = int((sample["Result"] > prop["line"]).sum())
                        sample_under = int((sample["Result"] < prop["line"]).sum())
                        sample_push = int((sample["Result"] == prop["line"]).sum())
                        sample_decided = sample_over + sample_under
                        hit = sample_over / sample_decided * 100 if sample_decided else 0
                        with col:
                            st.markdown(
                                f'<div class="hustle-sample-card"><div class="hustle-sample-label">LAST {n}</div><div class="hustle-sample-average">{avg:.1f}</div><div class="hustle-sample-caption">AVG · {count} GAMES</div><div class="hustle-sample-hit">{hit:.0f}% OVER</div><div class="hustle-sample-caption">{sample_over} O · {sample_under} U · {sample_push} P</div></div>',
                                unsafe_allow_html=True,
                            )
                    st.markdown("#### Game-by-game results")
                    for _, game in valid.head(20).iterrows():
                        game_date = pd.to_datetime(game["Date"], errors="coerce")
                        date_label = game_date.strftime("%b %d") if not pd.isna(game_date) else str(game["Date"])
                        outcome = game["Outcome"]
                        outcome_color = "#55e6a5" if outcome == "Over" else ("#65a9ff" if outcome == "Under" else "#f4c56a")
                        st.markdown(
                            f'<div class="hustle-prop-game"><div><strong>{html.escape(date_label)}</strong><span>{html.escape(str(game["Opponent"]))}</span></div><div class="hustle-prop-game-result"><strong>{game["Result"]:g}</strong><span style="color:{outcome_color}">{outcome.upper()}</span></div></div>',
                            unsafe_allow_html=True,
                        )
                    st.caption("Historical frequencies describe past results only; they are not predictions or calibrated probabilities. Pushes are excluded from over/under percentages.")
                    st.markdown("#### Save this pick")
                    side = st.radio("Choose a side", ["Over", "Under"], horizontal=True, key="save_side")
                    notes = st.text_input("Notes (optional)", key="prop_notes", placeholder="Add matchup notes or your reasoning")
                    if st.button("Save pick to tracker", use_container_width=True):
                        add_pick(prop["player"]["name"], prop["market"], prop["line"], side, "", notes)
                        st.success("Pick saved. Find it in Pick Tracker & Parlays.")
            except Exception as exc:
                st.error(f"Unable to analyze this player: {exc}")

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
            if st.button("Load matchup / box score", use_container_width=True):
                try:
                    with st.spinner("Loading matchup statistics..."):
                        summary = get_game_summary(game["Event ID"])
                    render_game_summary(summary)
                except Exception as exc:
                    st.info(f"Game details unavailable: {exc}")
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
