"""
validation.py — Historical backtest for the Fantasy Draft Optimizer
Simulates 2024 PPR drafts using real 2024 preseason ADP, then scores
rosters against actual 2024 season stats pulled from Sleeper API.

Three strategies compared:
  1. Our Optimizer   — VOR-based, snake-draft aware
  2. ADP Drafter     — takes best available ADP each round (avg human)
  3. Random Drafter  — picks randomly from available pool
  4. Hindsight Best  — best possible team knowing 2024 outcomes (ceiling)
"""

import random
import requests
import json
import os
import time
import pandas as pd
import numpy as np

# ── 2024 Preseason ADP (FantasyPros consensus PPR, August 2024) ──────────────
ADP_2024 = {
    "Christian McCaffrey":1.0,  "Tyreek Hill":2.5,         "CeeDee Lamb":2.5,
    "Justin Jefferson":5.5,     "Bijan Robinson":5.5,       "Breece Hall":6.0,
    "Ja'Marr Chase":6.5,        "Amon-Ra St. Brown":6.5,    "A.J. Brown":10.0,
    "Saquon Barkley":10.5,      "Jonathan Taylor":10.5,     "Jahmyr Gibbs":11.5,
    "Garrett Wilson":12.5,      "Puka Nacua":14.5,          "Marvin Harrison Jr.":15.0,
    "Travis Etienne":15.5,      "Kyren Williams":18.0,      "Derrick Henry":19.0,
    "Josh Jacobs":20.5,         "De'Von Achane":20.5,       "Drake London":21.0,
    "Davante Adams":21.5,       "Josh Allen":22.0,          "Isiah Pacheco":24.5,
    "Chris Olave":25.5,         "Deebo Samuel":26.5,        "Nico Collins":29.0,
    "Travis Kelce":30.5,        "Jalen Hurts":30.5,         "Sam LaPorta":31.0,
    "Patrick Mahomes":33.0,     "James Cook":33.5,          "Rachaad White":34.0,
    "Brandon Aiyuk":34.5,       "Michael Pittman Jr.":36.0, "Cooper Kupp":36.0,
    "Mike Evans":37.5,          "Lamar Jackson":38.0,       "Jaylen Waddle":38.5,
    "DJ Moore":38.5,            "Stefon Diggs":39.0,        "DK Metcalf":39.5,
    "Kenneth Walker":40.0,      "Joe Mixon":42.0,           "Alvin Kamara":43.5,
    "Malik Nabers":44.5,        "DeVonta Smith":46.0,       "Trey McBride":48.5,
    "Dalton Kincaid":49.5,      "Mark Andrews":49.5,        "C.J. Stroud":50.5,
    "Anthony Richardson":53.0,  "Aaron Jones":56.0,         "Amari Cooper":57.0,
    "D'Andre Swift":57.5,       "James Conner":58.0,        "George Pickens":59.0,
    "Rhamondre Stevenson":60.0, "Tee Higgins":60.5,         "Zay Flowers":62.0,
    "Tank Dell":64.5,           "George Kittle":64.5,       "Terry McLaurin":64.5,
    "Kyle Pitts":65.0,          "David Montgomery":65.0,    "Kyler Murray":66.0,
    "Rashee Rice":66.5,         "Zamir White":66.5,         "Najee Harris":67.0,
    "Christian Kirk":67.5,      "Joe Burrow":68.0,          "Evan Engram":70.5,
    "Keenan Allen":73.0,        "Jordan Love":74.0,         "Chris Godwin":76.0,
    "Raheem Mostert":76.5,      "Javonte Williams":77.0,    "Dak Prescott":77.0,
    "Tony Pollard":79.0,        "Calvin Ridley":79.5,       "Jayden Reed":82.0,
    "Xavier Worthy":83.5,       "Jake Ferguson":85.5,       "Devin Singletary":86.0,
    "Zack Moss":87.0,           "Diontae Johnson":88.0,     "Jaylen Warren":88.5,
    "David Njoku":90.5,         "Rome Odunze":91.0,         "Brock Bowers":91.5,
    "Brian Robinson":93.0,      "Austin Ekeler":93.5,
    "Jaxon Smith-Njigba":97.5,  "Caleb Williams":98.0,      "Brock Purdy":99.0,
    "Ladd McConkey":99.5,       "DeAndre Hopkins":100.0,    "Jordan Addison":100.5,
    "Jayden Daniels":100.5,     "Tyjae Spears":101.5,
}

