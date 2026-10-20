import { RankingsView } from "./components/rankings-view";
import { readMeta, readTeams } from "./lib/data";

export default function HomePage() {
  const teams = readTeams();
  const meta = readMeta();
  const leagues = meta?.leagues ?? [];
  const tournaments = meta?.tournaments ?? [
    { id: "UCL", name: "Champions League" },
    { id: "UEL", name: "Europa League" },
    { id: "UECL", name: "Conference League" },
  ];
  const clubelo = meta?.clubelo;

  return (
    <main>
      <section className="hero">
        <h1>Europe club Elo</h1>
        <p>
          One rating pool for the top men’s leagues, tied together by Champions League, Europa League,
          and Conference League matches. The slate below the rankings is a score model, not a price.
        </p>
        <div className="meta-row">
          <span className="pill">{meta?.season || "season"}</span>
          <span className="pill">{meta?.clubs ?? teams.length} clubs</span>
          <span className="pill">{meta?.matches_played ?? "—"} matches replayed</span>
          <span className="pill">Times in Chicago</span>
          {clubelo?.available && clubelo.spearman != null ? (
            <span className="pill">ClubElo rank correlation {clubelo.spearman}</span>
          ) : null}
        </div>
      </section>
      <RankingsView teams={teams} leagues={leagues} tournaments={tournaments} />
    </main>
  );
}
