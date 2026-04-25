import Link from "next/link";

const FEATURES = [
  {
    icon: "📝",
    title: "Feed Memory",
    body: "Upload or paste your knowledge.",
  },
  {
    icon: "✨",
    title: "Create Post",
    body: "Pick a topic. Get a post in 15 seconds.",
  },
  {
    icon: "💡",
    title: "Get Ideas",
    body: "Never run out of things to write about.",
  },
];

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-background text-on-surface font-sans flex flex-col">

      {/* ── Hero ── */}
      <section className="flex-1 flex flex-col items-center justify-center text-center px-4 py-24">
        <h1
          className="font-headline font-normal tracking-tight text-on-surface mb-4"
          style={{ fontSize: "clamp(2.4rem, 5vw, 3.5rem)", lineHeight: 1.1 }}
        >
          Write like yourself. At scale.
        </h1>
        <p
          className="font-sans text-secondary mx-auto"
          style={{ fontSize: "1.1rem", lineHeight: 1.7, maxWidth: "480px" }}
        >
          Contendo learns your voice and writes posts you&apos;d actually publish.
        </p>
      </section>

      {/* ── Feature cards ── */}
      <section className="px-4 pb-20">
        <div
          className="mx-auto grid grid-cols-1 sm:grid-cols-3 gap-6"
          style={{ maxWidth: "860px" }}
        >
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-2xl px-8 py-10 flex flex-col gap-3"
              style={{ background: "#f3f4f3" }}
            >
              <span style={{ fontSize: "1.75rem" }}>{f.icon}</span>
              <p className="font-headline text-on-surface" style={{ fontSize: "1.15rem" }}>
                {f.title}
              </p>
              <p className="font-sans text-secondary" style={{ fontSize: "0.95rem", lineHeight: 1.6 }}>
                {f.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="text-center pb-28 px-4">
        <Link
          href="/sign-up"
          className="inline-flex font-sans font-medium text-white text-base px-8 py-3 rounded-md transition-opacity hover:opacity-90"
          style={{ background: "linear-gradient(135deg, #58614f 0%, #4c5543 100%)" }}
        >
          Try for free
        </Link>
      </section>

    </div>
  );
}