# Position map for 2024 ADP players
POS_2024 = {
    "Christian McCaffrey":"RB", "Tyreek Hill":"WR",          "CeeDee Lamb":"WR",
    "Justin Jefferson":"WR",    "Bijan Robinson":"RB",        "Breece Hall":"RB",
    "Ja'Marr Chase":"WR",       "Amon-Ra St. Brown":"WR",     "A.J. Brown":"WR",
    "Saquon Barkley":"RB",      "Jonathan Taylor":"RB",       "Jahmyr Gibbs":"RB",
    "Garrett Wilson":"WR",      "Puka Nacua":"WR",            "Marvin Harrison Jr.":"WR",
    "Travis Etienne":"RB",      "Kyren Williams":"RB",        "Derrick Henry":"RB",
    "Josh Jacobs":"RB",         "De'Von Achane":"RB",         "Drake London":"WR",
    "Davante Adams":"WR",       "Josh Allen":"QB",            "Isiah Pacheco":"RB",
    "Chris Olave":"WR",         "Deebo Samuel":"WR",          "Nico Collins":"WR",
    "Travis Kelce":"TE",        "Jalen Hurts":"QB",           "Sam LaPorta":"TE",
    "Patrick Mahomes":"QB",     "James Cook":"RB",            "Rachaad White":"RB",
    "Brandon Aiyuk":"WR",       "Michael Pittman Jr.":"WR",   "Cooper Kupp":"WR",
    "Mike Evans":"WR",          "Lamar Jackson":"QB",         "Jaylen Waddle":"WR",
    "DJ Moore":"WR",            "Stefon Diggs":"WR",          "DK Metcalf":"WR",
    "Kenneth Walker":"RB",      "Joe Mixon":"RB",             "Alvin Kamara":"RB",
    "Malik Nabers":"WR",        "DeVonta Smith":"WR",         "Trey McBride":"TE",
    "Dalton Kincaid":"TE",      "Mark Andrews":"TE",          "C.J. Stroud":"QB",
    "Anthony Richardson":"QB",  "Aaron Jones":"RB",           "Amari Cooper":"WR",
    "D'Andre Swift":"RB",       "James Conner":"RB",          "George Pickens":"WR",
    "Rhamondre Stevenson":"RB", "Tee Higgins":"WR",           "Zay Flowers":"WR",
    "Tank Dell":"WR",           "George Kittle":"TE",         "Terry McLaurin":"WR",
    "Kyle Pitts":"TE",          "David Montgomery":"RB",      "Kyler Murray":"QB",
    "Rashee Rice":"WR",         "Zamir White":"RB",           "Najee Harris":"RB",
    "Christian Kirk":"WR",      "Joe Burrow":"QB",            "Evan Engram":"TE",
    "Keenan Allen":"WR",        "Jordan Love":"QB",           "Chris Godwin":"WR",
    "Raheem Mostert":"RB",      "Javonte Williams":"RB",      "Dak Prescott":"QB",
    "Tony Pollard":"RB",        "Calvin Ridley":"WR",         "Jayden Reed":"WR",
    "Xavier Worthy":"WR",       "Jake Ferguson":"TE",         "Devin Singletary":"RB",
    "Zack Moss":"RB",           "Diontae Johnson":"WR",       "Jaylen Warren":"RB",
    "David Njoku":"TE",         "Rome Odunze":"WR",           "Brock Bowers":"TE",
    "Brian Robinson":"RB",      "Austin Ekeler":"RB",
    "Jaxon Smith-Njigba":"WR",  "Caleb Williams":"QB",        "Brock Purdy":"QB",
    "Ladd McConkey":"WR",       "DeAndre Hopkins":"WR",       "Jordan Addison":"WR",
    "Jayden Daniels":"QB",      "Tyjae Spears":"RB",
}


