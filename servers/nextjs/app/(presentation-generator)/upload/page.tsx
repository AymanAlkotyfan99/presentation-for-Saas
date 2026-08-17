import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { localizePathname } from "@/i18n/routing";
import { messagesForLocale, requestLocale } from "@/i18n/server";
import {
  DISPLAY_PRODUCT,
  PRODUCT_DESCRIPTION,
  publicSiteUrl,
} from "@/lib/product-metadata";

const createUrl = new URL("/create", publicSiteUrl());

export async function generateMetadata(): Promise<Metadata> {
  const messages = messagesForLocale(await requestLocale());
  const localizedTitle = `${messages.generation.title} | ${DISPLAY_PRODUCT.shortName}`;
  const localizedDescription =
    messages.generation.heroDescription || PRODUCT_DESCRIPTION;
  return {
    title: localizedTitle,
    description: localizedDescription,
    alternates: { canonical: createUrl },
    openGraph: {
      title: localizedTitle,
      description: localizedDescription,
      type: "website",
      url: createUrl,
      siteName: DISPLAY_PRODUCT.name,
    },
  };
}

export default async function UploadCompatibilityPage() {
  redirect(localizePathname("/create", await requestLocale()));
}
