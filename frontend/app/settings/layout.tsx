import type { Metadata } from "next";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Settings",
  description: "Your profile, accounts and plan.",
  path: "/settings",
  index: false,
});

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
