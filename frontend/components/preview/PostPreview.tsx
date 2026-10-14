"use client";

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { measure } from "@/lib/post-length";
import PostMockup from "./PostMockup";
import { PLATFORMS, type Device, type PlatformConfig, type PreviewAuthor, type Theme } from "./platforms";

/** A row of mutually exclusive buttons (desktop/mobile, light/dark). */
function Toggle<T extends string>({ label, value, options, onChange }: {
  label: string; value: T; options: { value: T; label: string }[]; onChange: (value: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex rounded-md bg-surface-container-low p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={`min-h-11 sm:min-h-9 rounded-[0.6rem] px-3 text-[0.8125rem] transition-colors ${
            value === option.value ? "bg-surface-container-lowest text-on-surface" : "text-secondary hover:text-on-surface"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Scales a fixed-width child down to fit its container, so lines wrap exactly
 * as they would at the platform's real width even on a narrow screen.
 */
function FitToWidth({ width, children }: { width: number; children: React.ReactNode }) {
  const outer = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({ scale: 1, height: 0 });

  useEffect(() => {
    const measureBox = () => {
      const available = outer.current?.clientWidth ?? width;
      const scale = Math.min(1, available / width);
      setBox({ scale, height: (inner.current?.offsetHeight ?? 0) * scale });
    };
    measureBox();
    const observer = new ResizeObserver(measureBox);
    if (outer.current) observer.observe(outer.current);
    if (inner.current) observer.observe(inner.current);
    return () => observer.disconnect();
  }, [width]);

  return (
    <div ref={outer} className="w-full overflow-hidden" style={{ height: box.height || undefined }}>
      <div ref={inner} style={{ width, transform: `scale(${box.scale})`, transformOrigin: "top left" }}>
        {children}
      </div>
    </div>
  );
}

function LengthNote({ platform, count, over }: { platform: PlatformConfig; count: number; over: boolean }) {
  const limit = platform.maxCharacters.toLocaleString("en-US");
  return (
    <p aria-live="polite" className={`mt-3 text-[0.8125rem] ${over ? "text-error" : "text-secondary"}`}>
      {count.toLocaleString("en-US")} / {limit} characters
      {over && ` · ${(count - platform.maxCharacters).toLocaleString("en-US")} over ${platform.label}'s ${limit}-character limit. The marked text won't fit.`}
    </p>
  );
}

/**
 * A post as it will look on each platform: tabs per platform, desktop or
 * mobile, light or dark. Takes everything as props, so it works signed in
 * (CreatePost) and on public pages.
 */
export default function PostPreview({ text, author, platforms = PLATFORMS }: {
  /** The exact text that will be posted (see pastedText in lib/post-text.ts). */
  text: string;
  author: PreviewAuthor;
  platforms?: PlatformConfig[];
}) {
  const id = useId();
  const [active, setActive] = useState(platforms[0].id);
  const [device, setDevice] = useState<Device>("desktop");
  // Phones start in the mobile view: it is what they will see, and needs far less scaling.
  useEffect(() => {
    if (window.matchMedia?.("(max-width: 640px)").matches) setDevice("mobile");
  }, []);
  const [theme, setTheme] = useState<Theme>("light");
  const [expanded, setExpanded] = useState(false);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const platform = platforms.find((p) => p.id === active) ?? platforms[0];
  const { count, overflowAt } = useMemo(() => measure(text, platform.counting, platform.maxCharacters), [text, platform]);

  // A different platform or device cuts the post in a different place: show it collapsed again.
  useEffect(() => setExpanded(false), [active, device]);

  const onTabKey = (event: KeyboardEvent, index: number) => {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = (index + step + platforms.length) % platforms.length;
    setActive(platforms[next].id);
    tabs.current[next]?.focus();
  };

  const width = platform.cardWidth[device] + platform.feedPadding[device] * 2;
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label="Platform" className="flex gap-1">
          {platforms.map((p, index) => (
            <button
              key={p.id}
              ref={(el) => { tabs.current[index] = el; }}
              type="button"
              role="tab"
              id={`${id}-tab-${p.id}`}
              aria-selected={p.id === platform.id}
              aria-controls={`${id}-panel`}
              tabIndex={p.id === platform.id ? 0 : -1}
              onClick={() => setActive(p.id)}
              onKeyDown={(event) => onTabKey(event, index)}
              className={`min-h-11 sm:min-h-9 rounded-md px-3.5 text-[0.875rem] transition-colors ${
                p.id === platform.id ? "bg-surface-container-lowest text-on-surface font-medium" : "text-secondary hover:text-on-surface"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Toggle label="Device" value={device} onChange={setDevice} options={[{ value: "desktop", label: "Desktop" }, { value: "mobile", label: "Mobile" }]} />
          <Toggle label="Theme" value={theme} onChange={setTheme} options={[{ value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} />
        </div>
      </div>

      <div role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-tab-${platform.id}`} className="mt-4">
        <FitToWidth width={width}>
          <div style={{ background: platform.colors[theme].page, padding: platform.feedPadding[device], borderRadius: 12 }}>
            <PostMockup
              platform={platform}
              text={text}
              author={author}
              device={device}
              theme={theme}
              overflowAt={overflowAt}
              expanded={expanded}
              onExpand={() => setExpanded(true)}
            />
          </div>
        </FitToWidth>
        <LengthNote platform={platform} count={count} over={overflowAt !== null} />
      </div>
    </div>
  );
}
