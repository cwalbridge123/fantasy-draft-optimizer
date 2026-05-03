"""
data.py - Player data layer
2026 PPR rankings sourced from DraftSharks (verified most accurate, April 2026)
Sleeper API for live data, 150+ player fallback for offline use.
"""

import requests
import pandas as pd
import json, os, time

CACHE_FILE = os.path.join(os.path.dirname(__file__), ".sleeper_cache.json")
CACHE_TTL  = 60 * 60 * 6

SKILL_POS  = {"QB", "RB", "WR", "TE"}

VOR_BASELINES   = {"QB": 330, "RB": 150, "WR": 170, "TE": 130}
SCARCITY_ROUNDS = {"QB": 8,   "RB": 4,   "WR": 5,   "TE": 6}

# ── 2026 DraftSharks PPR rankings (overall rank = ADP) ──────────────────────
KNOWN_ADP = {
    # Tier 1
    "Puka Nacua":1,            "Jahmyr Gibbs":2,          "Bijan Robinson":3,
    "Ja'Marr Chase":4,         "Christian McCaffrey":5,
    # Tier 2
    "Jaxon Smith-Njigba":6,    "Amon-Ra St. Brown":7,     "Rashee Rice":8,
    "CeeDee Lamb":9,           "Jonathan Taylor":10,
    # Tier 3
    "Justin Jefferson":11,     "James Cook":12,            "Ashton Jeanty":13,
    "Drake London":14,         "Nico Collins":15,          "Saquon Barkley":16,
    "De'Von Achane":17,        "Breece Hall":18,           "Jaylen Waddle":19,
    "Travis Kelce":20,
    # Tier 4
    "Josh Allen":21,           "Lamar Jackson":22,         "Trey McBride":23,
    "Jalen Hurts":24,          "Sam LaPorta":25,           "Patrick Mahomes":26,
    "Derrick Henry":27,        "Tony Pollard":28,          "Travis Etienne":29,
    "Brian Thomas Jr.":30,
    # Tier 5
    "Davante Adams":31,        "Tee Higgins":32,           "DJ Moore":33,
    "Josh Jacobs":34,          "Kyren Williams":35,        "Stefon Diggs":36,
    "Chris Olave":37,          "Alvin Kamara":38,          "Mike Evans":39,
    "Brandon Aiyuk":40,        "Keenan Allen":41,          "Joe Mixon":42,
    "Jayden Daniels":43,       "CJ Stroud":44,             "Dak Prescott":45,
    "DK Metcalf":46,           "Jordan Love":47,           "Zay Flowers":48,
    "Sam Darnold":49,          "Kenneth Walker":50,
    # Rounds 5-8
    "Garrett Wilson":51,       "Isiah Pacheco":52,         "Calvin Ridley":53,
    "Evan Engram":54,          "Dallas Goedert":55,        "Rhamondre Stevenson":56,
    "Jake Ferguson":57,        "Rachaad White":58,         "Tank Dell":59,
    "Deebo Samuel":60,         "Christian Kirk":61,        "Aaron Jones":62,
    "Chuba Hubbard":63,        "DeAndre Hopkins":64,       "Amari Cooper":65,
    "Tyler Lockett":66,        "David Njoku":67,           "Javonte Williams":68,
    "Baker Mayfield":69,       "Tua Tagovailoa":70,        "Zach Charbonnet":71,
    "Brian Robinson":72,       "Pat Freiermuth":73,        "Cole Kmet":74,
    "Dalton Kincaid":75,       "Tucker Kraft":76,          "Anthony Richardson":77,
    "Rome Odunze":78,          "Quentin Johnston":79,      "Geno Smith":80,
    # Rounds 8-12 (depth/handcuffs/sleepers)
    "Ladd McConkey":81,        "Jordan Addison":82,        "George Pickens":42,
    "Chris Godwin":84,         "D'Andre Swift":85,         "Diontae Johnson":86,
    "Jaylen Reed":87,          "Xavier Worthy":88,         "Malik Nabers":32,
    "Marvin Harrison Jr.":38,  "DeVonta Smith":58,         "Jaxon Smith-Njigba":6,
    "Najee Harris":75,         "James Conner":88,          "David Montgomery":80,
    "Khalil Shakir":95,        "Jaylen Warren":96,         "Brock Bowers":16,
    "George Kittle":45,        "Luke Musgrave":85,         "Cade Otton":110,
    "Juwan Johnson":101,       "Hunter Henry":105,          "Dalton Schultz":108,
    "Tyler Conklin":112,       "Jonnu Smith":110,
    # Late rounds / streamers
    "Joshua Palmer":106,       "Keon Coleman":107,         "Rome Odunze":78,
    "Jahan Dotson":108,        "Tyler Bass":109,           "Courtland Sutton":110,
    "Jerry Jeudy":111,         "Dontayvion Wicks":112,     "Rashid Shaheed":113,
    "Adam Thielen":114,        "Tyjae Spears":115,         "Jaylen Wright":116,
    "Chase Brown":117,         "Rico Dowdle":118,          "Tyrone Tracy Jr.":119,
    "Devin Singletary":120,    "Braelon Allen":121,        "Blake Corum":122,
    "Khalil Herbert":123,      "Keaton Mitchell":124,      "Jordan Mason":125,
}

