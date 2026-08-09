import type { IconElement, ImageElement } from "@/generated/presentation-document";
import type { BrowserElementRendererProps } from "./types";
import { isSafeScopedAssetUrl } from "@/renderers/shared/asset-resolver";

export function BrowserImageRenderer({ element, context }: BrowserElementRendererProps<ImageElement>) {
  const candidateUrl = context.assetUrls[element.assetId];
  const url = candidateUrl && isSafeScopedAssetUrl(candidateUrl) ? candidateUrl : undefined;
  if (!url) return <BrowserAssetPlaceholder label="Unavailable image" />;
  // Canonical assets use short-lived scoped URLs; Next/Image cannot safely persist or optimize them.
  // eslint-disable-next-line @next/next/no-img-element
  return <img
    src={url}
    alt={element.altText ?? element.accessibility?.label ?? ""}
    loading="lazy"
    decoding="async"
    draggable={false}
    referrerPolicy="no-referrer"
    style={{ width: "100%", height: "100%", objectFit: element.fit, objectPosition: element.crop ? `${(element.crop.focalX ?? 0.5) * 100}% ${(element.crop.focalY ?? 0.5) * 100}%` : "50% 50%" }}
  />;
}

export function BrowserIconRenderer({ element, context }: BrowserElementRendererProps<IconElement>) {
  if (element.assetId) {
    const image: ImageElement = { ...element, type: "image", assetId: element.assetId, fit: "contain" };
    return <BrowserImageRenderer element={image} context={context} />;
  }
  return <BrowserAssetPlaceholder label={element.iconName ?? "Icon"} />;
}

export function BrowserAssetPlaceholder({ label }: { label: string }) {
  return <div role="img" aria-label={label} style={{ boxSizing: "border-box", display: "grid", width: "100%", height: "100%", placeItems: "center", border: "1px dashed #9CA3AF", background: "#F3F4F6", color: "#4B5563", fontSize: 12 }}>{label}</div>;
}
