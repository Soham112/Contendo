"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ChoiceGroup } from "@/components/ui/choice-group";
import { Dialog, DialogActions } from "@/components/ui/dialog";
import { Label, Textarea } from "@/components/ui/field";

const PLATFORMS = [
  { id: "linkedin", label: "LinkedIn" },
  { id: "other", label: "Other" },
];

/** Record where a post went live, and optionally the version that was posted. */
export default function MarkPublishedDialog({
  onSave,
  onClose,
  saving,
}: {
  onSave: (platform: string, content: string) => void;
  onClose: () => void;
  saving: boolean;
}) {
  const [platform, setPlatform] = useState("linkedin");
  const [finalContent, setFinalContent] = useState("");

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }} title="Mark as published" description="Record where this post went live.">
      <ChoiceGroup legend="Where" value={platform} onChange={setPlatform} options={PLATFORMS.map((p) => ({ value: p.id, label: p.label }))} />
      <div className="mt-5">
        <Label htmlFor="published-text">
          What you posted <span className="normal-case font-normal">(optional)</span>
        </Label>
        <Textarea
          id="published-text"
          value={finalContent}
          onChange={(e) => setFinalContent(e.target.value)}
          rows={4}
          placeholder="Paste the final version. Contendo learns your voice from it."
          className="resize-none"
        />
      </div>
      <DialogActions>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button onClick={() => onSave(platform, finalContent)} loading={saving}>Save</Button>
      </DialogActions>
    </Dialog>
  );
}
