import type { Metadata } from "next";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Scheduled and published",
  description: "Your scheduled and published posts.",
  path: "/scheduled",
  index: false,
});

export default function ScheduledLayout({ children }: { children: React.ReactNode }) {
  return children;
}
