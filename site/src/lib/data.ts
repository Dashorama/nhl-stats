import path from "path";
import fs from "fs";

export interface Shooter {
  player_id: number;
  player_name: string;
  team_abbrev: string;
  goals: number;
  xg: number;
  gax: number;
  shots: number;
}

export interface TeamEntry {
  abbrev: string;
  name: string;
  win_pct: number;
  xg_win_pct: number;
  diff: number;
}

export interface Leaderboard {
  date: string;
  hot_shooters: Shooter[];
  cold_shooters: Shooter[];
  teams: TeamEntry[];
}

export interface Headline {
  title: string;
  url: string;
  source: string;
}

export interface Story {
  date: string;
  story_type: string;
  headline: string;
  body: string;
  chart: string;
  subject_type: string;
  subject_id: number | string | null;
  subject_name: string;
  social_text: string;
  headlines: Headline[];
}

export interface PlayerSeason {
  season: string;
  goals: number;
  xg: number;
  gax: number;
  shots: number;
  sh_vs_expected: number;
  hd_shot_pct: number;   // % of shots from high-danger zone (slot)
  rebound_rate: number;  // % of shots that were rebounds
  rush_rate: number;     // % of shots off the rush
}

export interface EdgeTracking {
  max_speed_mph: number;
  max_speed_pct: number;
  shot_speed_mph: number;
  shot_speed_pct: number;
  oz_pct: number;
  oz_percentile: number;
  distance_mi: number;
  distance_pct: number;
}

export interface FaceoffStats {
  fo_wins: number;
  fo_losses: number;
  fo_pct: number;
  fo_oz_pct: number | null;
  fo_dz_pct: number | null;
  fo_nz_pct: number | null;
}

export interface Player {
  player_id: number;
  player_name: string;
  position: string;
  team_abbrev: string;
  seasons: PlayerSeason[];
  verdict: string;
  injury_status: string;
  tracking: EdgeTracking | null;
  faceoffs: FaceoffStats | null;
}

export interface Team {
  abbrev: string;
  name: string;
  conference: string;
  division: string;
  current_season: {
    wins?: number;
    losses?: number;
    ot_losses?: number;
    points?: number;
    games_played?: number;
    win_pct?: number;
    xg_win_pct?: number;
    diff?: number;
  };
}

function readJson<T>(filePath: string): T {
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
}

const PUBLIC_DATA = path.join(process.cwd(), "public", "data");
const SRC_DATA = path.join(process.cwd(), "src", "data");

export function loadStory(): Story {
  return readJson<Story>(path.join(PUBLIC_DATA, "story.json"));
}

export function loadLeaderboard(): Leaderboard {
  return readJson<Leaderboard>(path.join(PUBLIC_DATA, "leaderboard.json"));
}

export function loadAllPlayerIds(): string[] {
  const dir = path.join(SRC_DATA, "players");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((f) => f.endsWith(".json")).map((f) => f.replace(".json", ""));
}

export function loadPlayer(id: string): Player | null {
  const filePath = path.join(SRC_DATA, "players", `${id}.json`);
  if (!fs.existsSync(filePath)) return null;
  return readJson<Player>(filePath);
}

export function loadAllTeamAbbrevs(): string[] {
  const dir = path.join(SRC_DATA, "teams");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((f) => f.endsWith(".json")).map((f) => f.replace(".json", ""));
}

export function loadTeam(abbrev: string): Team | null {
  const filePath = path.join(SRC_DATA, "teams", `${abbrev}.json`);
  if (!fs.existsSync(filePath)) return null;
  return readJson<Team>(filePath);
}
