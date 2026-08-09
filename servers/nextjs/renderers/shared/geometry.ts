import type { Element as CanonicalElement, Geometry, Transform } from "@/generated/presentation-document";
import { rotatedBoundingBox, unionBoundingBoxes, type BoundingBox } from "@/components/editor/commands/document-index";

export const CANONICAL_SLIDE_WIDTH = 1280;

export type RenderGeometry = Geometry & Required<Pick<Transform, "rotation" | "flipHorizontal" | "flipVertical">>;

export function renderGeometry(element: CanonicalElement): RenderGeometry {
  return {
    ...element.geometry,
    rotation: element.transform?.rotation ?? 0,
    flipHorizontal: element.transform?.flipHorizontal ?? false,
    flipVertical: element.transform?.flipVertical ?? false,
  };
}

export function elementBoundingBox(element: CanonicalElement): BoundingBox {
  return rotatedBoundingBox(element.geometry, element.transform?.rotation);
}

export function elementsBoundingBox(elements: CanonicalElement[]): BoundingBox | null {
  if (!elements.length) return null;
  return unionBoundingBoxes(elements.map(elementBoundingBox));
}

export function toLocalPoints(
  points: Array<{ x: number; y: number }>,
  geometry: Geometry,
): number[] {
  return points.flatMap((point) => [point.x - geometry.x, point.y - geometry.y]);
}

export function browserTransform(element: CanonicalElement): string | undefined {
  const transforms: string[] = [];
  if (element.transform?.rotation) transforms.push(`rotate(${element.transform.rotation}deg)`);
  if (element.transform?.flipHorizontal) transforms.push("scaleX(-1)");
  if (element.transform?.flipVertical) transforms.push("scaleY(-1)");
  return transforms.length ? transforms.join(" ") : undefined;
}
