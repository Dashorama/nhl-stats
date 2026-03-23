import { loadPlayer, loadAllPlayerIds } from "@/lib/data";
import { notFound } from "next/navigation";

export async function generateStaticParams() {
  return loadAllPlayerIds().map(id => ({ id }));
}

export default async function PlayerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const player = loadPlayer(id);
  if (!player) notFound();

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

      {player.tracking && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-4">
          <h2 className="font-bold text-gray-700 mb-1 text-sm uppercase tracking-wide">
            NHL EDGE Tracking
          </h2>
          <p className="text-xs text-gray-400 mb-4">Season bests, 2024–25. Percentile vs. all skaters.</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-2xl font-black text-gray-900">{player.tracking.max_speed_mph} <span className="text-base font-normal text-gray-400">mph</span></p>
              <p className="text-xs text-gray-500 mt-0.5">Top Speed</p>
              <p className="text-xs text-blue-500 font-semibold">{player.tracking.max_speed_pct}th pct</p>
            </div>
            <div>
              <p className="text-2xl font-black text-gray-900">{player.tracking.shot_speed_mph} <span className="text-base font-normal text-gray-400">mph</span></p>
              <p className="text-xs text-gray-500 mt-0.5">Hardest Shot</p>
              <p className="text-xs text-blue-500 font-semibold">{player.tracking.shot_speed_pct}th pct</p>
            </div>
            <div>
              <p className="text-2xl font-black text-gray-900">{player.tracking.oz_pct}<span className="text-base font-normal text-gray-400">%</span></p>
              <p className="text-xs text-gray-500 mt-0.5">Offensive Zone Time</p>
              <p className="text-xs text-blue-500 font-semibold">{player.tracking.oz_percentile}th pct</p>
            </div>
            <div>
              <p className="text-2xl font-black text-gray-900">{player.tracking.distance_mi} <span className="text-base font-normal text-gray-400">mi</span></p>
              <p className="text-xs text-gray-500 mt-0.5">Distance Skated</p>
              <p className="text-xs text-blue-500 font-semibold">{player.tracking.distance_pct}th pct</p>
            </div>
          </div>
        </div>
      )}

      {player.faceoffs && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-4">
          <h2 className="font-bold text-gray-700 mb-1 text-sm uppercase tracking-wide">
            Faceoffs
          </h2>
          <p className="text-xs text-gray-400 mb-4">
            {player.faceoffs.fo_wins + player.faceoffs.fo_losses} total draws, 2024–25.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-2xl font-black text-gray-900">{player.faceoffs.fo_pct}<span className="text-base font-normal text-gray-400">%</span></p>
              <p className="text-xs text-gray-500 mt-0.5">Overall</p>
            </div>
            <div>
              <p className={`text-2xl font-black ${player.faceoffs.fo_oz_pct != null && player.faceoffs.fo_oz_pct >= 50 ? "text-blue-600" : "text-amber-600"}`}>
                {player.faceoffs.fo_oz_pct ?? "—"}<span className="text-base font-normal text-gray-400">%</span>
              </p>
              <p className="text-xs text-gray-500 mt-0.5">Off. Zone {player.faceoffs.fo_oz_pct != null ? (player.faceoffs.fo_oz_pct >= 50 ? "▲" : "▼") : ""}</p>
            </div>
            <div>
              <p className="text-2xl font-black text-gray-900">
                {player.faceoffs.fo_dz_pct ?? "—"}<span className="text-base font-normal text-gray-400">%</span>
              </p>
              <p className="text-xs text-gray-500 mt-0.5">Def. Zone</p>
            </div>
            <div>
              <p className="text-2xl font-black text-gray-900">
                {player.faceoffs.fo_nz_pct ?? "—"}<span className="text-base font-normal text-gray-400">%</span>
              </p>
              <p className="text-xs text-gray-500 mt-0.5">Neutral Zone</p>
            </div>
          </div>
        </div>
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
