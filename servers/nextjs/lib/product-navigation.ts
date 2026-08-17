import { stripLocalePrefix } from "@/i18n/routing";

export type ProductNavigationKey =
  | "dashboard"
  | "presentations"
  | "create"
  | "templates"
  | "settings"
  | "account"
  | "admin";

export type ProductNavigationItem = {
  key: ProductNavigationKey;
  href: string;
};

export const USER_PRODUCT_NAVIGATION: readonly ProductNavigationItem[] = [
  { key: "dashboard", href: "/dashboard" },
  { key: "presentations", href: "/presentations" },
  { key: "create", href: "/create" },
  { key: "templates", href: "/templates" },
];

function normalizePathname(pathname: string): string {
  const stripped = stripLocalePrefix(pathname || "/").split(/[?#]/, 1)[0];
  if (stripped === "/") return stripped;
  return stripped.replace(/\/+$/, "") || "/";
}

export function isProductRouteActive(pathname: string, href: string): boolean {
  const current = normalizePathname(pathname);
  const target = normalizePathname(href);
  return current === target || current.startsWith(`${target}/`);
}

export function safeReturnPath(value: string | null | undefined): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return null;
  try {
    const parsed = new URL(value, "https://bayanly.local");
    if (parsed.origin !== "https://bayanly.local") return null;
    if (parsed.pathname.startsWith("/api/") || parsed.pathname.startsWith("/_next/")) {
      return null;
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return null;
  }
}

