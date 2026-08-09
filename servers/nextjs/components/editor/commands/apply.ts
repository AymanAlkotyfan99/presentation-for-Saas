import type {
  Element as CanonicalElement,
  Geometry,
  GroupElement,
  PresentationDocument,
} from "@/generated/presentation-document";
import { validatePresentationDocument } from "@/lib/presentation-document/validate";
import {
  indexDocumentElements,
  insertElementInTree,
  normalizeElementOrder,
  normalizeSlideOrder,
  removeElementsFromTree,
  replaceElementInTree,
  rotatedBoundingBox,
  unionBoundingBoxes,
  updateElementTree,
  updateSlide,
} from "./document-index";
import type { EditorCommand, EditorInverseCommand } from "./types";
import { validateCommand } from "./validate";

export class EditorCommandError extends Error {
  constructor(
    readonly code: string,
    readonly targetId?: string,
    detail?: string,
  ) {
    super(detail ? `${code}:${detail}` : code);
    this.name = "EditorCommandError";
  }
}

export function applyCommand(
  document: PresentationDocument,
  command: EditorCommand | EditorInverseCommand,
): PresentationDocument {
  if (command.type === "RESTORE_DOCUMENT") {
    return assertValidResult(command.payload.document);
  }
  if (command.type === "BATCH") {
    assertCommandIsValid(document, command, false);
    return applyCommandBatch(document, command.payload.commands);
  }
  return applyEditorCommand(document, command, false);
}

export function applyCommandToValidDocument(
  document: PresentationDocument,
  command: EditorCommand,
): PresentationDocument {
  if (command.type === "BATCH") {
    assertCommandIsValid(document, command, true);
    return applyCommandBatchToValidDocument(document, command.payload.commands);
  }
  return applyEditorCommand(document, command, true);
}

function applyEditorCommand(
  document: PresentationDocument,
  command: Exclude<EditorCommand, { type: "BATCH" }>,
  assumeValidDocument: boolean,
) {
  assertCommandIsValid(document, command, assumeValidDocument);
  return assertValidResult(applyValidatedCommand(document, command));
}

function assertCommandIsValid(
  document: PresentationDocument,
  command: EditorCommand,
  assumeValidDocument: boolean,
) {
  const validation = validateCommand(document, command, { assumeValidDocument });
  if (!validation.ok) {
    const issue = validation.issues[0];
    throw new EditorCommandError(issue?.code ?? "EDITOR_COMMAND_INVALID", issue?.targetId, issue?.detail);
  }
}

export function applyCommandBatch(
  document: PresentationDocument,
  commands: readonly EditorCommand[],
): PresentationDocument {
  let next = document;
  for (const command of commands) next = applyCommand(next, command);
  return next;
}

export function applyCommandBatchToValidDocument(
  document: PresentationDocument,
  commands: readonly EditorCommand[],
): PresentationDocument {
  let next = document;
  for (const command of commands) next = applyCommandToValidDocument(next, command);
  return next;
}

export function invertCommand(
  before: PresentationDocument,
  command: EditorCommand,
): EditorInverseCommand {
  applyCommand(before, command);
  return {
    commandId: `${command.commandId}:inverse`,
    type: "RESTORE_DOCUMENT",
    targetIds: [...command.targetIds],
    payload: { document: before },
  };
}

