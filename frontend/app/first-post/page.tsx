import { Suspense } from 'react';
import FirstPostFlow from '@/components/onboarding/FirstPostFlow';
export default function FirstPostPage() {
  return <main className="min-h-screen bg-background px-4 py-10 sm:py-16 flex justify-center">
    <div className="w-full max-w-[40rem]">
      <p className="font-headline italic text-xl text-on-surface text-center mb-10">Contendo</p>
      <div className="bg-surface-container-lowest rounded-2xl shadow-card p-6 sm:p-10">
        <Suspense fallback={<p>Loading…</p>}><FirstPostFlow /></Suspense>
      </div>
    </div>
  </main>;
}
