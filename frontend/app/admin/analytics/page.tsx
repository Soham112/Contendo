"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import supabase from "@/lib/supabase";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ADMIN_SECRET = process.env.NEXT_PUBLIC_ADMIN_SECRET ?? "";
const ADMIN_EMAIL = "soham112000@gmail.com";

// ── Types ─────────────────────────────────────────────────────────────────────

interface EventBreakdownItem {
  event_type: string;
  count: number;
  unique_users: number;
  percentage: number;
}

interface PageViewItem {
  page_url: string;
  count: number;
  unique_users: number;
  percentage: number;
}

interface ButtonClickItem {
  button_name: string;
  count: number;
  unique_users: number;
  percentage: number;
}

interface DailyEvent {
  date: string;
  count: number;
}

interface AnalyticsData {
  total_events: number;
  unique_users: number;
  date_range: { start: string; end: string };
  event_breakdown: EventBreakdownItem[];
  page_views: PageViewItem[];
  button_clicks: ButtonClickItem[];
  feature_funnels: {
    first_post_flow: Record<string, number>;
    feed_memory: { shown: number; completed: number; skipped: number; completion_rate: number };
  };
  daily_events: DailyEvent[];
  retention: {
    cohort_1_post: number;
    cohort_2_posts: number;
    cohort_5_posts: number;
    retention_rate_2plus: number;
  };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number): string {
  return n.toLocaleString();
}

function fmtDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function Skeleton({ className }: { className: string }) {
  return <div className={`bg-surface-container animate-pulse rounded-lg ${className}`} />;
}

// ── Section heading ───────────────────────────────────────────────────────────

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-semibold uppercase tracking-widest text-secondary opacity-70 mb-3">
      {children}
    </h2>
  );
}

// ── Metric card ───────────────────────────────────────────────────────────────

function MetricCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-surface-container-low rounded-xl p-5 flex flex-col gap-1">
      <span className="text-xs font-medium uppercase tracking-widest text-secondary opacity-70">
        {label}
      </span>
      <span className="font-headline text-3xl text-on-surface">{typeof value === "number" ? fmt(value) : value}</span>
      {sub && <span className="text-xs text-secondary opacity-60">{sub}</span>}
    </div>
  );
}

// ── Horizontal bar ────────────────────────────────────────────────────────────

function HBar({ label, count, total, sub }: { label: string; count: number; total: number; sub?: string }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="flex flex-col gap-1 py-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-on-surface font-medium truncate max-w-[60%]">{label}</span>
        <span className="text-secondary shrink-0 ml-2">{fmt(count)}{sub ? ` · ${sub}` : ""}</span>
      </div>
      <div className="h-1.5 rounded-full bg-surface-container overflow-hidden">
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${pct}%`, transition: "width 0.4s ease" }}
        />
      </div>
    </div>
  );
}

// ── Daily trend (SVG) ─────────────────────────────────────────────────────────

function DailyTrend({ data }: { data: DailyEvent[] }) {
  const visible = data.slice(-30);
  const max = Math.max(...visible.map((d) => d.count), 1);
  const barW = 10;
  const gap = 4;
  const chartH = 72;
  const totalW = visible.length * (barW + gap) - gap;

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${totalW} ${chartH + 20}`}
      preserveAspectRatio="none"
      aria-label="Daily events bar chart"
    >
      {visible.map((d, i) => {
        const barH = Math.max(2, (d.count / max) * chartH);
        const x = i * (barW + gap);
        const y = chartH - barH;
        const isLast = i === visible.length - 1;
        return (
          <g key={d.date}>
            <rect x={x} y={y} width={barW} height={barH} rx={2} fill={isLast ? "#58614f" : "#c5cac4"} />
            {(i === 0 || i === Math.floor(visible.length / 2) || isLast) && (
              <text x={x + barW / 2} y={chartH + 14} textAnchor="middle" fontSize={7} fill="#645e57" opacity={0.7}>
                {fmtDate(d.date)}
              </text>
            )}
            <title>{`${d.date}: ${d.count} event${d.count !== 1 ? "s" : ""}`}</title>
          </g>
        );
      })}
    </svg>
  );
}

// ── Funnel step row ───────────────────────────────────────────────────────────

