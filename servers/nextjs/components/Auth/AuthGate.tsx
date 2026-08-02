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
import { notify } from "@/components/ui/sonner";
import { sanitizeAnalyticsError } from "@/utils/analytics";
import { MixpanelEvent, trackEvent } from "@/utils/mixpanel";

type AuthStatus = {
  configured: boolean;
  authenticated: boolean;
  username: string | null;
  role?: "admin" | "user" | null;
};

const initialStatus: AuthStatus = {
  configured: true,
  authenticated: false,
  username: null,
  role: null,
};

export default function AuthGate() {
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
        notify.error("Unauthorized", "Sign in to view this page.", {
          id: "auth-unauthorized-redirect",
          duration: 5000,
        });
      }
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [isLoading, status.authenticated, status.configured]);

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
      trackEvent(MixpanelEvent.Auth_Status_Checked, {
        configured: Boolean(data.configured),
        authenticated: Boolean(data.authenticated),
        auth_disabled: false,
        role: data.role ?? null,
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
        "Could not load login",
        "We could not connect to the login service. Please refresh and try again."
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
        "Username too short",
        "Your username must be at least 3 characters."
      );
      return;
    }

    if (password.length < 6) {
      trackEvent(MixpanelEvent.Auth_Validation_Failed, {
        flow: "sign_in",
        reason: "password_too_short",
      });
      notify.warning(
        "Password too short",
        "Your password must be at least 6 characters."
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
        trackEvent(MixpanelEvent.Auth_SignIn_Failed, {
          status_code: response.status,
          error_message: sanitizeAnalyticsError(detail, "Sign-in failed"),
        });
        if (response.status === 401) {
          notify.error(
            "Sign-in failed",
            detail === UNAUTHORIZED_DETAIL
              ? "The username or password is incorrect. Please try again."
              : detail
          );
        } else {
          notify.error(
            "Sign-in failed",
            detail || "Something went wrong. Please try again."
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
        "Signed in",
        "Welcome back. Loading your workspace."
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
        "Login unavailable",
        "The login service is unavailable right now. Please try again in a moment."
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
    return <PresentonSplashLoader message="Preparing your workspace..." />;
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-white p-6 font-syne">
      <section className="relative z-10 w-full max-w-lg rounded-[20px] border border-[#EDEEEF] bg-[#F9F8F8] p-7 sm:p-10">
        <div className="mb-7">
          <div className="flex items-center gap-4">
            <div className="flex h-[60px] w-[60px] shrink-0 items-center justify-center rounded-[4px] bg-[#F4F3FF] p-3">
              <Image
                src="/logo-with-bg.png"
                alt=""
                width={161}
                height={166}
                className="h-10 w-auto object-contain"
              />
            </div>
            <div>
              <p className="font-syne text-[10px] font-semibold uppercase tracking-[0.14em] text-[#7A5AF8]">
                Secure instance
              </p>
              <h1 className="mt-1 font-unbounded text-xl font-normal leading-tight tracking-[-0.03em] text-black sm:text-[22px]">
                Sign in to continue
              </h1>
            </div>
          </div>
        </div>

        <p className="max-w-md text-sm leading-relaxed text-[#6B7280]">
          This deployment is protected. Enter your credentials to open the app.
        </p>

        <form onSubmit={handleSubmit} className="mt-7 space-y-5">
          <div className="space-y-2">
            <label htmlFor="username" className="block text-sm font-medium text-[#374151]">
              Username
            </label>
            <input
              id="username"
              autoComplete="username"
              value={username}
              onChange={(event) =>
                setUsername(event.target.value.replace(/\s/g, ""))
              }
              placeholder="Username"
              minLength={3}
              maxLength={128}
              pattern="\S+"
              title="Username cannot contain spaces"
              required
              spellCheck={false}
              className="h-12 w-full rounded-lg border border-[#E1E1E5] bg-white px-4 text-sm text-[#191919] outline-none transition placeholder:text-[#9CA3AF] focus:border-[#7A5AF8] focus:ring-2 focus:ring-[#7A5AF8]/15"
              disabled={isSubmitting}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="block text-sm font-medium text-[#374151]">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
              minLength={6}
              maxLength={128}
              required
              className="h-12 w-full rounded-lg border border-[#E1E1E5] bg-white px-4 text-sm text-[#191919] outline-none transition placeholder:text-[#9CA3AF] focus:border-[#7A5AF8] focus:ring-2 focus:ring-[#7A5AF8]/15"
              disabled={isSubmitting}
            />
          </div>

          {status.configured ? (
            <p className="rounded-lg border border-[#EDEEEF] bg-white px-4 py-3 text-xs leading-relaxed text-[#6B7280]">
              Use the username and password provided by your administrator.
            </p>
          ) : null}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-[58px] border border-[#EDEEEF] bg-[#7C51F8] px-5 py-3 font-syne text-xs font-semibold text-white transition hover:bg-[#6d46e6] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
