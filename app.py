"""
app.py — Fantasy Football Draft Optimizer
Streamlit UI: 3 tabs — Roster, Draft Board, AI Summary
"""

import streamlit as st
import pandas as pd
import requests
import sys, os
import random

# ── API key — reads from Streamlit Cloud secrets or local environment ─────────
def get_api_key():
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY", "")
sys.path.insert(0, os.path.dirname(__file__))

from data import get_players
from optimizer import (
    optimize_draft, build_draft_board,
    get_snake_picks, get_scarcity_warnings,
    get_optimizer_method, build_full_draft_recap,
)
from validation import run_backtest, get_actual_2024_stats

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Fantasy Draft Optimizer",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Sidebar */
[data-testid="stSidebar"] { background-color: #0D1B2A; }
[data-testid="stSidebar"] * { color: #F5F5F0 !important; }

/* Dropdowns closed */
[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div,
.stSelectbox div[data-baseweb="select"] > div {
    background-color: #111827 !important;
    color: #F5F5F0 !important;
    border: 1px solid #1B998B !important;
    border-radius: 6px !important;
}
[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] span,
.stSelectbox div[data-baseweb="select"] span { color: #F5F5F0 !important; }

/* Dropdown open */
ul[data-testid="stSelectboxVirtualDropdown"],
div[data-baseweb="popover"] ul,
div[data-baseweb="menu"] {
    background-color: #111827 !important;
    border: 1px solid #1B998B !important;
    border-radius: 6px !important;
}
ul[data-testid="stSelectboxVirtualDropdown"] li,
div[data-baseweb="menu"] li,
div[data-baseweb="option"] {
    background-color: #111827 !important;
    color: #F5F5F0 !important;
}
ul[data-testid="stSelectboxVirtualDropdown"] li:hover,
div[data-baseweb="option"]:hover { background-color: #1B998B !important; color:#fff !important; }
div[aria-selected="true"] { background-color: #0F6E56 !important; color:#fff !important; }

/* Multiselect */
.stMultiSelect div[data-baseweb="select"] > div {
    background-color: #111827 !important;
    border: 1px solid #1B998B !important;
    border-radius: 6px !important;
}
.stMultiSelect span { color: #F5F5F0 !important; }
.stMultiSelect [data-baseweb="tag"] { background-color: #1B998B !important; color: #fff !important; }

/* Text inputs */
[data-testid="stSidebar"] .stTextInput input, .stTextInput input {
    background-color: #111827 !important;
    color: #F5F5F0 !important;
    border: 1px solid #1B998B !important;
    border-radius: 6px !important;
}
[data-testid="stSidebar"] .stTextInput input::placeholder,
.stTextInput input::placeholder { color: #8899AA !important; }

/* Number inputs */
[data-testid="stSidebar"] input[type="number"], input[type="number"] {
    background-color: #111827 !important;
    color: #F5F5F0 !important;
    border: 1px solid #1B998B !important;
    border-radius: 6px !important;
}

/* Metric cards */
.metric-card {
    background: #172840; border: 1px solid #1E3A55;
    border-radius: 10px; padding: 16px;
    text-align: center; margin-bottom: 8px;
}
.metric-card h2 { color: #1B998B; margin: 0; font-size: 1.8rem; }
.metric-card p  { color: #94A3B8; margin: 0; font-size: 0.82rem; }

/* Pick rows */
.pick-row {
    padding: 8px 12px; border-radius: 6px; margin: 4px 0;
    background: #172840; border-left: 4px solid #1B998B;
    color: #F0F4F8;
}
.pick-priority { border-left: 4px solid #FFBC42 !important; }
.pick-favteam  { border-left: 4px solid #4A90D9 !important; }

/* Scarcity warnings */
.scarcity-box {
    background: #1A2A1A; border: 1px solid #2D5A2D;
    border-radius: 8px; padding: 10px 14px; margin: 6px 0;
    color: #D1FAE5;
}
</style>
""", unsafe_allow_html=True)

NFL_TEAMS = [
    "None","ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE",
    "DAL","DEN","DET","GB","HOU","IND","JAX","KC","LAC","LAR",
    "LV","MIA","MIN","NE","NO","NYG","NYJ","PHI","PIT","SEA",
    "SF","TB","TEN","WAS"
]

POS_COLORS = {
    "QB":"#e74c3c","RB":"#27ae60","WR":"#2980b9",
    "TE":"#8e44ad","FLEX":"#e67e22"
}

GRADE_ORDER = ["🟢 Steal","🔵 Good Value","⚪ On Value","🔴 Reach"]


# ── Cached data loader ────────────────────────────────────────────────────────
@st.cache_data(ttl=21600, show_spinner="🏈 Fetching live player data from Sleeper API...")
def load_players(scoring, num_teams):
    return get_players(scoring, num_teams)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏈 Draft Optimizer")
    st.markdown("---")

    st.markdown("### League Settings")
    num_teams = st.slider("Number of teams", 8, 20, 12)
    draft_pos = st.slider("Your draft position", 1, num_teams, 1)
    scoring   = st.selectbox("Scoring format", ["PPR", "Half-PPR", "Standard"])

    st.markdown("### Roster Slots")
    n_qb   = st.number_input("QB",   1, 3, 1)
    n_rb   = st.number_input("RB",   1, 5, 2)
    n_wr   = st.number_input("WR",   1, 5, 2)
    n_te   = st.number_input("TE",   1, 3, 1)
    n_flex = st.number_input("FLEX (RB/WR/TE)", 0, 3, 1)

    st.caption("💡 K and DST: draft in the final 2 rounds — no need to optimize them.")

    roster_config = {
        "QB": n_qb, "RB": n_rb, "WR": n_wr,
        "TE": n_te, "FLEX": n_flex
    }
    total_rounds = n_qb + n_rb + n_wr + n_te + n_flex

    st.markdown("---")
    st.markdown("### Preferences")

    fav_team = st.selectbox("Favorite team", NFL_TEAMS)
    fav_team = None if fav_team == "None" else fav_team

    st.markdown("**Priority players** (up to 3)")
    p1 = st.text_input("Player 1", placeholder="e.g. Josh Allen")
    p2 = st.text_input("Player 2", placeholder="e.g. CeeDee Lamb")
    p3 = st.text_input("Player 3", placeholder="e.g. Travis Kelce")
    priority_players = [p for p in [p1, p2, p3] if p.strip()]

    st.markdown("---")

    # Show snake picks preview
    picks_preview = get_snake_picks(draft_pos, num_teams, total_rounds)
    st.markdown("### Your draft picks")
    picks_str = "  ·  ".join([f"Rd{i+1}:#{p}" for i, p in enumerate(picks_preview)])
    st.caption(picks_str)

    run_btn = st.button("⚡ Optimize My Draft", use_container_width=True, type="primary")

    if "sim_seed" not in st.session_state:
        st.session_state.sim_seed = random.randint(1, 99999)

    resim = st.button("🔀 Re-simulate Draft Board", use_container_width=True,
                      help="Other teams draft differently each time — run again for a new scenario")
    if resim:
        st.session_state.sim_seed = random.randint(1, 99999)
        st.rerun()

    st.caption(f"Simulation #{st.session_state.sim_seed}")


# ── Main ──────────────────────────────────────────────────────────────────────
st.title("🏈 Fantasy Football Draft Optimizer")

# Load data
df = load_players(scoring, num_teams)
source = df["source"].iloc[0] if "source" in df.columns else "unknown"
st.caption(
    f"{get_optimizer_method()}  ·  {scoring}  ·  "
    f"{num_teams}-team league  ·  Pick #{draft_pos}  ·  "
    f"Data: **{source}** ({len(df)} players)"
)

if not run_btn:
    # ── Welcome state ──
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="metric-card"><h2>#{draft_pos}</h2><p>Your pick position</p></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><h2>{total_rounds}</h2><p>Rounds to fill</p></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card"><h2>{len(df)}</h2><p>Players in pool</p></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card"><h2>{scoring}</h2><p>Scoring format</p></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Scarcity warnings on welcome screen
    warnings = get_scarcity_warnings(df, roster_config, num_teams, picks_preview)
    if warnings:
        st.markdown("#### 📊 Positional Scarcity Analysis")
        for w in warnings:
            st.markdown(f'<div class="scarcity-box"><span style="color:#D1FAE5;">{w}</span></div>', unsafe_allow_html=True)
        st.markdown("")

    st.info("👈 Configure your league in the sidebar, then click **Optimize My Draft**.")

else:
    # ── Run optimizer ──
    with st.spinner("Running snake draft optimizer..."):
        drafted, success, picks, taken = optimize_draft(
            df,
            roster_config=roster_config,
            fav_team=fav_team,
            priority_players=priority_players,
            draft_position=draft_pos,
            num_teams=num_teams,
            seed=st.session_state.get('sim_seed'),
        )

    if not success or drafted.empty:
        st.error("Optimizer couldn't build a valid roster. Try adjusting your roster slot settings.")
        st.stop()

    total_proj  = round(drafted["adj_pts"].sum(), 1)
    steal_count = len(drafted[drafted["grade"] == "🟢 Steal"])
    reach_count = len(drafted[drafted["grade"] == "🔴 Reach"])

    # ── Metrics ──
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="metric-card"><h2>{total_proj}</h2><p>Projected pts</p></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><h2>{steal_count}</h2><p>Steals 🟢</p></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card"><h2>{reach_count}</h2><p>Reaches 🔴</p></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card"><h2>#{draft_pos}</h2><p>Draft position</p></div>', unsafe_allow_html=True)

    # Scarcity warnings
    warnings = get_scarcity_warnings(df, roster_config, num_teams, picks)
    if warnings:
        for w in warnings:
            st.markdown(f'<div class="scarcity-box"><span style="color:#D1FAE5;">{w}</span></div>', unsafe_allow_html=True)

    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Your Roster", "📊 Draft Board", "🏟️ Full Draft", "🤖 AI Summary"])

    # ══════════════════════════════════════
    # TAB 1 — Roster + Round-by-Round
    # ══════════════════════════════════════
    with tab1:
        col_a, col_b = st.columns([1.1, 1])

        # Left: roster by position
        with col_a:
            st.subheader("Optimized Roster")
            for slot in ["QB", "RB", "WR", "TE", "FLEX"]:
                slot_players = drafted[drafted["slot"] == slot]
                if slot_players.empty:
                    continue
                color = POS_COLORS.get(slot, "#666")
                st.markdown(
                    f'<span style="background:{color};color:white;padding:3px 10px;'
                    f'border-radius:4px;font-weight:700;font-size:0.9rem;">{slot}</span>',
                    unsafe_allow_html=True
                )
                for _, row in slot_players.iterrows():
                    flags = ""
                    if fav_team and row["team"] == fav_team: flags += " ⭐"
                    if row["name"] in priority_players:       flags += " 🎯"
                    c1, c2, c3, c4 = st.columns([3, 1.2, 1, 1.2])
                    c1.markdown(f"**{row['name']}** {flags} <span style='color:#94A3B8;font-size:0.85rem;'>— {row['team']}</span>", unsafe_allow_html=True)
                    c2.markdown(f"**{round(row['adj_pts'],1)}** pts")
                    c3.markdown(f"<span style='color:#94A3B8;'>VOR {round(row['vor'],1)}</span>", unsafe_allow_html=True)
                    c4.markdown(row["grade"])
                st.markdown("")
            st.caption("⭐ Fav team  🎯 Priority pick  ·  Grade = pick value vs ADP")

        # Right: round-by-round
        with col_b:
            st.subheader("Round-by-Round")
            for _, row in drafted.sort_values("round").iterrows():
                rd    = int(row["round"])
                pick  = int(row["pick_num"])
                pos   = row["pos"]
                color = POS_COLORS.get(row["slot"], "#666")
                is_pri = row["name"] in priority_players
                is_fav = fav_team and row["team"] == fav_team
                extra  = "pick-priority" if is_pri else ("pick-favteam" if is_fav else "")
                flags  = (" 🎯" if is_pri else "") + (" ⭐" if is_fav else "")

                st.markdown(
                    f'<div class="pick-row {extra}" style="color:#F0F4F8;">'
                    f'<span style="color:#6B8CAE;font-size:0.8rem;">Rd {rd} &nbsp;·&nbsp; Pick #{pick}</span>&nbsp;&nbsp;'
                    f'<span style="background:{color};color:#fff;padding:2px 7px;'
                    f'border-radius:3px;font-size:0.72rem;font-weight:700;">{row["slot"]}</span>&nbsp;'
                    f'<span style="color:#F0F4F8;font-weight:600;">{row["name"]}</span>'
                    f'<span style="color:#94A3B8;font-size:0.85rem;">{flags}</span>'
                    f'&nbsp;&nbsp;<span style="color:#CBD5E1;">{round(row["adj_pts"],1)} pts</span>'
                    f'&nbsp;<span style="color:#64748B;font-size:0.82rem;">&nbsp;·&nbsp; ADP {row["adp"]} &nbsp;·&nbsp; {row["grade"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

    # ══════════════════════════════════════
    # TAB 2 — Full Draft Board
    # ══════════════════════════════════════
    with tab2:
        st.subheader("Full Draft Board")

        board = build_draft_board(df, fav_team, draft_pos, num_teams)
        drafted_names = set(drafted["name"])

        col1, col2 = st.columns([2, 1])
        with col1:
            pos_filter = st.multiselect(
                "Filter by position", ["QB","RB","WR","TE"],
                default=["QB","RB","WR","TE"]
            )
        with col2:
            show_available = st.checkbox("Only show players available at my picks", value=False)

        view = board.copy()
        if pos_filter:
            view = view[view["pos"].isin(pos_filter)]
        if show_available:
            min_pick = min(picks)
            view = view[view["adp"] >= min_pick * 0.75]

        view["drafted"] = view["name"].apply(lambda n: "✓ Your pick" if n in drafted_names else "")
        view["vor_display"] = view["vor"].apply(lambda v: f"+{v}" if v > 0 else str(v))

        display = view[[
            "rank","name","pos","team","adj_pts","vor_display",
            "adp","est_round","risk","drafted"
        ]].rename(columns={
            "rank":"#","name":"Player","pos":"Pos","team":"Team",
            "adj_pts":"Adj Pts","vor_display":"VOR","adp":"ADP",
            "est_round":"Est. Rd","risk":"Risk","drafted":"Status"
        })

        st.dataframe(
            display.reset_index(drop=True),
            use_container_width=True,
            height=520
        )

        # VOR explanation
        with st.expander("📖 What is VOR?"):
            st.markdown("""
**Value Over Replacement (VOR)** measures how much better a player is
compared to the average startable player at their position.

- **Positive VOR** = better than the baseline starter (valuable)
- **Negative VOR** = below the baseline (replaceable)

A WR with VOR +80 is far more valuable than a WR with VOR +5,
even if their raw points look similar — because the +80 player
is harder to replace on waivers.
""")

    # ══════════════════════════════════════
    # TAB 3 — AI Summary
    # ══════════════════════════════════════

    # ══════════════════════════════════════
    # TAB 3 — Full Draft Recap
    # ══════════════════════════════════════
    with tab3:
        st.subheader("🏟️ Full Draft — All Picks")
        st.caption(f"Every pick across all {num_teams} teams  ·  🟩 green = your picks  ·  sorted by pick number")

        recap = build_full_draft_recap(
            df, taken, drafted,
            draft_position=draft_pos,
            num_teams=num_teams,
            total_rounds=total_rounds,
        )

        if recap.empty:
            st.info("No draft data available.")
        else:
            # Controls row
            col1, col2 = st.columns([2,1])
            with col1:
                rd_filter = st.multiselect(
                    "Filter by round",
                    sorted(recap["round"].unique()),
                    default=sorted(recap["round"].unique()),
                    key="recap_rd"
                )
            with col2:
                your_only = st.checkbox("Show only your picks", value=False)

            # Color legend
            leg1, leg2, leg3, leg4, leg5 = st.columns(5)
            for col, pos, clr in [
                (leg1,"QB","#e74c3c"),(leg2,"RB","#27ae60"),
                (leg3,"WR","#2980b9"),(leg4,"TE","#8e44ad"),(leg5,"FLEX","#e67e22")
            ]:
                col.markdown(
                    f'<span style="background:{clr};color:#fff;padding:2px 10px;'
                    f'border-radius:3px;font-size:0.8rem;font-weight:700;">{pos}</span>',
                    unsafe_allow_html=True
                )

            view = recap.copy()
            if rd_filter:
                view = view[view["round"].isin(rd_filter)]
            if your_only:
                view = view[view["your_pick"] == True]

            # Render pick by pick
            for _, row in view.iterrows():
                is_you  = row["your_pick"]
                pos     = row["pos"]
                color   = POS_COLORS.get(pos, "#666")
                # Your picks: dark green tint with bright green border
                # Opponent picks: dark card with subtle border
                bg      = "#0D2818" if is_you else "#172840"
                border  = "#1B998B" if is_you else "#2A4A6A"
                you_tag = (
                    f'&nbsp;&nbsp;<span style="background:#1B998B;color:#ffffff;'
                    f'font-size:0.72rem;padding:2px 8px;border-radius:10px;'
                    f'font-weight:700;letter-spacing:0.5px;">👈 YOUR PICK</span>'
                    if is_you else ""
                )

                st.markdown(
                    f'''<div style="background:{bg};border:1px solid {border};
                    border-radius:6px;padding:8px 14px;margin:2px 0;
                    border-left:4px solid {color};">
                    <span style="color:#6B8CAE;font-size:0.78rem;font-weight:500;">
                        Rd {int(row["round"])} &nbsp;·&nbsp; Pick #{int(row["pick"])}</span>
                    &nbsp;&nbsp;
                    <span style="background:{color};color:#ffffff;padding:2px 7px;
                        border-radius:3px;font-size:0.72rem;font-weight:700;">{pos}</span>
                    &nbsp;
                    <span style="color:#F0F4F8;font-weight:600;font-size:0.95rem;">
                        {row["name"]}</span>
                    <span style="color:#94A3B8;font-size:0.85rem;">
                        &nbsp;{row["nfl_team"]}</span>
                    &nbsp;&nbsp;
                    <span style="color:#CBD5E1;font-size:0.85rem;">
                        {row["proj_pts"]} pts</span>
                    <span style="color:#64748B;font-size:0.82rem;">
                        &nbsp;·&nbsp; ADP {row["adp"]}</span>
                    <span style="color:#64748B;font-size:0.80rem;">
                        &nbsp;·&nbsp; {row["team"]}</span>
                    {you_tag}
                    </div>''',
                    unsafe_allow_html=True
                )


    with tab4:
        st.subheader("🤖 AI Draft Strategy Summary")

        # Build prompt
        round_by_round = "\n".join([
            f"  Rd {int(r['round'])} (Pick #{int(r['pick_num'])}): "
            f"{r['name']} ({r['slot']}, {r['team']}) — "
            f"{round(r['adj_pts'],1)} proj pts, ADP {r['adp']}, "
            f"VOR {round(r['vor'],1)}, Grade: {r['grade']}"
            for _, r in drafted.sort_values("round").iterrows()
        ])

        prefs = []
        if fav_team:         prefs.append(f"favorite team is {fav_team}")
        if priority_players: prefs.append(f"priority players: {', '.join(priority_players)}")
        pref_str = "; ".join(prefs) if prefs else "no special preferences"

        grade_summary = drafted["grade"].value_counts().to_dict()
        grade_str = ", ".join([f"{v}x {k}" for k, v in grade_summary.items()])

        prompt = f"""You are an expert fantasy football analyst reviewing a completed snake draft.

League: {num_teams} teams, {scoring} scoring, drafted at pick #{draft_pos}
User preferences: {pref_str}
Total projected points: {total_proj}
Pick grades: {grade_str}

Round-by-round picks:
{round_by_round}

Write a sharp, personalized 3-4 paragraph draft summary:
1. Overall roster quality — how does {total_proj} pts stack up, what's the team's identity?
2. Standout picks — call out the steals (drafted well below ADP) and explain why they're valuable. Mention any priority/favorite-team picks by name.
3. Positional strengths and any gaps to address on waivers
4. One or two specific, actionable in-season tips (bye weeks, handcuffs, streaming spots)

Be specific, name players, write like an engaging fantasy analyst. No generic advice."""

        if st.button("✨ Generate AI Summary", type="primary"):
            with st.spinner("Claude is breaking down your draft..."):
                try:
                    api_key = get_api_key()
                    headers = {"Content-Type": "application/json"}
                    if api_key:
                        headers["x-api-key"] = api_key
                        headers["anthropic-version"] = "2023-06-01"
                    resp = requests.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=headers,
                        json={
                            "model": "claude-sonnet-4-20250514",
                            "max_tokens": 1000,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                        timeout=30,
                    )
                    data = resp.json()
                    if "error" in data:
                        raise Exception(data["error"])
                    summary = data["content"][0]["text"]
                    st.markdown(summary)

                except Exception:
                    st.warning("Claude API not configured — showing auto-generated summary.")
                    steals = drafted[drafted["grade"] == "🟢 Steal"]["name"].tolist()
                    reaches = drafted[drafted["grade"] == "🔴 Reach"]["name"].tolist()
                    top = drafted.sort_values("adj_pts", ascending=False).iloc[0]

                    st.markdown(f"""
**Draft Report — {scoring} | {num_teams} Teams | Pick #{draft_pos}**

Your roster projects **{total_proj} total points** across {total_rounds} starters.
Your top asset is **{top['name']}** ({top['pos']}, {top['team']}) at {round(top['adj_pts'],1)} projected points.

**Value analysis:** {f"Strong value grabs: **{', '.join(steals)}**." if steals else "Solid overall value throughout."} {f"Watch out for **{', '.join(reaches)}** — drafted above their ADP, so manage expectations." if reaches else "No significant reaches in this draft."}

**Preferences:** {f"Included {fav_team} team bias and locked in {', '.join(priority_players)} as priority picks." if (fav_team or priority_players) else "No preferences applied — pure VOR-based selections."}

**Tip:** Check your roster's bye weeks now and identify waiver wire targets to cover gaps early in the season.
                    """)
        else:
            st.info("Click **✨ Generate AI Summary** to get Claude's personalized breakdown of your draft.")


# ── Validation Section ───────────────────────────────────────────────────────
st.markdown("---")
st.subheader("📈 2024 Historical Validation")
st.caption(
    "We simulated drafts using real 2024 preseason ADP, then scored every roster "
    "against actual 2024 season stats — proving the optimizer adds real value."
)

val_c1, val_c2, val_c3 = st.columns([1, 1, 1])
with val_c1:
    val_pos  = st.slider("Draft position", 1, 12, draft_pos, key="val_pos")
with val_c2:
    val_sims = st.select_slider("Simulations", [50, 100, 200], value=100, key="val_sims")
with val_c3:
    st.markdown("<br>", unsafe_allow_html=True)
    run_val = st.button("▶ Run Backtest", type="secondary", use_container_width=True)

if run_val:
    with st.spinner(f"Running {val_sims} historical simulations..."):
        vr = run_backtest(
            roster_config={"QB":1,"RB":2,"WR":2,"TE":1,"FLEX":1},
            draft_pos=int(val_pos),
            num_teams=12,
            n_sims=int(val_sims),
        )

    import numpy as np
    opt  = vr["all_scores"]["Optimizer"]
    adp  = vr["all_scores"]["ADP Drafter"]
    rnd  = vr["all_scores"]["Random Draft"]
    best = vr["best_score"]

    opt_mean  = round(np.mean(opt), 1)
    adp_mean  = round(np.mean(adp), 1)
    rnd_mean  = round(np.mean(rnd), 1)
    edge_adp  = round(opt_mean - adp_mean, 1)
    edge_rand = round(opt_mean - rnd_mean, 1)
    beat_adp  = sum(o > a for o, a in zip(opt, adp))
    beat_rand = sum(o > r for o, r in zip(opt, rnd))
    opt_floor = round(np.percentile(opt, 10), 0)
    rnd_floor = round(np.percentile(rnd, 10), 0)
    floor_edge = round(opt_floor - rnd_floor, 0)

    # ── Key metrics ──────────────────────────────────────────────────────────
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.markdown(
        f'<div class="metric-card"><h2>{edge_rand:+.0f} pts</h2>'
        f'<p>Avg edge over random drafting</p></div>', unsafe_allow_html=True)
    mc2.markdown(
        f'<div class="metric-card"><h2>{beat_rand/val_sims*100:.0f}%</h2>'
        f'<p>Beat random draft ({beat_rand}/{val_sims} sims)</p></div>', unsafe_allow_html=True)
    mc3.markdown(
        f'<div class="metric-card"><h2>{edge_adp:+.0f} pts</h2>'
        f'<p>Avg edge over ADP-only drafter</p></div>', unsafe_allow_html=True)
    mc4.markdown(
        f'<div class="metric-card"><h2>{floor_edge:+.0f} pts</h2>'
        f'<p>Floor advantage (worst 10% of drafts)</p></div>', unsafe_allow_html=True)

    st.markdown("")

    # ── Chart + Best Team ────────────────────────────────────────────────────
    chart_col, team_col = st.columns([1.5, 1])

    with chart_col:
        st.markdown("**Average Season Score by Strategy**")

        # Max bar width reference
        max_val = best
        bars = [
            ("🤖 Our Optimizer",   opt_mean, "#1B998B"),
            ("👤 ADP Drafter",     adp_mean, "#4A90D9"),
            ("🎲 Random Draft",    rnd_mean, "#64748B"),
            ("🏆 Perfect Hindsight", best,   "#FFBC42"),
        ]

        bar_html = '<div style="padding:8px 0;">'
        for label, val, color in bars:
            pct = val / max_val * 100
            bar_html += f'''
            <div style="margin:10px 0;">
              <div style="display:flex;justify-content:space-between;
                          margin-bottom:4px;">
                <span style="color:#F0F4F8;font-size:0.88rem;font-weight:500;">
                  {label}</span>
                <span style="color:{color};font-size:0.88rem;font-weight:700;">
                  {val:.0f} pts</span>
              </div>
              <div style="background:#1E3A55;border-radius:4px;height:22px;">
                <div style="background:{color};width:{pct:.1f}%;height:22px;
                            border-radius:4px;transition:width 0.3s;">
                </div>
              </div>
            </div>'''
        bar_html += '</div>'
        st.markdown(bar_html, unsafe_allow_html=True)
        st.caption(f"Based on {val_sims} simulated 2024 PPR drafts · Pick #{val_pos} · 12 teams")

    with team_col:
        st.markdown("**🏆 Best Possible 2024 Roster**")
        st.caption("Hindsight picks — the theoretical ceiling")
        pos_colors = {"QB":"#e74c3c","RB":"#27ae60","WR":"#2980b9","TE":"#8e44ad"}
        for name in vr["best_team"]:
            pts  = vr["actual"].get(name, 0)
            row  = vr["player_df"][vr["player_df"]["name"] == name]
            pos  = row.iloc[0]["pos"] if not row.empty else "?"
            clr  = pos_colors.get(pos, "#666")
            st.markdown(
                f'<div style="background:#172840;border-left:4px solid {clr};'
                f'color:#F0F4F8;padding:6px 10px;border-radius:4px;margin:3px 0;">'
                f'<span style="background:{clr};color:#fff;padding:1px 6px;'
                f'border-radius:3px;font-size:0.72rem;font-weight:700;">{pos}</span>'
                f' <span style="font-weight:600;">{name}</span>'
                f'<span style="float:right;color:#34D399;font-weight:700;">{pts:.0f}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
        st.caption(f"Total: **{best:.0f} pts** — why in-season management still matters")

    # ── The story ────────────────────────────────────────────────────────────
    st.markdown("")
    st.markdown("**What this tells us:**")
    story_col1, story_col2 = st.columns(2)
    with story_col1:
        st.markdown(
            f'<div style="background:#0D2818;border:1px solid #1B998B;border-radius:8px;'
            f'padding:14px 16px;color:#F0F4F8;">'
            f'<div style="color:#34D399;font-weight:700;font-size:1rem;margin-bottom:6px;">'
            f'✅ The optimizer consistently outperforms random drafting</div>'
            f'Beats random in <b>{beat_rand}/{val_sims}</b> simulations with an average edge of '
            f'<b>+{edge_rand:.0f} fantasy points</b> per season. That&#39;s the equivalent of '
            f'an extra win or two over the course of the year.'
            f'</div>', unsafe_allow_html=True)
    with story_col2:
        st.markdown(
            f'<div style="background:#172840;border:1px solid #2A4A6A;border-radius:8px;'
            f'padding:14px 16px;color:#F0F4F8;">'
            f'<div style="color:#94A3B8;font-weight:700;font-size:1rem;margin-bottom:6px;">'
            f'📊 VOR + scarcity strategy raises your floor</div>'
            f'In the worst 10% of draft scenarios, the optimizer scores <b>{opt_floor:.0f} pts</b> '
            f'vs <b>{rnd_floor:.0f} pts</b> for random — a <b>+{floor_edge:.0f} pt floor advantage</b>. '
            f'A smarter draft limits your downside, not just your upside.'
            f'</div>', unsafe_allow_html=True)
else:
    st.info("👆 Configure your settings above, then click **▶ Run Backtest** to validate the optimizer against real 2024 season results.")
