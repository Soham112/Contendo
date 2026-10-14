"use client";
import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import supabase from '@/lib/supabase';
import { useApi, type GenerateResponse } from '@/lib/api';
import { resolveNicheParam, type Account, type NicheOptions, type Segment, type SegmentAnswer } from '@/lib/account';
import type { FirstPostBrief, OnboardingStep, StepOutcome } from '@/lib/onboarding-api';
import { generateOutcome, generateErrorMessage } from '@/lib/generate-outcome';
import { requestErrorMessage, requireResponse } from '@/lib/request-errors';
import RetryNotice from '@/components/RetryNotice';
import SegmentQuestion from './SegmentQuestion';
import BusinessSetup from './BusinessSetup';
import IndividualBrief from './IndividualBrief';
import FirstDraft from './FirstDraft';

type Screen = 'segment' | 'business' | 'individual' | 'generating' | 'draft';
export default function FirstPostFlow() {
  const api = useApi();
  const router = useRouter();
  const params = useSearchParams();
  const [account, setAccount] = useState<Account | null>(null);
  const [options, setOptions] = useState<NicheOptions | null>(null);
  const [screen, setScreen] = useState<Screen>('segment');
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [takes, setTakes] = useState<string[]>([]);
  const [suggesting, setSuggesting] = useState(false);
  const [brief, setBrief] = useState<FirstPostBrief>({ topic: '', story: '', format: 'linkedin post', take: '' });
  const [draft, setDraft] = useState<GenerateResponse | null>(null);
  const [saveError, setSaveError] = useState('');
  const [trackingError, setTrackingError] = useState(false);
  const pendingEvents = useRef<Array<[OnboardingStep, StepOutcome, Segment | undefined]>>([]);
  const savedDraft = useRef(false);
  const flushing = useRef(false);
  const [selectedSegment, setSelectedSegment] = useState<Segment | null>(null);

  async function flushEvents() {
    if (flushing.current) return;
    flushing.current = true;
    try {
      while (pendingEvents.current.length) {
        await api.recordOnboardingStep(...pendingEvents.current[0]);
        pendingEvents.current.shift();
      }
      setTrackingError(false);
    } catch (failure) {
      console.error('[onboarding] step event was not saved', failure);
      setTrackingError(true);
    } finally { flushing.current = false; }
  }
  function track(step: OnboardingStep, outcome: StepOutcome, segment = account?.segment || undefined) {
    pendingEvents.current.push([step, outcome, segment]);
    void flushEvents();
  }

  useEffect(() => {
    let cancelled = false;
    setLoadError('');
    async function load() {
      try {
        const { data: { user }, error: authError } = await supabase.auth.getUser();
        if (authError) throw authError;
        if (!user) { router.replace('/sign-in?redirect_url=' + encodeURIComponent('/first-post' + (params.toString() ? '?' + params.toString() : ''))); return; }
        const [nextAccount, nextOptions] = await Promise.all([api.getAccount(), api.getNicheOptions()]);
        if (cancelled) return;
        setAccount(nextAccount); setSelectedSegment(nextAccount.segment); setOptions(nextOptions);
        setBrief(prev => ({ ...prev, topic: params.get('topic') || sessionStorage.getItem('contendo_topic') || prev.topic }));
        const nextScreen = nextAccount.ask_segment || !nextAccount.segment ? 'segment' : nextAccount.segment === 'business' ? 'business' : 'individual';
        setScreen(nextScreen); setLoaded(true);
        track(nextScreen === 'business' ? 'niche' : nextScreen === 'individual' ? 'individual_brief' : 'segment', 'started', nextAccount.segment || undefined);
      } catch (failure) {
        if (!cancelled) setLoadError(requestErrorMessage(failure, 'load your account and setup options'));
      }
    }
    void load();
    return () => { cancelled = true; };
    // API methods are created per render; retry explicitly controls refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);

  async function choose(segment: Segment, skipped = false) {
    setError(''); setSelectedSegment(segment);
    if (segment === 'business') {
      track('segment', 'completed', segment); track('niche', 'started', segment); setScreen('business'); return;
    }
    setBusy(true);
    try {
      setAccount(await api.saveSegment({ segment }));
      track('segment', skipped ? 'skipped' : 'completed', segment); track('individual_brief', 'started', segment); setScreen('individual');
    } catch (failure) { track('segment', 'error', segment); setError(requestErrorMessage(failure, 'save your choice')); }
    finally { setBusy(false); }
  }

  async function saveDraft(result = draft, source = brief) {
    if (!result || savedDraft.current) return;
    try {
      await requireResponse(await api.logPost({ topic: source.topic, format: source.format, tone: account?.business_profile?.tone || 'casual',
        content: result.post, authenticity_score: result.score || 0, trace_id: result.trace_id }));
      savedDraft.current = true; setSaveError(''); track('draft', 'completed');
    } catch (failure) { setSaveError(requestErrorMessage(failure, 'save this draft to History')); track('draft', 'error'); }
  }

  async function generate(source: FirstPostBrief, segment = selectedSegment) {
    setBrief(source); setError(''); setScreen('generating'); setBusy(true);
    try {
      const result = await api.generateFirstPost(source);
      const outcome = generateOutcome(result);
      if (outcome.kind !== 'post') { setError(generateErrorMessage(outcome)); setScreen(segment === 'business' ? 'business' : 'individual'); return; }
      setDraft(result); savedDraft.current = false; setScreen('draft'); track('draft', 'started');
      await saveDraft(result, source);
    } catch (failure) { setError(requestErrorMessage(failure, 'generate your first post')); setScreen(segment === 'business' ? 'business' : 'individual'); }
    finally { setBusy(false); }
  }

  async function business(answer: SegmentAnswer) {
    setBusy(true); setError('');
    try {
      const saved = await api.saveSegment(answer);
      if (saved.memory_saved === false) throw new Error('Business source not saved');
      setAccount(saved); track('business_profile', 'completed', 'business');
      const profile = answer.business_profile!;
      await generate({ topic: profile.current_offers.trim() || profile.services, story: [profile.services, profile.differentiators, profile.current_offers].filter(Boolean).join('\n'), format: 'linkedin post' }, 'business');
    } catch (failure) { track('business_profile', 'error', 'business'); setError(requestErrorMessage(failure, 'save your business profile')); }
    finally { setBusy(false); }
  }

  async function suggest() {
    setSuggesting(true); setError(''); track('takes', 'started');
    try { setTakes((await api.suggestTakes(brief)).takes); }
    catch (failure) { setError(requestErrorMessage(failure, 'suggest takes. You can also generate without a suggested take')); }
    finally { setSuggesting(false); }
  }

  if (loadError) return <RetryNotice message={loadError} onRetry={() => setAttempt(value => value + 1)} />;
  if (!loaded || !options) return <p className="text-secondary">Loading your setup…</p>;
  return <>
    {trackingError && <div role="alert" className="mb-5 text-tertiary">We couldn’t save your setup progress. <button className="underline" onClick={flushEvents}>Retry saving progress</button></div>}
    {error && screen !== 'business' && <p role="alert" className="mb-5 text-error">{error}</p>}
    {screen === 'segment' && <SegmentQuestion onChoose={choose} onSkip={() => { void choose('individual', true); }} busy={busy} />}
    {selectedSegment === 'business' && <div hidden={screen !== 'business'}><BusinessSetup options={options} initialNiche={account?.business_niche || resolveNicheParam(params.get('niche'), options)} prefill={account?.business_profile || undefined} busy={busy} error={error} onBack={() => { setScreen('segment'); track('segment', 'started'); }} onSubmit={business} onStep={(step, outcome) => track(step, outcome, 'business')} /></div>}
    {screen === 'individual' && <IndividualBrief brief={brief} onChange={value => { if (value.topic !== brief.topic || value.story !== brief.story) setTakes([]); setBrief(value); }} takes={takes} suggesting={suggesting} busy={busy} onSuggest={suggest} onGenerate={() => { track('individual_brief', 'completed'); if (!brief.take) track('takes', 'skipped'); void generate(brief); }} />}
    {screen === 'generating' && <div role="status"><h1 className="font-headline text-2xl">Writing your first post…</h1><p className="mt-3 text-secondary">We’re drafting and checking it against what you told us. This may take a minute.</p></div>}
    {screen === 'draft' && draft && <FirstDraft draft={draft} topic={brief.topic} format={brief.format} tone={account?.business_profile?.tone || 'casual'} saveError={saveError} onRetrySave={() => void saveDraft()} />}
  </>;
}
