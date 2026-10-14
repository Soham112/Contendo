"use client";

import { useState } from "react";
import { FORMATS, LENGTHS, TONES, type Format, type Length, type Tone } from "./config";

// ─── Settings Drawer ──────────────────────────────────────────────────────────

interface DrawerProps {
  initialTopic: string;
  initialFormat: Format;
  initialTone: Tone;
  initialLength: Length;
  initialContext: string;
  onCancel: () => void;
  onRegenerate: (overrides: { topic: string; format: Format; tone: Tone; length: Length; context: string }) => void;
}

export default function SettingsDrawer({ initialTopic, initialFormat, initialTone, initialLength, initialContext, onCancel, onRegenerate }: DrawerProps) {
  const [dTopic, setDTopic] = useState(initialTopic);
  const [dFormat, setDFormat] = useState<Format>(initialFormat);
  const [dTone, setDTone] = useState<Tone>(initialTone);
  const [dLength, setDLength] = useState<Length>(initialLength);
  const [dContext, setDContext] = useState(initialContext);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/10 z-40"
        onClick={onCancel}
      />
      {/* Drawer panel */}
      <div className="fixed top-0 right-0 h-full w-80 bg-background border-l border-surface-container-high z-50 flex flex-col shadow-card">
        {/* Header */}
        <div
          style={{ borderBottom: "0.5px solid #dfe3e2", height: "52px" }}
          className="flex items-center justify-between px-5 shrink-0"
        >
          <p className="text-sm font-medium text-on-surface font-headline">Regenerate settings</p>
          <button
            onClick={onCancel}
            className="text-outline hover:text-on-surface transition-colors text-xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-6 space-y-6">
          {/* Topic */}
          <div>
            <label className="label-caps text-secondary block mb-2">Topic</label>
            <input
              type="text"
              value={dTopic}
              onChange={(e) => setDTopic(e.target.value)}
              placeholder="What do you want to write about?"
              className="input-editorial w-full px-0 py-2 text-sm font-medium text-on-surface placeholder:text-outline-variant focus:outline-none"
            />
          </div>

          {/* Format */}
          <div>
            <label className="label-caps text-secondary block mb-2">Format</label>
            <div className="space-y-1.5">
              {FORMATS.map((f) => (
                <button
                  key={f.id}
                  onClick={() => setDFormat(f.id)}
                  className={`w-full px-3 py-2 rounded-lg text-sm text-left transition-colors ${
                    dFormat === f.id
                      ? "btn-primary text-white font-medium"
                      : "bg-surface-container text-secondary hover:bg-surface-container-high hover:text-on-surface"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* Tone */}
          <div>
            <label className="label-caps text-secondary block mb-2">Tone</label>
            <div className="space-y-1.5">
              {TONES.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setDTone(t.id)}
                  className={`w-full px-3 py-2.5 rounded-lg text-sm text-left transition-colors ${
                    dTone === t.id
                      ? "btn-primary text-white"
                      : "bg-surface-container text-secondary hover:bg-surface-container-high hover:text-on-surface"
                  }`}
                >
                  <div className="font-medium">{t.label}</div>
                  <div className={`text-xs mt-0.5 ${dTone === t.id ? "text-white/70" : "text-outline"}`}>
                    {t.description}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Length */}
          <div>
            <label className="label-caps text-secondary block mb-2">Length</label>
            <div className="flex flex-wrap gap-2">
              {LENGTHS.map((l) => (
                <button
                  key={l.id}
                  onClick={() => setDLength(l.id)}
                  className={`px-4 py-2 rounded-lg text-[13px] transition-all border ${
                    dLength === l.id
                      ? "btn-primary text-white border-transparent font-medium"
                      : "border-outline-variant text-secondary hover:border-outline hover:text-on-surface bg-transparent"
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          {/* Context */}
          <div>
            <label className="label-caps text-secondary block mb-2">
              Additional context{" "}
              <span className="normal-case font-normal text-outline-variant">(optional)</span>
            </label>
            <textarea
              value={dContext}
              onChange={(e) => setDContext(e.target.value)}
              placeholder="Specific angle, story, or data point..."
              rows={3}
              className="input-editorial w-full px-0 py-2 text-sm text-on-surface placeholder:text-outline-variant focus:outline-none resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div
          style={{ borderTop: "0.5px solid #dfe3e2" }}
          className="px-5 py-4 flex gap-2 shrink-0"
        >
          <button
            onClick={onCancel}
            className="flex-1 rounded-lg border border-surface-container-high text-secondary text-sm py-2 hover:border-outline-variant hover:text-on-surface transition-colors bg-surface-container-lowest"
          >
            Cancel
          </button>
          <button
            onClick={() => onRegenerate({ topic: dTopic, format: dFormat, tone: dTone, length: dLength, context: dContext })}
            className="flex-1 btn-primary rounded-lg text-white text-sm font-medium py-2 hover:opacity-90 transition-opacity"
          >
            Regenerate
          </button>
        </div>
      </div>
    </>
  );
}
