"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/ToastProvider";
import { useApi } from "@/lib/api";
import {
  AUTHORSHIP_CHOICES, AUTHORSHIP_FAILED_MESSAGE, AUTHORSHIP_QUESTION, authorshipOutcome, authorshipView,
  type AuthorshipChoice, type AuthorshipFields,
} from "@/lib/library";

/**
 * A Library card's authorship: the label with who set it and a Change button,
 * or the question when there is no label. The label changes only once the
 * backend confirms the save; a failure keeps the question open with the error.
 */
export function AuthorshipControl({
  source,
  onSaved,
}: {
  source: AuthorshipFields;
  onSaved: (sourceId: string, authorship: AuthorshipChoice) => void;
}) {
  const api = useApi();
  const { showToast } = useToast();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState<AuthorshipChoice | null>(null);
  const [error, setError] = useState("");
  const view = authorshipView(source);

  const choose = async (choice: AuthorshipChoice) => {
    setSaving(choice);
    setError("");
    try {
      const outcome = await authorshipOutcome(await api.setSourceAuthorship(source.source_id, choice), choice);
      if (outcome.ok) {
        onSaved(source.source_id, outcome.authorship);
        setEditing(false);
        showToast("Saved", "success");
      } else {
        setError(outcome.message);
        showToast(outcome.message, "error");
      }
    } catch {
      setError(AUTHORSHIP_FAILED_MESSAGE);
      showToast(AUTHORSHIP_FAILED_MESSAGE, "error");
    } finally {
      setSaving(null);
    }
  };

  if (view.kind === "label" && !editing) {
    return (
      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[11px]">
        <span className="font-medium text-on-surface">{view.label}</span>
        {view.note && <span className="text-on-surface-variant">· {view.note}</span>}
        {view.editable && (
          <Button variant="tertiary" size="sm" className="text-[11px]"
            onClick={() => setEditing(true)} aria-label={`Change who wrote this (now: ${view.label})`}>
            Change
          </Button>
        )}
      </div>
    );
  }

  const current = view.kind === "label" ? view.authorship : null;
  return (
    <div role="group" aria-label={AUTHORSHIP_QUESTION} className="flex flex-col gap-2 rounded-lg bg-surface-container-low p-2.5">
      <p className="text-[12px] text-on-surface">{AUTHORSHIP_QUESTION}</p>
      <div className="flex flex-wrap gap-2">
        {AUTHORSHIP_CHOICES.map((c) => (
          <Button key={c.value} variant="secondary" size="sm" aria-pressed={current === c.value}
            loading={saving === c.value} disabled={saving !== null} onClick={() => choose(c.value)}>
            {c.label}
          </Button>
        ))}
        {editing && (
          <Button variant="ghost" size="sm" disabled={saving !== null}
            onClick={() => { setEditing(false); setError(""); }}>
            Cancel
          </Button>
        )}
      </div>
      {error && <p role="alert" className="text-[11px] text-error">{error}</p>}
    </div>
  );
}
