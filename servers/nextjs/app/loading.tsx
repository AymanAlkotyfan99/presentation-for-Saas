"use client";

import { useTranslations } from "@/i18n/catalog";
import { DISPLAY_PRODUCT } from "@/lib/product-metadata";

export default function Loading() {
  const t = useTranslations();
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#F8F8FB] px-5" aria-busy="true" role="status">
      <div className="w-full max-w-sm rounded-2xl border border-[#E7E7ED] bg-white p-6 shadow-[0_18px_50px_rgba(36,31,65,0.08)]">
        <div className="flex items-center gap-3">
          <span className="h-10 w-10 animate-pulse rounded-xl bg-[#EEEAFE] motion-reduce:animate-none" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-[#20232D]">{DISPLAY_PRODUCT.shortName}</p>
            <p className="mt-0.5 text-xs text-[#7A8190]">{t("common.loading")}</p>
          </div>
        </div>
        <div className="mt-6 space-y-3" aria-hidden="true">
          <div className="h-3 w-4/5 animate-pulse rounded-full bg-[#EEEFF3] motion-reduce:animate-none" />
          <div className="h-3 w-full animate-pulse rounded-full bg-[#F2F2F5] motion-reduce:animate-none" />
          <div className="h-3 w-2/3 animate-pulse rounded-full bg-[#F2F2F5] motion-reduce:animate-none" />
        </div>
      </div>
    </div>
  );
}
