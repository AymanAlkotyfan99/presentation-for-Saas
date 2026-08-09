import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import "@/styles/rtl.css";
import { Providers } from "./providers";
import MixpanelInitializer from "./MixpanelInitializer";
import { Toaster } from "@/components/ui/sonner";
import { BRAND_ASSETS, DISPLAY_PRODUCT, PRODUCT_DESCRIPTION, PRODUCT_TITLE, publicSiteUrl } from "@/lib/product-metadata";
import { I18nProvider } from "@/i18n/catalog";
import { ARABIC_FONTS_ENABLED, localeDirection } from "@/i18n/config";
import { messagesForLocale, requestLocale } from "@/i18n/server";
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

const notoSansArabic = localFont({
  src: [{ path: "./fonts/NotoSansArabic.ttf", weight: "100 900", style: "normal" }],
  variable: "--font-arabic-ui",
  fallback: ["Tahoma", "Arial", "sans-serif"],
});

export async function generateMetadata(): Promise<Metadata> {
  const locale = await requestLocale();
  const localizedDescription = locale === "ar"
    ? "منصة مدعومة بالذكاء الاصطناعي لإنشاء عروض تقديمية احترافية بالعربية والإنجليزية."
    : PRODUCT_DESCRIPTION;
  return {
    metadataBase: publicSiteUrl(),
    title: PRODUCT_TITLE,
    description: localizedDescription,
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
    description: localizedDescription,
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
    locale: locale === "ar" ? "ar_AR" : "en_US",
    alternateLocale: locale === "ar" ? ["en_US"] : ["ar_AR"],
  },
  alternates: {
    canonical: publicSiteUrl(),
  },
  twitter: {
    card: "summary_large_image",
    title: PRODUCT_TITLE,
    description: localizedDescription,
    images: [BRAND_ASSETS.splash],
  },
  icons: {
    icon: BRAND_ASSETS.favicon,
    apple: BRAND_ASSETS.compactIcon,
  },
  };
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {

  const locale = await requestLocale();
  const direction = localeDirection(locale);
  const messages = messagesForLocale(locale);

  return (
    <html lang={locale} dir={direction} suppressHydrationWarning>
      <head>
        <link rel="preload" href={BRAND_ASSETS.splash} as="image" />
      </head>
      <body
        className={`${inter.variable} ${ARABIC_FONTS_ENABLED ? notoSansArabic.variable : ""} antialiased`}
      >
        <I18nProvider locale={locale} messages={messages}>
          <a href="#main-content" className="skip-link">{messages.accessibility.skipToContent}</a>
          <Providers>
            <MixpanelInitializer>

              <main id="main-content">{children}</main>

            </MixpanelInitializer>
          </Providers>
          <Toaster position="top-center" />
        </I18nProvider>
      </body>
    </html>
  );
}