function applyValidatedCommand(
  document: PresentationDocument,
  command: Exclude<EditorCommand, { type: "BATCH" }>,
): PresentationDocument {
  switch (command.type) {
    case "ADD_ELEMENT":
      return updateElementsOnSlide(document, command.payload.slideId, (elements) =>
        insertElementInTree(elements, command.payload.element, command.payload.parentId));
    case "DELETE_ELEMENTS":
      return updateElementsOnSlide(document, command.payload.slideId, (elements) =>
        removeElementsFromTree(elements, new Set(command.targetIds)));
    case "DUPLICATE_ELEMENTS":
      return updateElementsOnSlide(document, command.payload.slideId, (elements) =>
        command.payload.copies.reduce(
          (current, copy) => insertElementInTree(current, copy.element, copy.parentId),
          elements,
        ));
    case "UPDATE_ELEMENT":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({
        ...element,
        ...command.payload.changes,
      } as CanonicalElement));
    case "MOVE_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({
        ...element,
        geometry: {
          ...element.geometry,
          x: element.geometry.x + command.payload.deltaX,
          y: element.geometry.y + command.payload.deltaY,
        },
      }));
    case "RESIZE_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({
        ...element,
        geometry: command.payload.geometryById[element.id] ?? element.geometry,
      }));
    case "ROTATE_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({
        ...element,
        transform: {
          ...(element.transform ?? {}),
          rotation: command.payload.rotationById[element.id] ?? element.transform?.rotation ?? 0,
        },
      }));
    case "REORDER_ELEMENTS":
      return reorderElements(document, command.payload.slideId, command.payload.orderedIds, command.payload.parentId);
    case "GROUP_ELEMENTS":
      return groupElements(document, command.payload.slideId, command.targetIds, command.payload.group, command.payload.parentId);
    case "UNGROUP_ELEMENTS":
      return ungroupElements(document, command.payload.slideId, command.targetIds);
    case "LOCK_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({ ...element, locked: true }));
    case "UNLOCK_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({ ...element, locked: false }));
    case "HIDE_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({ ...element, hidden: true }));
    case "SHOW_ELEMENTS":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({ ...element, hidden: false }));
    case "ALIGN_ELEMENTS":
      return alignElements(document, command.payload.slideId, command.targetIds, command.payload.alignment);
    case "DISTRIBUTE_ELEMENTS":
      return distributeElements(document, command.payload.slideId, command.targetIds, command.payload.axis);
    case "UPDATE_TEXT":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) =>
        element.type === "text" ? { ...element, paragraphs: command.payload.paragraphs } : element);
    case "UPDATE_STYLE":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => ({
        ...element,
        style: { ...(element.style ?? {}), ...command.payload.style },
      }));
    case "REPLACE_ASSET":
      return updateTargets(document, command.payload.slideId, command.targetIds, (element) => {
        if (element.type === "image" || element.type === "icon") return { ...element, assetId: command.payload.assetId };
        return element;
      });
    case "ADD_SLIDE":
      return { ...document, slides: normalizeSlideOrder([...document.slides, command.payload.slide]) };
    case "DELETE_SLIDE":
      return { ...document, slides: normalizeSlideOrder(document.slides.filter((slide) => !command.targetIds.includes(slide.id))) };
    case "DUPLICATE_SLIDE":
      return { ...document, slides: normalizeSlideOrder([...document.slides, ...command.payload.copies.map((copy) => copy.slide)]) };
    case "REORDER_SLIDES": {
      const byId = new Map(document.slides.map((slide) => [slide.id, slide]));
      return { ...document, slides: command.payload.orderedSlideIds.map((id, order) => ({ ...byId.get(id)!, order })) };
    }
    case "UPDATE_SLIDE":
      return { ...document, slides: document.slides.map((slide) =>
        command.targetIds.includes(slide.id) ? { ...slide, ...command.payload.changes } : slide) };
  }
}

function updateElementsOnSlide(
  document: PresentationDocument,
  slideId: string,
  updater: (elements: CanonicalElement[]) => CanonicalElement[],
) {
  return updateSlide(document, slideId, (slide) => ({
    ...slide,
    elements: normalizeElementOrder(updater(slide.elements)),
  }));
}

function updateTargets(
  document: PresentationDocument,
  slideId: string,
  targetIds: string[],
  updater: (element: CanonicalElement) => CanonicalElement,
) {
  const targets = new Set(targetIds);
  return updateElementsOnSlide(document, slideId, (elements) =>
    updateElementTree(elements, targets, updater));
}

function updateParentChildren(
  slide: PresentationDocument["slides"][number],
  parentId: string | undefined,
  updater: (children: CanonicalElement[]) => CanonicalElement[],
): PresentationDocument["slides"][number] {
  if (!parentId) return { ...slide, elements: normalizeElementOrder(updater(slide.elements)) };
  const elements = updateElementTree(slide.elements, new Set([parentId]), (parent) => {
    if (parent.type !== "group" && parent.type !== "container") return parent;
    return { ...parent, children: normalizeElementOrder(updater(parent.children)) };
  });
  return { ...slide, elements: normalizeElementOrder(elements) };
}

function reorderElements(
  document: PresentationDocument,
  slideId: string,
  orderedIds: string[],
  parentId?: string,
) {
  return updateSlide(document, slideId, (slide) => updateParentChildren(slide, parentId, (children) => {
    const byId = new Map(children.map((element) => [element.id, element]));
    const ordered = orderedIds.flatMap((id) => byId.get(id) ? [byId.get(id)!] : []);
    const remaining = children.filter((element) => !orderedIds.includes(element.id));
    return [...ordered, ...remaining];
  }));
}

function groupElements(
  document: PresentationDocument,
  slideId: string,
  targetIds: string[],
  group: GroupElement,
  parentId?: string,
) {
  const targets = new Set(targetIds);
  return updateSlide(document, slideId, (slide) => updateParentChildren(slide, parentId, (children) => {
    const selected = children.filter((element) => targets.has(element.id));
    const firstIndex = Math.min(...selected.map((element) => children.indexOf(element)));
    const relativeChildren = selected.map((element) => ({
      ...element,
      geometry: {
        ...element.geometry,
        x: element.geometry.x - group.geometry.x,
        y: element.geometry.y - group.geometry.y,
      },
    }));
    const candidate: GroupElement = { ...group, children: normalizeElementOrder(relativeChildren) };
    const next = children.filter((element) => !targets.has(element.id));
    next.splice(firstIndex, 0, candidate);
    return next;
  }));
}

