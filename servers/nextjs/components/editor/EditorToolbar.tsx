"use client";

import type { Element as CanonicalElement, Slide } from "@/generated/presentation-document";
import { createEditorCommandId, rotatedBoundingBox, unionBoundingBoxes, type EditorCommand } from "@/components/editor/commands";
import { createCanonicalStableId } from "@/components/editor/clipboard/stable-id";
import { useTranslations } from "@/i18n/catalog";

export function EditorToolbar({
  slide,
  selectedElements,
  canUndo,
  canRedo,
  onCommand,
  onUndo,
  onRedo,
  onZoom,
  onEditText,
}: {
  slide: Slide;
  selectedElements: CanonicalElement[];
  canUndo: boolean;
  canRedo: boolean;
  onCommand: (command: EditorCommand) => void;
  onUndo: () => void;
  onRedo: () => void;
  onZoom: (action: "in" | "out" | "fit" | "width" | "reset") => void;
  onEditText: (id: string) => void;
}) {
  const t = useTranslations();
  const ids = selectedElements.map(({ id }) => id);
  const command = (type: EditorCommand["type"], payload: object) => onCommand({ commandId: createEditorCommandId("toolbar"), type, targetIds: ids, payload } as EditorCommand);
  return <div role="toolbar" aria-label={t("editor.keyboardShortcuts")} className="flex flex-wrap items-center gap-1 border-b p-2">
    <Button label={t("editor.undo")} disabled={!canUndo} onClick={onUndo}>↶</Button>
    <Button label={t("editor.redo")} disabled={!canRedo} onClick={onRedo}>↷</Button>
    <span aria-hidden="true" className="mx-1 h-5 border-s" />
    <Button label={t("editor.zoomOut")} onClick={() => onZoom("out")}>−</Button>
    <Button label={t("editor.zoomIn")} onClick={() => onZoom("in")}>+</Button>
    <Button label={t("editor.zoomReset")} onClick={() => onZoom("reset")}>100%</Button>
    <Button label={t("editor.fitSlide")} onClick={() => onZoom("fit")}>□</Button>
    <Button label={t("editor.fitWidth")} onClick={() => onZoom("width")}>↔</Button>
    <span aria-hidden="true" className="mx-1 h-5 border-s" />
    {(["start", "center-horizontal", "end", "top", "center-vertical", "bottom"] as const).map((alignment) => <Button key={alignment} label={t(`editor.alignControls.${alignment === "center-horizontal" ? "centerHorizontal" : alignment === "center-vertical" ? "centerVertical" : alignment}`)} disabled={ids.length < 2} onClick={() => command("ALIGN_ELEMENTS", { slideId: slide.id, alignment })}>{alignmentSymbol(alignment)}</Button>)}
    <Button label={t("editor.distributeHorizontal")} disabled={ids.length < 3} onClick={() => command("DISTRIBUTE_ELEMENTS", { slideId: slide.id, axis: "horizontal" })}>⇿</Button>
    <Button label={t("editor.distributeVertical")} disabled={ids.length < 3} onClick={() => command("DISTRIBUTE_ELEMENTS", { slideId: slide.id, axis: "vertical" })}>⇳</Button>
    <Button label={t("editor.lock")} disabled={!ids.length} onClick={() => command("LOCK_ELEMENTS", { slideId: slide.id })}>🔒</Button>
    <Button label={t("editor.unlock")} disabled={!ids.length} onClick={() => command("UNLOCK_ELEMENTS", { slideId: slide.id })}>🔓</Button>
    <Button label={t("editor.hideElement")} disabled={!ids.length} onClick={() => command("HIDE_ELEMENTS", { slideId: slide.id })}>◉</Button>
    <Button label={t("editor.showElement")} disabled={!ids.length} onClick={() => command("SHOW_ELEMENTS", { slideId: slide.id })}>◎</Button>
    <Button label={t("editor.group")} disabled={ids.length < 2} onClick={() => {
      const boxes = selectedElements.map((element) => rotatedBoundingBox(element.geometry, element.transform?.rotation));
      const box = unionBoundingBoxes(boxes);
      command("GROUP_ELEMENTS", { slideId: slide.id, group: { id: createCanonicalStableId(), type: "group", geometry: { x: box.left, y: box.top, width: box.right - box.left, height: box.bottom - box.top }, zOrder: Math.min(...selectedElements.map(({ zOrder }) => zOrder)), children: [] } });
    }}>▣</Button>
    <Button label={t("editor.ungroup")} disabled={!selectedElements.some(({ type }) => type === "group")} onClick={() => command("UNGROUP_ELEMENTS", { slideId: slide.id })}>▢</Button>
    <Button label={t("editor.editText")} disabled={selectedElements.length !== 1 || selectedElements[0]?.type !== "text"} onClick={() => onEditText(selectedElements[0]!.id)}>T</Button>
  </div>;
}

function Button({ label, disabled, onClick, children }: { label: string; disabled?: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" title={label} aria-label={label} disabled={disabled} onClick={onClick} className="min-h-8 min-w-8 rounded border px-2 text-xs disabled:opacity-40">{children}</button>;
}

function alignmentSymbol(alignment: string) {
  if (alignment === "top") return "⊤";
  if (alignment === "bottom") return "⊥";
  if (alignment === "center-vertical") return "↕";
  if (alignment === "center-horizontal") return "↔";
  return alignment === "start" ? "⇤" : "⇥";
}
