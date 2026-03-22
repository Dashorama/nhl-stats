import { Story } from "@/lib/data";

export function StoryCard({ story }: { story: Story }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-8">
      <p className="text-xs font-semibold uppercase tracking-widest text-blue-600 mb-2">
        Story of the Day · {story.date}
      </p>
      <h2 className="text-2xl font-bold text-gray-900 mb-4">{story.headline}</h2>
      {story.chart && (
        <div className="mb-4 rounded-xl overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`/data/${story.chart}`} alt={story.headline} className="w-full" />
        </div>
      )}
      <p className="text-gray-700 leading-relaxed mb-4">{story.body}</p>
      {story.headlines.length > 0 && (
        <div className="border-t border-gray-100 pt-4 mt-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Related
          </p>
          {story.headlines.map((h, i) => (
            <a key={i} href={h.url} target="_blank" rel="noopener noreferrer"
               className="block text-sm text-blue-600 hover:underline mb-1">
              {h.title}{" "}
              <span className="text-gray-400">— {h.source}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
