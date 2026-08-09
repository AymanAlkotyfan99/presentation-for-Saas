import type { Element as CanonicalElement, Slide } from "@/generated/presentation-document";
import type { EditorCommand } from "@/components/editor/commands";

export type LayerNode = {
  id: string;
  type: CanonicalElement["type"];
  locked: boolean;
  hidden: boolean;
  zOrder: number;
  depth: number;
  parentId: string | null;
  children: LayerNode[];
};

export type LayerOrderAction = "front" | "back" | "forward" | "backward";

export function buildLayerTree(slide: Slide): LayerNode[] {
  return layerNodes(slide.elements, 0, null).reverse();
}

function layerNodes(elements: CanonicalElement[], depth: number, parentId: string | null): LayerNode[] {
  return [...elements]
    .sort((a, b) => a.zOrder - b.zOrder || a.id.localeCompare(b.id))
    .map((element) => ({
      id: element.id,
      type: element.type,
      locked: element.locked ?? false,
      hidden: element.hidden ?? false,
      zOrder: element.zOrder,
      depth,
      parentId,
      children: element.type === "group" || element.type === "container"
        ? layerNodes(element.children, depth + 1, element.id).reverse()
        : [],
    }));
}

export function layerOrderCommand(
  slide: Slide,
  targetId: string,
  action: LayerOrderAction,
  commandId: string,
  parentId?: string,
): EditorCommand | null {
  const siblings = parentId ? findChildren(slide.elements, parentId) : slide.elements;
  if (!siblings) return null;
  const ordered = [...siblings].sort((a, b) => a.zOrder - b.zOrder || a.id.localeCompare(b.id));
  const index = ordered.findIndex((element) => element.id === targetId);
  if (index < 0) return null;
  const destination = action === "front"
    ? ordered.length - 1
    : action === "back"
      ? 0
      : action === "forward"
        ? Math.min(ordered.length - 1, index + 1)
        : Math.max(0, index - 1);
  if (destination === index) return null;
  const [element] = ordered.splice(index, 1);
  ordered.splice(destination, 0, element);
  return {
    commandId,
    type: "REORDER_ELEMENTS",
    targetIds: [targetId],
    payload: { slideId: slide.id, orderedIds: ordered.map(({ id }) => id), parentId },
  };
}

function findChildren(elements: CanonicalElement[], parentId: string): CanonicalElement[] | null {
  for (const element of elements) {
    if (element.id === parentId && (element.type === "group" || element.type === "container")) return element.children;
    if (element.type === "group" || element.type === "container") {
      const found = findChildren(element.children, parentId);
      if (found) return found;
    }
  }
  return null;
}
