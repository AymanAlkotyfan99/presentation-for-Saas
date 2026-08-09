"use client";

import { memo, type ComponentType } from "react";
import { Group, Rect, Text } from "react-konva";
import { BasicPlaceholder } from "./unsupported-placeholder";
import { ShapeRenderer, LineRenderer, ArrowRenderer, VectorRenderer } from "./basic-renderers";
import { TextRenderer } from "./text-renderer";
import { ImageRenderer, IconRenderer } from "./image-renderer";
import { TableRenderer, ChartRenderer } from "./data-renderers";
import { ContainerRenderer, GroupRenderer } from "./group-renderer";
import type { KonvaElementRendererProps, KonvaRendererRegistry } from "./types";

export const konvaRendererRegistry = Object.freeze({
  text: TextRenderer,
  image: ImageRenderer,
  shape: ShapeRenderer,
  line: LineRenderer,
  arrow: ArrowRenderer,
  vector: VectorRenderer,
  icon: IconRenderer,
  table: TableRenderer,
  chart: ChartRenderer,
  container: ContainerRenderer,
  group: GroupRenderer,
} satisfies KonvaRendererRegistry);

export const CanonicalKonvaElement = memo(function CanonicalKonvaElement({
  element,
  context,
}: KonvaElementRendererProps) {
  if (element.hidden) return null;
  const temporary = context.temporaryTransforms[element.id];
  const geometry = temporary?.geometry ?? element.geometry;
  const rotation = temporary?.rotation ?? element.transform?.rotation ?? 0;
  const Renderer = konvaRendererRegistry[element.type] as ComponentType<KonvaElementRendererProps> | undefined;
  if (!Renderer) return <BasicPlaceholder element={element} />;
  const dragEnabled = context.interactive && !element.locked;
  return <Group
    id={`canonical-${element.id}`}
    name="canonical-element"
    x={geometry.x + geometry.width / 2}
    y={geometry.y + geometry.height / 2}
    offsetX={geometry.width / 2}
    offsetY={geometry.height / 2}
    width={geometry.width}
    height={geometry.height}
    rotation={rotation}
    scaleX={element.transform?.flipHorizontal ? -1 : 1}
    scaleY={element.transform?.flipVertical ? -1 : 1}
    draggable={dragEnabled}
    onMouseDown={(event) => {
      event.cancelBubble = true;
      if (!context.selectedIds.has(element.id)) context.onSelect?.(element.id, Boolean(event.evt.shiftKey));
    }}
    onClick={(event) => {
      event.cancelBubble = true;
      context.onSelect?.(element.id, Boolean(event.evt.shiftKey));
    }}
    onTap={(event) => {
      event.cancelBubble = true;
      context.onSelect?.(element.id, false);
    }}
    onDragStart={() => context.onDragStart?.(element)}
    onDragMove={(event) => {
      const x = event.target.x() - geometry.width / 2;
      const y = event.target.y() - geometry.height / 2;
      const snapped = context.onDragPreview?.(element, x, y, Boolean(event.evt.altKey));
      if (snapped) event.target.position({ x: snapped.x + geometry.width / 2, y: snapped.y + geometry.height / 2 });
    }}
    onDragEnd={(event) => context.onDragCommit?.(element, event.target.x() - geometry.width / 2, event.target.y() - geometry.height / 2)}
  >
    <Renderer element={element} context={context} />
    {context.selectedIds.has(element.id) && <Rect width={geometry.width} height={geometry.height} stroke="#2563EB" strokeWidth={1.5 / 1} dash={[6, 3]} listening={false} />}
    {element.locked && context.selectedIds.has(element.id) && <Text text="🔒" fontSize={14} x={4} y={4} listening={false} />}
  </Group>;
});
