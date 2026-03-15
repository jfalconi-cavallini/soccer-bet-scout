"""
scorer.py

Soccer bet scout. Fetches upcoming soccer games, pulls real team
stats, and scores each game across 4 bet types:
  - Away Win
  - Away -1.5 (win by 2+)
  - Win + Over 2.5
  - Win + BTTS

Rate limiting: football-data.org free tier = 10 requests/minute.
We enforce 6.5s between every API call and cache team profiles
so each team is only fetched once per session.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from src.data.odds_data import get_all_upcoming_odds
from src.data.team_aliases import canonicalize
from src.data.football_stats import (
    get_standings, get_team_profile, get_h2h,
    find_team_in_standings, compute_stats_score,
    SPORT_SLUG_TO_CODE, _empty_profile, _empty_h2h,
)
from src.strategy.bet_profiler import profile_bets

# --- Config ---
MIN_BOOKS          = 5
MAX_HOURS_TO_START = 72
MIN_BET_SCORE      = 50
API_DELAY          = 6.5   # seconds between calls — stays under 10/min limit

SUPPORTED_LEAGUES = {
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",
    "soccer_germany_bundesliga", "soccer_france_ligue_one",
    "soccer_portugal_primeira_liga", "soccer_netherlands_eredivisie",
    "soccer_uefa_champs_league", "soccer_uefa_europa_league",
}


def hours_until_kickoff(commence_time):
    try:
        kickoff = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        return (kickoff - datetime.now(timezone.utc)).total_seconds() / 3600
    except Exception:
        return 999


def prefetch_all_standings(sports_needed):
    """Fetch all league standings upfront with rate limiting."""
    standings_cache = {}
    codes_needed    = set()

    for sport in sports_needed:
        code = SPORT_SLUG_TO_CODE.get(sport)
        if code:
            codes_needed.add(code)

    # Always include domestic leagues so CL/EL teams can be found
    codes_needed.update(["PL", "PD", "SA", "BL1", "FL1", "PPL", "DED"])

    print(f"  Fetching standings for {len(codes_needed)} leagues "
          f"(~{len(codes_needed) * API_DELAY:.0f}s)...")

    for code in sorted(codes_needed):
        standings = get_standings(code)
        standings_cache[code] = standings
        time.sleep(API_DELAY)

    return standings_cache


def find_standing(team_name, standings_cache, preferred_code=None):
    """Search standings cache for a team, preferred league first."""
    if preferred_code and preferred_code in standings_cache:
        entry = find_team_in_standings(team_name, standings_cache[preferred_code])
        if entry:
            return entry

    for standings in standings_cache.values():
        entry = find_team_in_standings(team_name, standings)
        if entry:
            return entry

    return None


def get_upcoming_soccer_games():
    """Pull upcoming soccer games, deduplicated, within our time window."""
    all_events = get_all_upcoming_odds()
    games      = []
    seen       = set()

    for event in all_events:
        sport = event.get("sport", "")
        if not sport.startswith("soccer_"):
            continue
        if event["num_books"] < MIN_BOOKS:
            continue

        hours = hours_until_kickoff(event["commence"])
        if hours < 0 or hours > MAX_HOURS_TO_START:
            continue

        home = event["home_team"]
        away = event["away_team"]

        if not canonicalize(home) or not canonicalize(away):
            continue

        key = f"{home}|{away}"
        if key in seen:
            continue
        seen.add(key)

        games.append((event, hours))

    return games


def fetch_all_team_profiles(games, standings_cache):
    """
    Fetch every unique team's profile exactly once.
    Returns a dict of team_id -> profile.
    """
    # Collect all unique team IDs needed
    team_ids   = {}   # team_name -> (team_id, standing_entry)
    id_to_name = {}   # team_id -> team_name

    for event, _ in games:
        if event["sport"] not in SUPPORTED_LEAGUES:
            continue

        comp_code = SPORT_SLUG_TO_CODE.get(event["sport"])

        for team_name in [event["home_team"], event["away_team"]]:
            if team_name in team_ids:
                continue
            entry = find_standing(team_name, standings_cache, comp_code)
            if entry:
                tid = entry["team_id"]
                team_ids[team_name]  = (tid, entry)
                id_to_name[tid]      = team_name

    unique_ids = list({tid for tid, _ in team_ids.values()})
    total      = len(unique_ids)
    print(f"  Fetching profiles for {total} unique teams "
          f"(~{total * API_DELAY:.0f}s)...")

    profiles = {}   # team_id -> profile dict

    for i, tid in enumerate(unique_ids, 1):
        name = id_to_name.get(tid, str(tid))
        print(f"  [{i}/{total}] {name}")
        profiles[tid] = get_team_profile(tid)
        time.sleep(API_DELAY)

    return profiles, team_ids


def fetch_all_h2h(games, team_ids, profiles):
    """
    Fetch H2H for every matched game where both teams have IDs.
    Returns a dict of "home|away" -> h2h dict.
    """
    h2h_results = {}
    needed      = []

    for event, _ in games:
        if event["sport"] not in SUPPORTED_LEAGUES:
            continue
        home = event["home_team"]
        away = event["away_team"]
        if home in team_ids and away in team_ids:
            needed.append((home, away))

    print(f"  Fetching H2H for {len(needed)} games "
          f"(~{len(needed) * API_DELAY:.0f}s)...")

    for i, (home, away) in enumerate(needed, 1):
        home_id = team_ids[home][0]
        away_id = team_ids[away][0]
        key     = f"{home}|{away}"
        print(f"  [{i}/{len(needed)}] {home} vs {away}")
        h2h_results[key] = get_h2h(home_id, away_id)
        time.sleep(API_DELAY)

    return h2h_results


def build_results(games, standings_cache, profiles, team_ids, h2h_map):
    """Assemble final result objects for each game."""
    results = []

    for event, hours in games:
        home      = event["home_team"]
        away      = event["away_team"]
        sport     = event["sport"]
        supported = sport in SUPPORTED_LEAGUES
        comp_code = SPORT_SLUG_TO_CODE.get(sport)
        key       = f"{home}|{away}"

        home_standing = team_ids[home][1] if home in team_ids else None
        away_standing = team_ids[away][1] if away in team_ids else None

        home_id = team_ids[home][0] if home in team_ids else None
        away_id = team_ids[away][0] if away in team_ids else None

        home_profile = profiles.get(home_id, _empty_profile()) if home_id else _empty_profile()
        away_profile = profiles.get(away_id, _empty_profile()) if away_id else _empty_profile()
        h2h          = h2h_map.get(key, _empty_h2h())

        standings  = standings_cache.get(comp_code, [])
        num_teams  = len(standings) if standings else 20

        stats_score = compute_stats_score(
            home_standing, away_standing,
            home_profile, away_profile,
            h2h, num_teams
        )

        bets = profile_bets(home, away, home_profile, away_profile, h2h, stats_score)

        results.append({
            "home": home, "away": away,
            "sport": sport, "kickoff": event["commence"],
            "hours": hours, "supported": supported,
            "home_profile": home_profile,
            "away_profile": away_profile,
            "h2h": h2h,
            "stats_score": stats_score,
            "bets": bets,
        })

    return results


def print_report(results):
    labels = {
        "AWAY_WIN":     "Away Win      ",
        "AWAY_MINUS15": "Away -1.5     ",
        "WIN_OVER25":   "Win + Over 2.5",
        "WIN_BTTS":     "Win + BTTS    ",
    }

    def best_score(r):
        strong = [b for b in r["bets"] if b.score >= MIN_BET_SCORE]
        return max((b.score for b in strong), default=0)

    results.sort(key=best_score, reverse=True)

    print(f"\n{'='*65}")
    print(f"  SOCCER BET SCOUT — {len(results)} GAME(S)")
    print(f"{'='*65}")

    for r in results:
        home  = r["home"]
        away  = r["away"]
        hours = r["hours"]
        hp    = r["home_profile"]
        ap    = r["away_profile"]
        h2h   = r["h2h"]
        stats = r["stats_score"]
        bets  = r["bets"]

        print(f"\n{'─'*65}")
        print(f"  {home} vs {away}")
        print(f"  {r['sport']} | {r['kickoff'][:16].replace('T',' ')} UTC | {hours:.0f}h away")
        print(f"{'─'*65}")

        if not r["supported"] or hp["games"] == 0:
            print(f"  ⚠  No stats available for this league/team")
        else:
            print(f"\n  {'STAT':<28} {'HOME':>16}  {'AWAY':>16}")
            print(f"  {'─'*62}")
            print(f"  {'Form (last 10)':<28} {hp['form_string']:>16}  {ap['form_string']:>16}")
            print(f"  {'Form score':<28} {str(hp['form_score'])+'/100':>16}  {str(ap['form_score'])+'/100':>16}")
            print(f"  {'Goals / game':<28} {str(hp['goals_pg']):>16}  {str(ap['goals_pg']):>16}")
            print(f"  {'Conceded / game':<28} {str(hp['conceded_pg']):>16}  {str(ap['conceded_pg']):>16}")
            print(f"  {'Home goals / game':<28} {str(hp['home_goals_pg']):>16}  {'—':>16}")
            print(f"  {'Away goals / game':<28} {'—':>16}  {str(ap['away_goals_pg']):>16}")
            print(f"  {'Home conceded / game':<28} {str(hp['home_conceded_pg']):>16}  {'—':>16}")
            print(f"  {'Away conceded / game':<28} {'—':>16}  {str(ap['away_conceded_pg']):>16}")
            print(f"  {'Home form score':<28} {str(hp['home_form_score'])+'/100':>16}  {'—':>16}")
            print(f"  {'Away form score':<28} {'—':>16}  {str(ap['away_form_score'])+'/100':>16}")
            print(f"  {'Clean sheet rate':<28} {str(hp['clean_sheet_rate'])+'%':>16}  {str(ap['clean_sheet_rate'])+'%':>16}")
            print(f"  {'BTTS rate':<28} {str(hp['btts_rate'])+'%':>16}  {str(ap['btts_rate'])+'%':>16}")
            print(f"\n  H2H   : {h2h['summary']}")
            print(f"  STATS : Home {stats['home_win_prob']}% | Away {stats['away_win_prob']}% | Conf {stats['confidence']}/100")

        strong_bets = [b for b in bets if b.score >= MIN_BET_SCORE]
        if strong_bets and r["supported"] and hp["games"] > 0:
            print(f"\n  BET SIGNALS")
            print(f"  {'─'*62}")
            for bet in strong_bets:
                bar   = "█" * int(bet.score // 5)
                label = labels.get(bet.bet_type, bet.bet_type)
                print(f"  [{label}]  {bet.team[-30:]:<30}  {bar} {bet.score:.0f}  conf:{bet.confidence}/100")
        else:
            print(f"\n  BET SIGNALS : none above {MIN_BET_SCORE}/100")


# --- Run ---
if __name__ == "__main__":
    print("=" * 65)
    print("  SOCCER BET SCOUT")
    print("=" * 65)

    print("\n[1] Loading upcoming soccer games...")
    games = get_upcoming_soccer_games()
    print(f"    Found {len(games)} games in next {MAX_HOURS_TO_START}h")

    if not games:
        print("    No games found.")
        exit()

    supported_games = [g for g in games if g[0]["sport"] in SUPPORTED_LEAGUES]
    print(f"    {len(supported_games)} in supported leagues (stats available)")

    print("\n[2] Fetching league standings...")
    sports_needed   = {e["sport"] for e, _ in games}
    standings_cache = prefetch_all_standings(sports_needed)

    print("\n[3] Fetching team profiles (each team fetched once)...")
    profiles, team_ids = fetch_all_team_profiles(games, standings_cache)

    print("\n[4] Fetching H2H data...")
    h2h_map = fetch_all_h2h(games, team_ids, profiles)

    print("\n[5] Building results...")
    results = build_results(games, standings_cache, profiles, team_ids, h2h_map)

    print_report(results)