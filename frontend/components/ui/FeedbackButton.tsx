"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { useApi } from "@/lib/api";

export default function FeedbackButton() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const pathname = usePathname();
  const api = useApi();

  const handleSubmit = async () => {
    if (!message.trim() || loading) return;
    setLoading(true);
    try {
      await api.submitFeedback(message.trim(), pathname ?? "/");
    } catch {
      // best-effort — don't surface errors to the user
    } finally {
      setLoading(false);
      setSubmitted(true);
      setTimeout(() => {
        setOpen(false);
        setSubmitted(false);
        setMessage("");
      }, 2000);
    }
  };

  const handleClose = () => {
    setOpen(false);
    setMessage("");
    setSubmitted(false);
  };

  return (
    <>
      {/* ── Floating pill button ─────────────────────────────────────────── */}
      <button
        onClick={() => setOpen(true)}
        className="fixed z-40 flex items-center gap-1.5 bg-background text-secondary hover:bg-surface-container-low transition-colors"
        style={{
          bottom: 24,
          right: 24,
          fontSize: 13,
          padding: "6px 14px",
          borderRadius: 99,
          border: "1px solid rgba(174, 179, 178, 0.35)",
          boxShadow:
            "0px 2px 8px rgba(47, 51, 51, 0.06), 0px 1px 2px rgba(47, 51, 51, 0.04)",
        }}
      >
        <svg
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        Feedback
      </button>

      {/* ── Modal ────────────────────────────────────────────────────────── */}
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: "rgba(0, 0, 0, 0.3)" }}
          onClick={(e) => {
            if (e.target === e.currentTarget) handleClose();
          }}
        >
          <div
            className="bg-background flex flex-col w-[90%]"
            style={{
              maxWidth: 420,
              borderRadius: 16,
              padding: 24,
              boxShadow:
                "0px 4px 20px rgba(47, 51, 51, 0.04), 0px 12px 40px rgba(47, 51, 51, 0.06)",
            }}
          >
            <h2
              className="font-headline text-on-surface mb-1"
              style={{ fontSize: 18, fontWeight: 400 }}
            >
              Send feedback
            </h2>
            <p className="text-secondary mb-4" style={{ fontSize: 13 }}>
              What&rsquo;s working, what isn&rsquo;t, or what you&rsquo;d like
              to see.
            </p>

            {submitted ? (
              <p
                className="text-secondary text-center py-6"
                style={{ fontSize: 14 }}
              >
                Thanks &mdash; feedback received.
              </p>
            ) : (
              <>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Share your thoughts..."
                  className="input-editorial w-full mb-4 px-3 py-2.5 text-on-surface placeholder:text-outline-variant text-sm"
                  style={{ minHeight: 120, resize: "vertical" }}
                />
                <div className="flex items-center justify-end gap-2">
                  <button
                    onClick={handleClose}
                    className="text-secondary hover:text-on-surface transition-colors px-4 py-2 rounded-lg text-sm"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSubmit}
                    disabled={!message.trim() || loading}
                    className="btn-primary text-white text-sm rounded-lg px-4 py-2 hover:opacity-90 transition-opacity disabled:opacity-40"
                  >
                    {loading ? "Sending…" : "Submit"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
