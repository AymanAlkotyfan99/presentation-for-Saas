import {
  DEFAULT_LOCALE,
  supportedLocaleOrNull,
  SUPPORTED_LOCALES,
  type SupportedLocale,
} from "./config";

const BYPASS_PREFIXES = [
  "/api",
  "/_next",
  "/app_data",
  "/health",
  "/pdf-maker",
];
const STATIC_FILE_PATTERN = /\/[A-Za-z0-9_.-]+\.[A-Za-z0-9]+$/;

export function localeFromPathname(pathname: string): SupportedLocale | null {
  const first = pathname.split("/").filter(Boolean)[0];
  return SUPPORTED_LOCALES.find((locale) => locale === first) ?? null;
}

export function stripLocalePrefix(pathname: string): string {
  const locale = localeFromPathname(pathname);
  if (!locale) return pathname || "/";
  const stripped = pathname.slice(locale.length + 1);
  return stripped ? (stripped.startsWith("/") ? stripped : `/${stripped}`) : "/";
}

export function localizePathname(pathname: string, locale: SupportedLocale): string {
  const base = stripLocalePrefix(pathname);
  return base === "/" ? `/${locale}` : `/${locale}${base}`;
}

export function shouldBypassLocaleRouting(pathname: string, method = "GET"): boolean {
  if (!['GET', 'HEAD'].includes(method.toUpperCase())) return true;
  if (BYPASS_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))) {
    return true;
  }
  return STATIC_FILE_PATTERN.test(pathname);
}

export function negotiateAcceptLanguage(value: string | null | undefined): SupportedLocale {
  if (!value) return DEFAULT_LOCALE;
  const candidates = value
    .split(",")
    .map((part) => {
      const [tag, ...parameters] = part.trim().split(";");
      const qValue = parameters.find((parameter) => parameter.trim().startsWith("q="));
      const quality = qValue ? Number(qValue.trim().slice(2)) : 1;
      return {
        locale: supportedLocaleOrNull(tag),
        quality: Number.isFinite(quality) && quality > 0 ? quality : 0,
      };
    })
    .filter(
      (candidate): candidate is { locale: SupportedLocale; quality: number } =>
        candidate.locale !== null && candidate.quality > 0,
    )
    .sort((left, right) => right.quality - left.quality);
  return candidates[0]?.locale ?? DEFAULT_LOCALE;
}

export function negotiateLocale(options: {
  pathname: string;
  savedLocale?: string | null;
  cookieLocale?: string | null;
  acceptLanguage?: string | null;
}): SupportedLocale {
  return (
    localeFromPathname(options.pathname) ??
    supportedLocaleOrNull(options.savedLocale) ??
    supportedLocaleOrNull(options.cookieLocale) ??
    negotiateAcceptLanguage(options.acceptLanguage)
  );
}
