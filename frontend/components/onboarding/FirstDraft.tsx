"use client";
import Link from 'next/link';
import GroundingNotice from '@/components/GroundingNotice';
import type { GenerateResponse } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { motion } from 'motion/react';
import { Button } from '@/components/ui/button';
import { riseIn, transition } from '@/components/ui/motion';
import { ErrorState } from '@/components/ui/states';
export default function FirstDraft({ draft, topic, format, tone, saveError, onRetrySave }: {
  draft: GenerateResponse; topic: string; format: string; tone: string; saveError: string; onRetrySave: () => void;
}) {
  const router = useRouter();
  function workspace() {
    const values: Record<string, string> = {
      post: draft.post, topic, format, tone, score: String(draft.score || 0), feedback: JSON.stringify(draft.score_feedback || []),
      iterations: String(draft.iterations || 1), scored: String(draft.scored || false), trace_id: draft.trace_id || '',
      grounding: JSON.stringify(draft.grounding || null), topic_meta: topic, format_meta: format,
    };
    Object.entries(values).forEach(([key, value]) => sessionStorage.setItem('contentOS_last_' + key, value));
    router.push('/create');
  }
  return <motion.div {...riseIn} transition={transition.slow} className="flex flex-col gap-6">
    <h1 className="font-headline text-[1.75rem] text-on-surface">Your first post</h1>
    <div className="whitespace-pre-wrap text-on-surface leading-relaxed">{draft.post}</div>
    <GroundingNotice grounding={draft.grounding} />
    {saveError && <ErrorState message={saveError} onRetry={onRetrySave} />}
    <Button size="lg" onClick={workspace} className="w-full sm:w-fit">Edit in workspace</Button>
    <div className="rounded-2xl bg-surface-container-low p-5">
      <p className="font-headline text-lg">Make your posts sound more like you</p>
      <p className="mt-2 text-sm text-secondary">Optional: add your work, upload a resume or describe your voice. Your draft is ready either way.</p>
      <Link href="/settings/personalization" className="mt-2 inline-flex min-h-11 items-center text-primary underline underline-offset-4">Personalize my posts</Link>
    </div>
  </motion.div>;
}
