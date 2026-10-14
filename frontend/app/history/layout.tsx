import type { Metadata } from "next";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "History",
  description: "The posts you have written.",
  path: "/history",
  index: false,
});

export default function HistoryLayout({ children }: { children: React.ReactNode }) {
  return children;
}