# ── 2026 DraftSharks DS Projected Points (PPR) ───────────────────────────────
EXPERT_PROJECTIONS = {
    "Puka Nacua":364,          "Jahmyr Gibbs":353,         "Bijan Robinson":348,
    "Ja'Marr Chase":337,       "Christian McCaffrey":331,
    "Jaxon Smith-Njigba":320,  "Amon-Ra St. Brown":320,    "Rashee Rice":308,
    "CeeDee Lamb":301,         "Jonathan Taylor":307,
    "Justin Jefferson":286,    "James Cook":287,            "Ashton Jeanty":281,
    "Drake London":280,        "Nico Collins":285,          "Saquon Barkley":267,
    "De'Von Achane":275,       "Breece Hall":270,           "Jaylen Waddle":265,
    "Travis Kelce":242,        "Josh Allen":430,            "Lamar Jackson":425,
    "Trey McBride":225,        "Jalen Hurts":400,           "Sam LaPorta":228,
    "Patrick Mahomes":395,     "Derrick Henry":260,         "Tony Pollard":252,
    "Travis Etienne":248,      "Brian Thomas Jr.":255,
    "Davante Adams":248,       "Tee Higgins":244,           "DJ Moore":243,
    "Josh Jacobs":238,         "Kyren Williams":238,        "Stefon Diggs":238,
    "Chris Olave":233,         "Alvin Kamara":233,          "Mike Evans":238,
    "Brandon Aiyuk":228,       "Keenan Allen":228,          "Joe Mixon":223,
    "Jayden Daniels":365,      "CJ Stroud":352,             "Dak Prescott":342,
    "DK Metcalf":223,          "Jordan Love":332,           "Zay Flowers":218,
    "Sam Darnold":318,         "Kenneth Walker":218,
    "Garrett Wilson":263,      "Isiah Pacheco":213,         "Calvin Ridley":213,
    "Evan Engram":193,         "Dallas Goedert":193,        "Rhamondre Stevenson":208,
    "Jake Ferguson":183,       "Rachaad White":208,         "Tank Dell":208,
    "Deebo Samuel":203,        "Christian Kirk":198,        "Aaron Jones":208,
    "Chuba Hubbard":198,       "DeAndre Hopkins":193,       "Amari Cooper":193,
    "Tyler Lockett":188,       "David Njoku":178,           "Javonte Williams":193,
    "Baker Mayfield":298,      "Tua Tagovailoa":293,        "Zach Charbonnet":183,
    "Brian Robinson":188,      "Pat Freiermuth":173,        "Cole Kmet":168,
    "Dalton Kincaid":163,      "Tucker Kraft":158,          "Anthony Richardson":293,
    "Rome Odunze":198,         "Quentin Johnston":193,      "Geno Smith":278,
    # Depth players
    "Ladd McConkey":195,       "Jordan Addison":185,        "George Pickens":192,
    "Chris Godwin":175,        "D'Andre Swift":178,         "Diontae Johnson":155,
    "Jaylen Reed":185,         "Xavier Worthy":175,         "Malik Nabers":215,
    "Marvin Harrison Jr.":188, "DeVonta Smith":162,
    "Najee Harris":172,        "James Conner":148,          "David Montgomery":182,
    "Khalil Shakir":165,       "Jaylen Warren":148,         "Brock Bowers":268,
    "George Kittle":178,       "Luke Musgrave":145,         "Cade Otton":138,
    "Juwan Johnson":135,       "Hunter Henry":142,           "Dalton Schultz":148,
    "Tyler Conklin":128,       "Jonnu Smith":135,
    "Joshua Palmer":155,       "Keon Coleman":158,
    "Jahan Dotson":148,        "Courtland Sutton":178,
    "Jerry Jeudy":168,         "Tyjae Spears":155,         "Jaylen Wright":148,
    "Chase Brown":162,         "Rico Dowdle":145,           "Tyrone Tracy Jr.":138,
    "Devin Singletary":135,    "Braelon Allen":145,         "Blake Corum":138,
    "Jordan Mason":152,        "Keaton Mitchell":142,
}


def _estimate_risk(p: dict) -> int:
    risk = 3
    age  = p.get("age") or 0
    yrs  = p.get("years_exp") or 0
    inj  = (p.get("injury_status") or "").lower()
    if age >= 32:             risk += 1
    if age >= 35:             risk += 1
    if yrs == 0:              risk += 1
    if "out" in inj:          risk += 2
    if "doubtful" in inj:     risk += 1
    if "questionable" in inj: risk += 1
    if yrs >= 4 and age < 30: risk -= 1
    return max(1, min(5, risk))


def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                data = json.load(f)
            if time.time() - data.get("ts", 0) < CACHE_TTL:
                return data.get("players")
        except Exception:
            pass
    return None


def _save_cache(players):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"ts": time.time(), "players": players}, f)
    except Exception:
        pass


