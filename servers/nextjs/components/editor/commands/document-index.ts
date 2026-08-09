import type {
  Element as CanonicalElement,
  Geometry,
  PresentationDocument,
  Slide,
} from "@/generated/presentation-document";
import type { ElementPath } from "@/components/editor/types";

export function elementChildren(element: CanonicalElement): CanonicalElement[] {
  return element.type === "group" || element.type === "container"
    ? element.children
    : [];
}

export function indexDocumentElements(document: PresentationDocument): Map<string, ElementPath> {
  const index = new Map<string, ElementPath>();
  for (const slide of document.slides) {
    walkElements(slide.elements, slide.id, null, 0, index);
  }
  return index;
}

function walkElements(
  elements: CanonicalElement[],
  slideId: string,
  parentId: string | null,
  depth: number,
  index: Map<string, ElementPath>,
) {
  elements.forEach((element, elementIndex) => {
    index.set(element.id, {
      slideId,
      element,
      parentId,
      depth,
      index: elementIndex,
    });
    const children = elementChildren(element);
    if (children.length) walkElements(children, slideId, element.id, depth + 1, index);
  });
}

export function countDocumentElements(document: PresentationDocument): number {
  return indexDocumentElements(document).size;
}

export function updateElementTree(
  elements: CanonicalElement[],
  targetIds: ReadonlySet<string>,
  updater: (element: CanonicalElement) => CanonicalElement,
): CanonicalElement[] {
  let changed = false;
  const next = elements.map((element) => {
    let candidate = targetIds.has(element.id) ? updater(element) : element;
    if (candidate.type === "group" || candidate.type === "container") {
      const children = updateElementTree(candidate.children, targetIds, updater);
      if (children !== candidate.children) candidate = { ...candidate, children };
    }
    if (candidate !== element) changed = true;
    return candidate;
  });
  return changed ? next : elements;
}

export function removeElementsFromTree(
  elements: CanonicalElement[],
  targetIds: ReadonlySet<string>,
): CanonicalElement[] {
  let changed = false;
  const next: CanonicalElement[] = [];
  for (const element of elements) {
    if (targetIds.has(element.id)) {
      changed = true;
      continue;
    }
    let candidate = element;
    if (element.type === "group" || element.type === "container") {
      const children = removeElementsFromTree(element.children, targetIds);
      if (children !== element.children) candidate = { ...element, children };
    }
    if (candidate !== element) changed = true;
    next.push(candidate);
  }
  return changed ? next : elements;
}

export function replaceElementInTree(
  elements: CanonicalElement[],
  targetId: string,
  replacement: CanonicalElement[],
): CanonicalElement[] {
  let changed = false;
  const next: CanonicalElement[] = [];
  for (const element of elements) {
    if (element.id === targetId) {
      next.push(...replacement);
      changed = true;
      continue;
    }
    let candidate = element;
    if (element.type === "group" || element.type === "container") {
      const children = replaceElementInTree(element.children, targetId, replacement);
      if (children !== element.children) candidate = { ...element, children };
    }
    if (candidate !== element) changed = true;
    next.push(candidate);
  }
  return changed ? next : elements;
}

export function insertElementInTree(
  elements: CanonicalElement[],
  element: CanonicalElement,
  parentId?: string,
): CanonicalElement[] {
  if (!parentId) return [...elements, element];
  return updateElementTree(elements, new Set([parentId]), (parent) => {
    if (parent.type !== "group" && parent.type !== "container") return parent;
    return { ...parent, children: [...parent.children, element] };
  });
}

export function updateSlide(
  document: PresentationDocument,
  slideId: string,
  updater: (slide: Slide) => Slide,
): PresentationDocument {
  let changed = false;
  const slides = document.slides.map((slide) => {
    if (slide.id !== slideId) return slide;
    changed = true;
    return updater(slide);
  });
  return changed ? { ...document, slides } : document;
}

export function normalizeElementOrder(elements: CanonicalElement[]): CanonicalElement[] {
  const sorted = [...elements].sort((a, b) => a.zOrder - b.zOrder || a.id.localeCompare(b.id));
  return sorted.map((element, index) => {
    let candidate = element.zOrder === index ? element : { ...element, zOrder: index };
    if (candidate.type === "group" || candidate.type === "container") {
      const previousChildren = candidate.children;
      const children = normalizeElementOrder(previousChildren);
      if (children.some((child, childIndex) => child !== previousChildren[childIndex])) {
        candidate = { ...candidate, children };
      }
    }
    return candidate;
  });
}

export function normalizeSlideOrder(slides: Slide[]): Slide[] {
  return slides.map((slide, order) => slide.order === order ? slide : { ...slide, order });
}

export type BoundingBox = { left: number; top: number; right: number; bottom: number };

export function rotatedBoundingBox(
  geometry: Geometry,
  rotation = 0,
): BoundingBox {
  const radians = rotation * Math.PI / 180;
  const cosine = Math.abs(Math.cos(radians));
  const sine = Math.abs(Math.sin(radians));
  const width = geometry.width * cosine + geometry.height * sine;
  const height = geometry.width * sine + geometry.height * cosine;
  const centerX = geometry.x + geometry.width / 2;
  const centerY = geometry.y + geometry.height / 2;
  return {
    left: centerX - width / 2,
    top: centerY - height / 2,
    right: centerX + width / 2,
    bottom: centerY + height / 2,
  };
}

export function unionBoundingBoxes(boxes: BoundingBox[]): BoundingBox {
  return {
    left: Math.min(...boxes.map((box) => box.left)),
    top: Math.min(...boxes.map((box) => box.top)),
    right: Math.max(...boxes.map((box) => box.right)),
    bottom: Math.max(...boxes.map((box) => box.bottom)),
  };
}
