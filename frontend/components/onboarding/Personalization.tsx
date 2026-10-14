"use client";
import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useApi, type ProfileData } from '@/lib/api';
import { ROLE_OPTIONS } from '@/lib/first-post-constants';
import { requestErrorMessage, requireResponse } from '@/lib/request-errors';
import RetryNotice from '@/components/RetryNotice';
import OnboardingIntercept from '@/components/OnboardingIntercept';
import { Button } from '@/components/ui/button';
import { Card, Skeleton } from '@/components/ui/card';
import { Input, Label } from '@/components/ui/field';
import { ErrorState } from '@/components/ui/states';

export default function Personalization() {
  const api = useApi();
  const params = useSearchParams();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [role, setRole] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [voice, setVoice] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setError('');
    api.getProfile().then(requireResponse).then(response => response.json()).then(data => {
      if (!cancelled) { setProfile(data.profile); setRole(data.profile?.role || ''); setVoice(params.get('voice') === '1'); }
    }).catch(failure => { if (!cancelled) setError(requestErrorMessage(failure, 'load your profile')); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
    return () => { cancelled = true; };
  }, [attempt]);
  async function save() {
    if (!profile) return;
    setBusy(true); setError(''); setSaved(false);
    try {
      let merged = { ...profile, role };
      if (file) {
        const response = await requireResponse(await api.extractResume(file));
        const data = await response.json();
        const extracted: ProfileData = data.profile || data;
        // Existing answers win; append extracted lists instead of overwriting voice.
        merged = { ...extracted, ...profile, role: role || extracted.role || '' };
        for (const key of ['topics_of_expertise', 'voice_descriptors', 'opinions', 'writing_samples'] as const) {
          merged[key] = Array.from(new Set([...(profile[key] || []), ...(extracted[key] || [])]));
        }
        for (const key of ['name', 'bio', 'location'] as const) merged[key] = profile[key] || extracted[key] || '';
        if (data.experience_nodes?.length) await requireResponse(await api.saveExperienceNodes(data.experience_nodes));
      }
      await api.saveProfile(merged);
      await api.recordOnboardingStep('enhancement', 'completed');
      setProfile(merged); setSaved(true);
    } catch (failure) { setError(requestErrorMessage(failure, 'save your profile details')); }
    finally { setBusy(false); }
  }
  if (!profile && error) return <RetryNotice message={error} onRetry={() => setAttempt(value => value + 1)} />;
  if (!profile) return (
    <div role="status" aria-label="Loading your profile" className="max-w-xl mx-auto flex flex-col gap-4">
      <Skeleton className="h-8 w-3/4" /><Skeleton className="h-4 w-1/2" /><Skeleton className="mt-4 h-11 w-full" /><Skeleton className="h-11 w-full" />
    </div>
  );
  return <div className="max-w-xl mx-auto flex flex-col gap-6">
    <div>
      <h1 className="font-headline text-3xl text-on-surface">Make your posts sound more like you</h1>
      <p className="mt-2 text-secondary">Everything here is optional. Your existing answers stay saved.</p>
    </div>
    <div>
      <Label htmlFor="work-role">What best describes your work?</Label>
      <Input id="work-role" list="work-options" value={role} onChange={e => setRole(e.target.value)} />
      <datalist id="work-options">{ROLE_OPTIONS.map(option => <option key={option.key} value={option.label} />)}</datalist>
    </div>
    <div>
      <Label htmlFor="work-resume">Resume <span className="normal-case font-normal">(optional, PDF)</span></Label>
      <input
        id="work-resume"
        type="file"
        accept="application/pdf"
        onChange={e => setFile(e.target.files?.[0] || null)}
        className="block w-full text-[0.875rem] text-on-surface-variant file:mr-3 file:min-h-11 file:cursor-pointer file:rounded-md file:border file:border-outline-variant file:bg-transparent file:px-4 file:text-[0.875rem] file:font-medium file:text-on-surface hover:file:bg-surface-container-high"
      />
    </div>
    {error && <ErrorState message={error} />}
    {saved && <p role="status" className="text-primary">Your details are saved.</p>}
    <Button onClick={save} loading={busy} className="w-full sm:w-fit">Save details</Button>
    <Card tone="low">
      <h2 className="font-headline text-xl">Your writing voice</h2>
      <p className="mt-2 text-secondary">Five optional questions about how you like to write.</p>
      <Button variant="secondary" className="mt-4" onClick={() => { setVoice(true); void api.recordOnboardingStep('enhancement', 'started').catch(failure => { console.error(failure); setError('We couldn’t save your progress. Please try again.'); }); }}>
        Start voice questions
      </Button>
    </Card>
    {voice && <OnboardingIntercept destination="/settings/personalization" onComplete={() => setVoice(false)} />}
  </div>;
}
