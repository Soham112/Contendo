"use client";

/**
 * ContendoLogo — quill icon variants for different surfaces.
 *
 * Exports
 * -------
 * default  ContendoLogo      Animated quill + "Contendo" wordmark (sidebar)
 * named    QuillIcon         Animated quill icon only — drops into any layout
 *                            (used in landing-page / welcome-page TopNav)
 * named    ContendoLogoSmall Static quill icon only (sidebar icon slot)
 *
 * SVG design
 * ----------
 * viewBox 0 0 64 96
 *  • Outer feather vane   — closed leaf-shape outline
 *  • Rachis               — central spine from tip to base
 *  • Inner barb line 1    — right side, upper
 *  • Inner barb line 2    — right side, lower
 *  • Calamus              — curved hollow-base hook at the bottom
 *
 * Animation (quill wrapper only, text is always still)
 * -------------------------------------------------------
 * 5.2s | cubic-bezier(.45,0,.2,1) | infinite
 * 0%→28%→52%→76%→100% sway + float keyframes
 * GPU-accelerated via translate3d + will-change
 * Respects prefers-reduced-motion
 */

/* ─── shared SVG paths ──────────────────────────────────────────────────── */

const QuillSVG = () => (
  <svg
    className="contendo-quill-icon"
    viewBox="0 0 64 96"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
    focusable="false"
  >
    {/* Outer feather vane — closed leaf/almond outline */}
    <path
      d="M 24 4
         C 6 10, 2 30, 4 48
         C 6 64, 16 78, 28 80
         C 40 82, 56 74, 60 56
         C 64 36, 58 12, 44 5
         C 36 1, 28 2, 24 4 Z"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinejoin="round"
    />
    {/* Rachis — central spine from tip to calamus junction */}
    <path
      d="M 24 4 C 26 28, 28 54, 30 80"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
    />
    {/* Inner barb line 1 — right side, upper */}
    <path
      d="M 32 12 C 48 22, 58 42, 56 64"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    />
    {/* Inner barb line 2 — right side, lower */}
    <path
      d="M 30 32 C 44 44, 54 60, 52 76"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    />
    {/* Calamus — curved hollow-base hook at the bottom of the quill */}
    <path
      d="M 22 78 C 12 84, 12 93, 22 91 C 32 89, 34 79, 28 78"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

/* ─── scoped CSS (injected once per page, class names are unique) ────────── */

const STYLES = `
  @keyframes contendoQuillSway {
    0%   { transform: translate3d(0,    0,   0) rotate(-1.4deg); }
    28%  { transform: translate3d(1px,  -2px, 0) rotate( 1.8deg); }
    52%  { transform: translate3d(0,    -1px, 0) rotate( 0.6deg); }
    76%  { transform: translate3d(-1px, -2px, 0) rotate(-1.8deg); }
    100% { transform: translate3d(0,    0,   0) rotate(-1.4deg); }
  }

  /* Animated wrapper — pivot at 70 % so the nib barely moves */
  .contendo-quill-animated {
    display: grid;
    place-items: center;
    flex-shrink: 0;
    animation: contendoQuillSway 5.2s cubic-bezier(.45, 0, .2, 1) infinite;
    transform-origin: 50% 70%;
    will-change: transform;
  }

  /* Static wrapper — same shape, no motion */
  .contendo-quill-static {
    display: grid;
    place-items: center;
    flex-shrink: 0;
  }

  /* The SVG itself — GPU layer promotion only */
  .contendo-quill-icon {
    display: block;
    width: 100%;
    height: 100%;
    color: inherit;
    backface-visibility: hidden;
  }

  /* Mobile: slightly smaller to avoid crowding text */
  @media (max-width: 640px) {
    .contendo-quill-animated,
    .contendo-quill-static {
      width: 20px !important;
      height: 30px !important;
    }
  }

  /* Accessibility: honour OS motion preference */
  @media (prefers-reduced-motion: reduce) {
    .contendo-quill-animated {
      animation: none !important;
      transform: none;
    }
  }
`;

/* ─── QuillIcon — animated icon only (for nav / any inline use) ─────────── */

/**
 * Renders only the animated quill SVG in a 28×42 px wrapper.
 * Drop this anywhere you need the quill beside existing text.
 */
export function QuillIcon({ size = 28 }: { size?: number }) {
  const height = Math.round(size * (96 / 64)); // preserve 64:96 aspect ratio
  return (
    <>
      <style>{STYLES}</style>
      <div
        className="contendo-quill-animated"
        aria-hidden="true"
        style={{ width: size, height }}
      >
        <QuillSVG />
      </div>
    </>
  );
}

/* ─── ContendoLogoSmall — static icon only (sidebar icon slot) ──────────── */

/**
 * Static (no animation) quill icon at 24×36 px.
 * Used in the Sidebar beside its own "Contendo" / "Editorial Atelier" text.
 */
export function ContendoLogoSmall({ size = 24 }: { size?: number }) {
  const height = Math.round(size * (96 / 64));
  return (
    <>
      <style>{STYLES}</style>
      <div
        className="contendo-quill-static"
        aria-hidden="true"
        style={{ width: size, height, color: "#58614f" }}
      >
        <QuillSVG />
      </div>
    </>
  );
}

/* ─── ContendoLogo — animated quill + full wordmark (sidebar / standalone) ─ */

/**
 * Full logo: animated quill + "Contendo" wordmark + "Editorial Atelier" sub-label.
 * Used in the Sidebar and anywhere a self-contained brand block is needed.
 */
export default function ContendoLogo() {
  return (
    <>
      <style>{STYLES}</style>

      {/*
       * color: #58614f sets currentColor for every SVG stroke in QuillSVG.
       * The text spans carry their own Tailwind color tokens so they
       * are unaffected by this property.
       */}
      <figure
        aria-label="Contendo"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          margin: 0,
          color: "#58614f",
        }}
      >
        {/* Animated quill wrapper */}
        <div
          className="contendo-quill-animated"
          aria-hidden="true"
          style={{ width: 26, height: 39 }}
        >
          <QuillSVG />
        </div>

        {/* Wordmark — untouched from the original Sidebar design */}
        <div className="flex flex-col leading-tight">
          <span className="text-[15px] font-bold text-on-surface tracking-tight font-headline">
            Contendo
          </span>
          <span className="text-[9px] uppercase tracking-[0.12em] text-secondary font-label">
            Editorial Atelier
          </span>
        </div>
      </figure>
    </>
  );
}
