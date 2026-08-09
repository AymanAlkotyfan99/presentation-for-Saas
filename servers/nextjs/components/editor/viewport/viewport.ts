import type { EditorViewport } from "@/components/editor/types";

export const MIN_EDITOR_ZOOM = 0.25;
export const MAX_EDITOR_ZOOM = 4;
export const EDITOR_ZOOM_STEP = 0.1;

export function clampZoom(zoom: number) {
  if (!Number.isFinite(zoom)) return 1;
  return Math.min(MAX_EDITOR_ZOOM, Math.max(MIN_EDITOR_ZOOM, Math.round(zoom * 1000) / 1000));
}

export function zoomViewport(
  viewport: EditorViewport,
  zoom: number,
  anchor = { x: viewport.containerWidth / 2, y: viewport.containerHeight / 2 },
): EditorViewport {
  const nextZoom = clampZoom(zoom);
  const worldX = (anchor.x - viewport.offsetX) / viewport.zoom;
  const worldY = (anchor.y - viewport.offsetY) / viewport.zoom;
  return {
    ...viewport,
    zoom: nextZoom,
    offsetX: anchor.x - worldX * nextZoom,
    offsetY: anchor.y - worldY * nextZoom,
  };
}

export function fitSlideViewport(
  viewport: EditorViewport,
  slideWidth: number,
  slideHeight: number,
  padding = 24,
): EditorViewport {
  const availableWidth = Math.max(1, viewport.containerWidth - padding * 2);
  const availableHeight = Math.max(1, viewport.containerHeight - padding * 2);
  const zoom = clampZoom(Math.min(availableWidth / slideWidth, availableHeight / slideHeight));
  return {
    ...viewport,
    zoom,
    offsetX: (viewport.containerWidth - slideWidth * zoom) / 2,
    offsetY: (viewport.containerHeight - slideHeight * zoom) / 2,
  };
}

export function fitWidthViewport(
  viewport: EditorViewport,
  slideWidth: number,
  padding = 24,
): EditorViewport {
  const zoom = clampZoom((Math.max(1, viewport.containerWidth - padding * 2)) / slideWidth);
  return {
    ...viewport,
    zoom,
    offsetX: (viewport.containerWidth - slideWidth * zoom) / 2,
    offsetY: padding,
  };
}

export function resetViewport(viewport: EditorViewport): EditorViewport {
  return { ...viewport, zoom: 1, offsetX: 0, offsetY: 0 };
}
