"use client";

import { ArrowLeft, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslations } from "@/i18n/catalog";

export function TemplatePreviewLoadingState() {
  const t = useTranslations();
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#FAFAFB]">
      <Loader2 className="h-8 w-8 animate-spin text-[#7A5AF8]" />
      <span className="ms-3 text-sm font-medium text-[#696969]">
        {t("templates.loadingTemplate")}
      </span>
    </div>
  );
}

export function TemplatePreviewErrorState({
  onBack,
}: {
  error: string | null | undefined;
  onBack: () => void;
}) {
  const t = useTranslations();
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#FAFAFB] px-6 text-center">
      <h2 className="mb-3 text-2xl font-semibold text-[#191919]">
        {t("templates.errorLoading")}
      </h2>
      <p className="mb-6 max-w-lg text-sm text-[#696969]">{t("templates.loadFailed")}</p>
      <Button onClick={onBack} variant="outline">
        <ArrowLeft className="h-4 w-4 rtl:rotate-180" />
        {t("templates.backToTemplates")}
      </Button>
    </div>
  );
}

export function TemplatePreviewNotFoundState({
  onBack,
}: {
  onBack: () => void;
}) {
  const t = useTranslations();
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#FAFAFB] px-6 text-center">
      <h2 className="mb-6 text-2xl font-semibold text-[#191919]">
        {t("templates.notFound")}
      </h2>
      <Button onClick={onBack} variant="outline">
        <ArrowLeft className="h-4 w-4 rtl:rotate-180" />
        {t("templates.backToTemplates")}
      </Button>
    </div>
  );
}
