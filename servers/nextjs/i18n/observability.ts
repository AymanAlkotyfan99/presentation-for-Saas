import { isSupportedLocale, type SupportedLocale } from "./config";

export type LocalizationSignal =
  | "locale_selected"
  | "missing_key"
  | "locale_routing_error"
  | "api_localization_fallback"
  | "rtl_layout_test_failure";

const SAFE_NAMESPACES = new Set([
  "common",
  "navigation",
  "auth",
  "onboarding",
  "dashboard",
  "generation",
  "outline",
  "presentation",
  "editor",
  "settings",
  "admin",
  "templates",
  "customTemplates",
  "errors",
  "validation",
  "privacy",
  "security",
  "files",
  "exports",
  "paymentsPlaceholder",
  "accessibility",
]);
const SAFE_SOURCES = new Set([
  "explicit_route",
  "locale_switcher",
  "account",
  "cookie",
  "browser",
  "default",
]);
const SAFE_REASONS = new Set([
  "invalid_locale",
  "missing_code",
  "unknown_code",
  "proxy_exception",
  "e2e_failure",
  "horizontal_overflow",
  "attribute_mismatch",
]);

export type LocalizationSignalMetadata = {
  locale?: SupportedLocale;
  namespace?: string;
  source?: string;
  reason?: string;
};

export function localizationSignalPayload(
  signal: LocalizationSignal,
  metadata: LocalizationSignalMetadata = {},
): Record<string, string> {
  const payload: Record<string, string> = { signal };
  if (metadata.locale && isSupportedLocale(metadata.locale)) {
    payload.locale = metadata.locale;
  }
  if (metadata.namespace && SAFE_NAMESPACES.has(metadata.namespace)) {
    payload.namespace = metadata.namespace;
  }
  if (metadata.source && SAFE_SOURCES.has(metadata.source)) {
    payload.source = metadata.source;
  }
  if (metadata.reason && SAFE_REASONS.has(metadata.reason)) {
    payload.reason = metadata.reason;
  }
  return payload;
}

export function recordLocalizationSignal(
  signal: LocalizationSignal,
  metadata: LocalizationSignalMetadata = {},
): Record<string, string> {
  const payload = localizationSignalPayload(signal, metadata);
  // Only finite, allow-listed values reach logs. Prompts, presentation text,
  // upload names, authentication data, and user-entered translations cannot.
  console.info("localization_metric", JSON.stringify(payload));
  return payload;
}
