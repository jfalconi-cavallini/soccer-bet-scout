"""Soccer Bet Scout command line.

    python -m src.cli build
    python -m src.cli rankings [--league E0] [--tournament UCL]
    python -m src.cli slate
    python -m src.cli match "Arsenal" "Everton"
    python -m src.cli team "Arsenal"
    python -m src.cli backtest
"""

from __future__ import annotations

import argparse
import json

from dotenv import load_dotenv

from src.names import canonicalize, slugify
from src.model.backtest import report_from_catalog
from src.pipeline.build import ARTIFACTS, _write, build
from src.report.cards import render_match, render_rankings

def _read(name: str) -> dict:
    path = ARTIFACTS / name
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run: python -m src.cli build")
    return json.loads(path.read_text(encoding="utf-8"))


def _cmd_build(_args: argparse.Namespace) -> None:
    meta = build()
    clubelo = meta.get("clubelo") or {}
    print("\nTop of the Europe pool:")
    rankings = _read("rankings.json")["teams"][:12]
    print(render_rankings(rankings, "Europe club Elo"))
    if clubelo.get("available"):
        print(f"ClubElo rank correlation (Spearman): {clubelo.get('spearman')}")
        for row in (clubelo.get("top") or [])[:8]:
            print(f"  {row['club']:<22} clubelo {row['clubelo']:>7}   ours {row['ours']:>7}")
    else:
        print(f"ClubElo comparison: {clubelo.get('reason')}")
    matches = _read("matches.json")["matches"]
    if matches:
        print("\nNext match:")
        print(render_match(matches[0]))


def _cmd_rankings(args: argparse.Namespace) -> None:
    teams = _read("rankings.json")["teams"]
    title = "All Europe"
    if args.league:
        teams = [team for team in teams if team.get("league_id") == args.league]
        title = args.league
    if args.tournament:
        teams = [team for team in teams if args.tournament in (team.get("tournaments") or [])]
        title = args.tournament
    for index, team in enumerate(teams, start=1):
        team["rank"] = index
    print(render_rankings(teams[: args.limit], title))


def _cmd_slate(_args: argparse.Namespace) -> None:
    matches = _read("matches.json")["matches"]
    if not matches:
        print("No upcoming matches in the artifact window.")
        return
    print(f"\n  Upcoming matches ({len(matches)})  ·  times in America/Chicago\n")
    for match in matches:
        pred = match["prediction"]
        print(
            f"  {match.get('kickoff_ct') or match['date']}"
            f"  {match['competition']:<22}  {match['home_name']} vs {match['away_name']}"
        )
        print(
            f"    {pred['home_win_pct']:.0f}% / {pred['draw_pct']:.0f}% / {pred['away_win_pct']:.0f}%"
            f"   xG {pred['xg_home']:.2f}-{pred['xg_away']:.2f}"
            f"   O2.5 {pred['over'].get('2.5', 0):.0f}%   BTTS {pred['btts_pct']:.0f}%"
        )


def _find_team(token: str, teams: list[dict]) -> dict | None:
    key = canonicalize(token)
    slug = slugify(key) if key else None
    for team in teams:
        if team["id"] == slug or team["name"].lower() == token.lower():
            return team
    if key:
        for team in teams:
            if key in team["name"].lower() or key in team["id"]:
                return team
    return None


def _cmd_match(args: argparse.Namespace) -> None:
    payload = _read("matches.json")
    teams = _read("rankings.json")["teams"]
    home = _find_team(args.home, teams)
    away = _find_team(args.away, teams)
    if not home or not away:
        raise SystemExit("Could not find both clubs in the current rankings. Check the spelling.")
    for match in payload["matches"]:
        pair = {match["home_id"], match["away_id"]}
        if pair == {home["id"], away["id"]}:
            print(render_match(match))
            return
    raise SystemExit("That pairing is not in the upcoming slate. Rebuild, or check the date window.")


def _cmd_clubelo(_args: argparse.Namespace) -> None:
    """Rank-correlation check. Target is above 0.9 once clubelo.com answers."""
    from datetime import date

    from src.data.cache import HttpCache
    from src.data.clubelo_compare import compare

    rankings = _read("rankings.json")
    # Slugs are the canonical name with spaces turned into hyphens.
    ratings = {team["id"].replace("-", " "): team["rating"] for team in rankings["teams"]}
    report = compare(HttpCache(), ratings, date.today())
    print(json.dumps(report, indent=2))
    spearman = report.get("spearman")
    if report.get("available") and spearman is not None:
        print(f"Spearman {spearman}. Target is above 0.9.")
    else:
        print(f"ClubElo unavailable: {report.get('reason')}. Target when it returns is above 0.9.")


