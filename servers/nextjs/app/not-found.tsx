"use client";

import Link from "next/link";
import { ArrowRight, Home } from "lucide-react";

import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";

export default function NotFound() {
  const { locale, t } = useI18n();
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#F8F8FB] p-5 text-center">
      <div className="mx-auto w-full max-w-lg rounded-3xl border border-[#E7E7ED] bg-white p-7 shadow-[0_18px_50px_rgba(36,31,65,0.08)] sm:p-10">
        <div aria-hidden="true" className="mx-auto mb-7 flex h-40 w-full max-w-[300px] items-center justify-center rounded-3xl bg-gradient-to-br from-[#EEEAFE] to-[#F4FBFA] text-6xl font-semibold tracking-[-0.08em] text-[#6344E8] sm:h-48 sm:text-7xl">
          404
        </div>
        <h1 className="font-syne text-2xl font-semibold tracking-[-0.04em] text-[#171A24] sm:text-3xl">{t("errors.notFoundTitle")}</h1>
        <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[#667085] sm:text-base">{t("errors.notFoundDescription")}</p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <Link href={localizePathname("/dashboard", locale)} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#6F4EF6] px-5 text-sm font-semibold text-white transition hover:bg-[#6242E8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] focus-visible:ring-offset-2">
            <Home className="h-4 w-4" aria-hidden="true" />
            {t("navigation.dashboard")}
          </Link>
          <Link href={localizePathname("/create", locale)} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-[#D9D4F8] bg-[#F7F5FF] px-5 text-sm font-semibold text-[#5538D7] transition hover:bg-[#F0EDFF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]">
            {t("navigation.create")}
            <ArrowRight className="rtl-flip h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </div>
  );
}
