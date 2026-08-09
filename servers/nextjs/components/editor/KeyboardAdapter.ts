"use client";

import { useEffect } from "react";
import type { PresentationDocument, Slide } from "@/generated/presentation-document";
import { createEditorCommandId, type EditorCommand } from "@/components/editor/commands";
import { canonicalClipboardFragment, pasteCanonicalClipboard, plainTextPasteCommand, serializeCanonicalClipboard } from "@/components/editor/clipboard/clipboard";
import { createCanonicalStableId } from "@/components/editor/clipboard/stable-id";
import { editorShortcut, nudgeDistance } from "@/components/editor/shortcuts/shortcuts";

export function useCanonicalKeyboardAdapter({
  document,
  slide,
  selectedIds,
  onCommand,
  onSelection,
  onEscape,
  onUndo,
  onRedo,
  onZoom,
}: {
  document: PresentationDocument;
  slide: Slide;
  selectedIds: string[];
  onCommand: (command: EditorCommand) => void;
  onSelection: (ids: string[]) => void;
  onEscape: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onZoom: (action: "in" | "out" | "reset") => void;
}) {
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      const action = editorShortcut(event);
      if (!action) return;
      const selected = selectedIds.filter((id) => findElement(slide, id)?.locked !== true);
      const execute = (command: EditorCommand) => {
        event.preventDefault();
        onCommand(command);
      };
      if (action === "undo") { event.preventDefault(); onUndo(); return; }
      if (action === "redo") { event.preventDefault(); onRedo(); return; }
      if (action === "escape") { event.preventDefault(); onEscape(); return; }
      if (action === "select-all") { event.preventDefault(); onSelection(visibleElementIds(slide)); return; }
      if (action === "zoom-in" || action === "zoom-out" || action === "zoom-reset") {
        event.preventDefault();
        onZoom(action === "zoom-in" ? "in" : action === "zoom-out" ? "out" : "reset");
        return;
      }
      if (action === "copy") {
        if (!selectedIds.length) return;
        event.preventDefault();
        void navigator.clipboard?.writeText(serializeCanonicalClipboard(canonicalClipboardFragment(document, selectedIds)));
        return;
      }
      if (action === "paste") {
        event.preventDefault();
        void navigator.clipboard?.readText().then((raw) => {
          const result = pasteCanonicalClipboard(raw, document, slide.id, createCanonicalStableId, () => createEditorCommandId("paste"));
          if (result.ok) {
            onCommand({ commandId: createEditorCommandId("paste-batch"), type: "BATCH", targetIds: result.targetIds, payload: { commands: result.commands } });
            onSelection(result.targetIds);
            return;
          }
          const plainText = plainTextPasteCommand(raw, document, slide.id, createCanonicalStableId, createEditorCommandId("paste-text"));
          if (plainText) {
            onCommand(plainText);
            onSelection(plainText.targetIds);
          }
        }).catch(() => undefined);
        return;
      }
      if (action === "duplicate") {
        if (!selectedIds.length) return;
        const raw = serializeCanonicalClipboard(canonicalClipboardFragment(document, selectedIds));
        const result = pasteCanonicalClipboard(raw, document, slide.id, createCanonicalStableId, () => createEditorCommandId("duplicate"));
        if (result.ok) {
          execute({ commandId: createEditorCommandId("duplicate-batch"), type: "BATCH", targetIds: result.targetIds, payload: { commands: result.commands } });
          onSelection(result.targetIds);
        }
        return;
      }
      if (action === "delete" && selected.length) {
        execute({ commandId: createEditorCommandId("delete"), type: "DELETE_ELEMENTS", targetIds: selected, payload: { slideId: slide.id } });
        onSelection([]);
        return;
      }
      if (action.startsWith("nudge-") && selected.length) {
        const distance = nudgeDistance(event.shiftKey);
        execute({
          commandId: createEditorCommandId("nudge"),
          type: "MOVE_ELEMENTS",
          targetIds: selected,
          payload: {
            slideId: slide.id,
            deltaX: action === "nudge-left" ? -distance : action === "nudge-right" ? distance : 0,
            deltaY: action === "nudge-up" ? -distance : action === "nudge-down" ? distance : 0,
          },
        });
      }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [document, onCommand, onEscape, onRedo, onSelection, onUndo, onZoom, selectedIds, slide]);
}

function findElement(slide: Slide, id: string): import("@/generated/presentation-document").Element | undefined {
  const stack = [...slide.elements];
  while (stack.length) {
    const element = stack.pop();
    if (!element) continue;
    if (element.id === id) return element;
    if (element.type === "group" || element.type === "container") stack.push(...element.children);
  }
}

function visibleElementIds(slide: Slide) {
  const ids: string[] = [];
  const stack = [...slide.elements];
  while (stack.length) {
    const element = stack.shift();
    if (!element) continue;
    if (!element.hidden) ids.push(element.id);
    if (element.type === "group" || element.type === "container") stack.unshift(...element.children);
  }
  return ids;
}
