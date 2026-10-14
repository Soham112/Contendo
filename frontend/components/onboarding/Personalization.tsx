"use client";
import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useApi, type ProfileData } from '@/lib/api';
import { ROLE_OPTIONS } from '@/lib/first-post-constants';
import { requestErrorMessage, requireResponse } from '@/lib/request-errors';
import RetryNotice from '@/components/RetryNotice';
import OnboardingIntercept from '@/components/OnboardingIntercept';

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
  if (!profile) return <p>Loading your profile…</p>;
  return <div className="max-w-xl mx-auto flex flex-col gap-6">
    <h1 className="font-headline text-3xl text-on-surface">Make your posts sound more like you</h1>
    <p className="text-secondary">Everything here is optional. Your existing answers stay saved.</p>
    <label className="flex flex-col gap-2 text-secondary">What best describes your work?
      <input className="input-editorial p-3" list="work-options" value={role} onChange={e => setRole(e.target.value)} />
      <datalist id="work-options">{ROLE_OPTIONS.map(option => <option key={option.key} value={option.label} />)}</datalist>
    </label>
    <label className="flex flex-col gap-2 text-secondary">Resume (optional PDF)
      <input type="file" accept="application/pdf" onChange={e => setFile(e.target.files?.[0] || null)} />
    </label>
    {error && <p role="alert" className="text-error">{error}</p>}
    {saved && <p role="status" className="text-primary">Your details are saved.</p>}
    <button onClick={save} disabled={busy} className="btn-primary rounded-md px-5 py-3 text-white disabled:opacity-50">{busy ? 'Saving…' : 'Save details'}</button>
    <div className="rounded-lg bg-surface-container-low p-5"><h2 className="font-headline text-xl">Your writing voice</h2><p className="mt-2 text-secondary">Five optional questions about how you like to write.</p><button onClick={() => { setVoice(true); void api.recordOnboardingStep('enhancement', 'started').catch(failure => { console.error(failure); setError('We couldn’t save your progress. Please try again.'); }); }} className="mt-3 text-primary underline">Start voice questions</button></div>
    {voice && <OnboardingIntercept destination="/settings/personalization" onComplete={() => setVoice(false)} />}
  </div>;
}