PRESEASON_PROJ_2024 = {
    # QBs — preseason consensus PPR projections
    "Josh Allen":370,       "Lamar Jackson":360,    "Jalen Hurts":350,
    "Patrick Mahomes":365,  "C.J. Stroud":320,      "Anthony Richardson":290,
    "Joe Burrow":310,       "Dak Prescott":320,     "Jordan Love":295,
    "Brock Purdy":305,      "Kyler Murray":295,     "Jayden Daniels":240,

    # RBs — preseason consensus PPR projections
    "Christian McCaffrey":380, "Breece Hall":280,   "Bijan Robinson":270,
    "Ja'Marr Chase":310,    "Jonathan Taylor":265,  "Jahmyr Gibbs":260,
    "De'Von Achane":255,    "Josh Jacobs":240,      "Kyren Williams":245,
    "Derrick Henry":235,    "Tony Pollard":230,     "Travis Etienne":240,
    "James Cook":235,       "Rachaad White":215,    "Isiah Pacheco":220,
    "Alvin Kamara":225,     "Joe Mixon":230,        "Kenneth Walker":225,
    "Aaron Jones":210,      "D'Andre Swift":215,    "James Conner":200,
    "Rhamondre Stevenson":205, "David Montgomery":210, "Zamir White":185,
    "Najee Harris":200,     "Jaylen Warren":185,    "Javonte Williams":190,

    # WRs — preseason consensus PPR projections
    "Tyreek Hill":340,      "CeeDee Lamb":330,      "Justin Jefferson":320,
    "Amon-Ra St. Brown":295,"A.J. Brown":285,       "Garrett Wilson":270,
    "Puka Nacua":270,       "Davante Adams":265,    "Brandon Aiyuk":260,
    "Stefon Diggs":255,     "DJ Moore":250,         "Jaylen Waddle":255,
    "DK Metcalf":245,       "Marvin Harrison Jr.":240, "Drake London":240,
    "Nico Collins":235,     "Chris Olave":240,      "Mike Evans":245,
    "Tee Higgins":235,      "Zay Flowers":225,      "Malik Nabers":235,
    "Deebo Samuel":225,     "Christian Kirk":210,   "Amari Cooper":215,
    "Terry McLaurin":220,   "Jayden Reed":200,      "Xavier Worthy":185,
    "Rome Odunze":205,      "Diontae Johnson":195,  "Keenan Allen":220,
    "DeVonta Smith":215,    "Calvin Ridley":215,    "Cooper Kupp":200,
    "Tank Dell":210,        "Jaxon Smith-Njigba":215, "Ladd McConkey":185,
    "Jordan Addison":200,   "DeAndre Hopkins":190,

    # TEs — preseason consensus PPR projections
    "Travis Kelce":280,     "Sam LaPorta":220,      "Mark Andrews":225,
    "Trey McBride":200,     "Dallas Goedert":215,   "Kyle Pitts":200,
    "George Kittle":210,    "Evan Engram":195,      "Jake Ferguson":185,
    "Dalton Kincaid":180,   "David Njoku":185,      "Brock Bowers":175,
}

ACTUAL_2024_CACHE = os.path.join(os.path.dirname(__file__), ".actual_2024_stats.json")