def _fmt(value) -> str:
    if value is None:
        return "  —  "
    return f"{value:6.3f}"


def _cmd_backtest(_args: argparse.Namespace) -> None:
    from datetime import date

    from src.data.catalog import load_catalog

    today = date.today()
    catalog, _cache = load_catalog(today)
    report = report_from_catalog(catalog, today)
    _write(ARTIFACTS / "backtest.json", report)
    overall = report["overall"]
    print(f"\n  Walk-forward {report['from']} through {report['through']}")
    print(f"  {report['rule']}\n")
    print(f"  {'':<22}{'Brier':>8}{'Log loss':>10}{'RPS':>8}{'Top pick':>10}{'Matches':>9}")
    print(
        f"  {'Model':<22}{_fmt(overall['model_brier']):>8}{_fmt(overall['model_log_loss']):>10}"
        f"{_fmt(overall['model_rps']):>8}{_fmt(overall['model_accuracy']):>10}{overall['matches']:9d}"
    )
    print(
        f"  {'League rates':<22}{_fmt(overall['rates_brier']):>8}{_fmt(overall['rates_log_loss']):>10}"
        f"{_fmt(overall['rates_rps']):>8}{_fmt(overall['rates_accuracy']):>10}{overall['matches']:9d}"
    )
    print(
        f"  {'Model on priced games':<22}{_fmt(overall['model_on_odds_brier']):>8}"
        f"{_fmt(overall['model_on_odds_log_loss']):>10}{_fmt(overall['model_on_odds_rps']):>8}"
        f"{_fmt(overall['model_on_odds_accuracy']):>10}{overall['odds_matches']:9d}"
    )
    print(
        f"  {'Closing odds':<22}{_fmt(overall['book_brier']):>8}{_fmt(overall['book_log_loss']):>10}"
        f"{_fmt(overall['book_rps']):>8}{_fmt(overall['book_accuracy']):>10}{overall['odds_matches']:9d}"
    )
    print("\n  By league")
    for league in report["by_league"]:
        book = _fmt(league["book_brier"]) if league["odds_matches"] else "  —  "
        print(
            f"  {league['name']:<22} model {_fmt(league['model_brier'])}"
            f"   rates {_fmt(league['rates_brier'])}   book {book}"
            f"   n {league['matches']}"
        )
    if report["miscalibration"]:
        print("\n  Where the prices miss the results")
        for note in report["miscalibration"]:
            print(f"  - {note}")
    print(f"\n  Wrote {ARTIFACTS / 'backtest.json'}\n")


def _cmd_team(args: argparse.Namespace) -> None:
    teams = _read("rankings.json")["teams"]
    team = _find_team(args.name, teams)
    if not team:
        raise SystemExit("Club not found in the current rankings.")
    path = ARTIFACTS / "history" / f"{team['id']}.json"
    history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"points": []}
    print(f"\n  {team['name']}   {team['rating']:.1f}")
    print(f"  {team.get('league') or '—'}   rank {team['rank']}   played {team['played']}")
    if team.get("tournaments"):
        print(f"  Europe this campaign: {', '.join(team['tournaments'])}")
    points = history.get("points") or []
    print("\n  Recent rating history")
    for point in points[-12:]:
        extra = f" vs {point['opponent']}" if point.get("opponent") else f" ({point['event']})"
        print(f"    {point['date']}   {point['rating']:7.1f}{extra}")
    print()


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="soccer-bet-scout", description="Europe club Elo and match breakdowns")
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser("build", help="Download data and write data/artifacts")
    build_parser.set_defaults(func=_cmd_build)

    rankings = sub.add_parser("rankings", help="Print Elo rankings from the last build")
    rankings.add_argument("--league", help="League id such as E0, SP1, I1, D1, F1")
    rankings.add_argument("--tournament", choices=["UCL", "UEL", "UECL"])
    rankings.add_argument("--limit", type=int, default=40)
    rankings.set_defaults(func=_cmd_rankings)

    slate = sub.add_parser("slate", help="Upcoming matches with Chicago kickoffs")
    slate.set_defaults(func=_cmd_slate)

    match = sub.add_parser("match", help="Breakdown for an upcoming pairing")
    match.add_argument("home")
    match.add_argument("away")
    match.set_defaults(func=_cmd_match)

    team = sub.add_parser("team", help="Rating history for one club")
    team.add_argument("name")
    team.set_defaults(func=_cmd_team)

    clubelo = sub.add_parser("clubelo", help="Compare saved ratings with clubelo.com (target correlation > 0.9)")
    clubelo.set_defaults(func=_cmd_clubelo)

    backtest = sub.add_parser("backtest", help="Walk-forward scores for 2024-25 through today")
    backtest.set_defaults(func=_cmd_backtest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
