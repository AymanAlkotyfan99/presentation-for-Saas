'use client'
import React from "react";
import PresentationPage from "./components/PresentationPage";
import { Button } from "@/components/ui/button";
import { useRouter, useSearchParams } from "next/navigation";
import "../utils/prism-languages";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";
const page = () => {
  const { locale, t } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const queryId = params.get("id");
  if (!queryId) {
    return (
      <div className="flex flex-col items-center justify-center h-screen font-syne">
        <h1 className="text-2xl font-bold">{t("presentation.missingId")}</h1>
        <p className="pb-4 text-gray-500">{t("common.retry")}</p>
        <Button onClick={() => router.push(localizePathname("/dashboard", locale))}>{t("presentation.goHome")}</Button>
      </div>
    );
  }
  return (

    <PresentationPage presentation_id={queryId} />

  );
};
export default page;
