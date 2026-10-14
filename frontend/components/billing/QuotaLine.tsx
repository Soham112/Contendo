"use client";

import Link from "next/link";
import { quotaLine, type Entitlements } from "@/lib/billing";

/** How many posts are left this month, with the way to get more. */
export default function QuotaLine({ entitlements }: { entitlements: Entitlements | null }) {
  if (!entitlements) return null;
  const out = entitlements.generations_remaining === 0;
  return (
    <p className={`text-[0.8125rem] ${out ? "text-error" : "text-secondary"}`}>
      {quotaLine(entitlements)}
      {entitlements.plan === "free" && (
        <>
          {" · "}
          <Link href="/settings/billing" className="text-tertiary underline underline-offset-4 hover:text-tertiary-dim">
            See Pro
          </Link>
        </>
      )}
    </p>
  );
}
