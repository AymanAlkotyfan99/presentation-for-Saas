import type { CanonicalElementType } from "./registry";

export type RendererCapabilityStatus =
  | "SUPPORTED"
  | "PARTIAL"
  | "UNSUPPORTED"
  | "RASTERIZED"
  | "LEGACY_ONLY";

export type RendererFeature =
  | CanonicalElementType
  | "mixed-bidi"
  | "image-crop"
  | "gradients"
  | "shadows"
  | "notes"
  | "rtl"
  | "fonts"
  | "hidden-elements"
  | "locked-elements";

export type RendererCapabilityManifest = Readonly<{
  renderer: "konva" | "browser" | "legacy" | "exportCompatibility";
  features: Readonly<Record<RendererFeature, RendererCapabilityStatus>>;
}>;

const common = {
  text: "SUPPORTED",
  image: "SUPPORTED",
  shape: "SUPPORTED",
  line: "SUPPORTED",
  arrow: "SUPPORTED",
  vector: "SUPPORTED",
  icon: "PARTIAL",
  table: "SUPPORTED",
  chart: "PARTIAL",
  container: "SUPPORTED",
  group: "SUPPORTED",
  "mixed-bidi": "PARTIAL",
  "image-crop": "PARTIAL",
  gradients: "UNSUPPORTED",
  shadows: "SUPPORTED",
  notes: "UNSUPPORTED",
  rtl: "SUPPORTED",
  fonts: "PARTIAL",
  "hidden-elements": "SUPPORTED",
  "locked-elements": "SUPPORTED",
} as const satisfies Record<RendererFeature, RendererCapabilityStatus>;

export const KONVA_CAPABILITIES: RendererCapabilityManifest = Object.freeze({
  renderer: "konva",
  features: common,
});

export const BROWSER_CAPABILITIES: RendererCapabilityManifest = Object.freeze({
  renderer: "browser",
  features: Object.freeze({ ...common, "mixed-bidi": "SUPPORTED", "image-crop": "SUPPORTED" }),
});

export const LEGACY_CAPABILITIES: RendererCapabilityManifest = Object.freeze({
  renderer: "legacy",
  features: Object.freeze(Object.fromEntries(
    Object.keys(common).map((feature) => [feature, "LEGACY_ONLY"]),
  ) as Record<RendererFeature, RendererCapabilityStatus>),
});

export const EXPORT_COMPATIBILITY_CAPABILITIES: RendererCapabilityManifest = Object.freeze({
  renderer: "exportCompatibility",
  features: Object.freeze({
    ...common,
    text: "PARTIAL",
    image: "RASTERIZED",
    icon: "RASTERIZED",
    chart: "RASTERIZED",
    table: "PARTIAL",
    vector: "PARTIAL",
    "mixed-bidi": "PARTIAL",
    shadows: "PARTIAL",
  }),
});

export const RENDERER_CAPABILITIES = Object.freeze({
  konva: KONVA_CAPABILITIES,
  browser: BROWSER_CAPABILITIES,
  legacy: LEGACY_CAPABILITIES,
  exportCompatibility: EXPORT_COMPATIBILITY_CAPABILITIES,
});

export function capabilityFor(
  manifest: RendererCapabilityManifest,
  feature: RendererFeature,
): RendererCapabilityStatus {
  return manifest.features[feature];
}

export function needsVisibleFallback(status: RendererCapabilityStatus) {
  return status === "UNSUPPORTED" || status === "LEGACY_ONLY";
}
