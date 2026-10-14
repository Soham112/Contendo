import type { Metadata } from "next";
import { Inter, Noto_Serif } from "next/font/google";
import "./globals.css";
import AppShell from "@/components/AppShell";
import { ToastProvider } from "@/components/ui/ToastProvider";
import { MotionProvider } from "@/components/ui/motion";
import { DEFAULT_DESCRIPTION, DEFAULT_SOCIAL_IMAGE, SITE_NAME, SITE_URL, TITLE_SUFFIX } from "@/lib/seo";

// Self-hosted at build time and swapped in when ready, so text paints at once
// and no request to Google blocks rendering. Exposed as CSS variables that
// tailwind.config.ts and globals.css read.
const headline = Noto_Serif({
  subsets: ["latin"], weight: ["400", "700"], style: ["normal", "italic"],
  display: "swap", variable: "--font-headline",
});
const body = Inter({ subsets: ["latin"], weight: ["300", "400", "500", "600"], display: "swap", variable: "--font-body" });

// Site-wide defaults only. No canonical URL here: a page inherits it unless it
// sets its own, and every page would then claim to be a copy of "/". Pages set
// theirs through pageMetadata() in lib/seo.ts.
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  // pageMetadata() writes each page's full title; the template covers pages
  // that set a plain title without it.
  title: { default: SITE_NAME, template: `%s${TITLE_SUFFIX}` },
  description: DEFAULT_DESCRIPTION,
  openGraph: { siteName: SITE_NAME, type: "website", images: [DEFAULT_SOCIAL_IMAGE] },
  twitter: { card: "summary_large_image", images: [DEFAULT_SOCIAL_IMAGE.url] },
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
        <MotionProvider>
          <ToastProvider>
            <AppShell>{children}</AppShell>
          </ToastProvider>
        </MotionProvider>
      </body>
    </html>
  );
}
