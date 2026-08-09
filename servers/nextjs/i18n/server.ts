import { headers } from "next/headers";
import ar from "@/messages/ar.json";
import en from "@/messages/en.json";
import {
  DEFAULT_LOCALE,
  LOCALE_REQUEST_HEADER,
  normalizeLocale,
  type SupportedLocale,
} from "./config";

export const MESSAGE_CATALOGS = { en, ar } as const;

export async function requestLocale(): Promise<SupportedLocale> {
  try {
    const requestHeaders = await headers();
    return normalizeLocale(requestHeaders.get(LOCALE_REQUEST_HEADER));
  } catch {
    return DEFAULT_LOCALE;
  }
}

export function messagesForLocale(locale: SupportedLocale) {
  return MESSAGE_CATALOGS[locale];
}

