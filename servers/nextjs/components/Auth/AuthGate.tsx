"use client";

import { FormEvent, useEffect, useState } from "react";
import Image from "next/image";
import { getApiUrl } from "@/utils/api";
import { isAuthDisabled } from "@/utils/auth";
import { formatFastApiDetail, UNAUTHORIZED_DETAIL } from "@/utils/authErrors";
import {
  PRESENTON_SPLASH_MIN_DURATION_MS,
  PresentonSplashLoader,
} from "@/components/ui/presenton-splash-loader";
import { BRAND_ASSETS } from "@/lib/product-metadata";
import { notify } from "@/components/ui/sonner";
import { sanitizeAnalyticsError } from "@/utils/analytics";
import { MixpanelEvent, trackEvent } from "@/utils/mixpanel";
import { useTranslations } from "@/i18n/catalog";
import { apiErrorLocalization } from "@/utils/apiErrorMessages";
import { LOCALE_COOKIE_NAME, type SupportedLocale } from "@/i18n/config";
import { recordLocalizationSignal } from "@/i18n/observability";

type AuthStatus = {
  configured: boolean;
  authenticated: boolean;
  username: string | null;
  role?: "admin" | "user" | null;
  preferred_locale?: SupportedLocale | null;
};

const initialStatus: AuthStatus = {
  configured: true,
  authenticated: false,
  username: null,
  role: null,
};

