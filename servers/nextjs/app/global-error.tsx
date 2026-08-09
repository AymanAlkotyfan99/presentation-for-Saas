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
      <body className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
        <section className="max-w-lg rounded-xl bg-white p-8 text-center shadow" role="alert">
          <h1 className="text-2xl font-bold">{t("errors.unknown")}</h1>
          <button className="mt-6 rounded-md bg-primary px-4 py-2 text-white" onClick={reset}>
            {t("common.retry")}
          </button>
        </section>
      </body>
    </html>
  );
}
