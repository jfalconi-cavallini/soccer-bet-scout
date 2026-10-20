"""Plain-text match cards. Kickoffs are printed in America/Chicago."""

from __future__ import annotations


def _bar(pct: float, width: int = 18) -> str:
    filled = max(0, min(width, round(pct / 100 * width)))
    return "█" * filled + "·" * (width - filled)


def render_match(match: dict) -> str:
    pred = match["prediction"]
    lines = [
        "",
        "─" * 72,
        f"  {match['home_name']}  vs  {match['away_name']}",
        f"  {match['competition']}  ·  {pred.get('kickoff_ct') or match.get('kickoff_ct') or match['date']}",
        "─" * 72,
        f"  Win %     {match['home_name']:<28} {pred['home_win_pct']:5.1f}%  {_bar(pred['home_win_pct'])}",
        f"  Draw      {'':<28} {pred['draw_pct']:5.1f}%  {_bar(pred['draw_pct'])}",
        f"  Win %     {match['away_name']:<28} {pred['away_win_pct']:5.1f}%  {_bar(pred['away_win_pct'])}",
        "",
        f"  xG        {pred['xg_home']:.2f}  –  {pred['xg_away']:.2f}"
        f"     1H  {pred['xg_home_1h']:.2f}  –  {pred['xg_away_1h']:.2f}",
        f"  Over 2.5  {pred['over'].get('2.5', 0):5.1f}%     BTTS  {pred['btts_pct']:5.1f}%",
        f"  Clean     {match['home_name']:<28} {pred['clean_sheet_home_pct']:5.1f}%",
        f"            {match['away_name']:<28} {pred['clean_sheet_away_pct']:5.1f}%",
        f"  Elo       {pred['elo_home']:.0f}  –  {pred['elo_away']:.0f}   gap {pred['elo_gap']:+.0f}",
        "",
        "  Top scorelines",
    ]
    for item in pred["top_scorelines"]:
        lines.append(f"    {item['score']:<6} {item['pct']:5.1f}%")
    lines.append("")
    for title, block in (("First half", pred.get("first_half")), ("Second half", pred.get("second_half"))):
        if not block:
            continue
        lines.append(f"  {title}")
        lines.append(f"    xG  {block['xg_home']:.2f}  –  {block['xg_away']:.2f}")
        lines.append(
            f"    W/D/L  {block['home_win_pct']:5.1f} / {block['draw_pct']:5.1f} / {block['away_win_pct']:5.1f}"
        )
        lines.append(
            f"    BTTS {block['btts_pct']:5.1f}%"
            f"    Over 0.5 {block['over'].get('0.5', 0):5.1f}%"
            f"    Over 1.5 {block['over'].get('1.5', 0):5.1f}%"
        )
        for item in block["top_scorelines"][:3]:
            lines.append(f"    {item['score']:<6} {item['pct']:5.1f}%")
        lines.append("")
    picks = pred.get("most_likely") or []
    if picks:
        lines.append("  Most likely")
        for item in picks:
            lines.append(f"    {item['label']:<44} {item['pct']:5.1f}%")
        lines.append("")
    lines.append(f"  Team totals over 1.5")
    lines.append(f"    {match['home_name']:<28} {pred['home_totals'].get('1.5', 0):5.1f}%")
    lines.append(f"    {match['away_name']:<28} {pred['away_totals'].get('1.5', 0):5.1f}%")
    for section in pred["narrative"]:
        lines.append("")
        lines.append(f"  {section['title']}")
        words = section["body"].split()
        buf = "  "
        for word in words:
            if len(buf) + len(word) + 1 > 64:
                lines.append(buf)
                buf = "  " + word
            else:
                buf = f"{buf} {word}" if buf.strip() else "  " + word
        if buf.strip():
            lines.append(buf)
    lines.append("")
    return "\n".join(lines)


def render_rankings(teams: list[dict], title: str) -> str:
    lines = ["", f"  {title}", f"  {'#':>3}  {'Elo':>7}  {'League':<22}  Club", "  " + "─" * 58]
    for team in teams:
        lines.append(
            f"  {team['rank']:>3}  {team['rating']:7.1f}  {team.get('league') or '—':<22}  {team['name']}"
        )
    lines.append("")
    return "\n".join(lines)
