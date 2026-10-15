import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import AppShell from "@/components/AppShell";
import { ToastProvider } from "@/components/ui/ToastProvider";
import { MotionProvider } from "@/components/ui/motion";
import { DEFAULT_DESCRIPTION, DEFAULT_SOCIAL_IMAGE, SITE_NAME, SITE_URL, TITLE_SUFFIX } from "@/lib/seo";

// Served from the app and swapped in when ready, so text paints at once and
// no request to Google blocks rendering. The files ship in app/fonts (the Latin
// variable fonts Google Fonts serves for Noto Serif and Inter), so the build
// never fetches from Google: a Google Fonts hiccup used to fail the Vercel
// build in next/font/google. Exposed as CSS variables that tailwind.config.ts
// and globals.css read.
const headline = localFont({
  src: [
    { path: "./fonts/noto-serif-latin-wght.woff2", weight: "100 900", style: "normal" },
    { path: "./fonts/noto-serif-latin-italic-wght.woff2", weight: "100 900", style: "italic" },
  ],
  display: "swap", variable: "--font-headline", adjustFontFallback: "Times New Roman",
});
const body = localFont({
  src: "./fonts/inter-latin-wght.woff2", weight: "100 900",
  display: "swap", variable: "--font-body", adjustFontFallback: "Arial",
});

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
