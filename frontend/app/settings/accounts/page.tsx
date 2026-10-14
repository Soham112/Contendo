"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useApi } from "@/lib/api";
import { PaywallError } from "@/lib/commerce-api";
import type { Paywall } from "@/lib/billing";
import type { ConnectedAccount, PlatformRules } from "@/lib/publishing";
import UpgradeScreen from "@/components/billing/UpgradeScreen";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/card";
import { EmptyState, ErrorState } from "@/components/ui/states";

const STATUS: Record<ConnectedAccount["status"], { text: string; tone: string }> = {
  connected: { text: "Connected", tone: "text-primary" },
  needs_reconnect: { text: "Needs reconnecting", tone: "text-error" },
  disconnected: { text: "Disconnected", tone: "text-secondary" },
};

function Accounts() {
  const api = useApi();
  const searchParams = useSearchParams();
  const connectStatus = searchParams.get("connect_status");

  const [accounts, setAccounts] = useState<ConnectedAccount[] | null>(null);
  const [platforms, setPlatforms] = useState<PlatformRules[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  // A failed first load: shown instead of the lists, never as "no accounts".
  const [loadError, setLoadError] = useState("");
  const [paywall, setPaywall] = useState<Paywall | null>(null);

  const load = useCallback(async () => {
    setLoadError("");
    try {
      const [loadedAccounts, loadedPlatforms] = await Promise.all([api.getConnectedAccounts(), api.getPlatformRules()]);
      setAccounts(loadedAccounts);
      setPlatforms(loadedPlatforms);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "We couldn't load your accounts. Please try again.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function run(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError("");
    try {
      await action();
    } catch (e) {
      if (e instanceof PaywallError) setPaywall(e.paywall);
      else setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
    } finally {
      setBusy("");
    }
  }

  const connect = (platform: string) =>
    run(`connect:${platform}`, async () => {
      window.location.assign((await api.connectAccount(platform)).url);
    });

  const disconnect = (account: ConnectedAccount) =>
    run(`disconnect:${account.id}`, async () => {
      await api.disconnectAccount(account.id);
      await load();
    });

  if (accounts === null && loadError) return <ErrorState message={loadError} onRetry={load} />;
  if (accounts === null) return (
    <div role="status" aria-label="Loading your accounts" className="flex flex-col gap-3">
      <Skeleton className="h-3 w-28" />
      <Skeleton className="h-16 w-full rounded-2xl" />
      <Skeleton className="h-16 w-full rounded-2xl" />
    </div>
  );

  return (
    <div className="flex flex-col gap-8">
      {connectStatus === "success" && (
        <p role="status" className="rounded-lg bg-primary-container text-on-primary-fixed px-4 py-3 text-[0.9375rem]">
          Account connected.
        </p>
      )}
      {(connectStatus === "error" || connectStatus === "cancelled") && (
        <p role="status" className="rounded-lg bg-surface-container-low text-secondary px-4 py-3 text-[0.9375rem]">
          The account wasn&apos;t connected. You can try again below.
        </p>
      )}
      {error && (
        <ErrorState message={error} />
      )}

      <section>
        <h2 className="label-caps text-secondary">Your accounts</h2>
        {accounts.length === 0 ? (
          <EmptyState
            className="mt-3"
            title="No accounts connected yet"
            body="Connect one below and Contendo can publish your posts for you."
          />
        ) : (
          <ul className="mt-3 flex flex-col gap-3">
            {accounts.map((account) => (
              <li
                key={account.id}
                className="rounded-lg bg-surface-container-lowest px-4 py-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="text-[1rem] text-on-surface font-medium truncate">
                    {account.label}
                    {account.display_name ? ` · ${account.display_name}` : ""}
                  </p>
                  <p className={`mt-0.5 text-[0.875rem] ${STATUS[account.status].tone}`}>{STATUS[account.status].text}</p>
                </div>
                <div className="flex gap-4 shrink-0">
                  {account.status === "needs_reconnect" && (
                    <Button size="sm" disabled={!!busy} onClick={() => connect(account.platform)}>
                      Reconnect
                    </Button>
                  )}
                  <Button variant="secondary" size="sm" disabled={!!busy && busy !== `disconnect:${account.id}`} loading={busy === `disconnect:${account.id}`} onClick={() => disconnect(account)}>
                    Disconnect
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="label-caps text-secondary">Connect an account</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {platforms.map((platform) => (
            <Button
              key={platform.platform}
              variant="secondary"
              size="lg"
              className="justify-start bg-surface-container-lowest"
              disabled={!!busy && busy !== `connect:${platform.platform}`}
              loading={busy === `connect:${platform.platform}`}
              onClick={() => connect(platform.platform)}
            >
              Connect {platform.label}
            </Button>
          ))}
        </div>
        <p className="mt-4 text-[0.875rem] leading-relaxed text-secondary">
          You sign in on the platform itself. We never see or store your password, and you can disconnect at any time.
        </p>
      </section>

      {paywall && <UpgradeScreen code={paywall.code} message={paywall.message} onClose={() => setPaywall(null)} />}
    </div>
  );
}

export default function AccountsPage() {
  return (
    <div className="max-w-[40rem] mx-auto">
      <h1 className="font-headline text-[2rem] sm:text-[2.5rem] text-on-surface leading-tight">Connected accounts</h1>
      <div className="mt-8">
        <Suspense fallback={<Skeleton className="h-16 w-full rounded-2xl" />}>
          <Accounts />
        </Suspense>
      </div>
    </div>
  );
}