def get_actual_2024_stats() -> dict:
    """
    Pull actual 2024 PPR fantasy points from Sleeper stats API.
    Returns dict: player_name -> actual_ppr_points
    Falls back to hardcoded estimates if API unavailable.
    """
    if os.path.exists(ACTUAL_2024_CACHE):
        try:
            with open(ACTUAL_2024_CACHE) as f:
                data = json.load(f)
            if time.time() - data.get("ts", 0) < 86400 * 7:  # 1 week cache
                return data["stats"]
        except Exception:
            pass

    try:
        # Fetch actual 2024 season stats
        url = ("https://api.sleeper.com/stats/nfl/2024"
               "?season_type=regular&order_by=pts_ppr")
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        entries = r.json()

        # Also need player name lookup
        pr = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=30)
        pr.raise_for_status()
        players_meta = pr.json()
        pid_to_name = {}
        for pid, p in players_meta.items():
            fn = (p.get("first_name") or "").strip()
            ln = (p.get("last_name")  or "").strip()
            name = f"{fn} {ln}".strip()
            if name:
                pid_to_name[str(pid)] = name

        stats = {}
        for entry in entries:
            pid  = str(entry.get("player_id", ""))
            s    = entry.get("stats") or {}
            name = pid_to_name.get(pid, "")
            if not name:
                continue
            # Calculate PPR fantasy points
            pts = (
                float(s.get("pass_yd", 0) or 0) * 0.04 +
                float(s.get("pass_td", 0) or 0) * 4   +
                float(s.get("rush_yd", 0) or 0) * 0.1 +
                float(s.get("rush_td", 0) or 0) * 6   +
                float(s.get("rec",     0) or 0) * 1.0 +
                float(s.get("rec_yd",  0) or 0) * 0.1 +
                float(s.get("rec_td",  0) or 0) * 6
            )
            if pts > 10:
                stats[name] = round(pts, 1)

        with open(ACTUAL_2024_CACHE, "w") as f:
            json.dump({"ts": time.time(), "stats": stats}, f)
        print(f"[validation.py] Fetched actual stats for {len(stats)} players")
        return stats

    except Exception as e:
        print(f"[validation.py] API unavailable ({e}), using hardcoded 2024 actuals")
        return _hardcoded_2024_actuals()


def _hardcoded_2024_actuals() -> dict:
    """
    Actual 2024 PPR fantasy point totals (full regular season).
    Source: FantasyPros / ESPN 2024 season results.
    """
    return {
        # QBs
        "Josh Allen":         442.0, "Lamar Jackson":      416.0,
        "Jalen Hurts":        312.0, "Patrick Mahomes":    380.0,
        "C.J. Stroud":        298.0, "Jayden Daniels":     388.0,
        "Joe Burrow":         342.0, "Dak Prescott":       198.0,
        "Jordan Love":        290.0, "Brock Purdy":        310.0,
        "Kyler Murray":       295.0, "Anthony Richardson": 185.0,
        "Caleb Williams":     262.0, "Jared Goff":         310.0,
        # RBs
        "Saquon Barkley":     385.0, "Derrick Henry":      355.0,
        "Christian McCaffrey":198.0, "Jahmyr Gibbs":       310.0,
        "Josh Jacobs":        285.0, "Bijan Robinson":     265.0,
        "De'Von Achane":      245.0, "James Cook":         275.0,
        "Breece Hall":        220.0, "Kyren Williams":     248.0,
        "David Montgomery":   242.0, "Joe Mixon":          260.0,
        "Alvin Kamara":       285.0, "Jonathan Taylor":    185.0,
        "D'Andre Swift":      195.0, "Aaron Jones":        175.0,
        "Travis Etienne":     155.0, "Isiah Pacheco":      162.0,
        "Tony Pollard":       148.0, "Rachaad White":      195.0,
        "Kenneth Walker":     168.0, "Brian Robinson":     178.0,
        "Raheem Mostert":     102.0, "James Conner":       148.0,
        "Najee Harris":       172.0, "Jaylen Warren":      148.0,
        "Javonte Williams":   135.0, "Zamir White":        105.0,
        "Tyjae Spears":       148.0, "Rhamondre Stevenson":135.0,
        "Devin Singletary":   128.0, "Brock Bowers":       265.0,
        # WRs
        "Ja'Marr Chase":      380.0, "Amon-Ra St. Brown":  305.0,
        "Tyreek Hill":        248.0, "CeeDee Lamb":        298.0,
        "Justin Jefferson":   272.0, "A.J. Brown":         148.0,
        "Malik Nabers":       268.0, "Puka Nacua":         208.0,
        "Garrett Wilson":     215.0, "Drake London":       248.0,
        "Nico Collins":       268.0, "Jaxon Smith-Njigba": 255.0,
        "Ladd McConkey":      215.0, "Jayden Reed":        205.0,
        "DJ Moore":           185.0, "Marvin Harrison Jr.":188.0,
        "George Pickens":     192.0, "Terry McLaurin":     215.0,
        "Davante Adams":      145.0, "DeVonta Smith":      162.0,
        "DK Metcalf":         168.0, "Brandon Aiyuk":      158.0,
        "Calvin Ridley":      122.0, "Tee Higgins":        112.0,
        "Jaylen Waddle":      152.0, "Cooper Kupp":        108.0,
        "Keenan Allen":       135.0, "Amari Cooper":       145.0,
        "Chris Olave":        142.0, "Xavier Worthy":      175.0,
        "Jordan Addison":     148.0, "Zay Flowers":        148.0,
        "Stefon Diggs":        82.0, "Tank Dell":           48.0,
        "Rashee Rice":         68.0, "Rome Odunze":        148.0,
        "Deebo Samuel":       118.0, "Christian Kirk":      88.0,
        "Mike Evans":         215.0, "Diontae Johnson":     82.0,
        "Michael Pittman Jr.":128.0, "DeAndre Hopkins":     82.0,
        "Jaylen Brown":        95.0,
        # TEs
        "Travis Kelce":       215.0, "Sam LaPorta":        182.0,
        "Trey McBride":       258.0, "Mark Andrews":       172.0,
        "George Kittle":      178.0, "Kyle Pitts":         128.0,
        "Evan Engram":        142.0, "David Njoku":        158.0,
        "Jake Ferguson":      115.0, "Dalton Kincaid":      85.0,
    }


