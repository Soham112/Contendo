import type { Metadata } from "next";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Get started",
  description: "Tell Contendo who you are creating content for.",
  path: "/get-started",
  index: false,
});

export default function GetStartedLayout({ children }: { children: React.ReactNode }) {
  return children;
}
