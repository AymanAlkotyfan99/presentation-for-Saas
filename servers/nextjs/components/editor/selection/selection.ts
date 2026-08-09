import type { PresentationDocument, Slide } from "@/generated/presentation-document";
import { indexDocumentElements, rotatedBoundingBox } from "@/components/editor/commands";
import type { BoundingBox } from "@/components/editor/commands/document-index";

export type SelectionState = {
  selectedIds: string[];
  anchorId: string | null;
};

export const EMPTY_SELECTION: SelectionState = Object.freeze({
  selectedIds: [],
  anchorId: null,
});

export function selectOnly(document: PresentationDocument, id: string): SelectionState {
  return indexDocumentElements(document).has(id)
    ? { selectedIds: [id], anchorId: id }
    : EMPTY_SELECTION;
}

export function toggleSelection(
  document: PresentationDocument,
  selection: SelectionState,
  id: string,
): SelectionState {
  if (!indexDocumentElements(document).has(id)) return selection;
  const selected = new Set(selection.selectedIds);
  if (selected.has(id)) selected.delete(id);
  else selected.add(id);
  return { selectedIds: [...selected], anchorId: id };
}

export function selectAllVisible(slide: Slide): SelectionState {
  const selectedIds: string[] = [];
  const stack = [...slide.elements];
  while (stack.length) {
    const element = stack.shift();
    if (!element) continue;
    if (!element.hidden) selectedIds.push(element.id);
    if (element.type === "group" || element.type === "container") stack.unshift(...element.children);
  }
  return { selectedIds, anchorId: selectedIds.at(-1) ?? null };
}

export function marqueeSelection(slide: Slide, marquee: BoundingBox): SelectionState {
  const document = { slides: [slide] } as PresentationDocument;
  const selectedIds = [...indexDocumentElements(document).values()]
    .filter(({ element }) => !element.hidden)
    .filter(({ element }) => intersects(
      rotatedBoundingBox(element.geometry, element.transform?.rotation),
      marquee,
    ))
    .map(({ element }) => element.id);
  return { selectedIds, anchorId: selectedIds.at(-1) ?? null };
}

export function sanitizeSelection(
  document: PresentationDocument,
  selection: SelectionState,
): SelectionState {
  const index = indexDocumentElements(document);
  const selectedIds = selection.selectedIds.filter((id) => index.has(id));
  return {
    selectedIds,
    anchorId: selection.anchorId && index.has(selection.anchorId)
      ? selection.anchorId
      : selectedIds.at(-1) ?? null,
  };
}

function intersects(a: BoundingBox, b: BoundingBox) {
  return a.left <= b.right && a.right >= b.left && a.top <= b.bottom && a.bottom >= b.top;
}
