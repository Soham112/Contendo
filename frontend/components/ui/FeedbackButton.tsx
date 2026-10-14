"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogActions } from "@/components/ui/dialog";
import { FieldMessage, Label, Textarea } from "@/components/ui/field";

interface FeedbackModalProps {
  open: boolean;
  onClose: () => void;
}

export default function FeedbackModal({ open, onClose }: FeedbackModalProps) {
  const [message, setMessage] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const pathname = usePathname();
  const api = useApi();

  // Reset internal state each time the modal opens
  useEffect(() => {
    if (open) {
      setMessage("");
      setSubmitted(false);
      setLoading(false);
      setFailed(false);
    }
  }, [open]);

  const handleSubmit = async () => {
    if (!message.trim() || loading) return;
    setLoading(true);
    setFailed(false);
    try {
      const res = await api.submitFeedback(message.trim(), pathname ?? "/");
      if (!res.ok) throw new Error("not sent");
      setSubmitted(true);
      setTimeout(onClose, 2000);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => { if (!next) onClose(); }}
      title="Send feedback"
      description="What's working, what isn't, or what you'd like to see."
    >
      {submitted ? (
        <p role="status" className="py-4 text-center text-[0.9375rem] text-on-surface">Thanks, we got your feedback.</p>
      ) : (
        <>
          <Label htmlFor="feedback-message">Your feedback</Label>
          <Textarea
            id="feedback-message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Share your thoughts..."
            className="min-h-[120px] resize-y"
            aria-describedby={failed ? "feedback-error" : undefined}
          />
          {failed && (
            <FieldMessage id="feedback-error" error>
              We couldn&apos;t send that. Check your connection and try again.
            </FieldMessage>
          )}
          <DialogActions>
            <Button variant="secondary" onClick={onClose}>Cancel</Button>
            <Button onClick={handleSubmit} loading={loading} disabled={!message.trim()} disabledReason="Write something to send">
              {failed ? "Try again" : "Send"}
            </Button>
          </DialogActions>
        </>
      )}
    </Dialog>
  );
}
