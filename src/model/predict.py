"""Per-match prediction: score grid, market-style totals, and a short narrative.

The numbers describe the match. They are not betting lines.
"""

from __future__ import annotations

from datetime import date, timedelta

from src.config import DIXON_COLES_RHO, FIRST_HALF_SHARE, STALE_RESULT_DAYS, XG_BLEND
from src.model.dixon_coles import score_grid, summarize
from src.model.elo import EloMatch, EloTable
from src.model.ratings import StrengthBook, blend_chance
from src.report.timeutil import format_kickoff


def _pct(probability: float) -> float:
    return round(probability * 100.0, 1)


def _form_char(team: str, match: EloMatch) -> str:
    if match.home == team:
        if match.home_goals > match.away_goals:
            return "W"
        if match.home_goals == match.away_goals:
            return "D"
        return "L"
    if match.away_goals > match.home_goals:
        return "W"
    if match.away_goals == match.home_goals:
        return "D"
    return "L"


def _team_context(team: str, matches: list[EloMatch], as_of: date, book: StrengthBook) -> dict:
    played = [
        match
        for match in matches
        if match.day < as_of and (match.home == team or match.away == team)
    ]
    played.sort(key=lambda match: match.day)
    last = played[-8:]
    form_matches = played[-5:]
    form = "".join(_form_char(team, match) for match in form_matches) or "—"
    points = sum(3 if ch == "W" else 1 if ch == "D" else 0 for ch in form if ch in "WDL")
    games = len(form_matches)

    goals = xg_for = xg_against = 0.0
    xg_games = 0
    for match in last:
        home = match.home == team
        scored = match.home_goals if home else match.away_goals
        allowed = match.away_goals if home else match.home_goals
        goals += scored
        own_xg = match.xg_home if home else match.xg_away
        opp_xg = match.xg_away if home else match.xg_home
        if own_xg is not None:
            xg_for += own_xg
            xg_against += opp_xg or 0.0
            xg_games += 1

    goals_minus_xg = None
    xg_pg = None
    if xg_games:
        goals_in_xg_games = 0
        for match in last:
            home = match.home == team
            own_xg = match.xg_home if home else match.xg_away
            if own_xg is None:
                continue
            goals_in_xg_games += match.home_goals if home else match.away_goals
        goals_minus_xg = (goals_in_xg_games - xg_for) / xg_games
        xg_pg = xg_for / xg_games

    def window_attack(sample: list[EloMatch]) -> float | None:
        if not sample:
            return None
        total = 0.0
        count = 0
        for match in sample:
            home = match.home == team
            value, _ = blend_chance(
                match.home_goals if home else match.away_goals,
                match.xg_home if home else match.xg_away,
            )
            total += value
            count += 1
        return total / count if count else None

    recent = window_attack(played[-4:])
    prior = window_attack(played[-8:-4])
    if recent is None or prior is None:
        trend = "unknown"
    elif recent - prior >= 0.25:
        trend = "rising"
    elif prior - recent >= 0.25:
        trend = "falling"
    else:
        trend = "flat"

    rest_days = None
    short_rest = False
    europe_week = False
    last_competition = None
    last_day = None
    if played:
        previous = played[-1]
        last_day = previous.day
        rest_days = (as_of - previous.day).days
        short_rest = rest_days <= 3
        last_competition = previous.competition_id
        europe_week = previous.kind == "cup" and rest_days <= 4

    attack = 0.5 * (
        book.attack_home.get(team, 1.0) + book.attack_away.get(team, 1.0)
    )
    defense = 0.5 * (
        book.defense_home.get(team, 1.0) + book.defense_away.get(team, 1.0)
    )
    return {
        "form": form,
        "points": points,
        "games": games,
        "ppg": round(points / games, 2) if games else None,
        "goals_pg": round(goals / len(last), 2) if last else None,
        "xg_pg": round(xg_pg, 2) if xg_pg is not None else None,
        "xg_against_pg": round(xg_against / xg_games, 2) if xg_games else None,
        "goals_minus_xg": round(goals_minus_xg, 2) if goals_minus_xg is not None else None,
        "xg_trend": trend,
        "attack": round(attack, 2),
        "defense": round(defense, 2),
        "rest_days": rest_days,
        "last_day": last_day,
        "short_rest": short_rest,
        "europe_week": europe_week,
        "last_competition": last_competition,
    }


