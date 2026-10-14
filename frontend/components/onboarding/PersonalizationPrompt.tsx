"use client";
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useApi } from '@/lib/api';
export default function PersonalizationPrompt() {
  const api = useApi();
  const [offered, setOffered] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const check = () => api.getPersonalization().then(result => { setOffered(result.offer_voice); setError(''); }).catch(failure => {
      console.error('[personalization] Could not check optional prompt', failure);
      setError('We couldn’t check your personalization options. You can open them in Settings.');
    });
    void check();
    window.addEventListener('contendo:post-saved', check);
    return () => window.removeEventListener('contendo:post-saved', check);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  async function dismiss() {
    try { await api.dismissPersonalization(); setOffered(false); }
    catch (failure) { console.error('[personalization] Dismiss failed', failure); setError('We couldn’t save that choice. Please try again.'); }
  }
  if (!offered) return error ? <p role="status" className="text-secondary text-sm mb-4">{error} <Link href="/settings/personalization" className="underline">Personalization</Link></p> : null;
  return <aside className="rounded-lg bg-surface-container-low p-5 mb-6">
    <p className="font-headline text-lg">Three posts in. Make the next one sound more like you.</p>
    <p className="text-sm text-secondary mt-2">An optional five-question voice exercise helps tailor your drafts.</p>
    <Link href="/settings/personalization?voice=1" className="text-primary underline inline-block mt-3">Describe my voice</Link>
    <button onClick={dismiss} className="ml-5 text-secondary underline">Not now</button>
    {error && <p role="alert" className="text-error">{error}</p>}
  </aside>;
}