function ungroupElements(
  document: PresentationDocument,
  slideId: string,
  targetIds: string[],
) {
  return updateSlide(document, slideId, (slide) => {
    let elements = slide.elements;
    for (const targetId of targetIds) {
      const path = indexSlide({ ...slide, elements }).get(targetId);
      if (!path || path.element.type !== "group") continue;
      const group = path.element;
      const rotation = group.transform?.rotation ?? 0;
      const children = group.children.map((child) => {
        const geometry = {
          ...child.geometry,
          x: child.geometry.x + group.geometry.x,
          y: child.geometry.y + group.geometry.y,
        };
        return rotation
          ? { ...child, geometry, transform: { ...(child.transform ?? {}), rotation: (child.transform?.rotation ?? 0) + rotation } }
          : { ...child, geometry };
      });
      elements = replaceElementInTree(elements, targetId, children);
    }
    return { ...slide, elements: normalizeElementOrder(elements) };
  });
}

function alignElements(
  document: PresentationDocument,
  slideId: string,
  targetIds: string[],
  alignment: "start" | "center-horizontal" | "end" | "top" | "center-vertical" | "bottom",
) {
  const index = indexDocumentElements(document);
  const targets = targetIds.map((id) => index.get(id)!.element);
  const boxes = targets.map((element) => rotatedBoundingBox(element.geometry, element.transform?.rotation));
  const union = unionBoundingBoxes(boxes);
  const geometryById = new Map<string, Geometry>();
  targets.forEach((element, i) => {
    const box = boxes[i];
    let dx = 0;
    let dy = 0;
    if (alignment === "start") dx = union.left - box.left;
    if (alignment === "center-horizontal") dx = (union.left + union.right - box.left - box.right) / 2;
    if (alignment === "end") dx = union.right - box.right;
    if (alignment === "top") dy = union.top - box.top;
    if (alignment === "center-vertical") dy = (union.top + union.bottom - box.top - box.bottom) / 2;
    if (alignment === "bottom") dy = union.bottom - box.bottom;
    geometryById.set(element.id, { ...element.geometry, x: rounded(element.geometry.x + dx), y: rounded(element.geometry.y + dy) });
  });
  return updateTargets(document, slideId, targetIds, (element) => ({
    ...element,
    geometry: geometryById.get(element.id) ?? element.geometry,
  }));
}

function distributeElements(
  document: PresentationDocument,
  slideId: string,
  targetIds: string[],
  axis: "horizontal" | "vertical",
) {
  const index = indexDocumentElements(document);
  const entries = targetIds.map((id) => {
    const element = index.get(id)!.element;
    return { element, box: rotatedBoundingBox(element.geometry, element.transform?.rotation) };
  }).sort((a, b) => axis === "horizontal" ? a.box.left - b.box.left : a.box.top - b.box.top);
  const first = entries[0].box;
  const last = entries[entries.length - 1].box;
  const totalSize = entries.reduce((sum, entry) => sum + (axis === "horizontal" ? entry.box.right - entry.box.left : entry.box.bottom - entry.box.top), 0);
  const span = axis === "horizontal" ? last.right - first.left : last.bottom - first.top;
  const gap = (span - totalSize) / (entries.length - 1);
  let cursor = axis === "horizontal" ? first.left : first.top;
  const geometryById = new Map<string, Geometry>();
  for (const entry of entries) {
    const size = axis === "horizontal" ? entry.box.right - entry.box.left : entry.box.bottom - entry.box.top;
    const delta = cursor - (axis === "horizontal" ? entry.box.left : entry.box.top);
    geometryById.set(entry.element.id, {
      ...entry.element.geometry,
      x: rounded(entry.element.geometry.x + (axis === "horizontal" ? delta : 0)),
      y: rounded(entry.element.geometry.y + (axis === "vertical" ? delta : 0)),
    });
    cursor += size + gap;
  }
  return updateTargets(document, slideId, targetIds, (element) => ({ ...element, geometry: geometryById.get(element.id)! }));
}

function indexSlide(slide: PresentationDocument["slides"][number]) {
  const document = { slides: [slide] } as PresentationDocument;
  return indexDocumentElements(document);
}

function assertValidResult(document: PresentationDocument) {
  const validation = validatePresentationDocument(document);
  if (!validation.ok) {
    const issue = validation.issues[0];
    throw new EditorCommandError("EDITOR_COMMAND_RESULT_INVALID", undefined, `${issue?.code ?? "CANONICAL_SCHEMA_INVALID"}:${issue?.path ?? "$"}`);
  }
  return validation.document;
}

function rounded(value: number) {
  return Math.round(value * 1_000_000) / 1_000_000;
}
