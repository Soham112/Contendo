"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import supabase from "@/lib/supabase";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ADMIN_SECRET = process.env.NEXT_PUBLIC_ADMIN_SECRET ?? "";
const ADMIN_EMAIL = "soham112000@gmail.com";

// ── Types ─────────────────────────────────────────────────────────────────────

interface DailyBucket {
  date: string;
  count: number;
}

interface TopUser {
  user_id: string;
  call_count: number;
  total_tokens: number;
  total_cost: number;
}

interface UsageData {
  distinct_users: number;
  calls: { today: number; this_week: number; all_time: number };
  cost_usd: { today: number; this_week: number; all_time: number };
  daily: DailyBucket[];
  top_users: TopUser[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number): string {
  return n.toLocaleString();
}

function fmtCost(n: number): string {
  if (n === 0) return "$0.00";
  if (n < 0.01) return `$${n.toFixed(6)}`;
  return `$${n.toFixed(4)}`;
}

function fmtDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function Skeleton({ className }: { className: string }) {
  return <div className={`bg-surface-container animate-pulse rounded ${className}`} />;
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  label,
  today,
  week,
  allTime,
  isCost,
}: {
  label: string;
  today: number;
  week: number;
  allTime: number;
  isCost?: boolean;
}) {
  const fmt_ = isCost ? fmtCost : fmt;
  return (
    <div className="bg-surface-container-low rounded-xl p-5 flex flex-col gap-3">
      <span className="text-xs font-medium uppercase tracking-widest text-secondary opacity-70">
        {label}
      </span>
      <div className="grid grid-cols-3 gap-2">
        {[
          { period: "Today", value: today },
          { period: "This week", value: week },
          { period: "All time", value: allTime },
        ].map(({ period, value }) => (
          <div key={period} className="flex flex-col gap-0.5">
            <span className="text-xs text-secondary opacity-60">{period}</span>
            <span className="font-headline text-lg text-on-surface">{fmt_(value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Bar chart (pure SVG — no recharts dep) ────────────────────────────────────

function BarChart({ data }: { data: DailyBucket[] }) {
  const max = Math.max(...data.map((d) => d.count), 1);
  const barW = 14;
  const gap = 6;
  const chartH = 80;
  const totalW = data.length * (barW + gap) - gap;

  return (
    <div className="bg-surface-container-low rounded-xl p-5">
      <span className="text-xs font-medium uppercase tracking-widest text-secondary opacity-70 block mb-4">
        Calls per day — last 14 days
      </span>
      <svg
        width="100%"
        viewBox={`0 0 ${totalW} ${chartH + 20}`}
        preserveAspectRatio="xMidYMid meet"
        aria-label="Bar chart of API calls per day"
      >
        {data.map((d, i) => {
          const barH = max > 0 ? Math.max(2, (d.count / max) * chartH) : 2;
          const x = i * (barW + gap);
          const y = chartH - barH;
          const isToday = i === data.length - 1;
          return (
            <g key={d.date}>
              <rect
                x={x}
                y={y}
                width={barW}
                height={barH}
                rx={3}
                fill={isToday ? "#58614f" : "#c5cac4"}
              />
              {/* Show date label for first, middle, last */}
              {(i === 0 || i === 6 || i === 13) && (
                <text
                  x={x + barW / 2}
                  y={chartH + 14}
                  textAnchor="middle"
                  fontSize={8}
                  fill="#645e57"
                  opacity={0.7}
                >
                  {fmtDate(d.date)}
                </text>
              )}
              <title>{`${d.date}: ${d.count} call${d.count !== 1 ? "s" : ""}`}</title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Top users table ───────────────────────────────────────────────────────────

function TopUsersTable({ users }: { users: TopUser[] }) {
  return (
    <div className="bg-surface-container-low rounded-xl p-5">
      <span className="text-xs font-medium uppercase tracking-widest text-secondary opacity-70 block mb-4">
        Top users by cost
      </span>
      {users.length === 0 ? (
        <p className="text-sm text-secondary opacity-60">No data yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="text-left text-xs text-secondary opacity-60 border-b border-outline-variant">
                <th className="pb-2 font-medium">User ID</th>
                <th className="pb-2 font-medium text-right">Calls</th>
                <th className="pb-2 font-medium text-right">Tokens</th>
                <th className="pb-2 font-medium text-right">Cost</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u, i) => (
                <tr
                  key={u.user_id}
                  className={i < users.length - 1 ? "border-b border-outline-variant border-opacity-30" : ""}
                >
                  <td className="py-2 text-on-surface font-mono text-xs truncate max-w-[180px]">
                    {u.user_id}
                  </td>
                  <td className="py-2 text-right text-on-surface">{fmt(u.call_count)}</td>
                  <td className="py-2 text-right text-on-surface">{fmt(u.total_tokens)}</td>
                  <td className="py-2 text-right text-on-surface">{fmtCost(u.total_cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [data, setData] = useState<UsageData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Auth guard: only soham112000@gmail.com
  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (user?.email === ADMIN_EMAIL) {
        setAuthorized(true);
      } else {
        router.replace("/");
      }
    });
  }, [router]);

  // Fetch usage data once authorized
  useEffect(() => {
    if (!authorized) return;
    fetch(`${API}/admin/usage`, {
      headers: { "x-admin-secret": ADMIN_SECRET },
    })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<UsageData>;
      })
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [authorized]);

  if (authorized === null) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <span className="text-sm text-secondary opacity-60">Checking access…</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-4 md:px-6 py-10 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-headline text-3xl text-on-surface mb-1">Usage</h1>
        <p className="text-sm text-secondary opacity-60">
          Claude API call tracking across all users
        </p>
      </div>

      {error && (
        <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm mb-6">
          Failed to load: {error}
        </div>
      )}

      {/* KPI strip */}
      <div className="mb-3 flex items-center gap-2">
        {data ? (
          <span className="text-xs text-secondary opacity-60">
            {data.distinct_users} distinct user{data.distinct_users !== 1 ? "s" : ""}
          </span>
        ) : (
          <Skeleton className="h-3 w-24" />
        )}
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        {data ? (
          <>
            <StatCard
              label="API calls"
              today={data.calls.today}
              week={data.calls.this_week}
              allTime={data.calls.all_time}
            />
            <StatCard
              label="Estimated cost"
              today={data.cost_usd.today}
              week={data.cost_usd.this_week}
              allTime={data.cost_usd.all_time}
              isCost
            />
          </>
        ) : (
          <>
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
          </>
        )}
      </div>

      {/* Bar chart */}
      <div className="mb-6">
        {data ? <BarChart data={data.daily} /> : <Skeleton className="h-44" />}
      </div>

      {/* Top users */}
      {data ? (
        <TopUsersTable users={data.top_users} />
      ) : (
        <Skeleton className="h-48" />
      )}
    </div>
  );
}
