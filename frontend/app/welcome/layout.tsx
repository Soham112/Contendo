import type { Metadata } from "next";
import { DEFAULT_DESCRIPTION, pageMetadata } from "@/lib/seo";

// "/" and "/welcome" render the same page: both name "/" as canonical.
export const metadata: Metadata = {
  ...pageMetadata({ title: "Contendo: posts in your voice, published for you", description: DEFAULT_DESCRIPTION, path: "/" }),
  title: { absolute: "Contendo: posts in your voice, published for you" },
};

export default function WelcomeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="min-h-screen">{children}</div>;
}
