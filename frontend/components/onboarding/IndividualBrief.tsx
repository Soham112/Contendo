"use client";
import type { FirstPostBrief } from '@/lib/onboarding-api';
import { Button } from '@/components/ui/button';
import { Input, Label, Textarea } from '@/components/ui/field';

// A native select styled like the other controls: no hooks, so this step renders as a plain function in tests.

export default function IndividualBrief({ brief, onChange, takes, suggesting, busy, onSuggest, onGenerate }: {
  brief: FirstPostBrief; onChange: (value: FirstPostBrief) => void; takes: string[];
  suggesting: boolean; busy: boolean; onSuggest: () => void; onGenerate: () => void;
}) {
  const valid = Boolean(brief.topic.trim() && brief.story.trim());
  const missing = !brief.topic.trim() ? 'Add a topic to continue' : !brief.story.trim() ? 'Add a sentence about it to continue' : undefined;
  return <form onSubmit={event => { event.preventDefault(); if (valid) onGenerate(); }} className="flex flex-col gap-6">
    <h1 className="font-headline text-[1.75rem] text-on-surface">What would you like to share?</h1>
    <div>
      <Label htmlFor="brief-topic">Topic</Label>
      <Input id="brief-topic" required maxLength={500} value={brief.topic} onChange={e => onChange({ ...brief, topic: e.target.value, take: '' })} />
    </div>
    <div>
      <Label htmlFor="brief-story">One sentence about it</Label>
      <Textarea id="brief-story" required maxLength={4000} rows={3} placeholder="Tell us the specific story, experience or idea you want to share." value={brief.story} onChange={e => onChange({ ...brief, story: e.target.value, take: '' })} />
    </div>
    <div>
      <Button variant="tertiary" disabled={!valid || busy} loading={suggesting} onClick={onSuggest} disabledReason={busy ? undefined : 'Add a topic and a sentence to get suggested takes'}>Suggest a take (optional)</Button>
      <p className="mt-2 text-sm text-secondary">Choose a viewpoint only if it reflects what you believe.</p>
      <div className="mt-3 flex flex-col gap-2">{takes.map(take => <button key={take} type="button" aria-pressed={brief.take === take} onClick={() => onChange({ ...brief, take: brief.take === take ? '' : take })} className={`min-h-11 rounded-xl border p-3 text-left text-[0.9375rem] transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${brief.take === take ? 'border-primary bg-primary-container text-on-primary-fixed' : 'border-outline-variant bg-surface-container-lowest hover:bg-surface-container-low'}`}>{take}</button>)}</div>
    </div>
    <Button type="submit" size="lg" disabled={!valid || suggesting} loading={busy} disabledReason={suggesting ? undefined : missing}>Create my first post</Button>
  </form>;
}
