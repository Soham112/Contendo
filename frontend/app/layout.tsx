import type { Metadata } from "next";
import { Inter, Noto_Serif } from "next/font/google";
import "./globals.css";
import AppShell from "@/components/AppShell";
import { ToastProvider } from "@/components/ui/ToastProvider";
import { DEFAULT_DESCRIPTION, SITE_NAME, SITE_URL, pageMetadata } from "@/lib/seo";

// Self-hosted at build time and swapped in when ready, so text paints at once
// and no request to Google blocks rendering. Exposed as CSS variables that
// tailwind.config.ts and globals.css read.
const headline = Noto_Serif({
  subsets: ["latin"], weight: ["400", "700"], style: ["normal", "italic"],
  display: "swap", variable: "--font-headline",
});
const body = Inter({ subsets: ["latin"], weight: ["300", "400", "500", "600"], display: "swap", variable: "--font-body" });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  ...pageMetadata({ title: `${SITE_NAME}: posts in your voice, published for you`, description: DEFAULT_DESCRIPTION, path: "/" }),
  // A page's own title is shown as "<title> | Contendo".
  title: { default: `${SITE_NAME}: posts in your voice, published for you`, template: `%s | ${SITE_NAME}` },
  icons: { icon: "/favicon.png" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${headline.variable} ${body.variable}`}>
      <body className="bg-page text-text-primary">
        <ToastProvider>
          <AppShell>{children}</AppShell>
        </ToastProvider>
      </body>
    </html>
  );
}
