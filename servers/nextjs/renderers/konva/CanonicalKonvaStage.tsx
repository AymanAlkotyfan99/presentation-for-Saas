"use client";

import { useMemo, useRef, useState } from "react";
import type Konva from "konva";
import { Layer, Rect, Stage } from "react-konva";
import type { PresentationDocument } from "@/generated/presentation-document";
import { validatePresentationDocument } from "@/lib/presentation-document/validate";
import type { EditorGuide, EditorViewport, TemporaryElementTransform } from "@/components/editor/types";
import { indexDocumentElements } from "@/components/editor/commands";
import { CANONICAL_SLIDE_WIDTH } from "@/renderers/shared/geometry";
import { SlideScene } from "./SlideScene";
import { GuideOverlay } from "./GuideOverlay";
import { TransformOverlay } from "./TransformOverlay";
import type { CanonicalKonvaContext } from "./types";

export function CanonicalKonvaStage({
  document,
  slideId,
  viewport,
  selectedElementIds = [],
  guides = [],
  temporaryTransforms = {},
  assetUrls = {},
  interactive = false,
  onSelect,
  onClearSelection,
  onDragStart,
  onDragPreview,
  onDragCommit,
  onTransformCommit,
  onMarqueeSelection,
}: {
  document: PresentationDocument;
  slideId: string;
  viewport: EditorViewport;
  selectedElementIds?: string[];
  guides?: EditorGuide[];
  temporaryTransforms?: Record<string, TemporaryElementTransform>;
  assetUrls?: Readonly<Record<string, string | undefined>>;
  interactive?: boolean;
  onSelect?: CanonicalKonvaContext["onSelect"];
  onClearSelection?: () => void;
  onDragStart?: CanonicalKonvaContext["onDragStart"];
  onDragPreview?: CanonicalKonvaContext["onDragPreview"];
  onDragCommit?: CanonicalKonvaContext["onDragCommit"];
  onTransformCommit?: (elementId: string, geometry: import("@/generated/presentation-document").Geometry, rotation: number) => void;
  onMarqueeSelection?: (box: { left: number; top: number; right: number; bottom: number }) => void;
}) {
  const stageRef = useRef<Konva.Stage>(null);
  const [stage, setStage] = useState<Konva.Stage | null>(null);
  const [marquee, setMarquee] = useState<{ startX: number; startY: number; endX: number; endY: number } | null>(null);
  const validation = useMemo(() => validatePresentationDocument(document), [document]);
  if (!validation.ok) return <div role="alert" data-renderer="konva" className="grid h-full place-items-center bg-red-50 text-red-800">Invalid canonical document</div>;
  const validDocument = validation.document;
  const slide = validDocument.slides.find(({ id }) => id === slideId);
  if (!slide) return <div role="alert" className="grid h-full place-items-center">Slide unavailable</div>;
  const slideHeight = CANONICAL_SLIDE_WIDTH * validDocument.aspectRatio.height / validDocument.aspectRatio.width;
  const selected = new Set(selectedElementIds);
  const firstSelected = selectedElementIds[0] ?? null;
  const selectedElement = firstSelected ? indexDocumentElements(validDocument).get(firstSelected)?.element : undefined;
  return <Stage
    ref={(node) => {
      stageRef.current = node;
      if (stage !== node) setStage(node);
    }}
    width={viewport.containerWidth}
    height={viewport.containerHeight}
    scaleX={viewport.zoom}
    scaleY={viewport.zoom}
    x={viewport.offsetX}
    y={viewport.offsetY}
    onMouseDown={(event) => {
      if (event.target === event.target.getStage()) {
        onClearSelection?.();
        const point = worldPointer(event.target.getStage(), viewport);
        if (interactive && point) setMarquee({ startX: point.x, startY: point.y, endX: point.x, endY: point.y });
      }
    }}
    onMouseMove={(event) => {
      if (!marquee) return;
      const point = worldPointer(event.target.getStage(), viewport);
      if (point) setMarquee({ ...marquee, endX: point.x, endY: point.y });
    }}
    onMouseUp={() => {
      if (marquee && (Math.abs(marquee.endX - marquee.startX) > 2 || Math.abs(marquee.endY - marquee.startY) > 2)) onMarqueeSelection?.(normalizeMarquee(marquee));
      setMarquee(null);
    }}
    onTouchStart={(event) => {
      if (event.target === event.target.getStage()) onClearSelection?.();
    }}
  >
    <Layer listening={interactive}>
      <SlideScene document={validDocument} slide={slide} width={CANONICAL_SLIDE_WIDTH} height={slideHeight} assetUrls={assetUrls} selectedIds={selected} temporaryTransforms={temporaryTransforms} interactive={interactive} onSelect={onSelect} onDragStart={onDragStart} onDragPreview={onDragPreview} onDragCommit={onDragCommit} />
      {interactive &&
      <TransformOverlay stage={stage} selectedElementId={firstSelected} locked={selectedElement?.locked ?? false} zoom={viewport.zoom} onCommit={onTransformCommit} />
      }
    </Layer>
    <Layer listening={false}>
      <GuideOverlay guides={guides} zoom={viewport.zoom} />
      {marquee && <Rect x={Math.min(marquee.startX, marquee.endX)} y={Math.min(marquee.startY, marquee.endY)} width={Math.abs(marquee.endX - marquee.startX)} height={Math.abs(marquee.endY - marquee.startY)} fill="rgba(37,99,235,.12)" stroke="#2563EB" strokeWidth={1 / Math.max(viewport.zoom, .01)} />}
    </Layer>
  </Stage>;
}

function worldPointer(stage: Konva.Stage | null, viewport: EditorViewport) {
  const point = stage?.getPointerPosition();
  return point ? { x: (point.x - viewport.offsetX) / viewport.zoom, y: (point.y - viewport.offsetY) / viewport.zoom } : null;
}

function normalizeMarquee(value: { startX: number; startY: number; endX: number; endY: number }) {
  return { left: Math.min(value.startX, value.endX), top: Math.min(value.startY, value.endY), right: Math.max(value.startX, value.endX), bottom: Math.max(value.startY, value.endY) };
}
