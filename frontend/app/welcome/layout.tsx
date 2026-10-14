import type { Metadata } from "next";
import { HOME_SEO } from "@/content/home";
import { pageMetadata } from "@/lib/seo";

// "/" and "/welcome" render the same page: both name "/" as canonical.
export const metadata: Metadata = pageMetadata(HOME_SEO);

export default function WelcomeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="min-h-screen">{children}</div>;
}
