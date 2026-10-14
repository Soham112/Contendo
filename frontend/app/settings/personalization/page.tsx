"use client";
import { Suspense } from 'react';
import Personalization from '@/components/onboarding/Personalization';
export default function PersonalizationPage() {
  return <Suspense fallback={<p>Loading…</p>}><Personalization /></Suspense>;
}