def _regression_sentence(name: str, ctx: dict) -> str:
    gap = ctx["goals_minus_xg"]
    if gap is None:
        return (
            f"{name} does not have enough xG in the recent window, "
            "so there is no goals-minus-xG regression flag."
        )
    if gap >= 0.35:
        return (
            f"{name} is scoring {gap:+.2f} goals per game above xG. "
            "That is a regression flag: the chance quality has not kept up with the scoreboard."
        )
    if gap <= -0.35:
        return (
            f"{name} is scoring {gap:+.2f} goals per game below xG. "
            "That is a positive regression flag: finishing has lagged the chances."
        )
    return f"{name} is close to xG ({gap:+.2f} per game). No regression flag."


def _trend_sentence(name: str, ctx: dict) -> str:
    trend = ctx["xg_trend"]
    form = ctx["form"]
    xg = ctx["xg_pg"]
    xg_bit = f" Recent xG is {xg:.2f} per game." if xg is not None else " Recent chance trend uses goals because xG is missing."
    if trend == "rising":
        direction = "Chance creation is rising across the last two blocks of games."
    elif trend == "falling":
        direction = "Chance creation is falling across the last two blocks of games."
    elif trend == "flat":
        direction = "Chance creation is flat across the last two blocks of games."
    else:
        direction = "There are not enough recent games to read a trend."
    return f"{name} form {form}.{xg_bit} {direction}"


def _script(home_name: str, away_name: str, summary: dict, lam_home: float, lam_away: float) -> str:
    home_p = summary["home_win"]
    away_p = summary["away_win"]
    total = lam_home + lam_away
    if abs(home_p - away_p) < 0.08:
        control = "This projects as an even game, with neither side clearly controlling it."
    elif home_p > away_p:
        control = f"{home_name} are the side more likely to control the game."
    else:
        control = f"{away_name} are the side more likely to control the game, even away from home."
    if total >= 3.0:
        tempo = "The grid expects a high-event match."
    elif total <= 2.15:
        tempo = "The grid expects a tighter, lower-scoring match."
    else:
        tempo = "The grid expects a normal tempo."
    if summary["btts"] >= 0.58:
        both = "Both teams are likelier than not to score."
    elif summary["btts"] <= 0.42:
        both = "One clean sheet is a live result."
    else:
        both = "Both teams scoring is close to a coin flip."
    return f"{control} {tempo} {both}"


