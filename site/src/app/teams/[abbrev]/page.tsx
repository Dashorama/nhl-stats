import { loadTeam, loadAllTeamAbbrevs } from "@/lib/data";

export async function generateStaticParams() {
  return loadAllTeamAbbrevs().map(abbrev => ({ abbrev }));
}

export default async function TeamPage({ params }: { params: Promise<{ abbrev: string }> }) {
  const { abbrev } = await params;
  const team = loadTeam(abbrev);
  const s = team.current_season;

  return (
    <main className="max-w-3xl mx-auto px-4 py-10">
      <p className="text-sm text-gray-500 mb-1">
        {team.conference} · {team.division}
      </p>
      <h1 className="text-3xl font-black text-gray-900 mb-6">{team.name}</h1>

      {s.win_pct != null && s.xg_win_pct != null && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
          <h2 className="font-bold text-gray-700 mb-4 text-sm uppercase tracking-wide">
            Record vs. Expected
          </h2>
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
              {(() => {
                const diff = s.win_pct - s.xg_win_pct;
                return (
                  <p className="text-3xl font-black text-gray-900">
                    {diff > 0 ? "+" : ""}{(diff * 100).toFixed(1)}%
                  </p>
                );
              })()}
              <p className="text-xs text-gray-400 mt-1">Difference</p>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
