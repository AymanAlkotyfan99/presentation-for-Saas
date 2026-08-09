"use client";

import { PresentonSplashLoader } from "@/components/ui/presenton-splash-loader";
import { useTranslations } from "@/i18n/catalog";

export default function Loading() {
  const t = useTranslations();
  return <PresentonSplashLoader message={t("common.loading")} />;
}
