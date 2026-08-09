import { memo, type ComponentType } from "react";
import type { Element as CanonicalElement } from "@/generated/presentation-document";
import { browserTransform } from "@/renderers/shared/geometry";
import { browserStyle } from "@/renderers/shared/style";
import type { BrowserElementRendererProps, BrowserRendererRegistry } from "./types";
import { BrowserTextRenderer } from "./text-renderer";
import { BrowserShapeRenderer, BrowserLineRenderer, BrowserArrowRenderer, BrowserVectorRenderer } from "./basic-renderers";
import { BrowserImageRenderer, BrowserIconRenderer } from "./asset-renderers";
import { BrowserTableRenderer, BrowserChartRenderer } from "./data-renderers";
import { BrowserContainerRenderer, BrowserGroupRenderer } from "./group-renderers";

export const browserRendererRegistry = Object.freeze({
  text: BrowserTextRenderer,
  image: BrowserImageRenderer,
  shape: BrowserShapeRenderer,
  line: BrowserLineRenderer,
  arrow: BrowserArrowRenderer,
  vector: BrowserVectorRenderer,
  icon: BrowserIconRenderer,
  table: BrowserTableRenderer,
  chart: BrowserChartRenderer,
  container: BrowserContainerRenderer,
  group: BrowserGroupRenderer,
} satisfies BrowserRendererRegistry);

export const CanonicalBrowserElement = memo(function CanonicalBrowserElement({ element, context }: BrowserElementRendererProps) {
  if (element.hidden) return null;
  const Renderer = browserRendererRegistry[element.type] as ComponentType<BrowserElementRendererProps> | undefined;
  if (!Renderer) return <BrowserUnsupportedElement element={element} />;
  return <div
    data-canonical-element-id={element.id}
    data-canonical-element-type={element.type}
    aria-disabled={element.locked || undefined}
    style={{
      position: "absolute",
      boxSizing: "border-box",
      left: element.geometry.x,
      top: element.geometry.y,
      width: element.geometry.width,
      height: element.geometry.height,
      transform: browserTransform(element),
      transformOrigin: "center",
      zIndex: element.zOrder,
      ...browserStyle(element.style),
    }}
  ><Renderer element={element} context={context} /></div>;
});

export function BrowserUnsupportedElement({ element }: { element: CanonicalElement }) {
  return <div role="img" aria-label={`Unsupported ${String(element.type)} element`} style={{ position: "absolute", left: element.geometry.x, top: element.geometry.y, width: element.geometry.width, height: element.geometry.height, display: "grid", placeItems: "center", border: "2px dashed #DC2626", background: "#FEF2F2", color: "#991B1B" }}>Unsupported: {String(element.type)}</div>;
}
