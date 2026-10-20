import Link from "next/link";
import { notFound } from "next/navigation";
import { readHistory, readTeams } from "../../lib/data";

export function generateStaticParams() {
  return readTeams().map((team) => ({ id: team.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const team = readTeams().find((row) => row.id === id);
  return { title: team ? `${team.name} · Soccer Bet Scout` : "Club · Soccer Bet Scout" };
}

function Chart({ points }: { points: { date: string; rating: number }[] }) {
  const sampled = points.filter((_, index) => index % Math.ceil(points.length / 180) === 0 || index === points.length - 1);
  if (sampled.length < 2) return <p className="sub">Not enough history to draw a line yet.</p>;
  const ratings = sampled.map((point) => point.rating);
  const min = Math.min(...ratings) - 8;
  const max = Math.max(...ratings) + 8;
  const width = 760;
  const height = 220;
  const coords = sampled.map((point, index) => {
    const x = (index / (sampled.length - 1)) * (width - 16) + 8;
    const y = height - 16 - ((point.rating - min) / (max - min)) * (height - 32);
    return `${x},${y}`;
  });
  return (
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Rating history">
      <polyline fill="none" stroke="#0c2f24" strokeWidth="3" points={coords.join(" ")} />
    </svg>
  );
}

export default async function TeamPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const team = readTeams().find((row) => row.id === id);
  const history = readHistory(id);
  if (!team && !history) notFound();
  const name = team?.name || history?.name || id;
  const points = history?.points ?? [];

  return (
    <main>
      <section className="hero">
        <div className="kicker" style={{ color: "var(--lime)" }}>{team?.league || history?.league || "Europe"}</div>
        <h1>{name}</h1>
        <p>
          Rating {team?.rating.toFixed(1) ?? "—"}
          {team ? ` · rank ${team.rank} · ${team.played} matches in the replay` : ""}
          {team?.tournaments.length ? ` · ${team.tournaments.join(", ")}` : ""}
        </p>
      </section>
      <div className="chart-wrap">
        <Chart points={points} />
        <p className="sub">
          {points.length
            ? `${points[0].date} to ${points[points.length - 1].date}. Season resets show up as a step.`
            : "No rating history stored yet."}
        </p>
      </div>
      <div className="table-wrap history-table">
        <table>
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Rating</th>
              <th scope="col">Note</th>
            </tr>
          </thead>
          <tbody>
            {points.slice(-25).reverse().map((point, index) => (
              <tr key={`${point.date}-${index}`}>
                <td>{point.date}</td>
                <td className="rating">{point.rating.toFixed(1)}</td>
                <td>{point.opponent ? `vs ${point.opponent}` : point.event}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="sub" style={{ marginTop: 16 }}>
        <Link href="/">Back to rankings</Link>
      </p>
    </main>
  );
}
