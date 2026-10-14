"use client";
import { Suspense } from 'react';
import Personalization from '@/components/onboarding/Personalization';
import { Skeleton } from '@/components/ui/card';
export default function PersonalizationPage() {
  return <Suspense fallback={<Skeleton className="mx-auto h-40 max-w-xl" />}><Personalization /></Suspense>;
}
