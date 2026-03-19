import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

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
      <body className="min-h-screen bg-gray-50 text-gray-900">
        <nav className="border-b border-gray-200 bg-white px-6 py-4">
          <div className="max-w-4xl mx-auto flex items-center justify-between">
            <span className="font-semibold text-gray-900 tracking-tight">
              Contendo
            </span>
            <div className="flex gap-6 text-sm">
              <Link
                href="/"
                className="text-gray-500 hover:text-gray-900 transition-colors"
              >
                Feed Memory
              </Link>
              <Link
                href="/library"
                className="text-gray-500 hover:text-gray-900 transition-colors"
              >
                Library
              </Link>
              <Link
                href="/create"
                className="text-gray-500 hover:text-gray-900 transition-colors"
              >
                Create Post
              </Link>
              <Link
                href="/history"
                className="text-gray-500 hover:text-gray-900 transition-colors"
              >
                History
              </Link>
            </div>
          </div>
        </nav>
        <main className="max-w-4xl mx-auto px-6 py-10">{children}</main>
      </body>
    </html>
  );
}
