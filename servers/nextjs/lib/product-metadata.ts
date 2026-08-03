import { PRODUCT_IDENTITY } from "@/lib/product-identity";

const NEW_BRAND_SHELL_ENABLED =
  (process.env.NEXT_PUBLIC_NEW_BRAND_SHELL_ENABLED ??
    process.env.NEW_BRAND_SHELL_ENABLED) !== "false";
export const DISPLAY_PRODUCT = NEW_BRAND_SHELL_ENABLED
  ? PRODUCT_IDENTITY.product
  : {
      name: PRODUCT_IDENTITY.upstream.name,
      shortName: PRODUCT_IDENTITY.upstream.name,
      description: "Open-source AI presentation generator",
      supportEmail: PRODUCT_IDENTITY.product.supportEmail,
    };
export const PRODUCT_TITLE = `${DISPLAY_PRODUCT.name} — AI presentations in Arabic and English`;
export const PRODUCT_DESCRIPTION = DISPLAY_PRODUCT.description;
export const BRAND_ASSETS = {
  primaryLogo: NEW_BRAND_SHELL_ENABLED ? `${PRODUCT_IDENTITY.assets.webBasePath}/${PRODUCT_IDENTITY.assets.primaryLogo}` : "/logo-with-bg.png",
  lightLogo: NEW_BRAND_SHELL_ENABLED ? `${PRODUCT_IDENTITY.assets.webBasePath}/${PRODUCT_IDENTITY.assets.lightLogo}` : "/logo-white.png",
  darkLogo: NEW_BRAND_SHELL_ENABLED ? `${PRODUCT_IDENTITY.assets.webBasePath}/${PRODUCT_IDENTITY.assets.darkLogo}` : "/logo-with-bg.png",
  compactIcon: NEW_BRAND_SHELL_ENABLED ? `${PRODUCT_IDENTITY.assets.webBasePath}/${PRODUCT_IDENTITY.assets.compactIcon}` : "/logo-with-bg.png",
  favicon: NEW_BRAND_SHELL_ENABLED ? `${PRODUCT_IDENTITY.assets.webBasePath}/${PRODUCT_IDENTITY.assets.favicon}` : "/favicon.ico",
  splash: NEW_BRAND_SHELL_ENABLED ? `${PRODUCT_IDENTITY.assets.webBasePath}/${PRODUCT_IDENTITY.assets.splash}` : "/Presenton_Splash.png",
} as const;

export function publicSiteUrl(): URL {
  const configured = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  // The approved example.ai value is a placeholder and must never silently
  // become production behavior. Deployments must configure their real origin.
  return new URL(configured || "http://localhost:3000");
}

export function newBrandShellEnabled(): boolean {
  return NEW_BRAND_SHELL_ENABLED;
}

export function newExportMetadataEnabled(): boolean {
  return process.env.NEW_EXPORT_METADATA_ENABLED === "true";
}
