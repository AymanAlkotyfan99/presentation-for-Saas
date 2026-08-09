import type {
  Element as CanonicalElement,
  PresentationDocument,
} from "@/generated/presentation-document";
import { CANONICAL_LIMITS, validatePresentationDocument } from "@/lib/presentation-document/validate";
import { countDocumentElements, indexDocumentElements } from "./document-index";
import type {
  EditorCommand,
  EditorCommandValidationIssue,
  EditorCommandValidationResult,
} from "./types";

const COMMAND_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const LOCK_BYPASS_TYPES = new Set<EditorCommand["type"]>([
  "LOCK_ELEMENTS",
  "UNLOCK_ELEMENTS",
  "HIDE_ELEMENTS",
  "SHOW_ELEMENTS",
]);

export function validateCommand(
  document: PresentationDocument,
  command: EditorCommand,
  options: { assumeValidDocument?: boolean } = {},
): EditorCommandValidationResult {
  const issues: EditorCommandValidationIssue[] = [];
  const baseValidation = options.assumeValidDocument ? null : validatePresentationDocument(document);
  if (baseValidation && !baseValidation.ok) {
    return {
      ok: false,
      issues: [{ code: "EDITOR_DOCUMENT_INVALID", detail: baseValidation.issues[0]?.code }],
    };
  }
  if (!COMMAND_ID.test(command.commandId)) issues.push({ code: "EDITOR_COMMAND_ID_INVALID" });
  if (new Set(command.targetIds).size !== command.targetIds.length) {
    issues.push({ code: "EDITOR_COMMAND_DUPLICATE_TARGET" });
  }
  if (!isSerializable(command)) issues.push({ code: "EDITOR_COMMAND_NOT_SERIALIZABLE" });
  if (command.type === "BATCH") {
    if (command.payload.commands.length === 0) issues.push({ code: "EDITOR_COMMAND_BATCH_EMPTY" });
    const nestedIds = new Set<string>();
    for (const nested of command.payload.commands) {
      if (nestedIds.has(nested.commandId)) issues.push({ code: "EDITOR_COMMAND_ID_DUPLICATE", detail: nested.commandId });
      nestedIds.add(nested.commandId);
    }
    return issues.length ? { ok: false, issues } : { ok: true };
  }

  const slides = new Map(document.slides.map((slide) => [slide.id, slide]));
  const elementIndex = indexDocumentElements(document);
  const targetPaths = command.targetIds.flatMap((targetId) => {
    const path = elementIndex.get(targetId);
    return path ? [path] : [];
  });
  const slideId = "slideId" in command.payload ? command.payload.slideId : null;
  if (slideId && !slides.has(slideId)) issues.push({ code: "EDITOR_SLIDE_NOT_FOUND", targetId: slideId });

  const newElementIds = command.type === "ADD_ELEMENT"
    ? [command.payload.element.id]
    : command.type === "DUPLICATE_ELEMENTS"
      ? command.payload.copies.flatMap((copy) => collectElementIds(copy.element))
      : [];
  if (newElementIds.length) {
    if (new Set(newElementIds).size !== newElementIds.length) issues.push({ code: "EDITOR_DUPLICATE_ID" });
    for (const id of newElementIds) {
      if (elementIndex.has(id)) issues.push({ code: "EDITOR_DUPLICATE_ID", targetId: id });
    }
    if (countDocumentElements(document) + newElementIds.length > CANONICAL_LIMITS.maxTotalElements) {
      issues.push({ code: "EDITOR_ELEMENT_LIMIT_EXCEEDED" });
    }
  }

  const elementTargetCommand = ![
    "ADD_ELEMENT",
    "ADD_SLIDE",
    "DELETE_SLIDE",
    "DUPLICATE_SLIDE",
    "REORDER_SLIDES",
    "UPDATE_SLIDE",
  ].includes(command.type);
  if (elementTargetCommand) {
    for (const targetId of command.targetIds) {
      const path = elementIndex.get(targetId);
      if (!path) issues.push({ code: "EDITOR_ELEMENT_NOT_FOUND", targetId });
      else if (slideId && path.slideId !== slideId) issues.push({ code: "EDITOR_TARGET_SLIDE_MISMATCH", targetId });
    }
  }
  if (!LOCK_BYPASS_TYPES.has(command.type)) {
    for (const path of targetPaths) {
      const lockedId = firstLockedId(path.element);
      if (lockedId) issues.push({ code: "EDITOR_ELEMENT_LOCKED", targetId: lockedId });
    }
  }

  if (command.type === "ADD_ELEMENT" && command.targetIds[0] !== command.payload.element.id) {
    issues.push({ code: "EDITOR_COMMAND_TARGET_MISMATCH" });
  }
  if (command.type === "ADD_ELEMENT" && command.payload.parentId) {
    validateParent(command.payload.parentId, command.payload.slideId, elementIndex, issues);
  }
  if (command.type === "DUPLICATE_ELEMENTS") {
    if (command.payload.copies.length !== command.targetIds.length || command.payload.copies.some((copy) => !command.targetIds.includes(copy.sourceId))) {
      issues.push({ code: "EDITOR_COMMAND_TARGET_MISMATCH" });
    }
    for (const copy of command.payload.copies) {
      const source = elementIndex.get(copy.sourceId);
      if (!source) issues.push({ code: "EDITOR_ELEMENT_NOT_FOUND", targetId: copy.sourceId });
      if (copy.parentId) validateParent(copy.parentId, command.payload.slideId, elementIndex, issues);
    }
  }
  if (["GROUP_ELEMENTS", "ALIGN_ELEMENTS", "DISTRIBUTE_ELEMENTS"].includes(command.type)) {
    const parents = new Set(targetPaths.map((path) => path.parentId));
    if (parents.size > 1) issues.push({ code: "EDITOR_TARGET_PARENT_MISMATCH" });
  }
  if (command.type === "GROUP_ELEMENTS") {
    if (command.targetIds.length < 2) issues.push({ code: "EDITOR_GROUP_REQUIRES_MULTIPLE" });
    if (elementIndex.has(command.payload.group.id)) issues.push({ code: "EDITOR_DUPLICATE_ID", targetId: command.payload.group.id });
    if (command.payload.group.children.length) issues.push({ code: "EDITOR_GROUP_PAYLOAD_CHILDREN_FORBIDDEN" });
    if (command.payload.parentId) validateParent(command.payload.parentId, command.payload.slideId, elementIndex, issues);
    const targetParent = targetPaths[0]?.parentId ?? undefined;
    if (targetParent !== command.payload.parentId) issues.push({ code: "EDITOR_TARGET_PARENT_MISMATCH" });
  }
  if (command.type === "UNGROUP_ELEMENTS") {
    targetPaths.filter((path) => path.element.type !== "group").forEach((path) => {
      issues.push({ code: "EDITOR_UNGROUP_TARGET_INVALID", targetId: path.element.id });
    });
  }
  if (command.type === "ALIGN_ELEMENTS" && command.targetIds.length < 2) {
    issues.push({ code: "EDITOR_ALIGNMENT_REQUIRES_MULTIPLE" });
  }
  if (command.type === "DISTRIBUTE_ELEMENTS" && command.targetIds.length < 3) {
    issues.push({ code: "EDITOR_DISTRIBUTION_REQUIRES_THREE" });
  }
  if (command.type === "UPDATE_TEXT") {
    targetPaths.filter((path) => path.element.type !== "text").forEach((path) => {
      issues.push({ code: "EDITOR_TEXT_TARGET_INVALID", targetId: path.element.id });
    });
  }
  if (command.type === "REPLACE_ASSET") {
    if (!document.assets.some((asset) => asset.assetId === command.payload.assetId)) {
      issues.push({ code: "EDITOR_ASSET_NOT_FOUND", targetId: command.payload.assetId });
    }
    targetPaths.filter((path) => path.element.type !== "image" && path.element.type !== "icon").forEach((path) => {
      issues.push({ code: "EDITOR_ASSET_TARGET_INVALID", targetId: path.element.id });
    });
  }
  if (command.type === "DELETE_SLIDE" || command.type === "UPDATE_SLIDE") {
    command.targetIds.filter((id) => !slides.has(id)).forEach((id) => {
      issues.push({ code: "EDITOR_SLIDE_NOT_FOUND", targetId: id });
    });
  }
  if (command.type === "ADD_SLIDE" && slides.has(command.payload.slide.id)) {
    issues.push({ code: "EDITOR_DUPLICATE_ID", targetId: command.payload.slide.id });
  }
  if (command.type === "DUPLICATE_SLIDE") {
    for (const copy of command.payload.copies) {
      if (!slides.has(copy.sourceId)) issues.push({ code: "EDITOR_SLIDE_NOT_FOUND", targetId: copy.sourceId });
      if (slides.has(copy.slide.id)) issues.push({ code: "EDITOR_DUPLICATE_ID", targetId: copy.slide.id });
    }
  }
  if (command.type === "REORDER_SLIDES") {
    const currentIds = new Set(slides.keys());
    const ordered = command.payload.orderedSlideIds;
    if (ordered.length !== currentIds.size || new Set(ordered).size !== ordered.length || ordered.some((id) => !currentIds.has(id))) {
      issues.push({ code: "EDITOR_SLIDE_ORDER_INVALID" });
    }
  }
  if (command.type === "REORDER_ELEMENTS") {
    if (command.payload.parentId) validateParent(command.payload.parentId, command.payload.slideId, elementIndex, issues);
    const slide = slides.get(command.payload.slideId);
    const siblings = slide ? siblingElements(slide.elements, command.payload.parentId) : null;
    const ordered = command.payload.orderedIds;
    if (!siblings || ordered.length !== siblings.length || new Set(ordered).size !== ordered.length || ordered.some((id) => !siblings.some((element) => element.id === id))) {
      issues.push({ code: "EDITOR_ELEMENT_ORDER_INVALID" });
    } else {
      const previous = [...siblings].sort((a, b) => a.zOrder - b.zOrder || a.id.localeCompare(b.id));
      previous.forEach((element, index) => {
        if (element.locked && ordered.indexOf(element.id) !== index) issues.push({ code: "EDITOR_ELEMENT_LOCKED", targetId: element.id });
      });
    }
  }
  if (!allFinite(command.payload)) issues.push({ code: "EDITOR_NONFINITE_NUMBER" });
  return issues.length ? { ok: false, issues } : { ok: true };
}

