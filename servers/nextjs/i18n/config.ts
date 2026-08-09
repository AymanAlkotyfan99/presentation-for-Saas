export const SUPPORTED_LOCALES = ["en", "ar"] as const;

export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];
export type LocaleDirection = "ltr" | "rtl";

export const DEFAULT_LOCALE: SupportedLocale = "en";
export const LOCALE_COOKIE_NAME = "bayanly_locale";
export const LOCALE_REQUEST_HEADER = "x-bayanly-locale";
export const LOCALE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

function flag(name: string, defaultValue: boolean): boolean {
  const value = process.env[name] ?? process.env[`NEXT_PUBLIC_${name}`];
  if (value === undefined) return defaultValue;
  return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
}

export const LOCALE_ROUTING_ENABLED = flag("LOCALE_ROUTING_ENABLED", true);
export const ARABIC_SHELL_ENABLED = flag("ARABIC_SHELL_ENABLED", true);
export const ARABIC_FONTS_ENABLED = flag("ARABIC_FONTS_ENABLED", true);

export function isSupportedLocale(value: unknown): value is SupportedLocale {
  return typeof value === "string" && SUPPORTED_LOCALES.includes(value as SupportedLocale);
}

export function supportedLocaleOrNull(value: unknown): SupportedLocale | null {
  if (typeof value !== "string") return null;
  const primary = value.trim().toLowerCase().replace("_", "-").split("-")[0];
  if (!isSupportedLocale(primary)) return null;
  if (primary === "ar" && !ARABIC_SHELL_ENABLED) return null;
  return primary;
}

export function normalizeLocale(value: unknown): SupportedLocale {
  return supportedLocaleOrNull(value) ?? DEFAULT_LOCALE;
}

export function localeDirection(locale: SupportedLocale): LocaleDirection {
  return locale === "ar" ? "rtl" : "ltr";
}
