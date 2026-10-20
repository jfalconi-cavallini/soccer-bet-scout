"""Precompute Elo, the upcoming slate, and settlement.

The web app reads these files. It does not call football-data.org or
The Odds API when someone opens a page.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src.config import (
    LEAGUES,
    SLATE_DAYS,
    TOURNAMENTS,
    season_label,
    season_start_year,
    tournament_filter_label,
)
from src.data.catalog import clubelo_report, load_catalog
from src.model.elo import replay
from src.model.halves import fit_half_shares
from src.model.predict import predict_match
from src.model.ratings import build_strengths
from src.names import clean_display_name, pretty_fallback, slugify
from src.report.timeutil import format_kickoff
from src.track.settlement import calibration, settle, upsert_prediction

ARTIFACTS = Path("data/artifacts")
LEAGUE_NAME = {league["id"]: league["name"] for league in LEAGUES}
LEAGUE_COUNTRY = {league["id"]: league["country"] for league in LEAGUES}


def _write(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _display_names(catalog) -> dict[str, str]:
    names: dict[str, str] = {}
    for match in catalog:
        for key, raw in ((match.home, match.home_name), (match.away, match.away_name)):
            cleaned = clean_display_name(raw)
            if not cleaned:
                continue
            current = names.get(key)
            if current is None or len(cleaned) > len(current):
                names[key] = cleaned
    return names


def _load_log(path: Path) -> dict:
    if not path.exists():
        return {"predictions": []}
    try:
        log = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"predictions": []}
    # Names were stored on the first write. Strip a source note if an older
    # row still has one; probabilities stay as they were logged.
    for row in log.get("predictions", []):
        for key in ("home_name", "away_name"):
            if row.get(key):
                row[key] = clean_display_name(row[key])
    return log


def build(today: date | None = None) -> dict:
    today = today or date.today()
    catalog, cache = load_catalog(today)
    names = _display_names(catalog)
    finished = [match.to_elo() for match in catalog if match.finished and match.day <= today]
    print(f"Replaying {len(finished)} matches...")
    table = replay(finished, today)
    print("Fitting attack and defense...")
    book = build_strengths(finished, today)
    half_book = fit_half_shares(finished)
    print(
        f"Half-time shares for {len(half_book.league_share)} leagues, "
        f"global {half_book.global_share:.3f}"
    )

    current_start = date(season_start_year(today), 7, 1)
    active: set[str] = set()
    league_of: dict[str, str] = {}
    for match in catalog:
        if match.day >= current_start:
            active.update((match.home, match.away))
        if match.kind == "league":
            league_of[match.home] = match.competition_id
            league_of[match.away] = match.competition_id

    def club_name(key: str) -> str:
        return names.get(key) or pretty_fallback(key)

    def in_tournament(team: str, tournament: str) -> bool:
        latest = table.tournament_season.get(tournament)
        if not latest:
            return False
        return table.team_tournament_seasons.get(team, {}).get(tournament) == latest

    rows = []
    for team, rating in table.ratings.items():
        if team not in active and table.matches_played.get(team, 0) == 0:
            continue
        # Rankings show clubs with a game since the previous July, so a
        # side that has not played yet this season still appears.
        previous_july = date(season_start_year(today) - 1, 7, 1)
        recent = any(
            point.event == "match" and point.day >= previous_july.isoformat()
            for point in table.history.get(team, [])
        )
        if team not in active and not recent:
            continue
        league_id = league_of.get(team) or table.league_by_team.get(team)
        tournaments = [code for code in TOURNAMENTS if in_tournament(team, code)]
        rows.append(
            {
                "id": slugify(team),
                "key": team,
                "name": club_name(team),
                "rating": round(rating, 1),
                "league_id": league_id,
                "league": LEAGUE_NAME.get(league_id, None),
                "country": LEAGUE_COUNTRY.get(league_id, None),
                "tournaments": tournaments,
                "played": table.matches_played.get(team, 0),
            }
        )
    rows.sort(key=lambda row: (-row["rating"], row["name"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    history_dir = ARTIFACTS / "history"
    if history_dir.exists():
        for old in history_dir.glob("*.json"):
            old.unlink()
    for row in rows:
        points = []
        for point in table.history.get(row["key"], []):
            if point.event == "seed":
                continue
            points.append(
                {
                    "date": point.day,
                    "rating": point.rating,
                    "opponent": club_name(point.opponent) if point.opponent else None,
                    "competition_id": point.competition_id,
                    "event": point.event,
                }
            )
        _write(
            history_dir / f"{row['id']}.json",
            {
                "id": row["id"],
                "name": row["name"],
                "league": row["league"],
                "rating": row["rating"],
                "points": points,
            },
        )

    data_through: dict[str, date] = {}
    for match in catalog:
        if match.finished and match.day <= today:
            current = data_through.get(match.competition_id)
            if current is None or match.day > current:
                data_through[match.competition_id] = match.day

    window_end = today + timedelta(days=SLATE_DAYS)
    slate = []
    for match in catalog:
        if match.finished or match.day < today or match.day > window_end:
            continue
        if match.home not in table.ratings or match.away not in table.ratings:
            # Still predict. Unseeded clubs sit at the initial rating.
            pass
        prediction = predict_match(
            match.home,
            match.away,
            club_name(match.home),
            club_name(match.away),
            match.day,
            match.kickoff_utc,
            match.competition_id,
            match.competition,
            match.kind,
            book,
            table,
            finished,
            match.neutral,
            data_through.get(match.competition_id),
            half_book,
        )
        through = data_through.get(match.competition_id)
        slate.append(
            {
                "id": match.id,
                "date": match.day.isoformat(),
                "kickoff_utc": match.kickoff_utc,
                "kickoff_ct": format_kickoff(match.kickoff_utc) if match.kickoff_utc else None,
                "competition": match.competition,
                "competition_id": match.competition_id,
                "data_through": through.isoformat() if through else None,
                "kind": match.kind,
                "neutral": match.neutral,
                "home_id": slugify(match.home),
                "away_id": slugify(match.away),
                "home_name": club_name(match.home),
                "away_name": club_name(match.away),
                "prediction": prediction,
            }
        )
    slate.sort(key=lambda item: item.get("kickoff_utc") or item["date"])

    log_path = ARTIFACTS / "prediction_log.json"
    log = _load_log(log_path)
    for item in slate:
        pred = item["prediction"]
        upsert_prediction(
            log,
            {
                "match_id": item["id"],
                "kickoff_utc": item["kickoff_utc"],
                "home": item["home_id"],
                "away": item["away_id"],
                "home_name": item["home_name"],
                "away_name": item["away_name"],
                "p_home": round(pred["home_win_pct"] / 100, 4),
                "p_draw": round(pred["draw_pct"] / 100, 4),
                "p_away": round(pred["away_win_pct"] / 100, 4),
                "xg_home": pred["xg_home"],
                "xg_away": pred["xg_away"],
                "markets": pred.get("markets"),
            },
        )
        # The page shows the ranked list. The full price book stays in the log.
        pred.pop("markets", None)
    results = {
        match.id: {
            "home_goals": int(match.home_goals),
            "away_goals": int(match.away_goals),
            "ht_home": match.ht_home,
            "ht_away": match.ht_away,
        }
        for match in catalog
        if match.finished
    }
    settled_now = settle(log, results)
    calib = calibration(log)
    print(f"Logged slate. Newly settled: {settled_now}. Brier: {calib['brier']}")

    comparison = clubelo_report(cache, {row["key"]: row["rating"] for row in rows}, today)
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    public_rows = [{key: value for key, value in row.items() if key != "key"} for row in rows]
    meta_season = season_label(season_start_year(today))
    meta = {
        "generated_at": generated,
        "timezone": "America/Chicago",
        "through": today.isoformat(),
        "season": meta_season,
        "matches_played": len(finished),
        "clubs": len(public_rows),
        "upcoming": len(slate),
        "xg_matches_in_strength_window": book.xg_matches,
        "tournament_seasons": table.tournament_season,
        "leagues": [
            {
                "id": league["id"],
                "name": league["name"],
                "country": league["country"],
                "data_through": data_through[league["id"]].isoformat() if league["id"] in data_through else None,
            }
            for league in LEAGUES
        ],
        "tournaments": [
            {
                "id": key,
                "name": tournament_filter_label(value, table.tournament_season.get(key), meta_season),
                "season": table.tournament_season.get(key),
            }
            for key, value in TOURNAMENTS.items()
        ],
        "clubelo": comparison,
        "calibration": calib,
    }
    _write(ARTIFACTS / "meta.json", meta)
    _write(ARTIFACTS / "rankings.json", {"generated_at": generated, "teams": public_rows})
    _write(ARTIFACTS / "matches.json", {"generated_at": generated, "matches": slate})
    _write(log_path, log)
    _write(ARTIFACTS / "calibration.json", calib)
    print(f"Wrote artifacts to {ARTIFACTS}")
    return meta
