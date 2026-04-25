"use client";

/**
 * ContendoLogo — animated quill icon beside the "Contendo" wordmark.
 *
 * The quill sways with a subtle float/rotation loop (5.2 s, GPU-accelerated).
 * The "Contendo" + "Editorial Atelier" text is untouched.
 * Respects prefers-reduced-motion.
 *
 * Animation spec:
 *   duration  5.2s | easing cubic-bezier(.45,0,.2,1) | infinite
 *   keyframes 0%→28%→52%→76%→100% sway + float
 */

export default function ContendoLogo() {
  return (
    <>
      {/* Scoped styles — unique class prefix avoids global bleed */}
      <style>{`
        @keyframes contendoQuillSway {
          0%   { transform: translate3d(0,    0,   0) rotate(-1.4deg); }
          28%  { transform: translate3d(1px,  -2px, 0) rotate( 1.8deg); }
          52%  { transform: translate3d(0,    -1px, 0) rotate( 0.6deg); }
          76%  { transform: translate3d(-1px, -2px, 0) rotate(-1.8deg); }
          100% { transform: translate3d(0,    0,   0) rotate(-1.4deg); }
        }

        /* Wrapper that carries the animation — keeps SVG untouched */
        .contendo-quill-wrapper {
          display: grid;
          place-items: center;
          width: 28px;
          height: 31px;
          flex-shrink: 0;
          animation: contendoQuillSway 5.2s cubic-bezier(.45, 0, .2, 1) infinite;
          /* Pivot near the nib — 70 % down from the top */
          transform-origin: 50% 70%;
          will-change: transform;
        }

        /* SVG itself just needs GPU-layer promotion */
        .contendo-quill-icon {
          width: 100%;
          height: 100%;
          display: block;
          backface-visibility: hidden;
          /* color inherited from figure — currentColor picks it up in SVG paths */
          color: inherit;
        }

        /* Mobile: shrink quill slightly so it doesn't crowd the text */
        @media (max-width: 640px) {
          .contendo-quill-wrapper {
            width: 24px;
            height: 26px;
          }
        }

        /* Accessibility: honour system motion preference */
        @media (prefers-reduced-motion: reduce) {
          .contendo-quill-wrapper {
            animation: none !important;
            transform: none;
          }
        }
      `}</style>

      {/*
       * color on the figure sets currentColor for the SVG paths below.
       * #58614f matches the sage-green used by the original sidebar icon.
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
        {/* Animated wrapper — only this element moves, not the text */}
        <div className="contendo-quill-wrapper" aria-hidden="true">
          {/*
           * Quill SVG — open, minimalist line-drawn feather pen.
           * Paths: curved stem + 2 left feather lines + 2 right feather lines.
           * Uses currentColor so a single color: value above controls everything.
           */}
          <svg
            className="contendo-quill-icon"
            viewBox="0 0 82 90"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            focusable="false"
          >
            {/* Main quill stem — curved line from nib (bottom) to tip (top) */}
            <path
              d="M 41 85 Q 38 70 40 50 Q 42 30 45 15"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            {/* Left feather line 1 (lower) */}
            <path
              d="M 40 65 L 25 60 Q 15 58 10 52"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
            {/* Left feather line 2 (upper) */}
            <path
              d="M 42 45 L 20 38 Q 8 35 5 28"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
            {/* Right feather line 1 (lower) */}
            <path
              d="M 42 62 L 65 58 Q 75 56 80 50"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
            {/* Right feather line 2 (upper) */}
            <path
              d="M 44 42 L 70 35 Q 80 32 82 25"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>

        {/* Brand text — must remain exactly as rendered in Sidebar */}
        <div className="flex flex-col leading-tight" style={{ color: "unset" }}>
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
