import Link from "next/link";

const STEPS = [
  {
    title: "Feed your knowledge",
    description:
      "Paste articles, YouTube transcripts, PDFs, or raw notes into Contendo. The system chunks and embeds everything into a personal vector memory store — searchable by meaning, not just keywords.",
  },
  {
    title: "Set up your voice profile",
    description:
      "Fill in your profile once: your role, your opinions, phrases you use, words you avoid, and a few writing samples. This is what separates posts that sound like you from posts that sound like ChatGPT.",
  },
  {
    title: "Generate a draft",
    description:
      "Pick a topic, format, and tone. Contendo retrieves the most relevant chunks from your memory, feeds them into the draft alongside your voice profile, then runs a humanizer pass to strip AI patterns.",
  },
  {
    title: "Score, refine, publish",
    description:
      "Every post gets an authenticity score across 5 dimensions. If anything scores low, one click sends targeted feedback to the refiner — which fixes exactly what's flagged, nothing else.",
  },
];

export default function WelcomePage() {
  return (
    <div style={{ backgroundColor: "#fdfcfb", minHeight: "100vh", fontFamily: '"DM Sans", system-ui, sans-serif' }}>
      {/* Top Navigation */}
      <nav style={{
        height: "56px",
        backgroundColor: "#fdfcfb",
        borderBottom: "0.5px solid #e8e3da",
        padding: "0 48px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        {/* Logo */}
        <Link href="/welcome" style={{ fontSize: "16px", fontWeight: 500, color: "#2c2a24", letterSpacing: "-0.01em", textDecoration: "none" }}>
          Contendo
        </Link>

        {/* Center links */}
        <div style={{ display: "flex", gap: "28px", alignItems: "center" }}>
          <a href="#features" style={{ fontSize: "13.5px", color: "#7a786f", textDecoration: "none", cursor: "pointer" }}>Features</a>
          <a href="#how-it-works" style={{ fontSize: "13.5px", color: "#7a786f", textDecoration: "none", cursor: "pointer" }}>How it works</a>
          <a href="#" style={{ fontSize: "13.5px", color: "#7a786f", textDecoration: "none", cursor: "pointer" }}>Pricing</a>
        </div>

        {/* Right buttons */}
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <Link
            href="/"
            style={{
              border: "0.5px solid #c8c3b8",
              borderRadius: "8px",
              padding: "9px 18px",
              fontSize: "13px",
              color: "#4a4843",
              backgroundColor: "transparent",
              textDecoration: "none",
              cursor: "pointer",
              display: "inline-block",
            }}
          >
            Log in
          </Link>
          <Link
            href="/"
            style={{
              backgroundColor: "#2c2a24",
              color: "#f5f4f1",
              border: "none",
              borderRadius: "8px",
              padding: "9px 18px",
              fontSize: "13px",
              fontWeight: 500,
              textDecoration: "none",
              cursor: "pointer",
              display: "inline-block",
            }}
          >
            Get started free
          </Link>
        </div>
      </nav>

      {/* Main content */}
      <main style={{ backgroundColor: "#fdfcfb", padding: "80px 48px 0" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center" }}>
          {/* Eyebrow */}
          <p style={{
            fontSize: "11.5px",
            fontWeight: 500,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "#6b6760",
            margin: "0 0 20px 0",
          }}>
            LinkedIn content, powered by your knowledge
          </p>

          {/* H1 */}
          <h1 style={{
            fontSize: "42px",
            fontWeight: 500,
            color: "#2c2a24",
            lineHeight: 1.18,
            letterSpacing: "-0.02em",
            maxWidth: "640px",
            margin: "0 0 20px 0",
          }}>
            Write posts that sound like{" "}
            <span style={{ fontStyle: "italic", color: "#2c2a24", fontWeight: 500 }}>you</span>
            {" "}— not like everyone else
          </h1>

          {/* Subheadline */}
          <p style={{
            fontSize: "15px",
            color: "#8a8880",
            lineHeight: 1.65,
            maxWidth: "480px",
            margin: "0 0 40px 0",
          }}>
            Contendo learns your knowledge base, your voice, and your style. Then it writes content that actually sounds like you wrote it.
          </p>

          {/* CTA buttons */}
          <div style={{ display: "flex", gap: "12px", justifyContent: "center", marginBottom: "64px" }}>
            <Link
              href="/"
              style={{
                border: "1.5px solid #2c2a24",
                borderRadius: "10px",
                padding: "14px 28px",
                fontSize: "14px",
                fontWeight: 500,
                color: "#2c2a24",
                backgroundColor: "transparent",
                textDecoration: "none",
                cursor: "pointer",
                display: "inline-block",
              }}
            >
              Start writing for free
            </Link>
            <a
              href="#how-it-works"
              style={{
                border: "0.5px solid #d0c2b8",
                borderRadius: "10px",
                padding: "14px 28px",
                fontSize: "14px",
                color: "#5a5855",
                backgroundColor: "transparent",
                textDecoration: "none",
                cursor: "pointer",
                display: "inline-block",
              }}
            >
              See how it works
            </a>
          </div>

          {/* Feature cards */}
          <div
            id="features"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "16px",
              maxWidth: "780px",
              width: "100%",
              margin: "0 auto",
              paddingBottom: "80px",
            }}
          >
            {/* Card 1 — Feed your knowledge */}
            <div style={{
              backgroundColor: "#ffffff",
              border: "0.5px solid #e8e3da",
              borderRadius: "12px",
              padding: "24px",
              textAlign: "left",
            }}>
              <div style={{
                width: "36px",
                height: "36px",
                backgroundColor: "#f0eeea",
                borderRadius: "8px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "16px",
              }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <rect x="8" y="1.5" width="7.5" height="7.5" rx="0.8" transform="rotate(45 8 1.5)" stroke="#6b6760" strokeWidth="1.2"/>
                </svg>
              </div>
              <p style={{ fontSize: "13.5px", fontWeight: 500, color: "#2c2a24", margin: "0 0 8px 0" }}>
                Feed your knowledge
              </p>
              <p style={{ fontSize: "12.5px", color: "#9a9890", lineHeight: 1.6, margin: 0 }}>
                Articles, notes, YouTube videos, PDFs — anything you&apos;ve read becomes fuel for your posts.
              </p>
            </div>

            {/* Card 2 — Generate in your voice */}
            <div style={{
              backgroundColor: "#ffffff",
              border: "0.5px solid #e8e3da",
              borderRadius: "12px",
              padding: "24px",
              textAlign: "left",
            }}>
              <div style={{
                width: "36px",
                height: "36px",
                backgroundColor: "#f0eeea",
                borderRadius: "8px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "16px",
              }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M8 1.5L9.4 6.6L14.5 8L9.4 9.4L8 14.5L6.6 9.4L1.5 8L6.6 6.6L8 1.5Z" stroke="#6b6760" strokeWidth="1.2" strokeLinejoin="round"/>
                </svg>
              </div>
              <p style={{ fontSize: "13.5px", fontWeight: 500, color: "#2c2a24", margin: "0 0 8px 0" }}>
                Generate in your voice
              </p>
              <p style={{ fontSize: "12.5px", color: "#9a9890", lineHeight: 1.6, margin: 0 }}>
                The AI learns your writing style, your opinions, and your phrases — then drafts in your exact voice.
              </p>
            </div>

            {/* Card 3 — Score and refine */}
            <div style={{
              backgroundColor: "#ffffff",
              border: "0.5px solid #e8e3da",
              borderRadius: "12px",
              padding: "24px",
              textAlign: "left",
            }}>
              <div style={{
                width: "36px",
                height: "36px",
                backgroundColor: "#f0eeea",
                borderRadius: "8px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "16px",
              }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="5.5" stroke="#6b6760" strokeWidth="1.2"/>
                  <path d="M8 5V8.2L10 10" stroke="#6b6760" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <p style={{ fontSize: "13.5px", fontWeight: 500, color: "#2c2a24", margin: "0 0 8px 0" }}>
                Score and refine
              </p>
              <p style={{ fontSize: "12.5px", color: "#9a9890", lineHeight: 1.6, margin: 0 }}>
                Every post gets an authenticity score. One-click refinement fixes what the AI flags before you publish.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* How it works */}
      <section
        id="how-it-works"
        style={{
          borderTop: "0.5px solid #e8e3da",
          backgroundColor: "#fdfcfb",
          padding: "80px 48px",
        }}
      >
        <div style={{ maxWidth: "760px", margin: "0 auto" }}>
          {/* Section header */}
          <div style={{ textAlign: "center", marginBottom: "56px" }}>
            <p style={{
              fontSize: "11px",
              fontWeight: 500,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "#9a9890",
              margin: "0 0 14px 0",
            }}>
              How it works
            </p>
            <h2 style={{
              fontSize: "28px",
              fontWeight: 500,
              color: "#2c2a24",
              letterSpacing: "-0.01em",
              margin: "0 0 12px 0",
            }}>
              From raw knowledge to published post in minutes
            </h2>
            <p style={{ fontSize: "14px", color: "#8a8880", margin: 0 }}>
              Four steps. No templates. No generic output.
            </p>
          </div>

          {/* Steps */}
          <div style={{ maxWidth: "600px", margin: "0 auto" }}>
            {STEPS.map((step, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: "24px",
                  alignItems: "flex-start",
                  marginBottom: i < STEPS.length - 1 ? "40px" : 0,
                  position: "relative",
                }}
              >
                {/* Step number */}
                <div style={{ position: "relative", flexShrink: 0 }}>
                  <div style={{
                    width: "32px",
                    height: "32px",
                    backgroundColor: "#2c2a24",
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "12px",
                    fontWeight: 500,
                    color: "#ffffff",
                  }}>
                    {i + 1}
                  </div>
                  {/* Connector line */}
                  {i < STEPS.length - 1 && (
                    <div style={{
                      position: "absolute",
                      left: "15px",
                      top: "32px",
                      width: "1px",
                      height: "40px",
                      backgroundColor: "#e2ddd5",
                    }} />
                  )}
                </div>

                {/* Step content */}
                <div style={{ paddingTop: "4px" }}>
                  <p style={{ fontSize: "15px", fontWeight: 500, color: "#2c2a24", margin: "0 0 6px 0" }}>
                    {step.title}
                  </p>
                  <p style={{ fontSize: "13.5px", color: "#8a8880", lineHeight: 1.65, margin: 0 }}>
                    {step.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={{
        borderTop: "0.5px solid #e8e3da",
        backgroundColor: "#f5f4f1",
        padding: "32px 48px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}>
        <p style={{ fontSize: "13px", color: "#9a9890", margin: 0 }}>
          © 2026 Contendo. Built for creators who think in public.
        </p>
        <div style={{ display: "flex", gap: "20px" }}>
          <a href="#" style={{ fontSize: "13px", color: "#9a9890", textDecoration: "none", cursor: "pointer" }}>Privacy</a>
          <a href="#" style={{ fontSize: "13px", color: "#9a9890", textDecoration: "none", cursor: "pointer" }}>Terms</a>
        </div>
      </footer>
    </div>
  );
}
