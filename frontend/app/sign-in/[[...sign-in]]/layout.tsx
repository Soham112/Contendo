import type { Metadata } from "next";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Sign in",
  description: "Sign in to Contendo.",
  path: "/sign-in",
  index: false,
});

export default function SignInLayout({ children }: { children: React.ReactNode }) {
  return children;
}
