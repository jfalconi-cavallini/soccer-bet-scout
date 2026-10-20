import Link from "next/link";
import { notFound } from "next/navigation";
import { ProbBars } from "../../components/prob-bars";
import { HalfView, LikelyPick, readMatch, readMatches } from "../../lib/data";

export function generateStaticParams() {
  return readMatches().map((match) => ({ id: match.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const match = readMatch(id);
  if (!match) return { title: "Match · Soccer Bet Scout" };
  return { title: `${match.home_name} vs ${match.away_name} · Soccer Bet Scout` };
}

function HalfPanel({ title, half, home, away }: { title: string; half: HalfView; home: string; away: string }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <div className="scoreline">
        <span>xG</span>
        <b>
          {half.xg_home.toFixed(2)} – {half.xg_away.toFixed(2)}
        </b>
      </div>
      <div className="scoreline">
        <span>
          {home} / draw / {away}
        </span>
        <b>
          {half.home_win_pct.toFixed(1)} / {half.draw_pct.toFixed(1)} / {half.away_win_pct.toFixed(1)}
        </b>
      </div>
      <div className="scoreline">
        <span>Both teams to score</span>
        <b>{half.btts_pct.toFixed(1)}%</b>
      </div>
      <div className="scoreline">
        <span>Over 0.5 / 1.5</span>
        <b>
          {half.over["0.5"]?.toFixed(1)}% / {half.over["1.5"]?.toFixed(1)}%
        </b>
      </div>
      <div className="scoreline">
        <span>Under 0.5 / 1.5</span>
        <b>
          {half.under["0.5"]?.toFixed(1)}% / {half.under["1.5"]?.toFixed(1)}%
        </b>
      </div>
      {half.top_scorelines.slice(0, 3).map((line) => (
        <div className="scoreline" key={line.score}>
          <span>{line.score}</span>
          <b>{line.pct.toFixed(1)}%</b>
        </div>
      ))}
    </section>
  );
}

function LikelyList({ picks }: { picks: LikelyPick[] }) {
  return (
    <>
      {picks.map((pick) => (
        <div className="scoreline" key={pick.key}>
          <span>{pick.label}</span>
          <b>{pick.pct.toFixed(1)}%</b>
        </div>
      ))}
    </>
  );
}

export default async function MatchPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const match = readMatch(id);
  if (!match) notFound();
  const pred = match.prediction;
  const totalXg = pred.xg_home + pred.xg_away;
  const homeShare = totalXg > 0 ? (pred.xg_home / totalXg) * 100 : 50;

  return (
    <main>
      <article className="report">
        <header className="report-head">
          <div className="kicker">
            {match.competition} · {match.kickoff_ct || match.date}
            {match.data_through ? ` · data through ${match.data_through}` : ""}
          </div>
          <h1>
            <Link href={`/teams/${match.home_id}`}>{match.home_name}</Link>
            {" vs "}
            <Link href={`/teams/${match.away_id}`}>{match.away_name}</Link>
          </h1>
          <p className="sub">Elo {pred.elo_home.toFixed(0)} – {pred.elo_away.toFixed(0)} · gap {pred.elo_gap > 0 ? "+" : ""}{pred.elo_gap.toFixed(0)}</p>
        </header>
        <div style={{ padding: "0 26px 16px" }}>
          <ProbBars home={pred.home_win_pct} draw={pred.draw_pct} away={pred.away_win_pct} />
        </div>
        <div className="stat-grid">
          <div className="stat"><span>Home win</span><b>{pred.home_win_pct.toFixed(1)}%</b></div>
          <div className="stat"><span>Draw</span><b>{pred.draw_pct.toFixed(1)}%</b></div>
          <div className="stat"><span>Away win</span><b>{pred.away_win_pct.toFixed(1)}%</b></div>
          <div className="stat"><span>Over 2.5</span><b>{pred.over["2.5"]?.toFixed(1)}%</b></div>
          <div className="stat"><span>BTTS</span><b>{pred.btts_pct.toFixed(1)}%</b></div>
          <div className="stat"><span>Under 2.5</span><b>{pred.under["2.5"]?.toFixed(1)}%</b></div>
        </div>
        <div className="xg-row">
          <div>
            <div className="kicker">{match.home_name} xG</div>
            <div className="xg-num">{pred.xg_home.toFixed(2)}</div>
            <div className="sub">1H {pred.xg_home_1h.toFixed(2)} · CS {pred.clean_sheet_home_pct.toFixed(0)}%</div>
          </div>
          <div className="xg-bar" aria-hidden="true">
            <span className="home-bar" style={{ width: `${homeShare}%` }} />
            <span className="away-bar" style={{ width: `${100 - homeShare}%` }} />
          </div>
          <div>
            <div className="kicker" style={{ textAlign: "right" }}>{match.away_name} xG</div>
            <div className="xg-num right">{pred.xg_away.toFixed(2)}</div>
            <div className="sub" style={{ textAlign: "right" }}>1H {pred.xg_away_1h.toFixed(2)} · CS {pred.clean_sheet_away_pct.toFixed(0)}%</div>
          </div>
        </div>
        <div className="body">
          {pred.most_likely && pred.most_likely.length > 0 ? (
            <section className="panel likely-panel">
              <h2>Most likely</h2>
              <p className="sub">Ranked by the model, not by a bookmaker price.</p>
              <LikelyList picks={pred.most_likely} />
            </section>
          ) : null}
          {pred.first_half && pred.second_half ? (
            <div className="cols half-cols">
              <HalfPanel title="First half" half={pred.first_half} home={match.home_name} away={match.away_name} />
              <HalfPanel title="Second half" half={pred.second_half} home={match.home_name} away={match.away_name} />
            </div>
          ) : null}
          <div className="cols">
            <section className="panel">
              <h2>Top scorelines</h2>
              {pred.top_scorelines.map((line) => (
                <div className="scoreline" key={line.score}>
                  <span>{line.score}</span>
                  <b>{line.pct.toFixed(1)}%</b>
                </div>
              ))}
            </section>
            <section className="panel">
              <h2>Totals</h2>
              {["1.5", "2.5", "3.5"].map((line) => (
                <div className="scoreline" key={line}>
                  <span>Over {line}</span>
                  <b>{pred.over[line]?.toFixed(1)}%</b>
                </div>
              ))}
              <div className="scoreline">
                <span>{match.home_name} over 1.5</span>
                <b>{pred.home_totals["1.5"]?.toFixed(1)}%</b>
              </div>
              <div className="scoreline">
                <span>{match.away_name} over 1.5</span>
                <b>{pred.away_totals["1.5"]?.toFixed(1)}%</b>
              </div>
            </section>
          </div>
          <div className="narrative">
            {pred.narrative.map((section) => (
              <article key={section.title}>
                <h3>{section.title}</h3>
                <p>{section.body}</p>
              </article>
            ))}
          </div>
        </div>
      </article>
    </main>
  );
}