function FunnelRow({ label, count, base }: { label: string; count: number; base: number }) {
  const pct = base > 0 ? Math.round((count / base) * 100) : 0;
  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="text-sm text-secondary w-36 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-surface-container overflow-hidden">
        <div className="h-full rounded-full bg-primary/70" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm text-on-surface w-10 text-right">{fmt(count)}</span>
      <span className="text-xs text-secondary opacity-60 w-10 text-right">{pct}%</span>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AnalyticsDashboard() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(30);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  // Auth guard
  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (user?.email === ADMIN_EMAIL) {
        setAuthorized(true);
      } else {
        router.replace("/");
      }
    });
  }, [router]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/admin/analytics-data?days=${days}`, {
        headers: { "x-admin-secret": ADMIN_SECRET },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json() as AnalyticsData;
      setData(json);
      setLastRefresh(new Date());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [days]);

  // Fetch on mount + days change
  useEffect(() => {
    if (!authorized) return;
    fetchData();
  }, [authorized, fetchData]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    if (!authorized) return;
    const id = setInterval(fetchData, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [authorized, fetchData]);

  if (authorized === null) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <span className="text-sm text-secondary opacity-60">Checking access…</span>
      </div>
    );
  }

  const firstPostFlow = data?.feature_funnels?.first_post_flow ?? {};
  const feedMemory = data?.feature_funnels?.feed_memory;
  const retention = data?.retention;
  const totalEvents = data?.total_events ?? 0;
  const totalPageViews = data?.page_views?.reduce((s, r) => s + r.count, 0) ?? 0;
  const totalClicks = data?.button_clicks?.reduce((s, r) => s + r.count, 0) ?? 0;

  // First-post funnel steps in order
  const fpSteps: [string, string][] = [
    ["step_0", "Topic (Step 0)"],
    ["step_1", "Role (Step 1)"],
    ["step_2", "Experience (Step 2)"],
    ["step_3", "Opinion (Step 3)"],
    ["step_4", "Audience (Step 4)"],
    ["step_5", "Voice (Step 5)"],
    ["step_complete", "Draft Ready"],
  ];
  const fpBase = firstPostFlow["step_0"] ?? 0;

  return (
    <div className="min-h-screen bg-background px-4 md:px-6 py-10 max-w-5xl mx-auto">

      {/* ── Header ── */}
      <div className="mb-8 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-headline text-3xl text-on-surface mb-1">Analytics</h1>
          <p className="text-sm text-secondary opacity-60">
            User behaviour tracking · last {days} days
          </p>
        </div>

        {/* Controls row */}
        <div
          className="flex items-center gap-3 px-4 py-2 rounded-full"
          style={{
            background: "rgba(255,255,255,0.8)",
            backdropFilter: "blur(20px)",
            boxShadow: "0 2px 8px rgba(47,51,51,0.08)",
          }}
        >
          {/* Period selector */}
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="text-sm text-on-surface bg-transparent outline-none cursor-pointer"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>

          <div className="w-px h-4 bg-outline-variant opacity-40" />

          {/* Refresh */}
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-1.5 text-sm text-primary font-medium disabled:opacity-50"
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              className={loading ? "animate-spin" : ""}
            >
              <path d="M14 8a6 6 0 1 1-1.76-4.24" />
              <path d="M14 3v5h-5" />
            </svg>
            Refresh
          </button>

          {lastRefresh && (
            <span className="text-xs text-secondary opacity-50">
              {lastRefresh.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm mb-6">
          Failed to load: {error}
        </div>
      )}

      {/* ── Key metrics ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        {data ? (
          <>
            <MetricCard label="Total events" value={data.total_events} />
            <MetricCard label="Unique users" value={data.unique_users} />
            <MetricCard
              label="Date range"
              value={`${fmtDate(data.date_range.start)}`}
              sub={`→ ${fmtDate(data.date_range.end)}`}
            />
            <MetricCard
              label="Auto-refresh"
              value="5 min"
              sub={lastRefresh ? `Last: ${lastRefresh.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "—"}
            />
          </>
        ) : (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)
        )}
      </div>

      {/* ── Daily trend ── */}
      <div className="bg-surface-container-low rounded-xl p-5 mb-6">
        <SectionHeading>Daily events</SectionHeading>
        {data ? (
          data.daily_events.every((d) => d.count === 0) ? (
            <p className="text-sm text-secondary opacity-60">No events in this period.</p>
          ) : (
            <DailyTrend data={data.daily_events} />
          )
        ) : (
          <Skeleton className="h-24" />
        )}
      </div>

      {/* ── Event breakdown + Page views ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Event breakdown */}
        <div className="bg-surface-container-low rounded-xl p-5">
          <SectionHeading>Event breakdown</SectionHeading>
          {data ? (
            data.event_breakdown.length === 0 ? (
              <p className="text-sm text-secondary opacity-60">No events yet.</p>
            ) : (
              <div className="divide-y divide-outline-variant/20">
                {data.event_breakdown.map((item) => (
                  <HBar
                    key={item.event_type}
                    label={item.event_type}
                    count={item.count}
                    total={totalEvents}
                    sub={`${item.unique_users} users · ${item.percentage}%`}
                  />
                ))}
              </div>
            )
          ) : (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-8" />)}
            </div>
          )}
        </div>

        {/* Page views */}
        <div className="bg-surface-container-low rounded-xl p-5">
          <SectionHeading>Top pages</SectionHeading>
          {data ? (
            data.page_views.length === 0 ? (
              <p className="text-sm text-secondary opacity-60">No page views yet.</p>
            ) : (
              <div className="divide-y divide-outline-variant/20">
                {data.page_views.slice(0, 8).map((item) => (
                  <HBar
                    key={item.page_url}
                    label={item.page_url}
                    count={item.count}
                    total={totalPageViews}
                    sub={`${item.unique_users} users`}
                  />
                ))}
              </div>
            )
          ) : (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-8" />)}
            </div>
          )}
        </div>
      </div>

      {/* ── Button clicks ── */}
      <div className="bg-surface-container-low rounded-xl p-5 mb-6">
        <SectionHeading>Most-clicked buttons</SectionHeading>
        {data ? (
          data.button_clicks.length === 0 ? (
            <p className="text-sm text-secondary opacity-60">No clicks recorded yet.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 divide-y divide-outline-variant/20 sm:divide-y-0">
              {data.button_clicks.slice(0, 10).map((item) => (
                <HBar
                  key={item.button_name}
                  label={item.button_name}
                  count={item.count}
                  total={totalClicks}
                  sub={`${item.unique_users} users`}
                />
              ))}
            </div>
          )
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-8" />)}
          </div>
        )}
      </div>

      {/* ── Feature funnels ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* First-post flow */}
        <div className="bg-surface-container-low rounded-xl p-5">
          <SectionHeading>First-post flow funnel</SectionHeading>
          {data ? (
            fpBase === 0 ? (
              <p className="text-sm text-secondary opacity-60">No first-post data yet.</p>
            ) : (
              <div>
                {fpSteps.map(([key, label]) => (
                  <FunnelRow
                    key={key}
                    label={label}
                    count={firstPostFlow[key] ?? 0}
                    base={fpBase}
                  />
                ))}
              </div>
            )
          ) : (
            <div className="space-y-2">
              {Array.from({ length: 7 }).map((_, i) => <Skeleton key={i} className="h-7" />)}
            </div>
          )}
        </div>

        {/* Feed memory tour + Retention */}
        <div className="flex flex-col gap-6">
          {/* Feed memory */}
          <div className="bg-surface-container-low rounded-xl p-5">
            <SectionHeading>Feed memory tour</SectionHeading>
            {data && feedMemory ? (
              feedMemory.shown === 0 ? (
                <p className="text-sm text-secondary opacity-60">Tour not shown yet.</p>
              ) : (
                <div className="space-y-1">
                  <FunnelRow label="Tour shown" count={feedMemory.shown} base={feedMemory.shown} />
                  <FunnelRow label="Completed" count={feedMemory.completed} base={feedMemory.shown} />
                  <FunnelRow label="Skipped" count={feedMemory.skipped} base={feedMemory.shown} />
                  <p className="text-xs text-secondary opacity-60 mt-2">
                    Completion rate: {Math.round(feedMemory.completion_rate * 100)}%
                  </p>
                </div>
              )
            ) : (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-7" />)}
              </div>
            )}
          </div>

          {/* Retention */}
          <div className="bg-surface-container-low rounded-xl p-5">
            <SectionHeading>Retention cohorts</SectionHeading>
            {data && retention ? (
              retention.cohort_1_post === 0 ? (
                <p className="text-sm text-secondary opacity-60">No generation data yet.</p>
              ) : (
                <div className="space-y-1">
                  <FunnelRow label="Generated 1+ post" count={retention.cohort_1_post} base={retention.cohort_1_post} />
                  <FunnelRow label="Generated 2+ posts" count={retention.cohort_2_posts} base={retention.cohort_1_post} />
                  <FunnelRow label="Power users (5+)" count={retention.cohort_5_posts} base={retention.cohort_1_post} />
                  <p className="text-xs text-secondary opacity-60 mt-2">
                    2+ retention: {Math.round(retention.retention_rate_2plus * 100)}%
                  </p>
                </div>
              )
            ) : (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-7" />)}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
