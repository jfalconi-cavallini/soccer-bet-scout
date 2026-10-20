import fs from "fs";
import path from "path";

export type TeamRow = {
  id: string;
  name: string;
  rating: number;
  league_id: string | null;
  league: string | null;
  country: string | null;
  tournaments: string[];
  played: number;
  rank: number;
};

export type NarrativeSection = { title: string; body: string };

export type Prediction = {
  home_win_pct: number;
  draw_pct: number;
  away_win_pct: number;
  xg_home: number;
  xg_away: number;
  xg_home_1h: number;
  xg_away_1h: number;
  btts_pct: number;
  clean_sheet_home_pct: number;
  clean_sheet_away_pct: number;
  over: Record<string, number>;
  under: Record<string, number>;
  home_totals: Record<string, number>;
  away_totals: Record<string, number>;
  top_scorelines: { score: string; pct: number }[];
  elo_home: number;
  elo_away: number;
  elo_gap: number;
  narrative: NarrativeSection[];
  model: Record<string, number>;
  kickoff_ct: string | null;
};

export type SlateMatch = {
  id: string;
  date: string;
  kickoff_utc: string | null;
  kickoff_ct: string | null;
  competition: string;
  competition_id: string;
  kind: string;
  home_id: string;
  away_id: string;
  home_name: string;
  away_name: string;
  prediction: Prediction;
};

export type HistoryPoint = {
  date: string;
  rating: number;
  opponent: string | null;
  competition_id: string | null;
  event: string;
};

export type Meta = {
  generated_at?: string;
  timezone?: string;
  season?: string;
  matches_played?: number;
  clubs?: number;
  upcoming?: number;
  tournament_seasons?: Record<string, string>;
  leagues?: { id: string; name: string; country: string }[];
  tournaments?: { id: string; name: string }[];
  clubelo?: {
    available?: boolean;
    spearman?: number | null;
    reason?: string;
    note?: string;
    top?: { club: string; clubelo: number; ours: number }[];
  };
  calibration?: {
    settled?: number;
    pending?: number;
    brier?: number | null;
    note?: string;
  };
};

const root = path.join(process.cwd(), "data", "artifacts");

function readJson<T>(relative: string, fallback: T): T {
  const full = path.join(root, relative);
  if (!fs.existsSync(full)) return fallback;
  return JSON.parse(fs.readFileSync(full, "utf8")) as T;
}

export function readMeta(): Meta | null {
  const meta = readJson<Meta | null>("meta.json", null);
  return meta;
}

export function readTeams(): TeamRow[] {
  return readJson<{ teams: TeamRow[] }>("rankings.json", { teams: [] }).teams;
}

export function readMatches(): SlateMatch[] {
  return readJson<{ matches: SlateMatch[] }>("matches.json", { matches: [] }).matches;
}

export function readMatch(id: string): SlateMatch | null {
  if (!/^[a-z0-9-]+$/.test(id)) return null;
  return readMatches().find((match) => match.id === id) ?? null;
}

export function readHistory(id: string): { name: string; points: HistoryPoint[]; rating: number; league: string | null } | null {
  if (!/^[a-z0-9-]+$/.test(id)) return null;
  return readJson("history/" + id + ".json", null);
}
