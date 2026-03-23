import { loadTeam, loadAllTeamAbbrevs } from "@/lib/data";
import { notFound } from "next/navigation";

export async function generateStaticParams() {
  return loadAllTeamAbbrevs().map(abbrev => ({ abbrev }));
}

export default async function TeamPage({ params }: { params: Promise<{ abbrev: string }> }) {
  const { abbrev } = await params;
  const team = loadTeam(abbrev);
  if (!team) notFound();
  const s = team.current_season;

  const diff = s.win_pct != null && s.xg_win_pct != null ? s.win_pct - s.xg_win_pct : null;

  return (
    <main className="max-w-3xl mx-auto px-4 py-10">
      <p className="text-sm text-gray-500 mb-1">
        {team.conference} · {team.division}
      </p>
      <h1 className="text-3xl font-black text-gray-900 mb-6">{team.name}</h1>

      {/* Record card */}
      {s.wins != null && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-4">
          <h2 className="font-bold text-gray-700 mb-4 text-sm uppercase tracking-wide">
            Current Season
          </h2>
          <div className="grid grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-3xl font-black text-gray-900">{s.wins}</p>
              <p className="text-xs text-gray-400 mt-1">Wins</p>
            </div>
            <div>
              <p className="text-3xl font-black text-gray-900">{s.losses}</p>
              <p className="text-xs text-gray-400 mt-1">Losses</p>
            </div>
            <div>
              <p className="text-3xl font-black text-gray-900">{s.ot_losses}</p>
              <p className="text-xs text-gray-400 mt-1">OTL</p>
            </div>
            <div>
              <p className="text-3xl font-black text-blue-600">{s.points}</p>
              <p className="text-xs text-gray-400 mt-1">Points</p>
            </div>
          </div>
        </div>
      )}

      {/* xG vs actual */}
      {s.win_pct != null && s.xg_win_pct != null && diff != null && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="font-bold text-gray-700 mb-1 text-sm uppercase tracking-wide">
            Record vs. Expected
          </h2>
          <p className="text-xs text-gray-400 mb-4">
            xG-implied win% is based on shot quality for and against all season.
            {diff > 0.05
              ? " This team is winning more than their shot quality suggests — possible regression ahead."
              : diff < -0.05
              ? " This team is winning less than their shot quality suggests — possible breakout ahead."
              : " Their record is tracking close to what their shot quality predicts."}
          </p>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-3xl font-black text-gray-900">
                {(s.win_pct * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-400 mt-1">Actual Win %</p>
            </div>
            <div>
              <p className="text-3xl font-black text-gray-500">
                {(s.xg_win_pct * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-400 mt-1">xG-Implied</p>
            </div>
            <div>
              <p className={`text-3xl font-black ${diff > 0 ? "text-emerald-600" : diff < 0 ? "text-red-500" : "text-gray-900"}`}>
                {diff > 0 ? "+" : ""}{(diff * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-400 mt-1">Difference</p>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
