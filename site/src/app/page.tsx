import { loadStory, loadLeaderboard } from "@/lib/data";
import { StoryCard } from "@/components/StoryCard";
import { ShooterLeaderboard, TeamLeaderboard } from "@/components/Leaderboard";

export const dynamic = "force-static";

export default function Home() {
  const story = loadStory();
  const leaderboard = loadLeaderboard();

  return (
    <main className="max-w-4xl mx-auto px-4 py-10">
      <header className="mb-10">
        <h1 className="text-4xl font-black text-gray-900 tracking-tight">
          Hockey Numbers
        </h1>
        <p className="text-gray-500 mt-1">
          Daily xG insights. Updated every morning.
        </p>
      </header>

      <StoryCard story={story} />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ShooterLeaderboard title="Running Hot" players={leaderboard.hot_shooters} />
        <ShooterLeaderboard title="Running Cold" players={leaderboard.cold_shooters} />
        <TeamLeaderboard teams={leaderboard.teams} />
      </div>
    </main>
  );
}
