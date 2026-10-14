import type { Metadata } from "next";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Create a post",
  description: "Write a post in your voice.",
  path: "/create",
  index: false,
});

export default function CreateLayout({ children }: { children: React.ReactNode }) {
  return children;
}
