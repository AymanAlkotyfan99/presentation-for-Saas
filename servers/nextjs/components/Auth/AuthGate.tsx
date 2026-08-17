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
import { useI18n } from "@/i18n/catalog";
import { apiErrorLocalization } from "@/utils/apiErrorMessages";
import { LOCALE_COOKIE_NAME, type SupportedLocale } from "@/i18n/config";
import { recordLocalizationSignal } from "@/i18n/observability";
import { localizePathname } from "@/i18n/routing";
import { safeReturnPath } from "@/lib/product-navigation";
import { CheckCircle2, Presentation, Sparkles } from "lucide-react";
import { fetchWithTimeout } from "@/utils/fetchWithTimeout";

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
  const { locale, t } = useI18n();
  const [status, setStatus] = useState<AuthStatus>(initialStatus);
  const [isLoading, setIsLoading] = useState(true);
  const [isRedirecting, setIsRedirecting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasMetSplashDuration, setHasMetSplashDuration] = useState(false);
  const [redirectReason, setRedirectReason] = useState<string | null>(null);
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
    // Authentication state is checked once on gate mount; the product shell owns later session checks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

    const params = new URLSearchParams(window.location.search);
    const requested = safeReturnPath(params.get("next"));
    let destination = localizePathname("/dashboard", locale);
    if (requested) {
      const parsed = new URL(requested, window.location.origin);
      destination = `${localizePathname(parsed.pathname, locale)}${parsed.search}${parsed.hash}`;
    }
    setIsRedirecting(true);
    window.location.replace(destination);
  }, [isLoading, isRedirecting, locale, status.authenticated]);

  useEffect(() => {
    if (typeof window === "undefined" || isLoading) {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const reason = params.get("reason");
    setRedirectReason(reason);
    if (reason === "unauthorized" || reason === "session-expired") {
      if (!status.authenticated) {
        trackEvent(MixpanelEvent.Auth_Unauthorized_Redirect, {
          configured: true,
        });
        notify.error(
          reason === "session-expired" ? t("auth.sessionExpiredTitle") : t("auth.required"),
          reason === "session-expired" ? t("auth.sessionExpiredDescription") : t("auth.required"),
          {
          id: "auth-unauthorized-redirect",
          duration: 5000,
          },
        );
      }
    }
  }, [isLoading, status.authenticated, status.configured, t]);

  const refreshStatus = async () => {
    setIsLoading(true);

    try {
      const response = await fetchWithTimeout(getApiUrl("/api/v1/auth/status"), {
        method: "GET",
        cache: "no-store",
        credentials: "include",
      }, 10_000);

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
      const response = await fetchWithTimeout(
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
        },
        15_000,
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
    <div className="relative grid min-h-screen overflow-hidden bg-[#F8F8FB] font-syne lg:grid-cols-[minmax(0,1.05fr)_minmax(480px,0.95fr)]">
      <section className="relative hidden overflow-hidden bg-[#16132A] px-12 py-14 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -end-24 -top-24 h-80 w-80 rounded-full bg-[#7A5AF8]/25 blur-3xl" aria-hidden="true" />
        <div className="absolute -bottom-28 -start-20 h-96 w-96 rounded-full bg-[#34C7B7]/15 blur-3xl" aria-hidden="true" />
        <div className="relative flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10">
            <Image src={BRAND_ASSETS.compactIcon} alt="" width={30} height={30} className="h-8 w-8 object-contain" />
          </span>
          <span className="text-xl font-bold tracking-[-0.03em]">Bayanly</span>
        </div>
        <div className="relative max-w-xl pb-10">
          <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-semibold text-[#DCD5FF]">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            {t("auth.secureInstance")}
          </p>
          <h2 className="text-balance text-4xl font-semibold leading-[1.13] tracking-[-0.04em] xl:text-5xl">
            {t("auth.loginSupporting")}
          </h2>
          <div className="mt-8 grid gap-3 text-sm text-white/75 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
            {["productOnboarding.stepOne", "productOnboarding.stepTwo", "productOnboarding.stepThree"].map((key) => (
              <span key={key} className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-[#A99AF8]" aria-hidden="true" /> {t(key)}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="relative flex items-center justify-center px-5 py-10 sm:px-10 lg:bg-white">
        <div className="w-full max-w-[440px]">
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <Image src={BRAND_ASSETS.compactIcon} alt="" width={36} height={36} className="h-9 w-9 object-contain" />
            <span className="text-xl font-bold tracking-[-0.03em] text-[#171A24]">Bayanly</span>
          </div>
          <div className="mb-8">
            <span className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#EEEAFE] text-[#6344E8]">
              <Presentation className="h-5 w-5" aria-hidden="true" />
            </span>
            <p className="text-sm font-semibold text-[#6F4EF6]">{t("auth.welcomeBack")}</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-[#171A24] sm:text-4xl">{t("auth.title")}</h1>
            <p className="mt-3 text-sm leading-6 text-[#667085]">{t("auth.protectedDescription")}</p>
          </div>

          {redirectReason === "session-expired" && (
            <div className="mb-6 rounded-xl border border-[#FECACA] bg-[#FFF7F6] px-4 py-3" role="alert">
              <p className="text-sm font-semibold text-[#9F2D25]">{t("auth.sessionExpiredTitle")}</p>
              <p className="mt-1 text-xs leading-5 text-[#B5473E]">{t("auth.sessionExpiredDescription")}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
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
              className="h-12 w-full rounded-xl border border-[#D9DCE3] bg-white px-4 text-sm text-[#191919] outline-none transition placeholder:text-[#9CA3AF] hover:border-[#BBB5E8] focus:border-[#7A5AF8] focus:ring-2 focus:ring-[#7A5AF8]/15"
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
              className="h-12 w-full rounded-xl border border-[#D9DCE3] bg-white px-4 text-sm text-[#191919] outline-none transition placeholder:text-[#9CA3AF] hover:border-[#BBB5E8] focus:border-[#7A5AF8] focus:ring-2 focus:ring-[#7A5AF8]/15"
              disabled={isSubmitting}
            />
          </div>

          {status.configured ? (
            <p className="rounded-xl bg-[#F5F4FA] px-4 py-3 text-xs leading-relaxed text-[#667085]">
              {t("auth.administratorCredentials")}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={isSubmitting}
            className="flex min-h-12 w-full items-center justify-center rounded-xl bg-[#6F4EF6] px-5 py-3 text-sm font-semibold text-white shadow-[0_8px_22px_rgba(111,78,246,0.2)] transition hover:-translate-y-0.5 hover:bg-[#6242E8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 motion-reduce:transform-none"
          >
            {isSubmitting ? t("auth.submitting") : t("auth.submit")}
          </button>
          </form>
        </div>
      </section>
    </div>
  );
}
