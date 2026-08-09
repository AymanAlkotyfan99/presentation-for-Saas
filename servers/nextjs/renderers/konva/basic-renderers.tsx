import { Arrow, Ellipse, Line, Rect, RegularPolygon } from "react-konva";
import type { KonvaElementRendererProps } from "./types";
import { rendererStyle } from "@/renderers/shared/style";

export function ShapeRenderer({ element }: KonvaElementRendererProps<Extract<Parameters<typeof rendererStyle>[0], { type: "shape" }>>) {
  const { width, height } = element.geometry;
  const style = rendererStyle(element);
  const common = { ...style, width, height, perfectDrawEnabled: false };
  if (element.shapeKind === "ellipse") return <Ellipse {...style} x={width / 2} y={height / 2} radiusX={width / 2} radiusY={height / 2} perfectDrawEnabled={false} />;
  if (element.shapeKind === "triangle") return <RegularPolygon {...style} x={width / 2} y={height / 2} sides={3} radius={Math.min(width, height) / 2} perfectDrawEnabled={false} />;
  if (element.shapeKind === "diamond") return <Rect {...common} x={width / 2} y={height / 2} offsetX={width / 2} offsetY={height / 2} rotation={45} scaleX={Math.SQRT1_2} scaleY={Math.SQRT1_2} />;
  return <Rect {...common} cornerRadius={element.shapeKind === "rounded-rectangle" ? Math.max(style.cornerRadius, Math.min(width, height) * 0.08) : style.cornerRadius} />;
}

export function LineRenderer({ element }: KonvaElementRendererProps<Extract<Parameters<typeof rendererStyle>[0], { type: "line" }>>) {
  const style = rendererStyle(element);
  return <Line points={normalizePoints(element.points, element.geometry)} stroke={style.stroke === "transparent" ? "#111827" : style.stroke} strokeWidth={style.strokeWidth || 2} opacity={style.opacity * style.strokeOpacity} dash={style.dash} lineCap="round" perfectDrawEnabled={false} />;
}

export function ArrowRenderer({ element }: KonvaElementRendererProps<Extract<Parameters<typeof rendererStyle>[0], { type: "arrow" }>>) {
  const style = rendererStyle(element);
  const pointerAtBeginning = element.head === "start" || element.head === "both";
  const pointerAtEnding = element.head === "end" || element.head === "both";
  return <Arrow points={normalizePoints(element.points, element.geometry)} stroke={style.stroke === "transparent" ? "#111827" : style.stroke} fill={style.stroke === "transparent" ? "#111827" : style.stroke} strokeWidth={style.strokeWidth || 2} opacity={style.opacity * style.strokeOpacity} dash={style.dash} pointerAtBeginning={pointerAtBeginning} pointerAtEnding={pointerAtEnding} perfectDrawEnabled={false} />;
}

export function VectorRenderer({ element }: KonvaElementRendererProps<Extract<Parameters<typeof rendererStyle>[0], { type: "vector" }>>) {
  const style = rendererStyle(element);
  return <Line points={normalizePoints(element.points, element.geometry)} closed={element.closed} fill={style.fill} stroke={style.stroke} strokeWidth={style.strokeWidth} opacity={style.opacity} dash={style.dash} perfectDrawEnabled={false} />;
}

function normalizePoints(points: Array<{ x: number; y: number }>, geometry: { x: number; y: number }) {
  if (!points.length) return [];
  const looksAbsolute = points.some((point) => point.x >= geometry.x || point.y >= geometry.y);
  return points.flatMap((point) => [looksAbsolute ? point.x - geometry.x : point.x, looksAbsolute ? point.y - geometry.y : point.y]);
}
