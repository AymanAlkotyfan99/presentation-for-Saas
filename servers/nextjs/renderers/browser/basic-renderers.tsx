import type { ArrowElement, LineElement, ShapeElement, VectorElement } from "@/generated/presentation-document";
import { rendererStyle, safeColor } from "@/renderers/shared/style";
import type { BrowserElementRendererProps } from "./types";

export function BrowserShapeRenderer({ element }: BrowserElementRendererProps<ShapeElement>) {
  const style = rendererStyle(element);
  const clipPath = element.shapeKind === "triangle"
    ? "polygon(50% 0, 100% 100%, 0 100%)"
    : element.shapeKind === "diamond"
      ? "polygon(50% 0, 100% 50%, 50% 100%, 0 50%)"
      : undefined;
  return <div style={{ width: "100%", height: "100%", background: style.fill, border: style.strokeWidth ? `${style.strokeWidth}px solid ${style.stroke}` : undefined, borderRadius: element.shapeKind === "ellipse" ? "50%" : style.cornerRadius, clipPath, opacity: style.opacity, boxShadow: style.shadowBlur ? `${style.shadowOffsetX}px ${style.shadowOffsetY}px ${style.shadowBlur}px ${style.shadowColor}` : undefined }} />;
}

export function BrowserLineRenderer({ element }: BrowserElementRendererProps<LineElement>) {
  return <SvgLine element={element} arrow="none" />;
}

export function BrowserArrowRenderer({ element }: BrowserElementRendererProps<ArrowElement>) {
  return <SvgLine element={element} arrow={element.head} />;
}

export function BrowserVectorRenderer({ element }: BrowserElementRendererProps<VectorElement>) {
  const style = rendererStyle(element);
  return <svg viewBox={`0 0 ${element.geometry.width} ${element.geometry.height}`} width="100%" height="100%" aria-label={element.accessibility?.label} role={element.accessibility?.decorative ? "presentation" : "img"}>
    <polyline points={points(element.points, element.geometry)} fill={element.closed ? style.fill : "none"} stroke={style.stroke} strokeWidth={style.strokeWidth || 1} strokeDasharray={style.dash?.join(" ")} opacity={style.opacity} />
  </svg>;
}

function SvgLine({ element, arrow }: { element: LineElement | ArrowElement; arrow: "none" | ArrowElement["head"] }) {
  const style = rendererStyle(element);
  const markerStart = arrow === "start" || arrow === "both" ? "url(#canonical-arrow)" : undefined;
  const markerEnd = arrow === "end" || arrow === "both" ? "url(#canonical-arrow)" : undefined;
  return <svg viewBox={`0 0 ${element.geometry.width} ${element.geometry.height}`} width="100%" height="100%" role="img" aria-label={element.accessibility?.label}>
    <defs><marker id="canonical-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill={safeColor(style.stroke, "#111827")} /></marker></defs>
    <polyline points={points(element.points, element.geometry)} fill="none" stroke={safeColor(style.stroke, "#111827")} strokeWidth={style.strokeWidth || 2} strokeDasharray={style.dash?.join(" ")} markerStart={markerStart} markerEnd={markerEnd} />
  </svg>;
}

function points(values: Array<{ x: number; y: number }>, geometry: { x: number; y: number }) {
  const absolute = values.some((point) => point.x >= geometry.x || point.y >= geometry.y);
  return values.map((point) => `${absolute ? point.x - geometry.x : point.x},${absolute ? point.y - geometry.y : point.y}`).join(" ");
}