def predict_match(
    home: str,
    away: str,
    home_name: str,
    away_name: str,
    day: date,
    kickoff_utc: str | None,
    competition_id: str,
    competition: str,
    kind: str,
    book: StrengthBook,
    table: EloTable,
    history: list[EloMatch],
    neutral: bool = False,
    data_through: date | None = None,
) -> dict:
    elo_home = table.rating(home)
    elo_away = table.rating(away)
    lambdas = book.lambdas(home, away, elo_home, elo_away, competition_id, kind, neutral)
    grid = score_grid(lambdas["lambda_home"], lambdas["lambda_away"], DIXON_COLES_RHO)
    summary = summarize(grid)
    home_ctx = _team_context(home, history, day, book)
    away_ctx = _team_context(away, history, day, book)

    attack_note = (
        f"{home_name} attack {home_ctx['attack']:.2f} against {away_name} defense "
        f"{away_ctx['defense']:.2f}. {away_name} attack {away_ctx['attack']:.2f} against "
        f"{home_name} defense {home_ctx['defense']:.2f}. "
        "An attack above 1.00 creates more than a typical side at that venue. "
        "A defense above 1.00 allows more than a typical side."
    )

    def rest_sentence(name: str, ctx: dict) -> str:
        if ctx["rest_days"] is None:
            return f"No prior match on file for {name}."
        bits = [f"{name} last played {ctx['rest_days']} days ago"]
        if ctx["short_rest"]:
            bits.append("which is a short rest")
        if ctx["europe_week"]:
            bits.append("and that match was in Europe, so this is a travel week")
        sentence = bits[0]
        if len(bits) == 2:
            sentence += f", {bits[1]}"
        elif len(bits) == 3:
            sentence += f", {bits[1]}, {bits[2]}"
        return sentence + "."

    def lags_the_file(ctx: dict) -> bool:
        """This club's last result is well behind the rest of the competition file."""
        last = ctx.get("last_day")
        if data_through is None or last is None:
            return False
        return (data_through - last).days > STALE_RESULT_DAYS

    def form_sentence(name: str, ctx: dict) -> str:
        last = ctx.get("last_day")
        if lags_the_file(ctx) and last is not None:
            return (
                f"{name} results on file stop on {last.isoformat()}, "
                "before the rest of this competition, so form is not shown."
            )
        return _trend_sentence(name, ctx)

    def one_rest(name: str, ctx: dict) -> str:
        last = ctx.get("last_day")
        if lags_the_file(ctx) and last is not None:
            return (
                f"Rest is not shown for {name}. Their last result on file is {last.isoformat()}, "
                "which is behind the rest of this competition."
            )
        return rest_sentence(name, ctx)

    stale = (
        data_through is not None and (day - data_through).days > STALE_RESULT_DAYS
    )
    if stale and data_through is not None:
        form_body = (
            f"Results on file for this competition stop on {data_through.isoformat()}, "
            "so form and the chance trend are not shown."
        )
        rest_body = (
            f"Rest is not shown. The file stops on {data_through.isoformat()}, "
            "so a long gap can be missing results rather than a real break."
        )
    else:
        form_body = form_sentence(home_name, home_ctx) + " " + form_sentence(away_name, away_ctx)
        rest_body = one_rest(home_name, home_ctx) + " " + one_rest(away_name, away_ctx)

    sections = [
        {
            "title": "Form and chance trend",
            "body": form_body,
        },
        {
            "title": "Goals minus xG",
            "body": _regression_sentence(home_name, home_ctx) + " " + _regression_sentence(away_name, away_ctx),
        },
        {"title": "Attack against defense", "body": attack_note},
        {
            "title": "Rest and travel",
            "body": rest_body,
        },
        {
            "title": "Game script",
            "body": _script(home_name, away_name, summary, lambdas["lambda_home"], lambdas["lambda_away"])
            + (
                f" First-half xG is about {FIRST_HALF_SHARE:.0%} of the full match: "
                f"{lambdas['lambda_home'] * FIRST_HALF_SHARE:.2f} to "
                f"{lambdas['lambda_away'] * FIRST_HALF_SHARE:.2f}."
            ),
        },
    ]

    def pack_lines(mapping: dict) -> dict:
        return {str(line): _pct(prob) for line, prob in mapping.items()}

    return {
        "home_win_pct": _pct(summary["home_win"]),
        "draw_pct": _pct(summary["draw"]),
        "away_win_pct": _pct(summary["away_win"]),
        "xg_home": round(lambdas["lambda_home"], 2),
        "xg_away": round(lambdas["lambda_away"], 2),
        "xg_home_1h": round(lambdas["lambda_home"] * FIRST_HALF_SHARE, 2),
        "xg_away_1h": round(lambdas["lambda_away"] * FIRST_HALF_SHARE, 2),
        "btts_pct": _pct(summary["btts"]),
        "clean_sheet_home_pct": _pct(summary["clean_sheet_home"]),
        "clean_sheet_away_pct": _pct(summary["clean_sheet_away"]),
        "over": pack_lines(summary["over"]),
        "under": pack_lines(summary["under"]),
        "home_totals": pack_lines(summary["home_over"]),
        "away_totals": pack_lines(summary["away_over"]),
        "top_scorelines": [
            {"score": item["score"], "pct": _pct(item["prob"])} for item in summary["top_scorelines"]
        ],
        "elo_home": round(elo_home, 1),
        "elo_away": round(elo_away, 1),
        "elo_gap": round(lambdas["elo_gap"], 1),
        "home_context": home_ctx,
        "away_context": away_ctx,
        "narrative": sections,
        "model": {
            "rho": DIXON_COLES_RHO,
            "xg_blend": XG_BLEND,
            "first_half_share": FIRST_HALF_SHARE,
            "lambda_home_before_elo": round(lambdas["lambda_home_raw"], 3),
            "lambda_away_before_elo": round(lambdas["lambda_away_raw"], 3),
            "home_attack": round(lambdas["home_attack"], 3),
            "away_attack": round(lambdas["away_attack"], 3),
            "home_defense": round(lambdas["home_defense"], 3),
            "away_defense": round(lambdas["away_defense"], 3),
        },
        "kickoff_ct": format_kickoff(kickoff_utc) if kickoff_utc else None,
        "competition": competition,
        "competition_id": competition_id,
    }


def upcoming_window(matches: list, today: date, days: int) -> list:
    end = today + timedelta(days=days)
    return [match for match in matches if today <= match.day <= end and match.home_goals is None]
