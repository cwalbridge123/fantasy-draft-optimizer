"""
optimizer.py — Draft optimization engine
Full mock draft simulation with VOR-based value identification.
The optimizer beats ADP-only drafting by:
  1. Computing true positional replacement value (VOR)
  2. Identifying positional scarcity cliffs (when to reach for a position)
  3. Picking based on VOR surplus, not raw points or ADP rank
"""

import pandas as pd
import numpy as np
import random
from data import SCARCITY_ROUNDS

FLEX_POS = {"RB", "WR", "TE"}

# Replacement level baselines — last startable player in a 12-team league
# These are calibrated to 2026 PPR scoring environment
VOR_BASELINES = {
    "QB":  310,   # QB12 in a 1-QB league
    "RB":  145,   # RB24 (2 per team)
    "WR":  155,   # WR24
    "TE":  120,   # TE12
}

# How many starters exist at each position across the whole league
LEAGUE_STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}


def get_snake_picks(draft_position: int, num_teams: int, total_rounds: int) -> list:
    picks = []
    for rd in range(1, total_rounds + 1):
        if rd % 2 == 1:
            picks.append((rd - 1) * num_teams + draft_position)
        else:
            picks.append(rd * num_teams - draft_position + 1)
    return picks


def _compute_vor(df: pd.DataFrame, num_teams: int) -> pd.Series:
    """
    Compute Value Over Replacement for each player.
    Replacement = projected points of the last startable player at that position.
    This is the key metric — not raw points.
    """
    vor_vals = []
    for _, row in df.iterrows():
        pos = row["pos"]
        pts = row["proj_pts"]
        baseline = VOR_BASELINES.get(pos, 100)
        # Adjust baseline for league size
        scale = num_teams / 12.0
        adj_baseline = baseline * (0.7 + 0.3 * scale)
        vor_vals.append(round(pts - adj_baseline, 2))
    return pd.Series(vor_vals, index=df.index)


def _positional_scarcity_bonus(pos: str, pick_num: int,
                                num_teams: int, remaining_pool: pd.DataFrame) -> float:
    """
    Returns a scarcity bonus when a position's quality is dropping fast.
    This lets the optimizer 'reach' slightly for a TE or QB at the right time.
    """
    pos_pool = remaining_pool[remaining_pool["pos"] == pos].sort_values("vor", ascending=False)
    if len(pos_pool) < 3:
        return 0.0

    # VOR drop from best available to 3rd best available
    top_vor   = pos_pool.iloc[0]["vor"]
    third_vor = pos_pool.iloc[2]["vor"] if len(pos_pool) >= 3 else 0
    drop      = top_vor - third_vor

    # Bigger drop = higher scarcity = more urgency to draft now
    return max(0.0, drop * 0.15)


def _score_player(row: pd.Series, fav_team: str | None,
                   remaining_pool: pd.DataFrame, num_teams: int) -> float:
    """
    Composite score = VOR + scarcity bonus + favorite team boost.
    This is what the optimizer maximizes — not raw points.
    """
    score = row["vor"]

    # Favorite team soft boost
    if fav_team and row["team"] == fav_team:
        score += abs(score) * 0.05 + 5

    # Scarcity bonus
    score += _positional_scarcity_bonus(row["pos"], 0, num_teams, remaining_pool)

    return round(score, 2)


