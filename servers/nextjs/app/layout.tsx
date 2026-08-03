import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Providers } from "./providers";
import MixpanelInitializer from "./MixpanelInitializer";
import { Toaster } from "@/components/ui/sonner";
import { BRAND_ASSETS, DISPLAY_PRODUCT, PRODUCT_DESCRIPTION, PRODUCT_TITLE, publicSiteUrl } from "@/lib/product-metadata";
const inter = localFont({
  src: [
    {
      path: "./fonts/Inter.ttf",
      weight: "400",
      style: "normal",
    },
  ],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  metadataBase: publicSiteUrl(),
  title: PRODUCT_TITLE,
  description: PRODUCT_DESCRIPTION,
  keywords: [
    "AI presentation generator",
    "data storytelling",
    "data visualization tool",
    "AI data presentation",
    "presentation generator",
    "data to presentation",
    "interactive presentations",
    "professional slides",
  ],
  openGraph: {
    title: PRODUCT_TITLE,
    description: PRODUCT_DESCRIPTION,
    url: publicSiteUrl(),
    siteName: DISPLAY_PRODUCT.name,
    images: [
      {
        url: BRAND_ASSETS.splash,
        width: 1200,
        height: 630,
        alt: `${DISPLAY_PRODUCT.name} preview`,
      },
    ],
    type: "website",
    locale: "en_US",
  },
  alternates: {
    canonical: publicSiteUrl(),
  },
  twitter: {
    card: "summary_large_image",
    title: PRODUCT_TITLE,
    description: PRODUCT_DESCRIPTION,
    images: [BRAND_ASSETS.splash],
  },
  icons: {
    icon: BRAND_ASSETS.favicon,
    apple: BRAND_ASSETS.compactIcon,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {

  return (
    <html lang="en">
      <head>
        <link rel="preload" href={BRAND_ASSETS.splash} as="image" />
      </head>
      <body
        className={`${inter.variable} antialiased`}
      >
        <Providers>
          <MixpanelInitializer>

            {children}

          </MixpanelInitializer>
        </Providers>
        <Toaster position="top-center" />
      </body>
    </html>
  );
}
