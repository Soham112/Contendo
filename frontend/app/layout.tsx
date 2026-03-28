import type { Metadata } from "next";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import AppShell from "@/components/AppShell";
import { ToastProvider } from "@/components/ui/ToastProvider";

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
    <ClerkProvider>
      <html lang="en">
        <body className="bg-page text-text-primary">
          <ToastProvider>
            <AppShell>{children}</AppShell>
          </ToastProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
