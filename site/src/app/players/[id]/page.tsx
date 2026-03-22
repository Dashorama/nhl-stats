import { loadPlayer, loadAllPlayerIds } from "@/lib/data";

export async function generateStaticParams() {
  return loadAllPlayerIds().map(id => ({ id }));
}

export default async function PlayerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const player = loadPlayer(id);

  return (
    <main className="max-w-3xl mx-auto px-4 py-10">
      <p className="text-sm text-gray-500 mb-1">
        {player.team_abbrev} · {player.position}
      </p>
      <h1 className="text-3xl font-black text-gray-900 mb-2">{player.player_name}</h1>

      {player.injury_status !== "HEALTHY" && (
        <span className="inline-block bg-amber-100 text-amber-800 text-xs font-semibold px-2 py-1 rounded mb-4">
          {player.injury_status}
        </span>
      )}

      {player.verdict && (
        <p className="text-gray-600 mb-6 italic">{player.verdict}</p>
      )}

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="font-bold text-gray-700 mb-4 text-sm uppercase tracking-wide">
          Goals vs. Expected Goals by Season
        </h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-400 text-left border-b">
              <th className="pb-2">Season</th>
              <th className="pb-2 text-right">Goals</th>
              <th className="pb-2 text-right">xG</th>
              <th className="pb-2 text-right">GAx</th>
              <th className="pb-2 text-right">Sh/Exp</th>
              <th className="pb-2 text-right" title="% of shots from the slot">HD%</th>
              <th className="pb-2 text-right" title="% of shots that were rebounds">Reb%</th>
              <th className="pb-2 text-right" title="% of shots off the rush">Rush%</th>
            </tr>
          </thead>
          <tbody>
            {player.seasons.map(s => (
              <tr key={s.season} className="border-b border-gray-50">
                <td className="py-2 text-gray-700">{s.season}</td>
                <td className="py-2 text-right font-mono">{s.goals}</td>
                <td className="py-2 text-right font-mono text-gray-500">{s.xg}</td>
                <td className="py-2 text-right font-mono">
                  {s.gax > 0 ? "+" : ""}{s.gax}
                </td>
                <td className="py-2 text-right font-mono text-gray-500">{s.sh_vs_expected}x</td>
                <td className="py-2 text-right font-mono text-gray-500">{s.hd_shot_pct}%</td>
                <td className="py-2 text-right font-mono text-gray-500">{s.rebound_rate}%</td>
                <td className="py-2 text-right font-mono text-gray-500">{s.rush_rate}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