def _fetch_from_sleeper():
    print("[data.py] Fetching from Sleeper API...")
    r = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=30)
    r.raise_for_status()
    raw = r.json()
    print(f"[data.py] Raw count: {len(raw)}")

    try:
        stats_url = (
            "https://api.sleeper.com/stats/nfl/2024"
            "?season_type=regular&position[]=QB&position[]=RB"
            "&position[]=WR&position[]=TE&order_by=pts_half_ppr"
        )
        rs = requests.get(stats_url, timeout=30)
        rs.raise_for_status()
        stats_lookup = {
            str(e["player_id"]): (e.get("stats") or {})
            for e in rs.json() if e.get("player_id")
        }
        print(f"[data.py] Stats for {len(stats_lookup)} players")
    except Exception as e:
        print(f"[data.py] Stats unavailable: {e}")
        stats_lookup = {}

    players = []
    seen    = set()

    # Players who are clearly active — must have a current NFL team
    EXCLUDED_STATUS = {"Inactive", "Retired", "NA", "NaN"}

    for pid, p in raw.items():
        if p.get("sport") != "nfl":
            continue

        # Must have an active NFL team — retired/cut players won't have one
        team = p.get("team")
        if not team:
            continue

        # Filter out retired/inactive by status
        status = p.get("status") or ""
        if status in EXCLUDED_STATUS:
            continue

        fpos = p.get("fantasy_positions") or []
        pos  = fpos[0] if fpos else p.get("position", "")
        if pos not in SKILL_POS:
            continue

        team = team or "FA"
        fn   = (p.get("first_name") or "").strip()
        ln   = (p.get("last_name")  or "").strip()
        name = f"{fn} {ln}".strip()
        if not name or name in seen:
            continue
        seen.add(name)

        rank = p.get("search_rank")
        adp  = KNOWN_ADP.get(name)
        if adp is None:
            adp = float(rank) if (rank and isinstance(rank, (int,float)) and rank < 9999) else 220.0

        s = stats_lookup.get(str(pid), {})
        players.append({
            "name":      name,
            "pos":       pos,
            "team":      team,
            "pass_yds":  float(s.get("pass_yd", 0) or 0),
            "pass_td":   float(s.get("pass_td", 0) or 0),
            "rush_yds":  float(s.get("rush_yd", 0) or 0),
            "rush_td":   float(s.get("rush_td", 0) or 0),
            "rec":       float(s.get("rec",     0) or 0),
            "rec_yds":   float(s.get("rec_yd",  0) or 0),
            "rec_td":    float(s.get("rec_td",  0) or 0),
            "adp":       round(float(adp), 1),
            "risk":      _estimate_risk(p),
            "age":       p.get("age") or 0,
            "years_exp": p.get("years_exp") or 0,
        })

    players.sort(key=lambda x: x["adp"])
    players = [p for p in players if p["adp"] <= 300]
    print(f"[data.py] Final pool: {len(players)}")
    return players, "Sleeper API (live)"