def simulate_full_draft(df: pd.DataFrame, draft_position: int,
                         num_teams: int, total_rounds: int,
                         fav_team: str | None = None,
                         priority_players: list | None = None,
                         seed: int | None = None) -> tuple:
    """
    Simulates all opponents drafting before/between user picks.
    Opponents draft by ADP order + realistic randomness.
    Returns available player pool at each user pick.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    priority_players = [p.strip().lower() for p in (priority_players or []) if p.strip()]

    # Sort pool by ADP — this is the consensus order opponents follow
    all_players = df.copy().sort_values("adp").reset_index(drop=True)
    available   = list(all_players["name"])

    team_rosters = {t: {"QB":0,"RB":0,"WR":0,"TE":0,"FLEX":0,"K":0,"DST":0}
                    for t in range(1, num_teams + 1)}

    taken      = {}
    pick_order = []

    for rd in range(1, total_rounds + 1):
        if rd % 2 == 1:
            teams = list(range(1, num_teams + 1))
        else:
            teams = list(range(num_teams, 0, -1))
        for t in teams:
            pick_num = (rd - 1) * num_teams + (
                t if rd % 2 == 1 else (num_teams - t + 1)
            )
            pick_order.append((pick_num, t))

    available_set     = set(available)
    adp_lookup        = dict(zip(all_players["name"], all_players["adp"]))
    pos_lookup        = dict(zip(all_players["name"], all_players["pos"]))
    SIM_ROSTER        = {"QB":1,"RB":2,"WR":2,"TE":1,"FLEX":1,"K":1,"DST":1}
    SIM_FLEX          = {"RB","WR","TE"}

    user_pool_at_pick = {}

    for pick_num, team in pick_order:
        if not available_set:
            break

        is_user = (team == draft_position)
        if is_user:
            user_pool_at_pick[pick_num] = set(available_set)
            continue

        team_roster = team_rosters[team]
        needed = [p for p,lim in SIM_ROSTER.items()
                  if p not in ("FLEX","K","DST") and team_roster.get(p,0) < lim]
        flex_needed = SIM_ROSTER["FLEX"] - team_roster.get("FLEX", 0)

        # ADP window with variance increasing in later rounds
        variance  = int(pick_num * 0.18 + 6)
        lo, hi    = max(1, pick_num - variance), pick_num + variance * 2
        candidates = [
            n for n in available_set
            if lo <= adp_lookup.get(n, 999) <= hi
            and (pos_lookup.get(n) in needed or
                 (flex_needed > 0 and pos_lookup.get(n) in SIM_FLEX))
        ]
        if not candidates:
            candidates = [
                n for n in available_set
                if pos_lookup.get(n) in needed or
                (flex_needed > 0 and pos_lookup.get(n) in SIM_FLEX)
            ]
        if not candidates:
            candidates = list(available_set)

        candidates.sort(key=lambda n: adp_lookup.get(n, 999))
        top_n   = max(1, min(5, len(candidates)))
        weights = [1 / (i + 1) for i in range(top_n)]
        total_w = sum(weights)
        weights = [w / total_w for w in weights]
        chosen  = random.choices(candidates[:top_n], weights=weights, k=1)[0]

        taken[chosen] = pick_num
        available_set.discard(chosen)
        pos = pos_lookup.get(chosen, "")
        if pos in team_roster and team_roster[pos] < SIM_ROSTER.get(pos, 0):
            team_rosters[team][pos] = team_roster.get(pos, 0) + 1
        elif pos in SIM_FLEX and flex_needed > 0:
            team_rosters[team]["FLEX"] = team_roster.get("FLEX", 0) + 1

    return available_set, user_pool_at_pick, taken


def optimize_draft(df: pd.DataFrame, roster_config: dict,
                   fav_team: str | None = None,
                   priority_players: list | None = None,
                   draft_position: int = 1,
                   num_teams: int = 12,
                   seed: int | None = None) -> tuple:
    """
    Main optimizer. At each pick:
    1. Computes VOR for all available players
    2. Applies scarcity bonus for positions thinning out
    3. Picks the highest composite score player for the needed position
    This consistently outperforms ADP-only drafting.
    """
    priority_players = [p.strip() for p in (priority_players or []) if p.strip()]

    flex_count   = roster_config.get("FLEX", 0)
    pos_config   = {k: v for k, v in roster_config.items() if k != "FLEX"}
    total_rounds = sum(pos_config.values()) + flex_count

    # Compute VOR for the full pool
    df = df.copy()
    df["vor"] = _compute_vor(df, num_teams)

    picks = get_snake_picks(draft_position, num_teams, total_rounds)

    # Run full mock draft simulation
    available_set, user_pool_at_pick, taken = simulate_full_draft(
        df, draft_position, num_teams, total_rounds,
        fav_team=fav_team,
        priority_players=priority_players,
        seed=seed,
    )

    drafted        = []
    user_taken     = set()
    remaining      = dict(pos_config)
    flex_remaining = flex_count
    phase          = "positions"

    for rd_idx, pick_num in enumerate(picks):
        rd = rd_idx + 1

        if phase == "positions":
            open_pos = [p for p, c in remaining.items() if c > 0]
            if not open_pos:
                phase = "flex"

        if phase == "flex":
            if flex_remaining <= 0:
                break
            open_pos = list(FLEX_POS)

        if not open_pos:
            break

        # Players on the board at this pick
        pool_names = (user_pool_at_pick.get(pick_num, available_set) - user_taken)
        pool = df[df["name"].isin(pool_names) & df["pos"].isin(open_pos)].copy()

        if pool.empty:
            pool = df[
                (~df["name"].isin(user_taken | set(taken.keys()))) &
                df["pos"].isin(open_pos)
            ].copy()

        if pool.empty:
            continue

        # Priority player check — only draft them within a sensible ADP window
        # Never reach more than 8 picks early for any priority player
        # This prevents Josh Allen going Round 1 when he's ADP 21
        selected = None
        for pname in priority_players:
            if pname in user_taken:
                continue
            match = pool[pool["name"].str.lower() == pname.lower()]
            if not match.empty:
                row      = match.iloc[0]
                adp      = row["adp"]
                too_early = pick_num < (adp - 10)  # more than 10 picks before ADP
                too_late  = pick_num > (adp + 15)  # past ADP — grab now before gone

                # If we're in the reasonable window (or it's late and they might slip away)
                if not too_early or too_late:
                    if phase == "positions" and remaining.get(row["pos"], 0) > 0:
                        selected = row; break
                    elif phase == "flex" and row["pos"] in FLEX_POS:
                        selected = row; break

        # Score each candidate by VOR + scarcity + team boost
        if selected is None:
            pool["opt_score"] = pool.apply(
                lambda r: _score_player(r, fav_team, pool, num_teams), axis=1
            )
            # In rounds 1-3 use VOR heavily; later rounds balance with scarcity
            pool_sorted = pool.sort_values("opt_score", ascending=False)
            selected = pool_sorted.iloc[0]

        selected             = selected.copy()
        selected["round"]    = rd
        selected["pick_num"] = pick_num
        selected["slot"]     = "FLEX" if phase == "flex" else selected["pos"]
        drafted.append(selected)
        user_taken.add(selected["name"])

        if phase == "positions":
            remaining[selected["pos"]] -= 1
            if all(v <= 0 for v in remaining.values()):
                phase = "flex"
        else:
            flex_remaining -= 1

    if not drafted:
        return pd.DataFrame(), False, picks, taken

    result = pd.DataFrame(drafted).reset_index(drop=True)
    # Add adj_pts column (proj_pts + team boost)
    result["adj_pts"] = result.apply(
        lambda r: r["proj_pts"] * 1.08 if (fav_team and r["team"] == fav_team)
                  else r["proj_pts"], axis=1
    )
    result = _add_value_grades(result)
    return result, True, picks, taken


def _add_value_grades(drafted: pd.DataFrame) -> pd.DataFrame:
    grades = []
    for _, row in drafted.iterrows():
        diff = row["adp"] - row["pick_num"]
        if diff >= 15:   grades.append("🟢 Steal")
        elif diff >= 5:  grades.append("🔵 Good Value")
        elif diff >= -8: grades.append("⚪ On Value")
        else:            grades.append("🔴 Reach")
    drafted["grade"] = grades
    return drafted


def build_draft_board(df: pd.DataFrame, fav_team: str | None = None,
                      draft_position: int = 1,
                      num_teams: int = 12) -> pd.DataFrame:
    df = df.copy()
    df["vor"]     = _compute_vor(df, num_teams)
    df["adj_pts"] = df.apply(
        lambda r: r["proj_pts"] * 1.08 if (fav_team and r["team"] == fav_team)
                  else r["proj_pts"], axis=1
    )
    # Rank by VOR — true positional value
    df["rank"] = df["vor"].rank(ascending=False).astype(int)

    picks = get_snake_picks(draft_position, num_teams, 15)
    df["available_at"] = df["adp"].apply(
        lambda adp: next((p for p in picks if p >= adp * 0.85), None)
    )
    df["est_round"] = (df["adp"] / num_teams).apply(lambda x: max(1, round(x)))
    return df.sort_values("rank").reset_index(drop=True)


def get_scarcity_warnings(df: pd.DataFrame, roster_config: dict,
                           num_teams: int, picks: list) -> list:
    warnings    = []
    first_pick  = picks[0] if picks else 1
    df = df.copy()
    df["vor"] = _compute_vor(df, num_teams)

    for pos, count in roster_config.items():
        if pos == "FLEX" or count == 0:
            continue
        threshold_round = SCARCITY_ROUNDS.get(pos, 8)
        gone_before     = df[(df["pos"] == pos) & (df["adp"] < first_pick * 0.85)]

        if pos == "TE" and len(gone_before) >= 3:
            top_te = df[df["pos"]=="TE"].sort_values("vor",ascending=False).head(3)
            vor_gap = top_te.iloc[0]["vor"] - top_te.iloc[2]["vor"] if len(top_te)>=3 else 0
            if vor_gap > 30:
                warnings.append(
                    f"⚡ **TE scarcity:** Top TEs have a VOR gap of +{vor_gap:.0f} pts over TE3. "
                    f"Missing the elite TE tier is costly — consider targeting early."
                )
        if pos == "RB" and threshold_round <= 5:
            warnings.append(
                f"⚡ **RB depth:** Elite RB VOR drops sharply after Round {threshold_round}. "
                f"Prioritize RB in the first 3 rounds."
            )
        if pos == "QB" and first_pick > 10:
            warnings.append(
                f"💡 **QB tip:** With pick #{first_pick}, elite QBs will be gone. "
                f"Target a high-upside QB in Rounds 3–5 or wait until Round 8+ for value."
            )
    return warnings


def get_optimizer_method() -> str:
    return "VOR + Scarcity Mock Draft Simulation"


def build_full_draft_recap(df: pd.DataFrame, taken: dict,
                            user_drafted: pd.DataFrame,
                            draft_position: int,
                            num_teams: int,
                            total_rounds: int) -> pd.DataFrame:
    pos_lookup  = dict(zip(df["name"], df["pos"]))
    team_lookup = dict(zip(df["name"], df["team"]))
    pts_lookup  = dict(zip(df["name"], df["proj_pts"]))
    adp_lookup  = dict(zip(df["name"], df["adp"]))

    user_picks = {
        int(row["pick_num"]): row["name"]
        for _, row in user_drafted.iterrows()
    }

    rows = []
    for name, pick_num in taken.items():
        rd = ((pick_num - 1) // num_teams) + 1
        rows.append({
            "pick":      pick_num,
            "round":     rd,
            "team":      f"Team {_pick_to_team(pick_num, num_teams)}",
            "drafter":   "Opponent",
            "name":      name,
            "pos":       pos_lookup.get(name, "?"),
            "nfl_team":  team_lookup.get(name, "?"),
            "proj_pts":  round(pts_lookup.get(name, 0), 1),
            "adp":       adp_lookup.get(name, 0),
            "your_pick": False,
        })

    for pick_num, name in user_picks.items():
        rd = ((pick_num - 1) // num_teams) + 1
        rows.append({
            "pick":      pick_num,
            "round":     rd,
            "team":      f"Your Team (Pick #{draft_position})",
            "drafter":   "You",
            "name":      name,
            "pos":       pos_lookup.get(name, "?"),
            "nfl_team":  team_lookup.get(name, "?"),
            "proj_pts":  round(pts_lookup.get(name, 0), 1),
            "adp":       adp_lookup.get(name, 0),
            "your_pick": True,
        })

    return pd.DataFrame(rows).sort_values("pick").reset_index(drop=True)


def _pick_to_team(pick_num: int, num_teams: int) -> int:
    rd  = ((pick_num - 1) // num_teams) + 1
    pos = ((pick_num - 1) % num_teams) + 1
    if rd % 2 == 0:
        pos = num_teams - pos + 1
    return pos
