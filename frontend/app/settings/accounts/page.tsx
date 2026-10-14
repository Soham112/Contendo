"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useApi } from "@/lib/api";
import { PaywallError } from "@/lib/commerce-api";
import type { Paywall } from "@/lib/billing";
import type { ConnectedAccount, PlatformRules } from "@/lib/publishing";
import UpgradeScreen from "@/components/billing/UpgradeScreen";

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
  const [paywall, setPaywall] = useState<Paywall | null>(null);

  const load = useCallback(async () => {
    try {
      const [loadedAccounts, loadedPlatforms] = await Promise.all([api.getConnectedAccounts(), api.getPlatformRules()]);
      setAccounts(loadedAccounts);
      setPlatforms(loadedPlatforms);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load your accounts.");
      setAccounts([]);
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

  if (accounts === null) return <p className="text-secondary text-[0.9375rem]">Loading…</p>;

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
        <p role="alert" className="text-[0.9375rem] text-error">
          {error}
        </p>
      )}

      <section>
        <h2 className="label-caps text-secondary">Your accounts</h2>
        {accounts.length === 0 ? (
          <p className="mt-3 text-[0.9375rem] text-secondary">
            No accounts yet. Connect one below and your posts can be published for you.
          </p>
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
                    <button
                      type="button"
                      disabled={!!busy}
                      onClick={() => connect(account.platform)}
                      className="btn-primary text-white rounded-md px-4 py-2.5 text-[0.875rem] font-medium disabled:opacity-50"
                    >
                      Reconnect
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={!!busy}
                    onClick={() => disconnect(account)}
                    className="py-2.5 text-[0.875rem] text-secondary hover:text-on-surface disabled:opacity-50"
                  >
                    {busy === `disconnect:${account.id}` ? "Disconnecting…" : "Disconnect"}
                  </button>
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
            <button
              key={platform.platform}
              type="button"
              disabled={!!busy}
              onClick={() => connect(platform.platform)}
              className="rounded-lg bg-surface-container-low hover:bg-surface-container-highest px-4 py-4 text-left text-[0.9375rem] text-on-surface transition-colors disabled:opacity-50"
            >
              {busy === `connect:${platform.platform}` ? "Opening…" : `Connect ${platform.label}`}
            </button>
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
        <Suspense fallback={<p className="text-secondary text-[0.9375rem]">Loading…</p>}>
          <Accounts />
        </Suspense>
      </div>
    </div>
  );
}
