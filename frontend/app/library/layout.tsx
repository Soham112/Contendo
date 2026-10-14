import type { Metadata } from "next";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Library",
  description: "Everything in your memory.",
  path: "/library",
  index: false,
});

export default function LibraryLayout({ children }: { children: React.ReactNode }) {
  return children;
}
