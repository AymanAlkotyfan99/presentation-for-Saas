"use client";

import { CircleAlert, SearchX } from "lucide-react";

import { useTranslations } from "@/i18n/catalog";
import { EmptyState } from "./EmptyState";

export function PresentationLibrarySkeleton() {
  return (
    <div className="grid w-full grid-cols-1 gap-5 sm:gap-6 md:grid-cols-2 lg:grid-cols-4" role="status" aria-label="Loading presentations">
      {Array.from({ length: 12 }, (_, index) => (
        <div key={index} className="flex min-h-[216px] animate-pulse flex-col overflow-hidden rounded-xl border border-[#EDEEEF] bg-[#F8FBFB] shadow-none motion-reduce:animate-none">
          <div className="relative flex-1 overflow-hidden p-4">
            <div aria-hidden="true" className="absolute inset-0 bg-[url('/card_bg.svg')] bg-cover bg-center opacity-70" />
            <div className="relative mx-auto mt-2 aspect-video w-[88%] rounded-lg border border-gray-200 bg-gray-200" />
          </div>
          <div className="relative z-10 border-t border-[#EDEEEF] bg-white px-5 py-3">
            <div className="flex items-center justify-between gap-6">
              <div className="space-y-2"><div className="h-3.5 w-24 rounded bg-gray-200" /><div className="h-3 w-16 rounded bg-gray-200" /></div>
              <div className="h-5 w-1 rounded-full bg-gray-200" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function PresentationLibraryError({ error, onRetry }: { error: string; onRetry?: () => void }) {
  const t = useTranslations();
  return (
    <div className="flex min-h-[260px] items-center justify-center rounded-2xl border border-[#F3D6D2] bg-[#FFF9F8] px-5" role="alert">
      <div className="max-w-sm text-center">
        <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-[#FFF0EE] text-[#B42318]"><CircleAlert className="h-5 w-5" aria-hidden="true" /></span>
        <h3 className="mt-4 text-base font-semibold text-[#632A25]">{t("dashboard.loadFailedTitle")}</h3>
        <p className="mt-2 text-sm leading-6 text-[#8E4A43]">{error}</p>
        <button type="button" onClick={onRetry} className="mt-5 min-h-10 rounded-xl bg-[#B42318] px-5 text-sm font-semibold text-white transition hover:bg-[#912018] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#B42318] focus-visible:ring-offset-2">
          {t("common.retry")}
        </button>
      </div>
    </div>
  );
}

export function PresentationLibraryEmpty({ searchActive, onClearSearch }: { searchActive?: boolean; onClearSearch?: () => void }) {
  const t = useTranslations();
  if (!searchActive) return <EmptyState />;
  return (
    <div className="flex min-h-[260px] flex-col items-center justify-center rounded-2xl bg-[#FAFAFC] px-5 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-[#7A8190] shadow-sm"><SearchX className="h-5 w-5" aria-hidden="true" /></span>
      <h3 className="mt-4 text-base font-semibold text-[#303442]">{t("dashboard.noResultsTitle")}</h3>
      <p className="mt-2 text-sm text-[#7A8190]">{t("dashboard.noResultsDescription")}</p>
      <button type="button" onClick={onClearSearch} className="mt-4 min-h-10 rounded-xl px-4 text-sm font-semibold text-[#5538D7] hover:bg-[#F0EDFF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]">{t("dashboard.clearSearch")}</button>
    </div>
  );
}
