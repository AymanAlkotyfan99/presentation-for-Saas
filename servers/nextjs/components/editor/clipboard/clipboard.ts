import type {
  ChartElement,
  Element as CanonicalElement,
  Paragraph,
  PresentationDocument,
  TableCell,
} from "@/generated/presentation-document";
import { applyCommandBatch, indexDocumentElements, type EditorCommand } from "@/components/editor/commands";

export const CANONICAL_CLIPBOARD_MIME = "application/vnd.bayanly.canonical-fragment+json";
export const CANONICAL_CLIPBOARD_VERSION = 1 as const;

export type CanonicalClipboardFragment = {
  kind: typeof CANONICAL_CLIPBOARD_MIME;
  version: typeof CANONICAL_CLIPBOARD_VERSION;
  elements: CanonicalElement[];
};

export type ClipboardPasteResult =
  | { ok: true; commands: EditorCommand[]; targetIds: string[] }
  | { ok: false; reason: "invalid" | "unsafe" | "unauthorized-asset" | "limit" };

export function canonicalClipboardFragment(
  document: PresentationDocument,
  selectedIds: string[],
): CanonicalClipboardFragment {
  const index = indexDocumentElements(document);
  const selected = new Set(selectedIds);
  const roots = selectedIds.flatMap((id) => {
    const path = index.get(id);
    if (!path) return [];
    let parentId = path.parentId;
    while (parentId) {
      if (selected.has(parentId)) return [];
      parentId = index.get(parentId)?.parentId ?? null;
    }
    return [path.element];
  });
  return { kind: CANONICAL_CLIPBOARD_MIME, version: CANONICAL_CLIPBOARD_VERSION, elements: roots };
}

export function serializeCanonicalClipboard(fragment: CanonicalClipboardFragment) {
  return JSON.stringify(fragment);
}

export function pasteCanonicalClipboard(
  raw: string,
  document: PresentationDocument,
  slideId: string,
  idFactory: () => string,
  commandIdFactory: () => string,
  offset = { x: 16, y: 16 },
): ClipboardPasteResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { ok: false, reason: "invalid" };
  }
  if (!isFragment(parsed)) return { ok: false, reason: "invalid" };
  const allowedAssets = new Set(document.assets.map(({ assetId }) => assetId));
  if (parsed.elements.some((element) => elementAssetIds(element).some((id) => !allowedAssets.has(id)))) {
    return { ok: false, reason: "unauthorized-asset" };
  }
  const copies = parsed.elements.map((element) => regenerateElementIds(element, idFactory, offset));
  const commands: EditorCommand[] = copies.map((element) => ({
    commandId: commandIdFactory(),
    type: "ADD_ELEMENT",
    targetIds: [element.id],
    payload: { slideId, element },
  }));
  try {
    applyCommandBatch(document, commands);
  } catch (error) {
    return {
      ok: false,
      reason: error instanceof RangeError || String(error).includes("LIMIT") ? "limit" : "unsafe",
    };
  }
  return { ok: true, commands, targetIds: copies.map(({ id }) => id) };
}

export function plainTextPasteCommand(
  raw: string,
  document: PresentationDocument,
  slideId: string,
  idFactory: () => string,
  commandId: string,
): EditorCommand | null {
  const text = raw.replace(/\r\n?/g, "\n").replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "").slice(0, 100_000);
  if (!text.trim() || text.trimStart().startsWith("{")) return null;
  const direction = document.slides.find(({ id }) => id === slideId)?.direction ?? document.baseDirection;
  const element: CanonicalElement = {
    id: idFactory(),
    type: "text",
    geometry: { x: 80, y: 80, width: 640, height: 240 },
    zOrder: document.slides.find(({ id }) => id === slideId)?.elements.length ?? 0,
    paragraphs: text.split("\n").slice(0, 1_000).map((line) => ({
      id: idFactory(),
      direction,
      logicalAlignment: "start",
      runs: [{ id: idFactory(), text: line }],
    })),
  };
  const command: EditorCommand = { commandId, type: "ADD_ELEMENT", targetIds: [element.id], payload: { slideId, element } };
  try {
    applyCommandBatch(document, [command]);
    return command;
  } catch {
    return null;
  }
}

function isFragment(value: unknown): value is CanonicalClipboardFragment {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return record.kind === CANONICAL_CLIPBOARD_MIME &&
    record.version === CANONICAL_CLIPBOARD_VERSION &&
    Array.isArray(record.elements) &&
    record.elements.length > 0 &&
    record.elements.length <= 5_000 &&
    record.elements.every((element) => element && typeof element === "object" && !Array.isArray(element));
}

function regenerateElementIds(
  element: CanonicalElement,
  idFactory: () => string,
  offset: { x: number; y: number },
): CanonicalElement {
  const base = {
    ...element,
    id: idFactory(),
    geometry: {
      ...element.geometry,
      x: element.geometry.x + offset.x,
      y: element.geometry.y + offset.y,
    },
  };
  if (element.type === "group" || element.type === "container") {
    return { ...base, children: element.children.map((child) => regenerateElementIds(child, idFactory, { x: 0, y: 0 })) } as CanonicalElement;
  }
  if (element.type === "text") {
    return { ...base, paragraphs: element.paragraphs.map((paragraph) => regenerateParagraphIds(paragraph, idFactory)) } as CanonicalElement;
  }
  if (element.type === "table") {
    return {
      ...base,
      rows: element.rows.map((row) => ({
        ...row,
        cells: row.cells.map((cell) => regenerateCellIds(cell, idFactory)),
      })),
    } as CanonicalElement;
  }
  if (element.type === "chart") {
    const chart: ChartElement = {
      ...element,
      id: base.id,
      geometry: base.geometry,
      chartId: idFactory(),
      series: element.series.map((series) => ({ ...series, id: idFactory() })),
    };
    return chart;
  }
  return base as CanonicalElement;
}

function regenerateParagraphIds(paragraph: Paragraph, idFactory: () => string): Paragraph {
  return {
    ...paragraph,
    id: idFactory(),
    runs: paragraph.runs.map((run) => ({ ...run, id: idFactory() })),
  };
}

function regenerateCellIds(cell: TableCell, idFactory: () => string): TableCell {
  return { ...cell, paragraphs: cell.paragraphs.map((paragraph) => regenerateParagraphIds(paragraph, idFactory)) };
}

function elementAssetIds(element: CanonicalElement): string[] {
  const own = element.type === "image"
    ? [element.assetId]
    : element.type === "icon" && element.assetId
      ? [element.assetId]
      : [];
  return element.type === "group" || element.type === "container"
    ? [...own, ...element.children.flatMap(elementAssetIds)]
    : own;
}
