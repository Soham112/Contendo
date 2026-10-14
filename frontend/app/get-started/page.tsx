"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useApi } from "@/lib/api";
import { resolveNicheParam, type NicheOptions, type Segment, type SegmentAnswer } from "@/lib/account";
import SegmentQuestion from "@/components/onboarding/SegmentQuestion";
import BusinessSetup from "@/components/onboarding/BusinessSetup";

const Loading = () => <p className="text-center text-[0.9375rem] text-secondary">Loading…</p>;

const SAVED_WITHOUT_MEMORY =
  "Your answers are saved, but we couldn't add them to your memory. Save again to finish.";

function GetStarted() {
  const api = useApi();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [options, setOptions] = useState<NicheOptions | null>(null);
  const [loadError, setLoadError] = useState("");
  const [step, setStep] = useState<"segment" | "business">("segment");
  const [presetNiche, setPresetNiche] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getNicheOptions()
      .then((loaded) => {
        setOptions(loaded);
        // A niche in the URL (from a landing page) is used only if the backend lists it.
        const niche = resolveNicheParam(searchParams.get("niche"), loaded);
        setPresetNiche(niche);
        if (niche || searchParams.get("segment") === "business") setStep("business");
      })
      .catch((e: Error) => setLoadError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Individuals with no voice profile yet go on to the first-post flow.
  async function leave(segment: Segment | null) {
    if (segment === "business") {
      router.push("/create");
      return;
    }
    const res = await api.getProfile();
    if (!res.ok) throw new Error("We couldn’t load your profile. Please try again.");
    const hasProfile = Boolean((await res.json()).has_profile);
    router.push(hasProfile ? "/create" : "/first-post");
  }

  async function run(action: () => Promise<Segment | null>) {
    setBusy(true);
    setError("");
    try {
      await leave(await action());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
      setBusy(false);
    }
  }

  function choose(segment: Segment) {
    if (segment === "business") {
      setError("");
      setStep("business");
      return;
    }
    run(async () => (await api.saveSegment({ segment })).segment);
  }

  function saveBusiness(answer: SegmentAnswer) {
    run(async () => {
      const account = await api.saveSegment(answer);
      if (account.memory_saved === false) throw new Error(SAVED_WITHOUT_MEMORY);
      return account.segment;
    });
  }

  if (loadError) {
    return (
      <p role="alert" className="text-[0.9375rem] text-error text-center">
        {loadError}
      </p>
    );
  }
  if (!options) return <Loading />;

  return step === "segment" ? (
    <SegmentQuestion
      onChoose={choose}
      onSkip={() => run(async () => (await api.skipSegment()).segment)}
      busy={busy}
      error={error}
    />
  ) : (
    <BusinessSetup
      options={options}
      initialNiche={presetNiche}
      busy={busy}
      error={error}
      onBack={() => setStep("segment")}
      onSubmit={saveBusiness}
    />
  );
}

export default function GetStartedPage() {
  return (
    <main className="min-h-screen bg-background px-4 py-10 sm:py-16 flex justify-center">
      <div className="w-full max-w-[36rem]">
        <p className="font-headline italic text-[1.25rem] text-on-surface text-center mb-10">Contendo</p>
        <div className="bg-surface-container-lowest rounded-2xl shadow-card px-5 py-8 sm:px-10 sm:py-10">
          <Suspense fallback={<Loading />}>
            <GetStarted />
          </Suspense>
        </div>
      </div>
    </main>
  );
}
