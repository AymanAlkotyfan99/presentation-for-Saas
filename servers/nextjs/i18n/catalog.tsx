"use client";

import React, { createContext, useContext, useEffect, useMemo } from "react";
import { DISPLAY_PRODUCT } from "@/lib/product-metadata";
import { DEFAULT_LOCALE, localeDirection, type SupportedLocale } from "./config";
import { recordLocalizationSignal } from "./observability";

export type MessageCatalog = Record<string, unknown>;
export type TranslationValues = Record<string, string | number | boolean>;

type I18nContextValue = {
  locale: SupportedLocale;
  direction: "ltr" | "rtl";
  messages: MessageCatalog;
  t: (key: string, values?: TranslationValues) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);
const SAFE_VARIABLE = /^[A-Za-z][A-Za-z0-9]*$/;

export function lookupMessage(messages: MessageCatalog, key: string): string | null {
  if (!/^[A-Za-z][A-Za-z0-9]*(\.[A-Za-z][A-Za-z0-9]*)+$/.test(key)) return null;
  let value: unknown = messages;
  for (const segment of key.split(".")) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    value = (value as Record<string, unknown>)[segment];
  }
  return typeof value === "string" ? value : null;
}

export function interpolateMessage(message: string, values: TranslationValues = {}): string {
  return message.replace(/\{([^{}]+)\}/g, (placeholder, name: string) => {
    if (!SAFE_VARIABLE.test(name)) return "";
    const value = values[name];
    return value === undefined || value === null ? placeholder : String(value);
  });
}

export function translateMessage(
  messages: MessageCatalog,
  key: string,
  values: TranslationValues = {},
): string {
  const message = lookupMessage(messages, key);
  if (!message) {
    recordLocalizationSignal("missing_key", { namespace: key.split(".")[0] });
    return key;
  }
  return interpolateMessage(message, {
    productName: DISPLAY_PRODUCT.name,
    productShortName: DISPLAY_PRODUCT.shortName,
    supportEmail: DISPLAY_PRODUCT.supportEmail,
    ...values,
  });
}

export function I18nProvider({
  locale,
  messages,
  children,
}: {
  locale: SupportedLocale;
  messages: MessageCatalog;
  children: React.ReactNode;
}) {
  useEffect(() => {
    recordLocalizationSignal("locale_selected", {
      locale,
      source: "explicit_route",
    });
  }, [locale]);
  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      direction: localeDirection(locale),
      messages,
      t: (key, values) => translateMessage(messages, key, values),
    }),
    [locale, messages],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const value = useContext(I18nContext);
  if (!value) {
    throw new Error("useI18n must be used inside I18nProvider");
  }
  return value;
}

export function useTranslations() {
  return useI18n().t;
}

export const FALLBACK_LOCALE = DEFAULT_LOCALE;