export default function AuthGate() {
  const t = useTranslations();
  const [status, setStatus] = useState<AuthStatus>(initialStatus);
  const [isLoading, setIsLoading] = useState(true);
  const [isRedirecting, setIsRedirecting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasMetSplashDuration, setHasMetSplashDuration] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setHasMetSplashDuration(true);
    }, PRESENTON_SPLASH_MIN_DURATION_MS);

    return () => window.clearTimeout(timeout);
  }, []);

  useEffect(() => {
    if (isAuthDisabled()) {
      trackEvent(MixpanelEvent.Auth_Status_Checked, {
        configured: true,
        authenticated: true,
        auth_disabled: true,
      });
      setStatus({
        configured: true,
        authenticated: true,
        username: "electron",
        role: "admin",
      });
      setIsLoading(false);
      return;
    }

    void refreshStatus();
  }, []);

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      isLoading ||
      !status.authenticated ||
      isRedirecting
    ) {
      return;
    }

    setIsRedirecting(true);
    window.location.replace("/");
  }, [isLoading, isRedirecting, status.authenticated]);

  useEffect(() => {
    if (typeof window === "undefined" || isLoading) {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    if (params.get("reason") === "unauthorized") {
      if (!status.authenticated) {
        trackEvent(MixpanelEvent.Auth_Unauthorized_Redirect, {
          configured: true,
        });
        notify.error(t("auth.required"), t("auth.required"), {
          id: "auth-unauthorized-redirect",
          duration: 5000,
        });
      }
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [isLoading, status.authenticated, status.configured, t]);

  const refreshStatus = async () => {
    setIsLoading(true);

    try {
      const response = await fetch(getApiUrl("/api/v1/auth/status"), {
        method: "GET",
        cache: "no-store",
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error("Could not load login state");
      }

      const data = (await response.json()) as AuthStatus;
      if (
        data.authenticated &&
        (data.preferred_locale === "en" || data.preferred_locale === "ar")
      ) {
        document.cookie = `${LOCALE_COOKIE_NAME}=${data.preferred_locale}; Path=/; Max-Age=31536000; SameSite=Lax`;
        recordLocalizationSignal("locale_selected", {
          locale: data.preferred_locale,
          source: "account",
        });
      }
      trackEvent(MixpanelEvent.Auth_Status_Checked, {
        configured: Boolean(data.configured),
        authenticated: Boolean(data.authenticated),
        auth_disabled: false,
        role: data.role ?? null,
        preferred_locale: data.preferred_locale ?? null,
      });
      setStatus({
        configured: Boolean(data.configured),
        authenticated: Boolean(data.authenticated),
        username: data.username ?? null,
        role: data.role ?? null,
      });
    } catch (fetchError) {
      console.error(fetchError);
      trackEvent(MixpanelEvent.Auth_Status_Checked, {
        configured: true,
        authenticated: false,
        auth_disabled: false,
        error_message: sanitizeAnalyticsError(
          fetchError,
          "Could not load login state"
        ),
      });
      notify.error(
        t("auth.unavailable"),
        t("errors.network")
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (
      isLoading ||
      isRedirecting ||
      status.authenticated ||
      !hasMetSplashDuration
    ) {
      return;
    }

    trackEvent(MixpanelEvent.Auth_Gate_Viewed, {
      flow: "sign_in",
    });
  }, [
    hasMetSplashDuration,
    isLoading,
    isRedirecting,
    status.authenticated,
  ]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const cleanedUsername = username.trim();
    if (cleanedUsername.length < 3) {
      trackEvent(MixpanelEvent.Auth_Validation_Failed, {
        flow: "sign_in",
        reason: "username_too_short",
      });
      notify.warning(
        t("validation.required"),
        t("auth.usernameTooShort")
      );
      return;
    }

    if (password.length < 6) {
      trackEvent(MixpanelEvent.Auth_Validation_Failed, {
        flow: "sign_in",
        reason: "password_too_short",
      });
      notify.warning(
        t("validation.required"),
        t("auth.passwordTooShort")
      );
      return;
    }

    setIsSubmitting(true);
    trackEvent(MixpanelEvent.Auth_SignIn_Started, {
      username_length: cleanedUsername.length,
    });

    try {
      const response = await fetch(
        getApiUrl("/api/v1/auth/login"),
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            username: cleanedUsername,
            password,
          }),
        }
      );

      const payload = await response.json();
      if (!response.ok) {
        const detail = formatFastApiDetail(payload?.detail);
        const localized = apiErrorLocalization(payload);
        const safeMessage = localized
          ? t(localized.key, localized.params)
          : t("errors.unknown");
        trackEvent(MixpanelEvent.Auth_SignIn_Failed, {
          status_code: response.status,
          error_message: sanitizeAnalyticsError(detail, "Sign-in failed"),
        });
        if (response.status === 401) {
          notify.error(
            t("auth.unauthorized"),
            detail === UNAUTHORIZED_DETAIL
              ? t("auth.unauthorized")
              : safeMessage
          );
        } else {
          notify.error(
            t("errors.unknown"),
            safeMessage
          );
        }
        return;
      }

      setStatus({
        configured: Boolean((payload as AuthStatus).configured),
        authenticated: Boolean((payload as AuthStatus).authenticated),
        username: (payload as AuthStatus).username ?? cleanedUsername,
        role: (payload as AuthStatus).role ?? null,
      });
      trackEvent(MixpanelEvent.Auth_SignIn_Completed, {
        username_length: cleanedUsername.length,
        role: (payload as AuthStatus).role ?? null,
      });
      setPassword("");
      notify.success(
        t("auth.submit"),
        t("auth.signedIn")
      );
    } catch (submitError) {
      console.error(submitError);
      trackEvent(MixpanelEvent.Auth_SignIn_Failed, {
        status_code: null,
        error_message: sanitizeAnalyticsError(
          submitError,
          "Login unavailable"
        ),
      });
      notify.error(
        t("auth.unavailable"),
        t("auth.unavailable")
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (
    isLoading ||
    isRedirecting ||
    status.authenticated ||
    !hasMetSplashDuration
  ) {
    return <PresentonSplashLoader message={t("auth.checking")} />;
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-white p-6 font-syne">
      <section className="relative z-10 w-full max-w-lg rounded-[20px] border border-[#EDEEEF] bg-[#F9F8F8] p-7 sm:p-10">
        <div className="mb-7">
          <div className="flex items-center gap-4">
            <div className="flex h-[60px] w-[60px] shrink-0 items-center justify-center rounded-[4px] bg-[#F4F3FF] p-3">
              <Image
                src={BRAND_ASSETS.compactIcon}
                alt=""
                width={161}
                height={166}
                className="h-10 w-auto object-contain"
              />
            </div>
            <div>
              <p className="font-syne text-[10px] font-semibold uppercase tracking-[0.14em] text-[#7A5AF8]">
                {t("auth.secureInstance")}
              </p>
              <h1 className="mt-1 font-unbounded text-xl font-normal leading-tight tracking-[-0.03em] text-black sm:text-[22px]">
                {t("auth.title")}
              </h1>
            </div>
          </div>
        </div>

        <p className="max-w-md text-sm leading-relaxed text-[#6B7280]">
          {t("auth.protectedDescription")}
        </p>

        <form onSubmit={handleSubmit} className="mt-7 space-y-5">
          <div className="space-y-2">
            <label htmlFor="username" className="block text-sm font-medium text-[#374151]">
              {t("auth.username")}
            </label>
            <input
              id="username"
              autoComplete="username"
              value={username}
              onChange={(event) =>
                setUsername(event.target.value.replace(/\s/g, ""))
              }
              placeholder={t("auth.username")}
              minLength={3}
              maxLength={128}
              pattern="\S+"
              title={t("auth.username")}
              required
              spellCheck={false}
              className="h-12 w-full rounded-lg border border-[#E1E1E5] bg-white px-4 text-sm text-[#191919] outline-none transition placeholder:text-[#9CA3AF] focus:border-[#7A5AF8] focus:ring-2 focus:ring-[#7A5AF8]/15"
              disabled={isSubmitting}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="block text-sm font-medium text-[#374151]">
              {t("auth.password")}
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={t("auth.password")}
              minLength={6}
              maxLength={128}
              required
              className="h-12 w-full rounded-lg border border-[#E1E1E5] bg-white px-4 text-sm text-[#191919] outline-none transition placeholder:text-[#9CA3AF] focus:border-[#7A5AF8] focus:ring-2 focus:ring-[#7A5AF8]/15"
              disabled={isSubmitting}
            />
          </div>

          {status.configured ? (
            <p className="rounded-lg border border-[#EDEEEF] bg-white px-4 py-3 text-xs leading-relaxed text-[#6B7280]">
              {t("auth.administratorCredentials")}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-[58px] border border-[#EDEEEF] bg-[#7C51F8] px-5 py-3 font-syne text-xs font-semibold text-white transition hover:bg-[#6d46e6] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? t("auth.submitting") : t("auth.submit")}
          </button>
        </form>
      </section>
    </main>
  );
}
