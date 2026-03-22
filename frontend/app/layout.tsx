import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "Contendo",
  description: "Personal content generation system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-page text-text-primary">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
