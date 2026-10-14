import type { Metadata } from "next";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Write your first post",
  description: "Answer a few questions and get your first post in your own voice.",
  path: "/first-post",
  index: false,
});

export default function FirstPostLayout({ children }: { children: React.ReactNode }) {
  return children;
}
