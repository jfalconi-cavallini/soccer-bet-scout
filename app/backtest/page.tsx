import { BacktestMarket, BacktestScores, readBacktest } from "../lib/data";

export const metadata = { title: "Backtest · Soccer Bet Scout" };

function num(value: number | null | undefined, digits = 3): string {
  if (value == null) return "—";
  return value.toFixed(digits);
}

function pct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function ScoreRow({ label, scores, source }: { label: string; scores: BacktestScores; source: "model" | "rates" | "book" | "model_on_odds" }) {
  const matches = source === "book" || source === "model_on_odds" ? scores.odds_matches : scores.matches;
  return (
    <tr>
      <td>{label}</td>
      <td className="rating">{num(scores[`${source}_brier`])}</td>
      <td className="rating">{num(scores[`${source}_log_loss`])}</td>
      <td className="rating">{num(scores[`${source}_rps`])}</td>
      <td className="rating">{pct(scores[`${source}_accuracy`])}</td>
      <td className="rating">{matches}</td>
    </tr>
  );
}

function MarketTable({ markets, withBins }: { markets: BacktestMarket[]; withBins: boolean }) {
  return (
    <div className="table-wrap" style={{ marginTop: 12 }}>
      <table>
        <thead>
          <tr>
            <th>Market</th>
            <th>Matches</th>
            <th>Model</th>
            <th>Actual</th>
            <th>Brier</th>
            {withBins ? <th>Bins</th> : null}
          </tr>
        </thead>
        <tbody>
          {markets.map((market) => (
            <tr key={market.market}>
              <td>{market.label}</td>
              <td className="rating">{market.count}</td>
              <td className="rating">{pct(market.predicted)}</td>
              <td className="rating">{pct(market.actual)}</td>
              <td className="rating">{num(market.brier)}</td>
              {withBins ? (
                <td>
                  {(market.bins ?? [])
                    .filter((bin) => bin.count > 0)
                    .map((bin) => (
                      <div key={`${bin.from}-${bin.to}`}>
                        {Math.round(bin.from * 100)}–{Math.round(bin.to * 100)}%: n {bin.count}, model {pct(bin.predicted)}, actual {pct(bin.actual)}
                      </div>
                    ))}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BacktestPage() {
  const report = readBacktest();
  if (!report) {
    return (
      <main>
        <section className="hero">
          <h1>Walk-forward backtest</h1>
          <p>No backtest artifact yet. Run python -m src.cli backtest.</p>
        </section>
      </main>
    );
  }
  const overall = report.overall;
  const families: { title: string; keys: string[] }[] = [
    { title: "Home, draw, away", keys: ["home", "draw", "away"] },
    { title: "Totals and both teams to score", keys: ["over_2.5", "btts"] },
    { title: "First half", keys: ["1h_home", "1h_draw", "1h_away", "1h_btts", "1h_over_0.5", "1h_over_1.5"] },
    {
      title: "Combinations and handicaps",
      keys: ["home_win_btts", "home_win_over_2.5", "btts_over_2.5", "dc_1x", "dc_1x_over_2.5", "ah_home_-1.5", "ah_home_-1"],
    },
  ];

  return (
    <main>
      <section className="hero">
        <h1>Walk-forward backtest</h1>
        <p>
          {report.seasons.join(", ")} · {report.from} through {report.through}. {report.rule} Lower Brier, log loss, and
          ranked probability score are better. The multiclass Brier of a flat one-third each way is about 0.667.
        </p>
        <div className="meta-row">
          <span className="pill">{overall.matches} matches</span>
          <span className="pill">Model Brier {num(overall.model_brier)}</span>
          <span className="pill">League rates {num(overall.rates_brier)}</span>
          <span className="pill">
            Closing odds {num(overall.book_brier)} on {overall.odds_matches}
          </span>
        </div>
      </section>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th></th>
              <th>Brier</th>
              <th>Log loss</th>
              <th>RPS</th>
              <th>Top pick</th>
              <th>Matches</th>
            </tr>
          </thead>
          <tbody>
            <ScoreRow label="Model" scores={overall} source="model" />
            <ScoreRow label="League rates" scores={overall} source="rates" />
            <ScoreRow label="Model on priced games" scores={overall} source="model_on_odds" />
            <ScoreRow label="Closing odds" scores={overall} source="book" />
          </tbody>
        </table>
      </div>

      <h2 className="day-label">By league</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>League</th>
              <th>Matches</th>
              <th>Model Brier</th>
              <th>Rates</th>
              <th>Book</th>
              <th>Top pick</th>
              <th>Rates pick</th>
            </tr>
          </thead>
          <tbody>
            {report.by_league.map((league) => (
              <tr key={league.id}>
                <td>{league.name}</td>
                <td className="rating">{league.matches}</td>
                <td className="rating">{num(league.model_brier)}</td>
                <td className="rating">{num(league.rates_brier)}</td>
                <td className="rating">{league.odds_matches ? num(league.book_brier) : "—"}</td>
                <td className="rating">{pct(league.model_accuracy)}</td>
                <td className="rating">{pct(league.rates_accuracy)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="day-label">By season</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Season</th>
              <th>Matches</th>
              <th>Model Brier</th>
              <th>Rates</th>
              <th>Book</th>
              <th>Top pick</th>
            </tr>
          </thead>
          <tbody>
            {report.by_season.map((season) => (
              <tr key={season.season}>
                <td>{season.season}</td>
                <td className="rating">{season.matches}</td>
                <td className="rating">{num(season.model_brier)}</td>
                <td className="rating">{num(season.rates_brier)}</td>
                <td className="rating">{season.odds_matches ? num(season.book_brier) : "—"}</td>
                <td className="rating">{pct(season.model_accuracy)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {report.cups && report.cups.matches > 0 ? (
        <>
          <h2 className="day-label">European cups</h2>
          <p className="sub">
            Champions League, Europa League, and Conference League, scored from the same pre-match ratings.
            Across leagues the goal difference follows the Elo gap, because attack and defense are centered inside
            each league. A mismatch is an Elo gap above 200, or a closing price above 75% on one side. Domestic
            leagues stay in the tables above.
            {report.cups.odds_matches
              ? " Closing prices are the football-data.co.uk lines on the matches that have them."
              : " These cup files do not carry a closing 1X2, so there is no bookmaker line on this slice."}
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th></th>
                  <th>Brier</th>
                  <th>Log loss</th>
                  <th>RPS</th>
                  <th>Top pick</th>
                  <th>Matches</th>
                </tr>
              </thead>
              <tbody>
                <ScoreRow label="Cups, model" scores={report.cups} source="model" />
                <ScoreRow label="Cup result rates" scores={report.cups} source="rates" />
                <ScoreRow label="Model on priced cups" scores={report.cups} source="model_on_odds" />
                <ScoreRow label="Closing odds" scores={report.cups} source="book" />
                {report.cup_mismatches ? (
                  <ScoreRow label="Mismatches, model" scores={report.cup_mismatches} source="model" />
                ) : null}
                {report.cup_mismatches ? (
                  <ScoreRow label="Mismatches, model on priced" scores={report.cup_mismatches} source="model_on_odds" />
                ) : null}
                {report.cup_mismatches ? (
                  <ScoreRow label="Mismatches, closing odds" scores={report.cup_mismatches} source="book" />
                ) : null}
              </tbody>
            </table>
          </div>
          {report.cup_competitions && report.cup_competitions.length > 0 ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Competition</th>
                    <th>Matches</th>
                    <th>Model Brier</th>
                    <th>Log loss</th>
                    <th>Top pick</th>
                    <th>Priced</th>
                    <th>Book Brier</th>
                  </tr>
                </thead>
                <tbody>
                  {report.cup_competitions.map((competition) => (
                    <tr key={competition.id}>
                      <td>{competition.name}</td>
                      <td className="rating">{competition.matches}</td>
                      <td className="rating">{num(competition.model_brier)}</td>
                      <td className="rating">{num(competition.model_log_loss)}</td>
                      <td className="rating">{pct(competition.model_accuracy)}</td>
                      <td className="rating">{competition.odds_matches}</td>
                      <td className="rating">{competition.odds_matches ? num(competition.book_brier) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      ) : null}

      {report.miscalibration.length > 0 ? (
        <section className="panel" style={{ marginTop: 18 }}>
          <h2>Where the prices miss the results</h2>
          {report.miscalibration.map((note) => (
            <p key={note}>{note}</p>
          ))}
        </section>
      ) : (
        <p className="sub" style={{ marginTop: 18 }}>
          No scored market is off by 3 points or more on a sample of at least 200 matches.
        </p>
      )}

      {families.map((family) => {
        const markets = family.keys
          .map((key) => report.markets.find((market) => market.market === key))
          .filter((market): market is BacktestMarket => Boolean(market));
        return (
          <section key={family.title}>
            <h2 className="day-label">{family.title}</h2>
            <MarketTable markets={markets} withBins />
          </section>
        );
      })}
    </main>
  );
}
