export interface ClaimFlag { id: string; sentence: string; text: string; reason: string }
export interface Grounding { outcome: "verified" | "needs_review"; flags: ClaimFlag[]; repairs: number }

export default function GroundingNotice({ grounding }: { grounding?: Grounding | null }) {
  if (!grounding || grounding.outcome === "verified") return null;
  return <section role="alert" className="mb-5 rounded-lg bg-surface-container-low px-5 py-5 text-on-surface">
    <h3 className="font-headline text-lg text-tertiary">Check these claims before publishing</h3>
    <p className="mt-2 text-sm text-secondary">These details could not be verified from your sources. Edit the text or confirm each flag during approval.</p>
    <ul className="mt-4 flex flex-col gap-4">{grounding.flags.map((flag) => <li key={flag.id}>
      {flag.text && <p className="font-medium">{flag.text}</p>}
      <p className="text-sm text-secondary">{flag.reason}</p>
    </li>)}</ul>
  </section>;
}
