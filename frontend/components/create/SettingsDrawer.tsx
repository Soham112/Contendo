"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ChoiceGroup } from "@/components/ui/choice-group";
import { Dialog, DialogActions } from "@/components/ui/dialog";
import { Input, Label, Textarea } from "@/components/ui/field";
import { FORMATS, LENGTHS, TONES, type Format, type Length, type Tone } from "./config";

interface DrawerProps {
  open: boolean;
  initialTopic: string;
  initialFormat: Format;
  initialTone: Tone;
  initialLength: Length;
  initialContext: string;
  onCancel: () => void;
  onRegenerate: (overrides: { topic: string; format: Format; tone: Tone; length: Length; context: string }) => void;
}

/** The settings for writing the post again: starts from the current ones each time it opens. */
export default function SettingsDrawer({ open, initialTopic, initialFormat, initialTone, initialLength, initialContext, onCancel, onRegenerate }: DrawerProps) {
  const [dTopic, setDTopic] = useState(initialTopic);
  const [dFormat, setDFormat] = useState<Format>(initialFormat);
  const [dTone, setDTone] = useState<Tone>(initialTone);
  const [dLength, setDLength] = useState<Length>(initialLength);
  const [dContext, setDContext] = useState(initialContext);

  useEffect(() => {
    if (!open) return;
    setDTopic(initialTopic);
    setDFormat(initialFormat);
    setDTone(initialTone);
    setDLength(initialLength);
    setDContext(initialContext);
    // Only when it opens: edits made while it is open are kept.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => { if (!next) onCancel(); }}
      title="Write it again"
      description="Change anything you like, then write a new version."
    >
      <div className="space-y-6">
        <div>
          <Label htmlFor="regen-topic">Topic</Label>
          <Input
            id="regen-topic"
            value={dTopic}
            onChange={(e) => setDTopic(e.target.value)}
            placeholder="What do you want to write about?"
          />
        </div>
        <ChoiceGroup
          legend="Format"
          value={dFormat}
          onChange={setDFormat}
          options={FORMATS.map((f) => ({ value: f.id, label: f.label }))}
        />
        <ChoiceGroup
          legend="Tone"
          value={dTone}
          onChange={setDTone}
          options={TONES.map((t) => ({ value: t.id, label: t.label, hint: t.description }))}
          className="grid gap-2 sm:grid-cols-3"
        />
        <ChoiceGroup
          legend="Length"
          value={dLength}
          onChange={setDLength}
          options={LENGTHS.map((l) => ({ value: l.id, label: l.label }))}
        />
        <div>
          <Label htmlFor="regen-context">
            Anything to add <span className="normal-case font-normal">(optional)</span>
          </Label>
          <Textarea
            id="regen-context"
            value={dContext}
            onChange={(e) => setDContext(e.target.value)}
            placeholder="A specific angle, story or detail..."
            rows={3}
            className="resize-none"
          />
        </div>
      </div>
      <DialogActions>
        <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button
          onClick={() => onRegenerate({ topic: dTopic, format: dFormat, tone: dTone, length: dLength, context: dContext })}
          disabled={!dTopic.trim()}
          disabledReason="Add a topic to continue"
        >
          Write new version
        </Button>
      </DialogActions>
    </Dialog>
  );
}
