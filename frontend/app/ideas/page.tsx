"use client";

import { useEffect, useState } from "react";
import { useToast } from "@/components/ui/ToastProvider";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/api";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, Skeleton } from "@/components/ui/card";
import { ChoiceGroup } from "@/components/ui/choice-group";
import { Input, Label } from "@/components/ui/field";
import { EmptyState, ErrorState } from "@/components/ui/states";

const LS_IDEAS = "contendo_ideas";
const LS_SAVED = "contendo_saved_ideas";
const LS_TOPIC = "contendo_ideas_topic";
const LS_COUNT = "contendo_ideas_count";

interface Idea {
  title: string;
  angle: string;
  format: string;
  reasoning: string;
}

// Display badge labels for format (uppercase pill)
const FORMAT_BADGE: Record<string, string> = {
  "linkedin post": "LinkedIn Post",
  "medium article": "Feature Story",
  thread: "Thread",
};

function lsGet(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function lsSet(key: string, value: string): void {
  try { localStorage.setItem(key, value); } catch { /* ignore */ }
}
function lsRemove(key: string): void {
  try { localStorage.removeItem(key); } catch { /* ignore */ }
}

// ─── Idea Grid Card ───────────────────────────────────────────────────────────

function IdeaCard({
  idea,
  isSaved,
  onUseThis,
  onSave,
  onUnsave,
}: {
  idea: Idea;
  isSaved: boolean;
  onUseThis: () => void;
  onSave: () => void;
  onUnsave: () => void;
}) {
  const badge = FORMAT_BADGE[idea.format] ?? idea.format;

  return (
    <Card className="flex flex-col gap-3">
      <span className="w-fit text-[0.6875rem] font-semibold tracking-[0.06em] uppercase px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant">
        {badge}
      </span>
      <h3 className="font-headline text-[1rem] text-on-surface leading-snug font-semibold flex-1">{idea.title}</h3>
      <p className="text-[0.875rem] text-secondary leading-relaxed">{idea.angle}</p>
      <div className="mt-1 flex gap-2">
        <Button variant="secondary" size="sm" className="flex-1" aria-pressed={isSaved} onClick={isSaved ? onUnsave : onSave}>
          {isSaved ? "Saved" : "Save for later"}
        </Button>
        <Button size="sm" className="flex-1" onClick={onUseThis}>Use this</Button>
      </div>
    </Card>
  );
}

function ArchiveRow({
  idea,
  onUseThis,
  onUnsave,
}: {
  idea: Idea;
  onUseThis: () => void;
  onUnsave: () => void;
}) {
  const badge = FORMAT_BADGE[idea.format] ?? idea.format;

  return (
    <li className="flex items-center gap-3 py-3">
      <div className="flex-1 min-w-0">
        <p className="label-caps text-on-surface-variant mb-0.5">{badge}</p>
        <p className="text-[0.9375rem] font-medium text-on-surface leading-snug truncate">{idea.title}</p>
      </div>
      <Button variant="ghost" size="icon" onClick={onUnsave} aria-label={`Remove "${idea.title}" from saved ideas`} className="text-error hover:text-error">
        <svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
        </svg>
      </Button>
      <Button variant="secondary" size="sm" onClick={onUseThis}>Use this</Button>
    </li>
  );
}

// How many ideas the user can ask for at once.
const COUNT_OPTIONS = [3, 5, 10];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function IdeasPage() {
  const api = useApi();
  const router = useRouter();

  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [savedIdeas, setSavedIdeas] = useState<Idea[]>([]);
  const [savedTitles, setSavedTitles] = useState<Set<string>>(new Set());
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sparse, setSparse] = useState(false);
  const [clearConfirm, setClearConfirm] = useState(false);
  const { showToast } = useToast();

  // Restore from localStorage on mount
  useEffect(() => {
    const ideasStr = lsGet(LS_IDEAS);
    if (ideasStr) {
      try { setIdeas(JSON.parse(ideasStr)); } catch { /* ignore */ }
    }
    const topicStr = lsGet(LS_TOPIC);
    if (topicStr) setTopic(topicStr);
    const countStr = lsGet(LS_COUNT);
    if (countStr && COUNT_OPTIONS.includes(parseInt(countStr))) setCount(parseInt(countStr));
    const savedStr = lsGet(LS_SAVED);
    if (savedStr) {
      try {
        const parsed: Idea[] = JSON.parse(savedStr);
        setSavedIdeas(parsed);
        setSavedTitles(new Set(parsed.map((i) => i.title)));
      } catch { /* ignore */ }
    }
  }, []);

  const handleGenerate = async () => {
    setLoading(true);
    setError("");
    setSparse(false);
    try {
      const res = await api.getSuggestions(count, topic.trim() || undefined);
      if (!res.ok) throw new Error("Failed");
      const data = await res.json();
      if (data.sparse) {
        setSparse(true);
        setIdeas([]);
        lsRemove(LS_IDEAS);
        return;
      }
      const newIdeas: Idea[] = data.suggestions ?? [];
      setIdeas(newIdeas);
            lsSet(LS_IDEAS, JSON.stringify(newIdeas));
      lsSet(LS_TOPIC, topic);
      lsSet(LS_COUNT, String(count));
    } catch {
      setError("We couldn't get ideas right now. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = (idea: Idea) => {
    const current: Idea[] = JSON.parse(lsGet(LS_SAVED) || "[]");
    const updated = [...current, idea];
    lsSet(LS_SAVED, JSON.stringify(updated));
    setSavedIdeas(updated);
    setSavedTitles(new Set(updated.map((i) => i.title)));
    showToast("Idea saved", "success");
  };

  const handleUnsave = (idea: Idea) => {
    const updated = savedIdeas.filter((s) => s.title !== idea.title);
    lsSet(LS_SAVED, JSON.stringify(updated));
    setSavedIdeas(updated);
    setSavedTitles(new Set(updated.map((i) => i.title)));
    showToast("Idea removed", "info");
  };

  const handleClearAll = () => {
    lsRemove(LS_IDEAS);
    setIdeas([]);
    setClearConfirm(false);
  };

  const handleUseThis = (idea: Idea) => {
    try {
      sessionStorage.setItem("contentOS_last_topic", idea.title);
      sessionStorage.setItem("contentOS_prefill_format", idea.format);
    } catch { /* ignore */ }
    router.push("/create");
  };

  const hasIdeas = ideas.length > 0;
  const hasSaved = savedIdeas.length > 0;


  return (
    <div className="-mx-4 -mt-6 -mb-6 sm:-mx-6 md:-mx-10 md:-mt-10 md:-mb-10 min-h-screen bg-background flex flex-col">
      <div className="flex-1 overflow-y-auto px-4 md:px-10 py-8 md:py-10">
        <div className="mx-auto mb-10 max-w-xl text-center">
          <h1 className="font-headline text-[2.25rem] md:text-[3rem] text-on-surface leading-[1.1] mb-4">Find your next post</h1>
          <p className="text-on-surface-variant text-[0.9375rem] leading-relaxed">
            Ideas come from what you&apos;ve added to your library. Add a topic to narrow them down, or leave it blank.
          </p>
        </div>

        <form
          className="mx-auto mb-12 flex max-w-[420px] flex-col gap-5"
          onSubmit={(e) => { e.preventDefault(); if (!loading) handleGenerate(); }}
        >
          <div>
            <Label htmlFor="ideas-topic">Topic <span className="normal-case font-normal">(optional)</span></Label>
            <Input id="ideas-topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. first-time buyers" />
          </div>
          <ChoiceGroup
            legend="How many ideas"
            value={String(count)}
            onChange={(v) => setCount(Number(v))}
            options={COUNT_OPTIONS.map((n) => ({ value: String(n), label: String(n) }))}
            className="grid grid-cols-3 gap-2"
            tileClassName="items-center"
          />
          <Button type="submit" size="lg" loading={loading} className="w-full">Get ideas</Button>
        </form>

        {loading && (
          <div role="status" aria-label="Finding ideas" className="mb-12 grid grid-cols-1 gap-4 md:grid-cols-3">
            {Array.from({ length: Math.min(count, 3) }, (_, n) => (
              <div key={n} className="rounded-2xl bg-surface-container-lowest p-5">
                <Skeleton className="h-4 w-20" /><Skeleton className="mt-4 h-5 w-4/5" /><Skeleton className="mt-3 h-3 w-full" /><Skeleton className="mt-2 h-3 w-2/3" />
              </div>
            ))}
          </div>
        )}

        {!loading && error && <div className="mx-auto mb-12 max-w-xl"><ErrorState message={error} onRetry={handleGenerate} /></div>}

        {!loading && hasIdeas && (
          <section aria-labelledby="ideas-heading" className="mb-12">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
              <h2 id="ideas-heading" className="font-headline text-2xl text-on-surface">
                Ideas <span className="text-on-surface-variant text-[1rem] font-sans">({ideas.length})</span>
              </h2>
              {clearConfirm ? (
                <div role="alert" className="flex items-center gap-2">
                  <span className="text-[0.875rem] text-on-surface">Clear these ideas?</span>
                  <Button variant="destructive" size="sm" onClick={handleClearAll}>Clear</Button>
                  <Button variant="secondary" size="sm" onClick={() => setClearConfirm(false)}>Keep</Button>
                </div>
              ) : (
                <Button variant="tertiary" size="sm" onClick={() => setClearConfirm(true)}>Clear all</Button>
              )}
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {ideas.map((idea, i) => (
                <IdeaCard
                  key={i}
                  idea={idea}
                  isSaved={savedTitles.has(idea.title)}
                  onUseThis={() => handleUseThis(idea)}
                  onSave={() => handleSave(idea)}
                  onUnsave={() => handleUnsave(idea)}
                />
              ))}
            </div>
          </section>
        )}

        {!hasIdeas && !loading && !error && (
          sparse ? (
            <EmptyState
              title="Add something to write from first"
              body="Ideas come from your library. Add an article, a note or a video, then come back for ideas."
              action={<Button asChild><Link href="/feed-memory">Add a source</Link></Button>}
            />
          ) : (
            <EmptyState title="No ideas yet" body="Choose how many you'd like, then select Get ideas." />
          )
        )}

        {hasSaved && (
          <section aria-labelledby="saved-heading" className="mt-12">
            <h2 id="saved-heading" className="font-headline text-2xl text-on-surface mb-2">Saved ideas</h2>
            <ul className="divide-y divide-surface-container-high">
              {savedIdeas.map((idea, i) => (
                <ArchiveRow key={i} idea={idea} onUseThis={() => handleUseThis(idea)} onUnsave={() => handleUnsave(idea)} />
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
