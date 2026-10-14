import Link from "next/link";
import { NICHE_PAGES } from "@/content/niches";

/** Links to every niche landing page, for footers, so crawlers reach them all. */
export default function NicheLinks() {
  return (
    <div>
      <p className="label-caps text-on-surface" style={{ fontSize: "0.72rem" }}>
        Contendo for
      </p>
      <div className="mt-3 flex flex-col gap-2.5">
        <Link href="/privacy-policy" className="text-secondary hover:text-on-surface text-sm">Privacy policy</Link>
        <Link href="/terms-of-service" className="text-secondary hover:text-on-surface text-sm">Terms of service</Link>
        {NICHE_PAGES.map((page) => (
          <Link
            key={page.slug}
            href={`/${page.slug}`}
            className="text-secondary hover:text-on-surface transition-colors"
            style={{ fontSize: "0.9rem" }}
          >
            {page.linkLabel}
          </Link>
        ))}
      </div>
    </div>
  );
}
