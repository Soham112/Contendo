import type { Metadata } from "next";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Admin",
  description: "Admin.",
  path: "/admin",
  index: false,
});

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return children;
}
