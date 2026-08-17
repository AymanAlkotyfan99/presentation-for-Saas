"use client";

import { useTransition } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { Languages } from "lucide-react";
import {
  LOCALE_COOKIE_MAX_AGE_SECONDS,
  LOCALE_COOKIE_NAME,
  SUPPORTED_LOCALES,
  type SupportedLocale,
} from "@/i18n/config";
import { localizePathname } from "@/i18n/routing";
import { useI18n } from "@/i18n/catalog";
import { recordLocalizationSignal } from "@/i18n/observability";

async function persistAuthenticatedLocale(locale: SupportedLocale) {
  try {
    await fetch("/api/v1/auth/preferences/locale", {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preferred_locale: locale }),
    });
  } catch {
    // The safe cookie still persists anonymous/local-mode selection. The API
    // remains the source of truth when an authenticated account is available.
  }
}

export function LocaleSwitcher({ compact = false }: { compact?: boolean }) {
  const { locale, t } = useI18n();
  const pathname = usePathname() || "/";
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const switchLocale = (nextLocale: SupportedLocale) => {
    if (nextLocale === locale) return;
    document.cookie = `${LOCALE_COOKIE_NAME}=${nextLocale}; Path=/; Max-Age=${LOCALE_COOKIE_MAX_AGE_SECONDS}; SameSite=Lax`;
    recordLocalizationSignal("locale_selected", {
      locale: nextLocale,
      source: "locale_switcher",
    });
    void persistAuthenticatedLocale(nextLocale);
    const query = searchParams.toString();
    const href = `${localizePathname(pathname, nextLocale)}${query ? `?${query}` : ""}`;
    // The locale catalog and document direction live in the persistent root
    // layout. A document navigation ensures <html lang/dir> and the complete
    // server-rendered catalog change together instead of retaining stale LTR
    // state during an App Router transition.
    startTransition(() => window.location.assign(href));
  };

  return (
    <label className="inline-flex items-center gap-2 text-sm" aria-label={t("accessibility.changeLanguage")}>
      <Languages className="h-4 w-4" aria-hidden="true" />
      <span className={compact ? "sr-only" : "hidden sm:inline"}>{t("common.language")}</span>
      <select
        value={locale}
        disabled={isPending}
        onChange={(event) => switchLocale(event.target.value as SupportedLocale)}
        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary"
        aria-label={t("accessibility.changeLanguage")}
      >
        {SUPPORTED_LOCALES.map((supportedLocale) => (
          <option key={supportedLocale} value={supportedLocale}>
            {supportedLocale === "ar" ? t("common.arabic") : t("common.english")}
          </option>
        ))}
      </select>
    </label>
  );
}
