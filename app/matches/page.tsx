import Link from "next/link";
import { ProbBars } from "../components/prob-bars";
import { readMatches, readMeta } from "../lib/data";

export const metadata = { title: "Slate · Soccer Bet Scout" };

export default function SlatePage() {
  const matches = readMatches();
  const meta = readMeta();
  const groups = new Map<string, typeof matches>();
  for (const match of matches) {
    const label = (match.kickoff_ct || match.date).replace(/, \d{1,2}:\d{2}.*$/, "");
    const bucket = groups.get(label) ?? [];
    bucket.push(match);
    groups.set(label, bucket);
  }

  return (
    <main>
      <section className="hero">
        <h1>Upcoming slate</h1>
        <p>
          The next {meta?.upcoming ?? matches.length} matches in the window, with Chicago kickoff times.
          Open a match for the score grid, totals, and the written breakdown.
        </p>
      </section>
      {matches.length === 0 ? (
        <p className="empty">No upcoming matches in the artifacts. Run python -m src.cli build.</p>
      ) : (
        <div className="slate">
          {[...groups.entries()].map(([day, items]) => (
            <section key={day}>
              <h2 className="day-label">{day}</h2>
              {items.map((match) => (
                <Link key={match.id} href={`/matches/${match.id}`} className="match-card">
                  <div>
                    <div className="kicker">{match.competition}</div>
                    <div className="clubs">
                      {match.home_name}
                      <span style={{ color: "var(--muted)" }}> vs </span>
                      {match.away_name}
                    </div>
                    <div className="sub">
                      {match.kickoff_ct || match.date}
                      {" · "}xG {match.prediction.xg_home.toFixed(2)}–{match.prediction.xg_away.toFixed(2)}
                      {" · "}O2.5 {match.prediction.over["2.5"]?.toFixed(0)}%
                      {" · "}BTTS {match.prediction.btts_pct.toFixed(0)}%
                    </div>
                  </div>
                  <ProbBars
                    home={match.prediction.home_win_pct}
                    draw={match.prediction.draw_pct}
                    away={match.prediction.away_win_pct}
                  />
                </Link>
              ))}
            </section>
          ))}
        </div>
      )}
    </main>
  );
}
