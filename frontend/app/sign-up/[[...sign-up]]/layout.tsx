import type { Metadata } from "next";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Create your account",
  description: "Create a Contendo account and write your first post free.",
  path: "/sign-up",
  index: false,
});

export default function SignUpLayout({ children }: { children: React.ReactNode }) {
  return children;
}
