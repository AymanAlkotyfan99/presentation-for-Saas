import { injectFontResources } from "@/lib/font-loading-security.mjs";
import { getFastAPIUrl } from "@/utils/api";

export const useFontLoader = (fonts: Record<string, string>) => {
  if (
    typeof document === "undefined" ||
    typeof window === "undefined" ||
    !document.head
  ) {
    return;
  }

  const documentOrigin = window.location.origin;
  const trustedAssetOrigins = [documentOrigin];
  try {
    trustedAssetOrigins.push(getFastAPIUrl());
  } catch {
    // Invalid runtime configuration must not widen the font URL policy.
  }

  injectFontResources(
    fonts,
    { documentOrigin, trustedAssetOrigins },
    document,
  );
};
