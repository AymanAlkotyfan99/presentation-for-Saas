"use client";

import { useMemo } from "react";
import type { Element as CanonicalElement, Geometry, PresentationDocument, Slide } from "@/generated/presentation-document";
import { createEditorCommandId, indexDocumentElements, type EditorCommand } from "@/components/editor/commands";
import { buildSnapIndex, snapBoundingBox } from "@/components/editor/snapping/snapping";
import { rotatedBoundingBox, unionBoundingBoxes } from "@/components/editor/commands/document-index";
import type { EditorGuide, EditorInteractionMode, TemporaryElementTransform } from "@/components/editor/types";

export function useCanonicalInteractionAdapter({
  document,
  slide,
  slideWidth,
  slideHeight,
  zoom,
  selectedIds,
  onCommand,
  onInteraction,
}: {
  document: PresentationDocument;
  slide: Slide;
  slideWidth: number;
  slideHeight: number;
  zoom: number;
  selectedIds: string[];
  onCommand: (command: EditorCommand) => void;
  onInteraction: (mode: EditorInteractionMode, guides?: EditorGuide[], transforms?: Record<string, TemporaryElementTransform>) => void;
}) {
  const snapIndex = useMemo(() => buildSnapIndex(slide, slideWidth, slideHeight, new Set(selectedIds)), [selectedIds, slide, slideHeight, slideWidth]);
  const elementIndex = useMemo(() => indexDocumentElements(document), [document]);
  const movableSelection = selectedIds.flatMap((id) => {
    const element = elementIndex.get(id)?.element;
    return element && !element.locked ? [element] : [];
  });
  const dragTargets = (element: CanonicalElement) => selectedIds.includes(element.id) && movableSelection.length ? movableSelection : [element];
  return {
    onDragStart(element: CanonicalElement) {
      onInteraction("drag", [], Object.fromEntries(dragTargets(element).map((target) => [target.id, { geometry: target.geometry }])));
    },
    onDragPreview(element: CanonicalElement, x: number, y: number, snappingDisabled = false) {
      const dx = x - element.geometry.x;
      const dy = y - element.geometry.y;
      const targets = dragTargets(element);
      const boxes = targets.map((target) => rotatedBoundingBox({ ...target.geometry, x: target.geometry.x + dx, y: target.geometry.y + dy }, target.transform?.rotation));
      const snap = snapBoundingBox(unionBoundingBoxes(boxes), snapIndex, { zoom, disabled: snappingDisabled });
      const transforms = Object.fromEntries(targets.map((target) => [target.id, { geometry: { ...target.geometry, x: target.geometry.x + dx + snap.deltaX, y: target.geometry.y + dy + snap.deltaY } }]));
      onInteraction("drag", snap.guides, transforms);
      return { x: x + snap.deltaX, y: y + snap.deltaY };
    },
    onDragCommit(element: CanonicalElement, x: number, y: number) {
      const dx = roundGeometry(x - element.geometry.x);
      const dy = roundGeometry(y - element.geometry.y);
      if (dx || dy) onCommand({
        commandId: createEditorCommandId("move"),
        type: "MOVE_ELEMENTS",
        targetIds: dragTargets(element).map(({ id }) => id),
        payload: { slideId: slide.id, deltaX: dx, deltaY: dy },
      });
      onInteraction("select", [], {});
    },
    onTransformCommit(elementId: string, geometry: Geometry, rotation: number) {
      const element = elementIndex.get(elementId)?.element;
      if (!element || element.locked) return;
      const commands: EditorCommand[] = [{
        commandId: createEditorCommandId("resize"),
        type: "RESIZE_ELEMENTS",
        targetIds: [elementId],
        payload: { slideId: slide.id, geometryById: { [elementId]: roundedGeometry(geometry) } },
      }];
      if (roundGeometry(rotation) !== roundGeometry(element.transform?.rotation ?? 0)) commands.push({
        commandId: createEditorCommandId("rotate"),
        type: "ROTATE_ELEMENTS",
        targetIds: [elementId],
        payload: { slideId: slide.id, rotationById: { [elementId]: roundGeometry(rotation) } },
      });
      onCommand(commands.length === 1 ? commands[0] : {
        commandId: createEditorCommandId("transform"),
        type: "BATCH",
        targetIds: [elementId],
        payload: { commands },
      });
    },
  };
}

function roundGeometry(value: number) {
  return Math.round(value * 1000) / 1000;
}

function roundedGeometry(geometry: Geometry): Geometry {
  return Object.fromEntries(Object.entries(geometry).map(([key, value]) => [key, typeof value === "number" ? roundGeometry(value) : value])) as Geometry;
}
