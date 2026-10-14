"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Ellipsis, Globe } from "lucide-react";
import { initials } from "@/lib/post-text";
import {
  PLACEHOLDER_AUTHOR, type Device, type PlatformColors, type PlatformConfig, type PreviewAuthor, type Theme,
} from "./platforms";

// Layout effects warn during server rendering (the public tool page renders here first).
const useIsomorphicLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

// The system fonts both platforms use, so lines wrap where they would in the feed.
const PLATFORM_FONT = '-apple-system, system-ui, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

function Avatar({ author, size }: { author: PreviewAuthor; size: number }) {
  const [failed, setFailed] = useState(false);
  const style = { width: size, height: size, borderRadius: "50%", flexShrink: 0 };
  if (author.avatarUrl && !failed) {
    // A plain img: the photo is on the sign-in provider's domain, and the name beside it says who it is.
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={author.avatarUrl} alt="" referrerPolicy="no-referrer" onError={() => setFailed(true)} style={{ ...style, objectFit: "cover" }} />;
  }
  return (
    <span aria-hidden="true" style={{ ...style, display: "grid", placeItems: "center", background: "#c9ccd1", color: "#2f3333", fontSize: size * 0.38, fontWeight: 600 }}>
      {initials(author.name || PLACEHOLDER_AUTHOR.name)}
    </span>
  );
}

/** The post text, clamped to the feed's lines with a "see more" button when it is cut. */
function PostBody({ platform, text, device, colors, overflowAt, expanded, onExpand }: {
  platform: PlatformConfig; text: string; device: Device; colors: PlatformColors;
  overflowAt: number | null; expanded: boolean; onExpand: () => void;
}) {
  const lines = platform.seeMore?.lines[device];
  const clamped = !!lines && !expanded;
  const ref = useRef<HTMLParagraphElement>(null);
  const [cut, setCut] = useState(false);

  // Whether the clamped text really overflows its lines, measured on the
  // rendered card: the font and width decide it, not a character count.
  useIsomorphicLayoutEffect(() => {
    const el = ref.current;
    if (!el || !clamped) return setCut(false);
    const check = () => setCut(el.scrollHeight - el.clientHeight > 1);
    check();
    document.fonts?.ready.then(check).catch(() => {});
  }, [clamped, text, device, platform.id, colors]);

  const font = { fontSize: platform.font.size, lineHeight: `${platform.font.lineHeight}px` };
  return (
    <div style={{ position: "relative", marginTop: platform.byline === "headline" ? 8 : 2 }}>
      <p
        ref={ref}
        style={{
          ...font, whiteSpace: "pre-wrap", overflowWrap: "anywhere",
          ...(clamped ? { display: "-webkit-box", WebkitBoxOrient: "vertical", WebkitLineClamp: lines, overflow: "hidden" } : {}),
        }}
      >
        {overflowAt === null ? text : (
          <>
            {text.slice(0, overflowAt)}
            <mark style={{ background: colors.overflow, color: "inherit" }}>{text.slice(overflowAt)}</mark>
          </>
        )}
      </p>
      {clamped && cut && platform.seeMore && (
        <button
          type="button"
          onClick={onExpand}
          aria-expanded={false}
          style={{
            ...font, position: "absolute", right: 0, bottom: 0, color: colors.muted, cursor: "pointer",
            paddingLeft: 24, background: `linear-gradient(to right, transparent, ${colors.card} 20px)`,
          }}
        >
          {platform.seeMore.label}
        </button>
      )}
    </div>
  );
}

/** The engagement bar. Decorative: no counts, since there are none to show. */
function ActionBar({ platform, device, colors }: { platform: PlatformConfig; device: Device; colors: PlatformColors }) {
  const desktop = device === "desktop";
  return (
    <footer
      aria-hidden="true"
      style={{
        display: "flex", justifyContent: platform.actionLabels ? "space-around" : "space-between",
        marginTop: 12, padding: "4px 0", color: colors.muted, maxWidth: platform.actionLabels ? undefined : 425,
      }}
    >
      {platform.actions.map(({ label, icon: Icon }) => (
        <span
          key={label}
          style={{
            display: "flex", alignItems: "center", gap: desktop ? 6 : 2, padding: "8px 4px",
            flexDirection: desktop ? "row" : "column", fontSize: desktop ? 14 : 12, fontWeight: 600,
          }}
        >
          <Icon size={18} strokeWidth={1.75} />
          {platform.actionLabels ? label : null}
        </span>
      ))}
    </footer>
  );
}

/** One post as the platform's feed would show it. Purely presentational: no data loading. */
export default function PostMockup({ platform, text, author, device, theme, overflowAt, expanded, onExpand }: {
  platform: PlatformConfig;
  text: string;
  author: PreviewAuthor;
  device: Device;
  theme: Theme;
  /** Where the text first goes over the platform's limit; marked from there on. */
  overflowAt: number | null;
  expanded: boolean;
  onExpand: () => void;
}) {
  const colors = platform.colors[theme];
  const name = author.name.trim() || PLACEHOLDER_AUTHOR.name;
  const handle = (author.handle || PLACEHOLDER_AUTHOR.handle || "").replace(/^@/, "");
  const headline = author.headline?.trim() || PLACEHOLDER_AUTHOR.headline;
  const more = <Ellipsis size={20} aria-hidden="true" style={{ color: colors.muted, flexShrink: 0 }} />;
  const body = <PostBody {...{ platform, text, device, colors, overflowAt, expanded, onExpand }} />;
  const actions = <ActionBar platform={platform} device={device} colors={colors} />;
  const ellipsis = { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } as const;

  return (
    <article
      aria-label={`Preview of your post on ${platform.label}`}
      style={{
        width: platform.cardWidth[device], boxSizing: "border-box", background: colors.card, color: colors.text, fontFamily: PLATFORM_FONT,
        borderRadius: device === "desktop" && platform.byline === "headline" ? 8 : 0, padding: "12px 16px 4px",
      }}
    >
      {platform.byline === "headline" ? (
        <>
          <header style={{ display: "flex", gap: 8, alignItems: "flex-start", lineHeight: "18px" }}>
            <Avatar author={author} size={48} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <p style={{ fontSize: 14, fontWeight: 600 }}>{name}</p>
              <p style={{ fontSize: 12, color: colors.muted, ...ellipsis }}>{headline}</p>
              <p style={{ fontSize: 12, color: colors.muted, display: "flex", alignItems: "center", gap: 4 }}>
                {platform.timestamp} · <Globe size={12} aria-label="Public" />
              </p>
            </div>
            {more}
          </header>
          {body}
          {actions}
        </>
      ) : (
        <div style={{ display: "flex", gap: 8 }}>
          <Avatar author={author} size={40} />
          <div style={{ minWidth: 0, flex: 1 }}>
            <header style={{ display: "flex", gap: 8, alignItems: "center", lineHeight: "20px" }}>
              <p style={{ fontSize: 15, minWidth: 0, flex: 1, ...ellipsis }}>
                <span style={{ fontWeight: 700 }}>{name}</span>{" "}
                <span style={{ color: colors.muted }}>@{handle} · {platform.timestamp}</span>
              </p>
              {more}
            </header>
            {body}
            {actions}
          </div>
        </div>
      )}
    </article>
  );
}
