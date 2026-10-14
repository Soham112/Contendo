"use client";
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useApi } from '@/lib/api';
import { buttonVariants } from '@/components/ui/button';
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
  if (!offered) return error ? <p role="status" className="text-secondary text-sm mb-4">{error} <Link href="/settings/personalization" className="underline underline-offset-4">Personalization</Link></p> : null;
  return <aside className="rounded-2xl bg-surface-container-low p-5 mb-6">
    <p className="font-headline text-lg">Three posts in. Make the next one sound more like you.</p>
    <p className="text-sm text-secondary mt-2">An optional five-question voice exercise helps tailor your drafts.</p>
    <div className="mt-4 flex flex-wrap gap-3">
      <Link href="/settings/personalization?voice=1" className={buttonVariants({ variant: 'primary', size: 'sm' })}>Describe my voice</Link>
      <button type="button" onClick={dismiss} className={buttonVariants({ variant: 'tertiary', size: 'sm' })}>Not now</button>
    </div>
    {error && <p role="alert" className="mt-3 text-error">{error}</p>}
  </aside>;
}
