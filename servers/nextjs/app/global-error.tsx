"use client";

import { useEffect } from "react";
import ar from "@/messages/ar.json";
import en from "@/messages/en.json";
import { localeDirection, normalizeLocale } from "@/i18n/config";
import { translateMessage } from "@/i18n/catalog";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global error:", error);
  }, [error]);

  const cookieLocale = typeof document === "undefined"
    ? "en"
    : document.cookie.match(/(?:^|; )bayanly_locale=([^;]+)/)?.[1];
  const locale = normalizeLocale(cookieLocale);
  const messages = locale === "ar" ? ar : en;
  const t = (key: string) => translateMessage(messages, key);

  return (
    <html lang={locale} dir={localeDirection(locale)}>
      <body className="flex min-h-screen items-center justify-center bg-[#F8F8FB] p-5 font-sans">
        <section className="w-full max-w-lg rounded-3xl border border-[#E7E7ED] bg-white p-8 text-center shadow-[0_18px_50px_rgba(36,31,65,0.08)]" role="alert">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#FFF1F0] text-2xl font-bold text-[#B42318]" aria-hidden="true">!</div>
          <h1 className="mt-6 text-2xl font-semibold tracking-[-0.04em] text-[#171A24]">{t("errors.unknown")}</h1>
          <p className="mt-3 text-sm leading-6 text-[#667085]">{t("errors.network")}</p>
          <div className="mt-7 flex flex-col justify-center gap-3 sm:flex-row">
            <button className="min-h-11 rounded-xl bg-[#6F4EF6] px-5 text-sm font-semibold text-white transition hover:bg-[#6242E8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] focus-visible:ring-offset-2" onClick={reset}>
              {t("common.retry")}
            </button>
            <button className="min-h-11 rounded-xl border border-[#D9D4F8] bg-[#F7F5FF] px-5 text-sm font-semibold text-[#5538D7] transition hover:bg-[#F0EDFF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]" onClick={() => window.location.assign(`/${locale}/dashboard`)}>
              {t("navigation.dashboard")}
            </button>
          </div>
        </section>
      </body>
    </html>
  );
}
