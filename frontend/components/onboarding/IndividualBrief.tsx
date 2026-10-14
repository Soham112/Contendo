"use client";
import type { FirstPostBrief } from '@/lib/onboarding-api';

const FIELD = 'input-editorial w-full px-3 py-2.5 text-on-surface';
export default function IndividualBrief({ brief, onChange, takes, suggesting, busy, onSuggest, onGenerate }: {
  brief: FirstPostBrief; onChange: (value: FirstPostBrief) => void; takes: string[];
  suggesting: boolean; busy: boolean; onSuggest: () => void; onGenerate: () => void;
}) {
  const valid = Boolean(brief.topic.trim() && brief.story.trim());
  return <form onSubmit={event => { event.preventDefault(); if (valid) onGenerate(); }} className="flex flex-col gap-6">
    <h1 className="font-headline text-[1.75rem] text-on-surface">What would you like to share?</h1>
    <label className="flex flex-col gap-2 text-secondary">Topic
      <input required maxLength={500} className={FIELD} value={brief.topic} onChange={e => onChange({ ...brief, topic: e.target.value, take: '' })} />
    </label>
    <label className="flex flex-col gap-2 text-secondary">Format
      <select className={FIELD} value={brief.format} onChange={e => onChange({ ...brief, format: e.target.value })}>
        <option value="linkedin post">LinkedIn post</option><option value="medium article">Medium article</option><option value="twitter thread">Thread</option>
      </select>
    </label>
    <label className="flex flex-col gap-2 text-secondary">One sentence about it
      <textarea required maxLength={4000} rows={3} className={FIELD} placeholder="Tell us the specific story, experience or idea you want to share." value={brief.story} onChange={e => onChange({ ...brief, story: e.target.value, take: '' })} />
    </label>
    <div>
      <button type="button" disabled={!valid || suggesting || busy} onClick={onSuggest} className="text-primary underline underline-offset-4 disabled:opacity-50">{suggesting ? 'Thinking of takes…' : 'Suggest a take (optional)'}</button>
      <p className="mt-2 text-sm text-secondary">Choose a viewpoint only if it reflects what you believe.</p>
      <div className="mt-3 flex flex-col gap-2">{takes.map(take => <button key={take} type="button" aria-pressed={brief.take === take} onClick={() => onChange({ ...brief, take: brief.take === take ? '' : take })} className={`rounded-lg p-3 text-left ${brief.take === take ? 'bg-primary-container' : 'bg-surface-container-low'}`}>{take}</button>)}</div>
    </div>
    <button disabled={!valid || busy || suggesting} className="btn-primary rounded-md px-5 py-3 text-white disabled:opacity-50">Generate my first post</button>
  </form>;
}
