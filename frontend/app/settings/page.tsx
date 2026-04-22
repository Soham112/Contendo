"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/api";
import type { User } from "@supabase/supabase-js";
import supabase from "@/lib/supabase";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ProfileSnapshot {
  name: string;
  role: string;
  bio: string;
  location: string;
  voice_descriptors: string[];
  words_to_avoid: string[];
  writing_rules: string[];
  topics_of_expertise: string[];
  writing_samples: string[];
  opinions: string[];
}

interface StatsSnapshot {
  total_chunks: number;
  tags: string[];
}

interface UsageSnapshot {
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  calls_this_week: number;
  cost_this_week: number;
}

// ── Helper ────────────────────────────────────────────────────────────────────

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0 || !parts[0]) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// ── Skeleton bar ──────────────────────────────────────────────────────────────

function SkeletonBar({ w }: { w: string }) {
  return <div className={`bg-surface-container animate-pulse rounded h-3.5 ${w}`} />;
}

// ── Arrow icon (for card link rows) ──────────────────────────────────────────

function ArrowRight() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M3 7h8M7 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SettingsHubPage() {
  const api = useApi();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  const [profile, setProfile] = useState<ProfileSnapshot | null>(null);
  const [stats, setStats] = useState<StatsSnapshot | null>(null);
  const [usage, setUsage] = useState<UsageSnapshot | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [usageLoading, setUsageLoading] = useState(true);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => setUser(user));
  }, []);

  useEffect(() => {
    async function loadProfile() {
      try {
        const res = await api.getProfile();
        const data = await res.json();
        const p = data.profile ?? {};
        setProfile({
          name: p.name ?? "",
          role: p.role ?? "",
          bio: p.bio ?? "",
          location: p.location ?? "",
          voice_descriptors: p.voice_descriptors ?? [],
          words_to_avoid: p.words_to_avoid ?? [],
          writing_rules: p.writing_rules ?? [],
          topics_of_expertise: p.topics_of_expertise ?? [],
          writing_samples: p.writing_samples ?? [],
          opinions: p.opinions ?? [],
        });
      } catch {
        setProfile(null);
      } finally {
        setProfileLoading(false);
      }
    }

    async function loadStats() {
      try {
        const res = await api.getStats();
        const data = await res.json();
        setStats({
          total_chunks: data.total_chunks ?? 0,
          tags: data.tags ?? [],
        });
      } catch {
        setStats(null);
      } finally {
        setStatsLoading(false);
      }
    }

    async function loadUsage() {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        const headers: Record<string, string> = {};
        if (session?.access_token) {
          headers["Authorization"] = `Bearer ${session.access_token}`;
        }
        const res = await fetch(`${API}/usage/me`, { headers });
        if (!res.ok) throw new Error("Failed");
        const data = await res.json();
        setUsage({
          total_calls: data.total_calls ?? 0,
          total_input_tokens: data.total_input_tokens ?? 0,
          total_output_tokens: data.total_output_tokens ?? 0,
          total_cost_usd: data.total_cost_usd ?? 0,
          calls_this_week: data.calls_this_week ?? 0,
          cost_this_week: data.cost_this_week ?? 0,
        });
      } catch {
        setUsage(null);
      } finally {
        setUsageLoading(false);
      }
    }

    loadProfile();
    loadStats();
    loadUsage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSignOut() {
    setSigningOut(true);
    try {
      await supabase.auth.signOut();
      router.push("/sign-in");
    } catch {
      setSigningOut(false);
    }
  }

  // ── Profile card ────────────────────────────────────────────────────────────

  const profileCard = (
    <Link href="/settings/profile" className="block h-full">
      <div className="bg-surface-container-low rounded-2xl p-6 h-full flex flex-col gap-4 hover:bg-surface-container transition-colors duration-200 cursor-pointer">
        <p className="label-caps text-secondary">Profile</p>
        <div className="flex-1 flex flex-col gap-3">
          {profileLoading ? (
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-surface-container animate-pulse shrink-0" />
                <div className="flex flex-col gap-2 flex-1">
                  <SkeletonBar w="w-2/3" />
                  <SkeletonBar w="w-1/2" />
                </div>
              </div>
              <SkeletonBar w="w-full" />
              <SkeletonBar w="w-4/5" />
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                  <span className="text-primary font-medium text-[14px]">
                    {profile?.name ? getInitials(profile.name) : "?"}
                  </span>
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className="text-on-surface font-medium text-[14px] leading-snug">
                    {profile?.name || "No name set"}
                  </span>
                  <span className="text-secondary text-[12px]">
                    {profile?.role || "No role set"}
                  </span>
                  {profile?.location && (
                    <span className="text-outline text-[11px]">{profile.location}</span>
                  )}
                </div>
              </div>
              {profile?.bio && (
                <p className="text-[12px] text-secondary leading-relaxed line-clamp-2">
                  {profile.bio}
                </p>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 text-primary text-[13px] font-medium">
          Edit profile <ArrowRight />
        </div>
      </div>
    </Link>
  );

  // ── Voice & Fingerprint card ─────────────────────────────────────────────────

  const voiceCard = (
    <Link href="/settings/profile" className="block h-full">
      <div className="bg-surface-container-low rounded-2xl p-6 h-full flex flex-col gap-4 hover:bg-surface-container transition-colors duration-200 cursor-pointer">
        <p className="label-caps text-secondary">Voice &amp; Fingerprint</p>
        <div className="flex-1 flex flex-col gap-3">
          {profileLoading ? (
            <div className="flex flex-col gap-2.5">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="flex items-center justify-between">
                  <SkeletonBar w="w-1/2" />
                  <div className="bg-surface-container animate-pulse rounded h-3.5 w-8" />
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col gap-2.5">
              {[
                { label: "Phrases you use", count: profile?.voice_descriptors.length ?? 0 },
                { label: "Words to avoid", count: profile?.words_to_avoid.length ?? 0 },
                { label: "Writing rules", count: profile?.writing_rules.filter(Boolean).length ?? 0 },
                { label: "Expertise topics", count: profile?.topics_of_expertise.length ?? 0 },
              ].map(({ label, count }) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-[13px] text-secondary">{label}</span>
                  <span
                    className={`text-[13px] font-medium tabular-nums ${
                      count > 0 ? "text-primary" : "text-outline-variant"
                    }`}
                  >
                    {count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 text-primary text-[13px] font-medium">
          Edit fingerprint <ArrowRight />
        </div>
      </div>
    </Link>
  );

  // ── Writing Samples card ─────────────────────────────────────────────────────

  const samplesCard = (
    <Link href="/settings/profile" className="block h-full">
      <div className="bg-surface-container-low rounded-2xl p-6 h-full flex flex-col gap-4 hover:bg-surface-container transition-colors duration-200 cursor-pointer">
        <p className="label-caps text-secondary">Writing Samples</p>
        <div className="flex-1 flex flex-col gap-3">
          {profileLoading ? (
            <div className="flex flex-col gap-2">
              <SkeletonBar w="w-1/4" />
              <SkeletonBar w="w-3/4" />
              <SkeletonBar w="w-2/3" />
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {(() => {
                const count = profile?.writing_samples.filter(Boolean).length ?? 0;
                return (
                  <>
                    <span className="text-[32px] font-headline text-on-surface leading-none">
                      {count}
                    </span>
                    <p className="text-[13px] text-secondary leading-relaxed">
                      {count === 1
                        ? "writing sample teaching Contendo your rhythm."
                        : "writing samples teaching Contendo your rhythm."}
                    </p>
                    {count === 0 && (
                      <p className="text-[12px] text-outline mt-1">
                        Add at least one real sample for best results.
                      </p>
                    )}
                  </>
                );
              })()}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 text-primary text-[13px] font-medium">
          {profile?.writing_samples.filter(Boolean).length === 0 ? "Add samples" : "Edit samples"}{" "}
          <ArrowRight />
        </div>
      </div>
    </Link>
  );

  // ── Memory card ──────────────────────────────────────────────────────────────

  const memoryCard = (
    <Link href="/library" className="block h-full">
      <div className="bg-surface-container-low rounded-2xl p-6 h-full flex flex-col gap-4 hover:bg-surface-container transition-colors duration-200 cursor-pointer">
        <p className="label-caps text-secondary">Memory</p>
        <div className="flex-1 flex flex-col gap-3">
          {statsLoading ? (
            <div className="flex flex-col gap-2">
              <div className="bg-surface-container animate-pulse rounded h-10 w-1/3" />
              <SkeletonBar w="w-2/3" />
              <SkeletonBar w="w-1/2" />
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <span className="text-[40px] font-headline text-on-surface leading-none">
                {(stats?.total_chunks ?? 0).toLocaleString()}
              </span>
              <p className="text-[13px] text-secondary">
                knowledge chunks stored
              </p>
              <p className="text-[12px] text-outline">
                {stats?.tags.length ?? 0} unique tags &middot; Clear / export options coming soon
              </p>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 text-primary text-[13px] font-medium">
          Open library <ArrowRight />
        </div>
      </div>
    </Link>
  );

  // ── Account card ─────────────────────────────────────────────────────────────

  const accountCard = (
    <div className="bg-surface-container-low rounded-2xl p-6 h-full flex flex-col gap-4">
      <p className="label-caps text-secondary">Account</p>
      <div className="flex-1 flex flex-col gap-4">
        <div className="flex items-center gap-3">
          {user?.user_metadata?.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={user.user_metadata.avatar_url}
              alt={user.user_metadata?.full_name ?? "Avatar"}
              className="w-10 h-10 rounded-full object-cover shrink-0"
            />
          ) : (
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
              <span className="text-primary text-[13px] font-medium">
                {user?.user_metadata?.full_name
                  ? getInitials(user.user_metadata.full_name)
                  : "?"}
              </span>
            </div>
          )}
          <div className="flex flex-col gap-0.5 min-w-0">
            <span className="text-on-surface font-medium text-[14px] truncate">
              {user?.user_metadata?.full_name ?? user?.user_metadata?.name ?? ""}
            </span>
            <span className="text-secondary text-[12px] truncate">
              {user?.email ?? ""}
            </span>
          </div>
        </div>

        <div className="flex flex-col gap-2 mt-1">
          <button
            type="button"
            onClick={handleSignOut}
            disabled={signingOut}
            className="w-full py-2 px-4 rounded-xl bg-surface-container text-on-surface text-[13px] font-medium hover:bg-[#e5e7e6] transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-left"
          >
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
          <p className="text-[11px] text-outline-variant">
            Delete account — coming soon
          </p>
        </div>
      </div>
    </div>
  );

  // ── Usage & Tokens card ──────────────────────────────────────────────────────

  const totalTokens = (usage?.total_input_tokens ?? 0) + (usage?.total_output_tokens ?? 0);
  const generateCalls =
    usage?.total_calls != null ? usage.total_calls : null;

  const usageCard = (
    <div className="bg-surface-container-low rounded-2xl p-6 h-full flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <p className="label-caps text-secondary">Usage &amp; Tokens</p>
        {/* Pulse icon */}
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true" className="text-primary opacity-70">
          <path d="M1 6h2l1.5-4L7 10l1.5-4H11" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>

      <div className="flex-1 flex flex-col gap-3">
        {usageLoading ? (
          <div className="flex flex-col gap-2.5">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex items-center justify-between">
                <SkeletonBar w="w-1/2" />
                <div className="bg-surface-container animate-pulse rounded h-3.5 w-12" />
              </div>
            ))}
          </div>
        ) : usage == null ? (
          <p className="text-[12px] text-outline">Usage data unavailable.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {/* Primary stats — leads with posts, not cost */}
            <div className="flex items-start justify-between gap-4">
              <div className="flex flex-col gap-0.5">
                <span className="text-[11px] text-secondary uppercase tracking-wide">Posts generated</span>
                <span className="text-[28px] font-headline text-on-surface leading-none">
                  {(generateCalls ?? 0).toLocaleString()}
                </span>
              </div>
              <div className="flex flex-col gap-0.5 text-right">
                <span className="text-[11px] text-secondary uppercase tracking-wide">This week</span>
                <span className="text-[28px] font-headline text-on-surface leading-none">
                  {usage.calls_this_week.toLocaleString()}
                </span>
              </div>
            </div>

            {/* Token count */}
            <p className="text-[13px] text-secondary">
              Estimated tokens used:{" "}
              <span className="text-on-surface font-medium tabular-nums">
                {totalTokens.toLocaleString()}
              </span>
            </p>

            {/* Cost — de-emphasised */}
            <p className="text-[11px] text-outline" style={{ fontSize: "0.78rem" }}>
              API cost to date: ${usage.total_cost_usd.toFixed(4)}
            </p>
          </div>
        )}
      </div>
    </div>
  );

  // ── Integrations card ────────────────────────────────────────────────────────

  const integrationsCard = (
    <div className="bg-surface-container-low rounded-2xl p-6 h-full flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <p className="label-caps text-secondary">Integrations</p>
        <span className="text-[10px] uppercase tracking-widest font-medium text-primary bg-primary/10 px-2 py-0.5 rounded-full">
          Soon
        </span>
      </div>
      <div className="flex-1 flex flex-col gap-2">
        <p className="text-[12px] text-secondary mb-1">
          Connect your knowledge sources directly:
        </p>
        {[
          "Notion",
          "Google Drive",
          "RSS feeds",
          "LinkedIn saves",
          "GitHub READMEs",
          "Pocket",
        ].map((item) => (
          <div key={item} className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-outline-variant shrink-0" />
            <span className="text-[13px] text-secondary">{item}</span>
          </div>
        ))}
      </div>
    </div>
  );

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      {/* Page header */}
      <p className="label-caps text-secondary mb-2">YOUR WORKSPACE</p>
      <h1 className="font-headline text-[32px] text-on-surface mb-2">Settings</h1>
      <p className="text-[14px] text-secondary mb-10">
        Manage your profile, voice, memory, and account preferences.
      </p>

      {/* Cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {profileCard}
        {voiceCard}
        {samplesCard}
        {memoryCard}
        {usageCard}
        {accountCard}
        {integrationsCard}
      </div>
    </div>
  );
}
