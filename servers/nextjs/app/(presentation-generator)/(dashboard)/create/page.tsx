import type { Metadata } from "next";

import UploadPage from "../../upload/components/UploadPage";
import { DISPLAY_PRODUCT } from "@/lib/product-metadata";
import { messagesForLocale, requestLocale } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const messages = messagesForLocale(await requestLocale());
  return {
    title: `${messages.generation.title} | ${DISPLAY_PRODUCT.shortName}`,
    description: messages.generation.heroDescription,
  };
}

export default function CreatePresentationPage() {
  return <UploadPage />;
}
