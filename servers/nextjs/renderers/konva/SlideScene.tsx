"use client";

import { useMemo } from "react";
import { Rect } from "react-konva";
import type { Element as CanonicalElement, PresentationDocument, Slide } from "@/generated/presentation-document";
import { resolveDirection } from "@/renderers/shared/direction";
import { safeColor } from "@/renderers/shared/style";
import { CanonicalKonvaElement } from "./registry";
import type { CanonicalKonvaContext } from "./types";
import type { TemporaryElementTransform } from "@/components/editor/types";

export function SlideScene({
  document,
  slide,
  width,
  height,
  assetUrls,
  selectedIds,
  temporaryTransforms,
  interactive,
  onSelect,
  onDragStart,
  onDragPreview,
  onDragCommit,
}: {
  document: PresentationDocument;
  slide: Slide;
  width: number;
  height: number;
  assetUrls: Readonly<Record<string, string | undefined>>;
  selectedIds: ReadonlySet<string>;
  temporaryTransforms: Readonly<Record<string, TemporaryElementTransform>>;
  interactive: boolean;
  onSelect?: CanonicalKonvaContext["onSelect"];
  onDragStart?: CanonicalKonvaContext["onDragStart"];
  onDragPreview?: CanonicalKonvaContext["onDragPreview"];
  onDragCommit?: CanonicalKonvaContext["onDragCommit"];
}) {
  const context = useMemo<Omit<CanonicalKonvaContext, "renderElement">>(() => ({
    document,
    locale: slide.locale ?? document.locale,
    direction: resolveDirection(slide.direction, slide.locale ?? document.locale, resolveDirection(document.baseDirection, document.locale)),
    assetUrls,
    selectedIds,
    temporaryTransforms,
    interactive,
    onSelect,
    onDragStart,
    onDragPreview,
    onDragCommit,
  }), [assetUrls, document, interactive, onDragCommit, onDragPreview, onDragStart, onSelect, selectedIds, slide.direction, slide.locale, temporaryTransforms]);
  return <>
    <Rect width={width} height={height} fill={safeColor(slide.background?.color ?? document.theme.defaultBackground, "#FFFFFF")} listening={false} />
    {[...slide.elements].sort((a, b) => a.zOrder - b.zOrder || a.id.localeCompare(b.id)).map((element) => renderKonvaElement(element, context))}
  </>;
}

function renderKonvaElement(element: CanonicalElement, base: Omit<CanonicalKonvaContext, "renderElement">): React.ReactNode {
  const context: CanonicalKonvaContext = { ...base, renderElement: (child) => renderKonvaElement(child, base) };
  return <CanonicalKonvaElement key={element.id} element={element} context={context} />;
}
