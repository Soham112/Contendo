import type { Metadata } from "next";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Post ideas",
  description: "Ideas for posts, drawn from your memory.",
  path: "/ideas",
  index: false,
});

export default function IdeasLayout({ children }: { children: React.ReactNode }) {
  return children;
}
