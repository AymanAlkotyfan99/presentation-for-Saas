import type { Element as CanonicalElement, Style } from "@/generated/presentation-document";

const SAFE_COLOR = /^(?:#[0-9a-f]{3,8}|rgba?\([\d\s.,%]+\)|hsla?\([\d\s.,%deg]+\)|[a-z]{1,24})$/i;

export function safeColor(value: string | undefined, fallback = "transparent") {
  return value && SAFE_COLOR.test(value.trim()) ? value.trim() : fallback;
}

export function rendererStyle(element: CanonicalElement) {
  const style = element.style;
  return {
    opacity: clamp(style?.opacity ?? 1, 0, 1),
    fill: safeColor(style?.fill),
    stroke: safeColor(style?.stroke?.color),
    strokeWidth: clamp(style?.stroke?.width ?? 0, 0, 256),
    strokeOpacity: clamp(style?.stroke?.opacity ?? 1, 0, 1),
    dash: style?.stroke?.dash?.filter((value) => Number.isFinite(value) && value >= 0).slice(0, 32),
    cornerRadius: clamp(style?.cornerRadius ?? 0, 0, 10_000),
    shadowColor: safeColor(style?.shadow?.color),
    shadowBlur: clamp(style?.shadow?.blur ?? 0, 0, 512),
    shadowOffsetX: clamp(style?.shadow?.offsetX ?? 0, -10_000, 10_000),
    shadowOffsetY: clamp(style?.shadow?.offsetY ?? 0, -10_000, 10_000),
    shadowOpacity: clamp(style?.shadow?.opacity ?? 1, 0, 1),
  };
}

export function browserStyle(style: Style | undefined): React.CSSProperties {
  return {
    opacity: clamp(style?.opacity ?? 1, 0, 1),
    background: safeColor(style?.fill),
    borderColor: safeColor(style?.stroke?.color),
    borderStyle: style?.stroke ? (style.stroke.dash?.length ? "dashed" : "solid") : undefined,
    borderWidth: style?.stroke ? clamp(style.stroke.width, 0, 256) : undefined,
    borderRadius: clamp(style?.cornerRadius ?? 0, 0, 10_000),
    boxShadow: style?.shadow
      ? `${clamp(style.shadow.offsetX ?? 0, -10_000, 10_000)}px ${clamp(style.shadow.offsetY ?? 0, -10_000, 10_000)}px ${clamp(style.shadow.blur ?? 0, 0, 512)}px ${safeColor(style.shadow.color)}`
      : undefined,
  };
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, Number.isFinite(value) ? value : minimum));
}
