"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Post {
  id: number;
  created_at: string;
  topic: string;
  format: string;
  tone: string;
  content: string;
  authenticity_score: number;
}

const FORMAT_LABELS: Record<string, string> = {
  "linkedin post": "LinkedIn",
  "medium article": "Medium",
  "thread": "Thread",
};

const TONE_LABELS: Record<string, string> = {
  "casual": "Casual",
  "technical": "Technical",
  "storytelling": "Storytelling",
};

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 75
      ? "bg-green-100 text-green-700"
      : score >= 50
      ? "bg-amber-100 text-amber-700"
      : "bg-red-100 text-red-600";
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${color}`}>
      {score}/100
    </span>
  );
}

function PostCard({ post }: { post: Post }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(post.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const date = new Date(post.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-gray-900 text-sm leading-snug truncate">
              {post.topic}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                {FORMAT_LABELS[post.format] ?? post.format}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                {TONE_LABELS[post.tone] ?? post.tone}
              </span>
              <ScoreBadge score={post.authenticity_score} />
              <span className="text-xs text-gray-400">{date}</span>
            </div>
          </div>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-gray-500 hover:text-gray-900 whitespace-nowrap transition-colors pt-0.5"
          >
            {expanded ? "Hide" : "See full post"}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-100 px-5 py-4 space-y-3">
          <pre className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed font-sans">
            {post.content}
          </pre>
          <button
            onClick={handleCopy}
            className="text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-600 hover:border-gray-400 hover:text-gray-900 transition-colors"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      )}
    </div>
  );
}

export default function HistoryPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/history`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load history");
        return r.json();
      })
      .then((data) => setPosts(data.posts ?? []))
      .catch(() => setError("Could not load post history. Is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">History</h1>
        <p className="mt-1 text-gray-500 text-sm">
          Posts you have saved. Newest first.
        </p>
      </div>

      {loading && (
        <p className="text-sm text-gray-400">Loading...</p>
      )}

      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}

      {!loading && !error && posts.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white px-6 py-12 text-center">
          <p className="text-gray-400 text-sm">No saved posts yet.</p>
          <p className="text-gray-400 text-xs mt-1">
            Generate a post and click "Save to history" to see it here.
          </p>
        </div>
      )}

      {!loading && posts.length > 0 && (
        <div className="space-y-4">
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      )}
    </div>
  );
}
