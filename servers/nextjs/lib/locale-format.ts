import type { SupportedLocale } from "@/i18n/config";

const LOCALE_TAGS: Record<SupportedLocale, string> = {
  en: "en",
  // Pin the numbering system because some small-ICU Windows builds resolve
  // bare `ar` to Latin digits even though the interface is Arabic.
  ar: "ar-u-nu-arab",
};

export function formatDate(value: Date | string | number, locale: SupportedLocale) {
  return new Intl.DateTimeFormat(LOCALE_TAGS[locale], { dateStyle: "medium" }).format(new Date(value));
}

export function formatTime(value: Date | string | number, locale: SupportedLocale) {
  return new Intl.DateTimeFormat(LOCALE_TAGS[locale], { timeStyle: "short" }).format(new Date(value));
}

export function formatNumber(value: number, locale: SupportedLocale, options?: Intl.NumberFormatOptions) {
  return new Intl.NumberFormat(LOCALE_TAGS[locale], options).format(value);
}

export function formatPercent(value: number, locale: SupportedLocale) {
  return formatNumber(value, locale, { style: "percent", maximumFractionDigits: 1 });
}

export function formatCurrency(value: number, currency: string, locale: SupportedLocale) {
  return formatNumber(value, locale, { style: "currency", currency });
}

export function formatList(values: string[], locale: SupportedLocale) {
  return new Intl.ListFormat(LOCALE_TAGS[locale], { style: "long", type: "conjunction" }).format(values);
}

export function formatRelativeTime(value: number, unit: Intl.RelativeTimeFormatUnit, locale: SupportedLocale) {
  return new Intl.RelativeTimeFormat(LOCALE_TAGS[locale], { numeric: "auto" }).format(value, unit);
}

export function formatFileSize(bytes: number, locale: SupportedLocale) {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = units[0];
  for (let index = 1; index < units.length && value >= 1024; index += 1) {
    value /= 1024;
    unit = units[index];
  }
  return `${formatNumber(value, locale, { maximumFractionDigits: value < 10 ? 1 : 0 })} ${unit}`;
}
