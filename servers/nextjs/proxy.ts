import { NextRequest, NextResponse } from "next/server";
import {
  ARABIC_SHELL_ENABLED,
  DEFAULT_LOCALE,
  LOCALE_COOKIE_MAX_AGE_SECONDS,
  LOCALE_COOKIE_NAME,
  LOCALE_REQUEST_HEADER,
  LOCALE_ROUTING_ENABLED,
} from "@/i18n/config";
import { recordLocalizationSignal } from "@/i18n/observability";
import {
  localeFromPathname,
  localizePathname,
  negotiateLocale,
  shouldBypassLocaleRouting,
  stripLocalePrefix,
} from "@/i18n/routing";

const LOCALE_REWRITE_HEADER = "x-bayanly-locale-rewrite";

function withLocaleCookie(response: NextResponse, locale: "en" | "ar") {
  response.cookies.set(LOCALE_COOKIE_NAME, locale, {
    httpOnly: false,
    maxAge: LOCALE_COOKIE_MAX_AGE_SECONDS,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
  });
  return response;
}

export function proxy(request: NextRequest) {
  try {
    const { pathname } = request.nextUrl;
    if (!LOCALE_ROUTING_ENABLED || shouldBypassLocaleRouting(pathname, request.method)) {
      return NextResponse.next();
    }
    // Next.js 16 may pass an internal rewrite through the proxy a second time.
    // Let the already-localized request reach the flat App Router tree instead
    // of redirecting the stripped path back to its locale prefix forever.
    if (request.headers.get(LOCALE_REWRITE_HEADER) === "1") {
      return NextResponse.next();
    }

    const explicitLocale = localeFromPathname(pathname);
    if (explicitLocale === "ar" && !ARABIC_SHELL_ENABLED) {
      const redirectUrl = request.nextUrl.clone();
      redirectUrl.pathname = localizePathname(pathname, DEFAULT_LOCALE);
      recordLocalizationSignal("locale_routing_error", {
        locale: DEFAULT_LOCALE,
        reason: "invalid_locale",
      });
      return withLocaleCookie(NextResponse.redirect(redirectUrl), DEFAULT_LOCALE);
    }
    if (!explicitLocale) {
      const locale = negotiateLocale({
        pathname,
        cookieLocale: request.cookies.get(LOCALE_COOKIE_NAME)?.value,
        acceptLanguage: request.headers.get("accept-language"),
      });
      const redirectUrl = request.nextUrl.clone();
      redirectUrl.pathname = localizePathname(pathname, locale);
      return withLocaleCookie(NextResponse.redirect(redirectUrl), locale);
    }

    const requestHeaders = new Headers(request.headers);
    requestHeaders.set(LOCALE_REQUEST_HEADER, explicitLocale);
    requestHeaders.set(LOCALE_REWRITE_HEADER, "1");
    const rewriteUrl = request.nextUrl.clone();
    rewriteUrl.pathname = stripLocalePrefix(pathname);
    return withLocaleCookie(
      NextResponse.rewrite(rewriteUrl, { request: { headers: requestHeaders } }),
      explicitLocale,
    );
  } catch {
    recordLocalizationSignal("locale_routing_error", {
      reason: "proxy_exception",
    });
    return NextResponse.next();
  }
}

export const config = { matcher: ["/:path*"] };