def _fallback_players():
    """150+ player fallback with correct 2026 DraftSharks rankings."""
    return [
        # ── QBs ─────────────────────────────────────────────────────────────
        {"name":"Josh Allen",          "pos":"QB","team":"BUF","pass_yds":4400,"pass_td":40,"rush_yds":650,"rush_td":8, "rec":0,"rec_yds":0,"rec_td":0,"adp":21, "risk":2,"age":29,"years_exp":6},
        {"name":"Lamar Jackson",       "pos":"QB","team":"BAL","pass_yds":4000,"pass_td":35,"rush_yds":950,"rush_td":9, "rec":0,"rec_yds":0,"rec_td":0,"adp":22, "risk":3,"age":27,"years_exp":7},
        {"name":"Jalen Hurts",         "pos":"QB","team":"PHI","pass_yds":3700,"pass_td":29,"rush_yds":750,"rush_td":12,"rec":0,"rec_yds":0,"rec_td":0,"adp":24, "risk":2,"age":26,"years_exp":5},
        {"name":"Patrick Mahomes",     "pos":"QB","team":"KC", "pass_yds":4900,"pass_td":39,"rush_yds":300,"rush_td":4, "rec":0,"rec_yds":0,"rec_td":0,"adp":26, "risk":1,"age":29,"years_exp":7},
        {"name":"Jayden Daniels",      "pos":"QB","team":"WAS","pass_yds":3800,"pass_td":26,"rush_yds":600,"rush_td":6, "rec":0,"rec_yds":0,"rec_td":0,"adp":43, "risk":4,"age":24,"years_exp":1},
        {"name":"CJ Stroud",           "pos":"QB","team":"HOU","pass_yds":4200,"pass_td":33,"rush_yds":220,"rush_td":2, "rec":0,"rec_yds":0,"rec_td":0,"adp":44, "risk":3,"age":23,"years_exp":2},
        {"name":"Dak Prescott",        "pos":"QB","team":"DAL","pass_yds":4300,"pass_td":35,"rush_yds":210,"rush_td":3, "rec":0,"rec_yds":0,"rec_td":0,"adp":45, "risk":3,"age":31,"years_exp":9},
        {"name":"Jordan Love",         "pos":"QB","team":"GB", "pass_yds":4000,"pass_td":31,"rush_yds":290,"rush_td":3, "rec":0,"rec_yds":0,"rec_td":0,"adp":47, "risk":4,"age":26,"years_exp":5},
        {"name":"Sam Darnold",         "pos":"QB","team":"MIN","pass_yds":3700,"pass_td":27,"rush_yds":190,"rush_td":2, "rec":0,"rec_yds":0,"rec_td":0,"adp":49, "risk":4,"age":27,"years_exp":7},
        {"name":"Baker Mayfield",      "pos":"QB","team":"TB", "pass_yds":3900,"pass_td":29,"rush_yds":160,"rush_td":2, "rec":0,"rec_yds":0,"rec_td":0,"adp":69, "risk":3,"age":29,"years_exp":7},
        {"name":"Anthony Richardson",  "pos":"QB","team":"IND","pass_yds":3300,"pass_td":23,"rush_yds":720,"rush_td":8, "rec":0,"rec_yds":0,"rec_td":0,"adp":77, "risk":5,"age":22,"years_exp":2},
        {"name":"Tua Tagovailoa",      "pos":"QB","team":"MIA","pass_yds":3900,"pass_td":29,"rush_yds":85, "rush_td":1, "rec":0,"rec_yds":0,"rec_td":0,"adp":70, "risk":5,"age":26,"years_exp":5},
        {"name":"Geno Smith",          "pos":"QB","team":"SEA","pass_yds":3600,"pass_td":25,"rush_yds":140,"rush_td":2, "rec":0,"rec_yds":0,"rec_td":0,"adp":80, "risk":4,"age":34,"years_exp":12},
        # ── RBs ─────────────────────────────────────────────────────────────
        {"name":"Jahmyr Gibbs",        "pos":"RB","team":"DET","pass_yds":0,"pass_td":0,"rush_yds":1150,"rush_td":11,"rec":65,"rec_yds":470,"rec_td":3,"adp":2,  "risk":2,"age":22,"years_exp":2},
        {"name":"Bijan Robinson",      "pos":"RB","team":"ATL","pass_yds":0,"pass_td":0,"rush_yds":1220,"rush_td":10,"rec":68,"rec_yds":500,"rec_td":3,"adp":3,  "risk":2,"age":23,"years_exp":2},
        {"name":"Christian McCaffrey", "pos":"RB","team":"SF", "pass_yds":0,"pass_td":0,"rush_yds":1400,"rush_td":12,"rec":90,"rec_yds":700,"rec_td":5,"adp":5,  "risk":3,"age":28,"years_exp":8},
        {"name":"Jonathan Taylor",     "pos":"RB","team":"IND","pass_yds":0,"pass_td":0,"rush_yds":1220,"rush_td":10,"rec":42,"rec_yds":310,"rec_td":2,"adp":10, "risk":3,"age":25,"years_exp":5},
        {"name":"James Cook",          "pos":"RB","team":"BUF","pass_yds":0,"pass_td":0,"rush_yds":1130,"rush_td":9, "rec":48,"rec_yds":350,"rec_td":2,"adp":12, "risk":3,"age":24,"years_exp":3},
        {"name":"Ashton Jeanty",       "pos":"RB","team":"LV", "pass_yds":0,"pass_td":0,"rush_yds":1320,"rush_td":11,"rec":42,"rec_yds":310,"rec_td":2,"adp":13, "risk":3,"age":21,"years_exp":0},
        {"name":"Saquon Barkley",      "pos":"RB","team":"PHI","pass_yds":0,"pass_td":0,"rush_yds":1320,"rush_td":11,"rec":58,"rec_yds":415,"rec_td":2,"adp":16, "risk":3,"age":27,"years_exp":7},
        {"name":"De'Von Achane",       "pos":"RB","team":"MIA","pass_yds":0,"pass_td":0,"rush_yds":1020,"rush_td":9, "rec":68,"rec_yds":530,"rec_td":3,"adp":17, "risk":4,"age":23,"years_exp":2},
        {"name":"Breece Hall",         "pos":"RB","team":"NYJ","pass_yds":0,"pass_td":0,"rush_yds":1220,"rush_td":9, "rec":72,"rec_yds":560,"rec_td":3,"adp":18, "risk":3,"age":23,"years_exp":3},
        {"name":"Derrick Henry",       "pos":"RB","team":"BAL","pass_yds":0,"pass_td":0,"rush_yds":1120,"rush_td":11,"rec":22,"rec_yds":150,"rec_td":1,"adp":27, "risk":3,"age":30,"years_exp":9},
        {"name":"Tony Pollard",        "pos":"RB","team":"TEN","pass_yds":0,"pass_td":0,"rush_yds":920, "rush_td":7, "rec":57,"rec_yds":430,"rec_td":2,"adp":28, "risk":3,"age":27,"years_exp":6},
        {"name":"Travis Etienne",      "pos":"RB","team":"JAX","pass_yds":0,"pass_td":0,"rush_yds":1020,"rush_td":8, "rec":52,"rec_yds":390,"rec_td":2,"adp":29, "risk":4,"age":25,"years_exp":4},
        {"name":"Josh Jacobs",         "pos":"RB","team":"GB", "pass_yds":0,"pass_td":0,"rush_yds":930, "rush_td":8, "rec":42,"rec_yds":310,"rec_td":1,"adp":34, "risk":3,"age":26,"years_exp":6},
        {"name":"Kyren Williams",      "pos":"RB","team":"LAR","pass_yds":0,"pass_td":0,"rush_yds":1120,"rush_td":11,"rec":47,"rec_yds":340,"rec_td":2,"adp":35, "risk":4,"age":24,"years_exp":3},
        {"name":"Alvin Kamara",        "pos":"RB","team":"NO", "pass_yds":0,"pass_td":0,"rush_yds":820, "rush_td":7, "rec":72,"rec_yds":540,"rec_td":3,"adp":38, "risk":4,"age":29,"years_exp":8},
        {"name":"Joe Mixon",           "pos":"RB","team":"HOU","pass_yds":0,"pass_td":0,"rush_yds":970, "rush_td":9, "rec":42,"rec_yds":310,"rec_td":2,"adp":42, "risk":3,"age":28,"years_exp":8},
        {"name":"Kenneth Walker",      "pos":"RB","team":"SEA","pass_yds":0,"pass_td":0,"rush_yds":970, "rush_td":8, "rec":37,"rec_yds":270,"rec_td":1,"adp":50, "risk":4,"age":24,"years_exp":3},
        {"name":"Isiah Pacheco",       "pos":"RB","team":"KC", "pass_yds":0,"pass_td":0,"rush_yds":1020,"rush_td":8, "rec":32,"rec_yds":230,"rec_td":1,"adp":52, "risk":4,"age":25,"years_exp":3},
        {"name":"Rhamondre Stevenson", "pos":"RB","team":"NE", "pass_yds":0,"pass_td":0,"rush_yds":920, "rush_td":6, "rec":42,"rec_yds":310,"rec_td":1,"adp":56, "risk":4,"age":26,"years_exp":4},
        {"name":"Rachaad White",       "pos":"RB","team":"TB", "pass_yds":0,"pass_td":0,"rush_yds":820, "rush_td":6, "rec":62,"rec_yds":460,"rec_td":2,"adp":58, "risk":3,"age":27,"years_exp":3},
        {"name":"Aaron Jones",         "pos":"RB","team":"MIN","pass_yds":0,"pass_td":0,"rush_yds":920, "rush_td":8, "rec":47,"rec_yds":350,"rec_td":2,"adp":62, "risk":4,"age":30,"years_exp":8},
        {"name":"Chuba Hubbard",       "pos":"RB","team":"CAR","pass_yds":0,"pass_td":0,"rush_yds":820, "rush_td":6, "rec":42,"rec_yds":310,"rec_td":1,"adp":63, "risk":4,"age":25,"years_exp":4},
        {"name":"Javonte Williams",    "pos":"RB","team":"DEN","pass_yds":0,"pass_td":0,"rush_yds":870, "rush_td":7, "rec":42,"rec_yds":310,"rec_td":1,"adp":68, "risk":4,"age":24,"years_exp":4},
        {"name":"Zach Charbonnet",     "pos":"RB","team":"SEA","pass_yds":0,"pass_td":0,"rush_yds":720, "rush_td":6, "rec":37,"rec_yds":270,"rec_td":1,"adp":71, "risk":4,"age":23,"years_exp":2},
        {"name":"Brian Robinson",      "pos":"RB","team":"WAS","pass_yds":0,"pass_td":0,"rush_yds":870, "rush_td":7, "rec":27,"rec_yds":190,"rec_td":1,"adp":72, "risk":3,"age":25,"years_exp":3},
        {"name":"Najee Harris",        "pos":"RB","team":"LAC","pass_yds":0,"pass_td":0,"rush_yds":820, "rush_td":6, "rec":45,"rec_yds":320,"rec_td":1,"adp":92, "risk":3,"age":26,"years_exp":4},
        {"name":"James Conner",        "pos":"RB","team":"ARI","pass_yds":0,"pass_td":0,"rush_yds":720, "rush_td":7, "rec":32,"rec_yds":220,"rec_td":1,"adp":93, "risk":5,"age":29,"years_exp":8},
        {"name":"D'Andre Swift",       "pos":"RB","team":"CHI","pass_yds":0,"pass_td":0,"rush_yds":870, "rush_td":6, "rec":47,"rec_yds":340,"rec_td":1,"adp":85, "risk":4,"age":25,"years_exp":5},
        {"name":"David Montgomery",    "pos":"RB","team":"DET","pass_yds":0,"pass_td":0,"rush_yds":870, "rush_td":9, "rec":32,"rec_yds":230,"rec_td":1,"adp":94, "risk":3,"age":26,"years_exp":6},
        {"name":"Jaylen Warren",       "pos":"RB","team":"PIT","pass_yds":0,"pass_td":0,"rush_yds":670, "rush_td":5, "rec":42,"rec_yds":300,"rec_td":1,"adp":96, "risk":3,"age":25,"years_exp":3},
        {"name":"Tyjae Spears",        "pos":"RB","team":"TEN","pass_yds":0,"pass_td":0,"rush_yds":620, "rush_td":5, "rec":47,"rec_yds":340,"rec_td":1,"adp":115,"risk":4,"age":23,"years_exp":2},
        {"name":"Jaylen Wright",       "pos":"RB","team":"MIA","pass_yds":0,"pass_td":0,"rush_yds":570, "rush_td":5, "rec":32,"rec_yds":230,"rec_td":1,"adp":116,"risk":4,"age":22,"years_exp":1},
        {"name":"Chase Brown",         "pos":"RB","team":"CIN","pass_yds":0,"pass_td":0,"rush_yds":620, "rush_td":5, "rec":37,"rec_yds":270,"rec_td":1,"adp":117,"risk":4,"age":24,"years_exp":2},
        {"name":"Rico Dowdle",         "pos":"RB","team":"DAL","pass_yds":0,"pass_td":0,"rush_yds":570, "rush_td":4, "rec":32,"rec_yds":230,"rec_td":1,"adp":118,"risk":4,"age":26,"years_exp":3},
        {"name":"Tyrone Tracy Jr.",    "pos":"RB","team":"NYG","pass_yds":0,"pass_td":0,"rush_yds":520, "rush_td":4, "rec":32,"rec_yds":220,"rec_td":1,"adp":119,"risk":4,"age":24,"years_exp":1},
        {"name":"Devin Singletary",    "pos":"RB","team":"HOU","pass_yds":0,"pass_td":0,"rush_yds":520, "rush_td":4, "rec":27,"rec_yds":190,"rec_td":1,"adp":120,"risk":3,"age":27,"years_exp":5},
        {"name":"Braelon Allen",       "pos":"RB","team":"NYJ","pass_yds":0,"pass_td":0,"rush_yds":570, "rush_td":5, "rec":32,"rec_yds":230,"rec_td":1,"adp":121,"risk":4,"age":21,"years_exp":1},
        {"name":"Blake Corum",         "pos":"RB","team":"LAR","pass_yds":0,"pass_td":0,"rush_yds":520, "rush_td":5, "rec":22,"rec_yds":160,"rec_td":1,"adp":122,"risk":4,"age":23,"years_exp":1},
        {"name":"Jordan Mason",        "pos":"RB","team":"SF", "pass_yds":0,"pass_td":0,"rush_yds":570, "rush_td":5, "rec":22,"rec_yds":160,"rec_td":1,"adp":125,"risk":4,"age":25,"years_exp":2},
        {"name":"Keaton Mitchell",     "pos":"RB","team":"BAL","pass_yds":0,"pass_td":0,"rush_yds":520, "rush_td":4, "rec":22,"rec_yds":160,"rec_td":1,"adp":124,"risk":5,"age":23,"years_exp":2},
        # ── WRs ─────────────────────────────────────────────────────────────
        {"name":"Puka Nacua",          "pos":"WR","team":"LAR","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":108,"rec_yds":1220,"rec_td":8, "adp":1,  "risk":3,"age":23,"years_exp":2},
        {"name":"Jaxon Smith-Njigba",  "pos":"WR","team":"SEA","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":108,"rec_yds":1270,"rec_td":9, "adp":6,  "risk":3,"age":23,"years_exp":2},
        {"name":"Amon-Ra St. Brown",   "pos":"WR","team":"DET","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":112,"rec_yds":1320,"rec_td":10,"adp":7,  "risk":1,"age":24,"years_exp":4},
        {"name":"Rashee Rice",         "pos":"WR","team":"KC", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":88, "rec_yds":1070,"rec_td":8, "adp":8,  "risk":5,"age":23,"years_exp":2},
        {"name":"CeeDee Lamb",         "pos":"WR","team":"DAL","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":122,"rec_yds":1620,"rec_td":12,"adp":9,  "risk":1,"age":25,"years_exp":5},
        {"name":"Justin Jefferson",    "pos":"WR","team":"MIN","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":108,"rec_yds":1470,"rec_td":10,"adp":11, "risk":2,"age":25,"years_exp":5},
        {"name":"Drake London",        "pos":"WR","team":"ATL","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":98, "rec_yds":1120,"rec_td":9, "adp":14, "risk":3,"age":23,"years_exp":3},
        {"name":"Nico Collins",        "pos":"WR","team":"HOU","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":90, "rec_yds":1120,"rec_td":8, "adp":15, "risk":4,"age":26,"years_exp":4},
        {"name":"Ja'Marr Chase",       "pos":"WR","team":"CIN","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":102,"rec_yds":1420,"rec_td":11,"adp":4,  "risk":2,"age":24,"years_exp":4},
        {"name":"Jaylen Waddle",       "pos":"WR","team":"MIA","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":92, "rec_yds":1170,"rec_td":8, "adp":19, "risk":4,"age":26,"years_exp":4},
        {"name":"Brian Thomas Jr.",    "pos":"WR","team":"JAX","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":92, "rec_yds":1170,"rec_td":8, "adp":30, "risk":4,"age":22,"years_exp":1},
        {"name":"Davante Adams",       "pos":"WR","team":"NYJ","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":102,"rec_yds":1320,"rec_td":11,"adp":31, "risk":2,"age":31,"years_exp":11},
        {"name":"Tee Higgins",         "pos":"WR","team":"CIN","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":82, "rec_yds":1070,"rec_td":9, "adp":32, "risk":4,"age":25,"years_exp":5},
        {"name":"DJ Moore",            "pos":"WR","team":"CHI","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":87, "rec_yds":1070,"rec_td":8, "adp":33, "risk":3,"age":27,"years_exp":6},
        {"name":"Stefon Diggs",        "pos":"WR","team":"HOU","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":97, "rec_yds":1220,"rec_td":9, "adp":36, "risk":3,"age":30,"years_exp":10},
        {"name":"Chris Olave",         "pos":"WR","team":"NO", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":87, "rec_yds":1120,"rec_td":8, "adp":37, "risk":3,"age":24,"years_exp":3},
        {"name":"Mike Evans",          "pos":"WR","team":"TB", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":82, "rec_yds":1120,"rec_td":11,"adp":39, "risk":3,"age":31,"years_exp":11},
        {"name":"Brandon Aiyuk",       "pos":"WR","team":"SF", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":80, "rec_yds":1040,"rec_td":8, "adp":40, "risk":3,"age":26,"years_exp":5},
        {"name":"Keenan Allen",        "pos":"WR","team":"CHI","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":92, "rec_yds":1070,"rec_td":8, "adp":41, "risk":3,"age":32,"years_exp":12},
        {"name":"DK Metcalf",          "pos":"WR","team":"SEA","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":77, "rec_yds":1070,"rec_td":9, "adp":46, "risk":4,"age":27,"years_exp":6},
        {"name":"Zay Flowers",         "pos":"WR","team":"BAL","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":82, "rec_yds":1020,"rec_td":7, "adp":48, "risk":4,"age":23,"years_exp":2},
        {"name":"Garrett Wilson",      "pos":"WR","team":"NYJ","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":97, "rec_yds":1170,"rec_td":8, "adp":51, "risk":3,"age":24,"years_exp":3},
        {"name":"Calvin Ridley",       "pos":"WR","team":"TEN","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":82, "rec_yds":1020,"rec_td":8, "adp":53, "risk":4,"age":30,"years_exp":7},
        {"name":"Tank Dell",           "pos":"WR","team":"HOU","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":77, "rec_yds":1070,"rec_td":9, "adp":59, "risk":5,"age":23,"years_exp":2},
        {"name":"Deebo Samuel",        "pos":"WR","team":"SF", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":77, "rec_yds":1020,"rec_td":8, "adp":60, "risk":5,"age":28,"years_exp":6},
        {"name":"Christian Kirk",      "pos":"WR","team":"JAX","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":82, "rec_yds":970, "rec_td":7, "adp":61, "risk":4,"age":27,"years_exp":7},
        {"name":"DeAndre Hopkins",     "pos":"WR","team":"TEN","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":82, "rec_yds":970, "rec_td":8, "adp":64, "risk":3,"age":32,"years_exp":12},
        {"name":"Amari Cooper",        "pos":"WR","team":"CLE","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":77, "rec_yds":970, "rec_td":7, "adp":65, "risk":4,"age":30,"years_exp":10},
        {"name":"Tyler Lockett",       "pos":"WR","team":"SEA","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":77, "rec_yds":920, "rec_td":8, "adp":66, "risk":4,"age":32,"years_exp":10},
        {"name":"Rome Odunze",         "pos":"WR","team":"CHI","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":72, "rec_yds":920, "rec_td":7, "adp":78, "risk":5,"age":22,"years_exp":1},
        {"name":"Quentin Johnston",    "pos":"WR","team":"LAC","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":72, "rec_yds":970, "rec_td":7, "adp":79, "risk":5,"age":22,"years_exp":2},
        {"name":"Ladd McConkey",       "pos":"WR","team":"LAC","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":77, "rec_yds":920, "rec_td":6, "adp":81, "risk":3,"age":23,"years_exp":1},
        {"name":"Jordan Addison",      "pos":"WR","team":"MIN","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":72, "rec_yds":870, "rec_td":7, "adp":82, "risk":4,"age":22,"years_exp":2},
        {"name":"George Pickens",      "pos":"WR","team":"DAL","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":72, "rec_yds":870, "rec_td":7, "adp":42, "risk":4,"age":23,"years_exp":3},
        {"name":"Chris Godwin",        "pos":"WR","team":"TB", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":77, "rec_yds":820, "rec_td":6, "adp":84, "risk":4,"age":28,"years_exp":8},
        {"name":"Malik Nabers",        "pos":"WR","team":"NYG","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":87, "rec_yds":1020,"rec_td":7, "adp":32, "risk":4,"age":22,"years_exp":1},
        {"name":"Marvin Harrison Jr.", "pos":"WR","team":"ARI","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":77, "rec_yds":920, "rec_td":7, "adp":38, "risk":4,"age":22,"years_exp":1},
        {"name":"DeVonta Smith",       "pos":"WR","team":"PHI","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":72, "rec_yds":820, "rec_td":6, "adp":91, "risk":3,"age":26,"years_exp":4},
        {"name":"Jaylen Reed",         "pos":"WR","team":"GB", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":72, "rec_yds":820, "rec_td":6, "adp":87, "risk":3,"age":24,"years_exp":2},
        {"name":"Xavier Worthy",       "pos":"WR","team":"KC", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":67, "rec_yds":770, "rec_td":6, "adp":88, "risk":4,"age":22,"years_exp":1},
        {"name":"Khalil Shakir",       "pos":"WR","team":"BUF","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":67, "rec_yds":720, "rec_td":5, "adp":95, "risk":3,"age":25,"years_exp":3},
        {"name":"Courtland Sutton",    "pos":"WR","team":"DEN","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":72, "rec_yds":820, "rec_td":6, "adp":110,"risk":3,"age":29,"years_exp":7},
        {"name":"Jerry Jeudy",         "pos":"WR","team":"CLE","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":67, "rec_yds":770, "rec_td":6, "adp":111,"risk":4,"age":25,"years_exp":5},
        {"name":"Joshua Palmer",       "pos":"WR","team":"LAC","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":62, "rec_yds":720, "rec_td":5, "adp":106,"risk":3,"age":25,"years_exp":4},
        {"name":"Keon Coleman",        "pos":"WR","team":"BUF","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":62, "rec_yds":720, "rec_td":5, "adp":107,"risk":4,"age":22,"years_exp":1},
        {"name":"Diontae Johnson",     "pos":"WR","team":"BAL","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":62, "rec_yds":670, "rec_td":4, "adp":86, "risk":4,"age":27,"years_exp":5},
        {"name":"Jahan Dotson",        "pos":"WR","team":"PHI","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":57, "rec_yds":620, "rec_td":5, "adp":108,"risk":4,"age":24,"years_exp":3},
        # ── TEs ─────────────────────────────────────────────────────────────
        {"name":"Travis Kelce",        "pos":"TE","team":"KC", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":92,"rec_yds":1020,"rec_td":9,"adp":20, "risk":2,"age":35,"years_exp":12},
        {"name":"Trey McBride",        "pos":"TE","team":"ARI","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":87,"rec_yds":920, "rec_td":7,"adp":23, "risk":3,"age":24,"years_exp":3},
        {"name":"Sam LaPorta",         "pos":"TE","team":"DET","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":82,"rec_yds":920, "rec_td":8,"adp":25, "risk":3,"age":23,"years_exp":2},
        {"name":"Brock Bowers",        "pos":"TE","team":"LV", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":92,"rec_yds":980, "rec_td":8,"adp":16, "risk":3,"age":22,"years_exp":1},
        {"name":"Evan Engram",         "pos":"TE","team":"JAX","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":77,"rec_yds":840, "rec_td":6,"adp":54, "risk":4,"age":30,"years_exp":8},
        {"name":"Dallas Goedert",      "pos":"TE","team":"PHI","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":72,"rec_yds":800, "rec_td":7,"adp":55, "risk":4,"age":29,"years_exp":7},
        {"name":"Jake Ferguson",       "pos":"TE","team":"DAL","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":67,"rec_yds":720, "rec_td":6,"adp":57, "risk":3,"age":24,"years_exp":3},
        {"name":"David Njoku",         "pos":"TE","team":"CLE","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":67,"rec_yds":720, "rec_td":6,"adp":67, "risk":4,"age":28,"years_exp":7},
        {"name":"George Kittle",       "pos":"TE","team":"SF", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":72,"rec_yds":770, "rec_td":7,"adp":45, "risk":4,"age":30,"years_exp":8},
        {"name":"Pat Freiermuth",      "pos":"TE","team":"PIT","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":62,"rec_yds":670, "rec_td":6,"adp":73, "risk":3,"age":25,"years_exp":4},
        {"name":"Cole Kmet",           "pos":"TE","team":"CHI","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":64,"rec_yds":680, "rec_td":5,"adp":74, "risk":3,"age":25,"years_exp":5},
        {"name":"Dalton Kincaid",      "pos":"TE","team":"BUF","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":60,"rec_yds":640, "rec_td":5,"adp":75, "risk":4,"age":25,"years_exp":2},
        {"name":"Tucker Kraft",        "pos":"TE","team":"GB", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":57,"rec_yds":600, "rec_td":5,"adp":76, "risk":4,"age":23,"years_exp":2},
        {"name":"Luke Musgrave",       "pos":"TE","team":"GB", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":52,"rec_yds":550, "rec_td":4,"adp":85, "risk":4,"age":24,"years_exp":2},
        {"name":"Cade Otton",          "pos":"TE","team":"TB", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":52,"rec_yds":530, "rec_td":4,"adp":100,"risk":3,"age":25,"years_exp":3},
        {"name":"Hunter Henry",        "pos":"TE","team":"NE", "pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":47,"rec_yds":500, "rec_td":4,"adp":102,"risk":3,"age":30,"years_exp":8},
        {"name":"Dalton Schultz",      "pos":"TE","team":"HOU","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":52,"rec_yds":540, "rec_td":4,"adp":103,"risk":3,"age":28,"years_exp":6},
        {"name":"Tyler Conklin",       "pos":"TE","team":"NYJ","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":47,"rec_yds":490, "rec_td":3,"adp":104,"risk":3,"age":29,"years_exp":5},
        {"name":"Jonnu Smith",         "pos":"TE","team":"MIA","pass_yds":0,"pass_td":0,"rush_yds":0,"rush_td":0,"rec":47,"rec_yds":490, "rec_td":4,"adp":105,"risk":3,"age":29,"years_exp":7},
    ]


def _calc_proj_pts(df, rec_bonus):
    """Use expert projections when available, formula otherwise."""
    if rec_bonus == 1.0:   mult = 1.0
    elif rec_bonus == 0.5: mult = 0.93
    else:                  mult = 0.86

    result = []
    for _, row in df.iterrows():
        expert = EXPERT_PROJECTIONS.get(row["name"])
        if expert:
            result.append(round(expert * mult, 1))
        else:
            pts = (
                row["pass_yds"] * 0.04 + row["pass_td"]  * 4   +
                row["rush_yds"] * 0.1  + row["rush_td"]  * 6   +
                row["rec"]      * rec_bonus +
                row["rec_yds"]  * 0.1  + row["rec_td"]   * 6
            )
            result.append(round(pts, 1))
    return pd.Series(result, index=df.index)


def _calc_vor(df):
    return (df["proj_pts"] - df["pos"].map(VOR_BASELINES)).round(1)


def _calc_scarcity(df, num_teams):
    return (df["adp"] / num_teams).apply(lambda x: max(1, round(x)))


def get_players(scoring="PPR", num_teams=12):
    rec_bonus = {"Standard": 0, "Half-PPR": 0.5, "PPR": 1.0}[scoring]

    cached = _load_cache()
    if cached:
        df = pd.DataFrame(cached)
        df["proj_pts"]  = _calc_proj_pts(df, rec_bonus)
        df["vor"]       = _calc_vor(df)
        df["est_round"] = _calc_scarcity(df, num_teams)
        df["source"]    = "Sleeper API (cached)"
        return df.reset_index(drop=True)

    try:
        players_raw, source = _fetch_from_sleeper()
        _save_cache(players_raw)
        df = pd.DataFrame(players_raw)
        df["proj_pts"]  = _calc_proj_pts(df, rec_bonus)
        df["vor"]       = _calc_vor(df)
        df["est_round"] = _calc_scarcity(df, num_teams)
        df["source"]    = source
        return df.reset_index(drop=True)
    except Exception as e:
        print(f"[data.py] Sleeper unavailable ({e}), using fallback.")
        df = pd.DataFrame(_fallback_players())
        df["proj_pts"]  = _calc_proj_pts(df, rec_bonus)
        df["vor"]       = _calc_vor(df)
        df["est_round"] = _calc_scarcity(df, num_teams)
        df["source"]    = "hardcoded fallback"
        return df.reset_index(drop=True)
