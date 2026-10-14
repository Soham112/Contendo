import type { Metadata } from "next";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Feed memory",
  description: "Add what you know to your memory.",
  path: "/feed-memory",
  index: false,
});

export default function FeedMemoryLayout({ children }: { children: React.ReactNode }) {
  return children;
}