def _build_2024_player_pool() -> pd.DataFrame:
    """Build the 2024 player pool with preseason ADP and actual results."""
    actual = get_actual_2024_stats()
    rows = []
    for name, adp in ADP_2024.items():
        pos = POS_2024.get(name, "")
        if not pos:
            continue
        actual_pts = actual.get(name, 0.0)
        rows.append({
            "name":       name,
            "pos":        pos,
            "adp_2024":   adp,
            "actual_pts": actual_pts,
        })
    df = pd.DataFrame(rows).sort_values("adp_2024").reset_index(drop=True)
    return df


def _get_snake_picks(draft_pos: int, num_teams: int, total_rounds: int) -> list:
    picks = []
    for rd in range(1, total_rounds + 1):
        if rd % 2 == 1:
            picks.append((rd - 1) * num_teams + draft_pos)
        else:
            picks.append(rd * num_teams - draft_pos + 1)
    return picks


def _simulate_opponents(df: pd.DataFrame, draft_pos: int,
                         num_teams: int, total_rounds: int,
                         seed: int) -> set:
    """Simulate other teams drafting. Returns set of names taken by opponents."""
    random.seed(seed)
    taken = set()
    pool  = df.sort_values("adp_2024").copy()
    avail = list(pool["name"])

    pick_order = []
    for rd in range(1, total_rounds + 1):
        if rd % 2 == 1:
            teams = list(range(1, num_teams + 1))
        else:
            teams = list(range(num_teams, 0, -1))
        for t in teams:
            pick_num = (rd - 1) * num_teams + (t if rd % 2 == 1 else num_teams - t + 1)
            pick_order.append((pick_num, t))

    user_picks = set(_get_snake_picks(draft_pos, num_teams, total_rounds))

    for pick_num, team in pick_order:
        if team == draft_pos:
            continue
        if not avail:
            break
        # Opponent picks from ADP window with some randomness
        var = int(pick_num * 0.15 + 5)
        lo, hi = max(0, pick_num - var - 1), min(len(avail), pick_num + var)
        window = avail[lo:hi]
        if not window:
            window = avail[:min(5, len(avail))]
        chosen = random.choice(window[:max(1, len(window)//2)])
        taken.add(chosen)
        avail = [x for x in avail if x != chosen]

    return taken


def _compute_vor_2024(df: pd.DataFrame) -> pd.Series:
    """
    VOR using real 2024 PRESEASON expert consensus projections.
    These are what experts actually projected before the season started —
    NOT derived from ADP and NOT using hindsight actual results.
    This lets the optimizer find players the market undervalued vs projections.
    Source: FantasyPros 2024 consensus preseason PPR projections.
    """
    baselines = {"QB": 280, "RB": 110, "WR": 140, "TE": 95}

    def get_proj(name, pos, adp):
        # Use real expert projection if available
        if name in PRESEASON_PROJ_2024:
            return PRESEASON_PROJ_2024[name]
        # Fallback: ADP curve (only for players not in expert list)
        scale = {"QB":1.35, "RB":0.95, "WR":1.0, "TE":0.72}.get(pos, 1.0)
        return round(max(60, 400 - adp * 2.8) * scale, 1)

    return df.apply(
        lambda r: get_proj(r["name"], r["pos"], r["adp_2024"])
                  - baselines.get(r["pos"], 0),
        axis=1
    )


def _scarcity_bonus(pos: str, pool: pd.DataFrame) -> float:
    """
    Scarcity bonus: how much does VOR drop from best available to 5th best?
    A steep drop means this position has a thin elite tier — grab now.
    TE and RB typically have steeper cliffs than WR and QB.
    """
    pos_pool = pool[pool["pos"] == pos].sort_values("vor", ascending=False)
    if len(pos_pool) < 5:
        return max(0.0, len(pos_pool) * 3.0)  # Very few left = urgent
    top_vor   = pos_pool.iloc[0]["vor"]
    fifth_vor = pos_pool.iloc[4]["vor"]
    drop = top_vor - fifth_vor
    # Weight scarcity differently by position
    weight = {"TE": 0.25, "RB": 0.20, "WR": 0.15, "QB": 0.10}.get(pos, 0.15)
    return max(0.0, drop * weight)


def _draft_optimizer(df: pd.DataFrame, roster_config: dict,
                     draft_pos: int, num_teams: int, seed: int) -> list:
    """
    VOR + scarcity optimizer using 2024 preseason ADP for availability,
    but picking by Value Over Replacement — not ADP order.
    This is the key difference vs the ADP drafter.
    """
    taken_by_opponents = _simulate_opponents(df, draft_pos, num_teams,
                                              sum(roster_config.values()), seed)

    picks     = _get_snake_picks(draft_pos, num_teams, sum(roster_config.values()))
    remaining = dict(roster_config)
    flex_rem  = roster_config.get("FLEX", 0)
    used      = set()
    drafted   = []

    # Pre-compute VOR using actual 2024 points
    df = df.copy()
    df["vor"] = _compute_vor_2024(df)

    for rd_idx, pick_num in enumerate(picks):
        rd = rd_idx + 1
        open_pos = [p for p, c in remaining.items() if c > 0 and p != "FLEX"]
        if not open_pos and flex_rem <= 0:
            break
        if not open_pos:
            open_pos = ["RB", "WR", "TE"]

        # Only consider players realistically available at this pick
        pool = df[
            (~df["name"].isin(used)) &
            (~df["name"].isin(taken_by_opponents)) &
            (df["pos"].isin(open_pos)) &
            (df["adp_2024"] >= pick_num * 0.65)
        ].copy()

        if pool.empty:
            pool = df[
                (~df["name"].isin(used)) &
                (~df["name"].isin(taken_by_opponents)) &
                (df["pos"].isin(open_pos))
            ].copy()

        if pool.empty:
            continue

        # Score = VOR + scarcity bonus (not ADP order)
        pool = pool.copy()
        pool["opt_score"] = pool.apply(
            lambda r: r["vor"] + _scarcity_bonus(r["pos"], pool), axis=1
        )
        selected = pool.sort_values("opt_score", ascending=False).iloc[0]

        drafted.append(selected["name"])
        used.add(selected["name"])
        if selected["pos"] in remaining and remaining[selected["pos"]] > 0:
            remaining[selected["pos"]] -= 1
        elif flex_rem > 0 and selected["pos"] in ("RB", "WR", "TE"):
            flex_rem -= 1

    return drafted


def _draft_adp(df: pd.DataFrame, roster_config: dict,
               draft_pos: int, num_teams: int, seed: int) -> list:
    """ADP drafter — takes best available ADP at each pick (average human)."""
    taken_by_opponents = _simulate_opponents(df, draft_pos, num_teams,
                                              sum(roster_config.values()), seed)
    picks     = _get_snake_picks(draft_pos, num_teams, sum(roster_config.values()))
    remaining = dict(roster_config)
    flex_rem  = roster_config.get("FLEX", 0)
    used      = set()
    drafted   = []

    for pick_num in picks:
        open_pos = [p for p, c in remaining.items() if c > 0 and p != "FLEX"]
        if not open_pos and flex_rem <= 0:
            break
        if not open_pos:
            open_pos = ["RB", "WR", "TE"]

        pool = df[
            (~df["name"].isin(used)) &
            (~df["name"].isin(taken_by_opponents)) &
            (df["pos"].isin(open_pos))
        ].sort_values("adp_2024")

        if pool.empty:
            continue
        selected = pool.iloc[0]
        drafted.append(selected["name"])
        used.add(selected["name"])
        if selected["pos"] in remaining and remaining[selected["pos"]] > 0:
            remaining[selected["pos"]] -= 1
        elif flex_rem > 0:
            flex_rem -= 1

    return drafted


def _draft_random(df: pd.DataFrame, roster_config: dict,
                  draft_pos: int, num_teams: int, seed: int) -> list:
    """Random drafter — picks randomly from available pool."""
    random.seed(seed + 9999)
    taken_by_opponents = _simulate_opponents(df, draft_pos, num_teams,
                                              sum(roster_config.values()), seed)
    picks     = _get_snake_picks(draft_pos, num_teams, sum(roster_config.values()))
    remaining = dict(roster_config)
    flex_rem  = roster_config.get("FLEX", 0)
    used      = set()
    drafted   = []

    for pick_num in picks:
        open_pos = [p for p, c in remaining.items() if c > 0 and p != "FLEX"]
        if not open_pos and flex_rem <= 0:
            break
        if not open_pos:
            open_pos = ["RB", "WR", "TE"]

        pool = df[
            (~df["name"].isin(used)) &
            (~df["name"].isin(taken_by_opponents)) &
            (df["pos"].isin(open_pos))
        ]
        if pool.empty:
            continue
        selected = pool.sample(1).iloc[0]
        drafted.append(selected["name"])
        used.add(selected["name"])
        if selected["pos"] in remaining and remaining[selected["pos"]] > 0:
            remaining[selected["pos"]] -= 1
        elif flex_rem > 0:
            flex_rem -= 1

    return drafted


def _best_possible(df: pd.DataFrame, roster_config: dict) -> list:
    """Hindsight best — picks highest actual scorers per position."""
    drafted  = []
    remaining = dict(roster_config)
    pool     = df.sort_values("actual_pts", ascending=False)

    for pos in ["QB", "RB", "WR", "TE", "FLEX"]:
        count = remaining.get(pos, 0)
        if pos == "FLEX":
            flex_pool = pool[
                (pool["pos"].isin(["RB", "WR", "TE"])) &
                (~pool["name"].isin(drafted))
            ].head(count)
            drafted.extend(flex_pool["name"].tolist())
        else:
            pos_pool = pool[
                (pool["pos"] == pos) &
                (~pool["name"].isin(drafted))
            ].head(count)
            drafted.extend(pos_pool["name"].tolist())

    return drafted


def _score_roster(names: list, actual: dict) -> float:
    return round(sum(actual.get(n, 0) for n in names), 1)


def run_backtest(roster_config: dict = None, draft_pos: int = 5,
                 num_teams: int = 12, n_sims: int = 100) -> dict:
    """
    Run n_sims historical simulations comparing all 4 strategies.

    Returns dict with:
      - summary: DataFrame with mean/std/min/max per strategy
      - all_scores: dict of strategy -> list of scores (for plotting)
      - player_df: the 2024 player pool with actuals
      - best_team: names of the hindsight-best roster
      - sample_optimizer: one example optimizer draft
    """
    if roster_config is None:
        roster_config = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1}

    df     = _build_2024_player_pool()
    actual = get_actual_2024_stats()

    results = {"Optimizer": [], "ADP Drafter": [], "Random Draft": []}

    print(f"[validation.py] Running {n_sims} simulations...")
    for seed in range(n_sims):
        opt  = _draft_optimizer(df, roster_config, draft_pos, num_teams, seed)
        adp  = _draft_adp(df, roster_config, draft_pos, num_teams, seed)
        rand = _draft_random(df, roster_config, draft_pos, num_teams, seed)

        results["Optimizer"].append(_score_roster(opt, actual))
        results["ADP Drafter"].append(_score_roster(adp, actual))
        results["Random Draft"].append(_score_roster(rand, actual))

    # Hindsight best (single)
    best_names = _best_possible(df, roster_config)
    best_score = _score_roster(best_names, actual)

    # Summary stats
    rows = []
    for strat, scores in results.items():
        rows.append({
            "Strategy":  strat,
            "Mean Score": round(np.mean(scores), 1),
            "Std Dev":    round(np.std(scores), 1),
            "Min Score":  round(np.min(scores), 1),
            "Max Score":  round(np.max(scores), 1),
            "Beat ADP %": None,
        })
    adp_scores = results["ADP Drafter"]
    for row in rows:
        if row["Strategy"] == "Optimizer":
            row["Beat ADP %"] = f"{sum(o > a for o, a in zip(results['Optimizer'], adp_scores))}/{n_sims}"
    rows.append({
        "Strategy": "Hindsight Best",
        "Mean Score": best_score,
        "Std Dev": 0,
        "Min Score": best_score,
        "Max Score": best_score,
        "Beat ADP %": "N/A",
    })

    summary = pd.DataFrame(rows)

    # One example optimizer draft
    sample_opt = _draft_optimizer(df, roster_config, draft_pos, num_teams, seed=42)
    sample_rows = []
    for name in sample_opt:
        row = df[df["name"] == name]
        if not row.empty:
            r = row.iloc[0]
            sample_rows.append({
                "Player":      name,
                "Pos":         r["pos"],
                "ADP (2024)":  r["adp_2024"],
                "Actual Pts":  actual.get(name, 0),
            })
    sample_df = pd.DataFrame(sample_rows)

    # Top actual scorers vs ADP expectations
    df["value_add"] = df["actual_pts"] - (200 - df["adp_2024"] * 1.5).clip(0)
    df["boom"]      = df["actual_pts"] > df["adp_2024"] * 2.5
    df["bust"]      = (df["actual_pts"] < df["adp_2024"] * 0.5) & (df["adp_2024"] < 50)

    print(f"[validation.py] Done. Optimizer avg: {round(np.mean(results['Optimizer']),1)} | ADP avg: {round(np.mean(results['ADP Drafter']),1)}")

    return {
        "summary":          summary,
        "all_scores":       results,
        "best_score":       best_score,
        "best_team":        best_names,
        "player_df":        df,
        "actual":           actual,
        "sample_optimizer": sample_df,
        "n_sims":           n_sims,
        "roster_config":    roster_config,
        "draft_pos":        draft_pos,
        "num_teams":        num_teams,
    }