function firstLockedId(element: CanonicalElement): string | null {
  if (element.locked) return element.id;
  if (element.type === "group" || element.type === "container") {
    for (const child of element.children) {
      const locked = firstLockedId(child);
      if (locked) return locked;
    }
  }
  return null;
}

function siblingElements(elements: CanonicalElement[], parentId?: string): CanonicalElement[] | null {
  if (!parentId) return elements;
  for (const element of elements) {
    if (element.id === parentId && (element.type === "group" || element.type === "container")) return element.children;
    if (element.type === "group" || element.type === "container") {
      const nested = siblingElements(element.children, parentId);
      if (nested) return nested;
    }
  }
  return null;
}

function validateParent(
  parentId: string,
  slideId: string,
  index: ReturnType<typeof indexDocumentElements>,
  issues: EditorCommandValidationIssue[],
) {
  const parent = index.get(parentId);
  if (!parent) issues.push({ code: "EDITOR_PARENT_NOT_FOUND", targetId: parentId });
  else if (parent.slideId !== slideId) issues.push({ code: "EDITOR_TARGET_SLIDE_MISMATCH", targetId: parentId });
  else if (parent.element.type !== "group" && parent.element.type !== "container") {
    issues.push({ code: "EDITOR_PARENT_TYPE_INVALID", targetId: parentId });
  }
}

function collectElementIds(element: CanonicalElement): string[] {
  return [
    element.id,
    ...(element.type === "group" || element.type === "container"
      ? element.children.flatMap(collectElementIds)
      : []),
  ];
}

function isSerializable(value: unknown): boolean {
  const stack = [value];
  const seen = new Set<object>();
  while (stack.length) {
    const current = stack.pop();
    if (typeof current === "function" || typeof current === "symbol" || typeof current === "bigint" || current === undefined) return false;
    if (!current || typeof current !== "object") continue;
    if (seen.has(current)) continue;
    seen.add(current);
    if (Array.isArray(current)) stack.push(...current);
    else stack.push(...Object.values(current));
  }
  try {
    const serialized = JSON.stringify(value);
    return serialized !== undefined && JSON.parse(serialized) != null;
  } catch {
    return false;
  }
}

function allFinite(value: unknown): boolean {
  const stack = [value];
  while (stack.length) {
    const current = stack.pop();
    if (typeof current === "number" && !Number.isFinite(current)) return false;
    if (Array.isArray(current)) stack.push(...current);
    else if (current && typeof current === "object") stack.push(...Object.values(current));
  }
  return true;
}
