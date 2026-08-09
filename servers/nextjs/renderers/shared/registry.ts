import type { Element as CanonicalElement } from "@/generated/presentation-document";

export type CanonicalElementType = CanonicalElement["type"];
export type ElementOfType<T extends CanonicalElementType> = Extract<CanonicalElement, { type: T }>;

export type TypedRenderer<TOutput, TContext> = <T extends CanonicalElementType>(
  element: ElementOfType<T>,
  context: TContext,
) => TOutput;

export type RendererRegistry<TRenderer> = {
  [K in CanonicalElementType]: TRenderer;
};

export const CANONICAL_ELEMENT_TYPES = [
  "text",
  "image",
  "shape",
  "line",
  "arrow",
  "vector",
  "icon",
  "table",
  "chart",
  "container",
  "group",
] as const satisfies readonly CanonicalElementType[];

export function defineRendererRegistry<TRenderer>(
  registry: RendererRegistry<TRenderer>,
): RendererRegistry<TRenderer> {
  return Object.freeze(registry);
}

export function isCanonicalElementType(value: unknown): value is CanonicalElementType {
  return typeof value === "string" && (CANONICAL_ELEMENT_TYPES as readonly string[]).includes(value);
}

export function rendererFor<TRenderer>(
  registry: RendererRegistry<TRenderer>,
  element: CanonicalElement,
): TRenderer {
  return registry[element.type];
}
