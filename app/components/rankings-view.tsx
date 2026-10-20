"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { TeamRow } from "../lib/data";

type League = { id: string; name: string };
type Tournament = { id: string; name: string };

export function RankingsView({
  teams,
  leagues,
  tournaments,
}: {
  teams: TeamRow[];
  leagues: League[];
  tournaments: Tournament[];
}) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return teams.filter((team) => {
      if (filter.startsWith("league:") && team.league_id !== filter.slice(7)) return false;
      if (filter.startsWith("cup:") && !team.tournaments.includes(filter.slice(4))) return false;
      if (!needle) return true;
      return team.name.toLowerCase().includes(needle) || (team.league || "").toLowerCase().includes(needle);
    });
  }, [teams, filter, query]);

  return (
    <>
      <div className="filters" role="toolbar" aria-label="Ranking filters">
        <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>
          All Europe
        </button>
        {leagues.map((league) => (
          <button
            key={league.id}
            type="button"
            aria-pressed={filter === `league:${league.id}`}
            onClick={() => setFilter(`league:${league.id}`)}
          >
            {league.name}
          </button>
        ))}
        {tournaments.map((cup) => (
          <button
            key={cup.id}
            type="button"
            aria-pressed={filter === `cup:${cup.id}`}
            onClick={() => setFilter(`cup:${cup.id}`)}
          >
            {cup.name}
          </button>
        ))}
        <input
          className="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Find a club"
          aria-label="Find a club"
        />
      </div>
      {visible.length === 0 ? (
        <p className="empty">No clubs match that filter. Run the artifact build if this is a fresh checkout.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <caption className="sub" style={{ textAlign: "left", padding: "12px 14px 0" }}>
              {visible.length} clubs
            </caption>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Club</th>
                <th scope="col">League</th>
                <th scope="col">Europe</th>
                <th scope="col">Elo</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((team, index) => (
                <tr key={team.id}>
                  <td>{index + 1}</td>
                  <td>
                    <Link href={`/teams/${team.id}`}>{team.name}</Link>
                  </td>
                  <td>{team.league || "—"}</td>
                  <td>
                    {team.tournaments.map((code) => (
                      <span className="tag" key={code}>
                        {code}
                      </span>
                    ))}
                  </td>
                  <td className="rating">{team.rating.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
