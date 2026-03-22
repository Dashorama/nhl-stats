import Link from "next/link";
import { Shooter, TeamEntry } from "@/lib/data";

export function ShooterLeaderboard({
  title, players,
}: {
  title: string;
  players: Shooter[];
}) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
      <h3 className="font-bold text-gray-900 mb-3 text-sm uppercase tracking-wide">{title}</h3>
      <ul className="space-y-2">
        {players.slice(0, 8).map(p => (
          <li key={p.player_id} className="flex items-center justify-between text-sm">
            <Link href={`/players/${p.player_id}`}
                  className="text-blue-700 hover:underline font-medium">
              {p.player_name}
            </Link>
            <span className="text-gray-500 font-mono">
              {p.gax > 0 ? "+" : ""}{p.gax} GAx
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TeamLeaderboard({ teams }: { teams: TeamEntry[] }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
      <h3 className="font-bold text-gray-900 mb-3 text-sm uppercase tracking-wide">
        Record vs. Numbers
      </h3>
      <ul className="space-y-2">
        {teams.slice(0, 8).map(t => (
          <li key={t.abbrev} className="flex items-center justify-between text-sm">
            <Link href={`/teams/${t.abbrev}`}
                  className="text-blue-700 hover:underline font-medium">
              {t.name}
            </Link>
            <span className="font-mono text-gray-700">
              {t.diff > 0 ? "+" : ""}{(t.diff * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
