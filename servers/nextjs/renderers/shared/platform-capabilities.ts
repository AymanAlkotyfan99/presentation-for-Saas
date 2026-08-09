import type { Asset } from "@/generated/presentation-document";
import type { CanonicalElementType } from "./registry";

export type AssetFontCapabilityManifest = Readonly<{
  assetMimeTypes: readonly Asset["mimeType"][];
  maximumRasterDimensions: Readonly<{ width: number; height: number }>;
  rendererElementTypes: readonly CanonicalElementType[];
  fontScriptCoverage: Readonly<Record<string, readonly ("arabic" | "latin" | "unknown")[]>>;
}>;

export type VerifiedFontCapability = Readonly<{
  id: string;
  scripts: readonly ("arabic" | "latin" | "unknown")[];
}>;

export const DEFAULT_ASSET_MIME_TYPES = [
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
  "font/ttf",
  "font/otf",
  "font/woff",
  "font/woff2",
] as const satisfies readonly Asset["mimeType"][];

export function assetFontCapabilities(
  verifiedFonts: readonly VerifiedFontCapability[],
  rendererElementTypes: readonly CanonicalElementType[],
): AssetFontCapabilityManifest {
  return Object.freeze({
    assetMimeTypes: DEFAULT_ASSET_MIME_TYPES,
    maximumRasterDimensions: Object.freeze({ width: 16_384, height: 16_384 }),
    rendererElementTypes,
    fontScriptCoverage: Object.freeze(Object.fromEntries(verifiedFonts.map((font) => [
      font.id,
      [...font.scripts],
    ]))),
  });
}

export function supportsAsset(manifest: AssetFontCapabilityManifest, asset: Asset) {
  const dimensions = asset.metadata;
  return manifest.assetMimeTypes.includes(asset.mimeType) &&
    (!dimensions?.width || dimensions.width <= manifest.maximumRasterDimensions.width) &&
    (!dimensions?.height || dimensions.height <= manifest.maximumRasterDimensions.height);
}
