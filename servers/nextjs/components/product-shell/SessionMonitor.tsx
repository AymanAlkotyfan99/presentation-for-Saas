"use client";

import { useCallback, useEffect } from "react";
import { usePathname } from "next/navigation";

import { getApiUrl } from "@/utils/api";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";
import { fetchWithTimeout } from "@/utils/fetchWithTimeout";

const SESSION_CHECK_INTERVAL_MS = 60_000;

export function SessionMonitor() {
  const pathname = usePathname() || "/";
  const { locale } = useI18n();

  const checkSession = useCallback(async () => {
    try {
      const response = await fetchWithTimeout(getApiUrl("/api/v1/auth/status"), {
        cache: "no-store",
        credentials: "include",
      }, 10_000);
      if (!response.ok) return;
      const status = (await response.json()) as { authenticated?: boolean };
      if (status.authenticated) return;

      const login = new URL(localizePathname("/", locale), window.location.origin);
      login.searchParams.set("reason", "session-expired");
      login.searchParams.set("next", pathname);
      window.location.replace(`${login.pathname}${login.search}`);
    } catch {
      // Temporary network loss is handled by each screen's recoverable error UI.
      // It must not be mistaken for a signed-out session.
    }
  }, [locale, pathname]);

  useEffect(() => {
    const interval = window.setInterval(() => void checkSession(), SESSION_CHECK_INTERVAL_MS);
    const handleVisibility = () => {
      if (document.visibilityState === "visible") void checkSession();
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [checkSession]);

  return null;
}
