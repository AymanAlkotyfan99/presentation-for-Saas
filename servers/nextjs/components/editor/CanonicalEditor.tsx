"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import type { PresentationDocument, TextElement } from "@/generated/presentation-document";
import { countDocumentElements, indexDocumentElements, type EditorCommand } from "@/components/editor/commands";
import { marqueeSelection, toggleSelection } from "@/components/editor/selection/selection";
import { fitSlideViewport, fitWidthViewport, resetViewport, zoomViewport, EDITOR_ZOOM_STEP } from "@/components/editor/viewport/viewport";
import { CANONICAL_SLIDE_WIDTH } from "@/renderers/shared/geometry";
import { CanonicalKonvaStage, useCanonicalInteractionAdapter } from "@/renderers/konva";
import { useCanonicalEditorStore } from "./document-store";
import { LayerPanel } from "./layers/LayerPanel";
import { EditorToolbar } from "./EditorToolbar";
import { CanonicalTextEditor } from "./CanonicalTextEditor";
import { useCanonicalKeyboardAdapter } from "./KeyboardAdapter";
import { useI18n } from "@/i18n/catalog";
import { editorDeckMetric, useEditorPerformanceObserver, type EditorMetricSink } from "./observability";

export function CanonicalEditor({
  document,
  onDocumentChange,
  assetUrls = {},
  className = "",
  metricSink,
}: {
  document: PresentationDocument;
  onDocumentChange?: (document: PresentationDocument) => void;
  assetUrls?: Readonly<Record<string, string | undefined>>;
  className?: string;
  metricSink?: EditorMetricSink;
}) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const baseMetric = useMemo(() => editorDeckMetric("konva", document.slides.length, countDocumentElements(document)), [document]);
  const handleDocumentChange = useCallback((next: PresentationDocument, command?: EditorCommand) => {
    onDocumentChange?.(next);
    if (command) metricSink?.({ ...baseMetric, commandType: command.type, commandStatus: "success" });
  }, [baseMetric, metricSink, onDocumentChange]);
  const handleCommandError = useCallback((command: EditorCommand) => {
    metricSink?.({ ...baseMetric, commandType: command.type, commandStatus: "failure" });
  }, [baseMetric, metricSink]);
  const store = useCanonicalEditorStore({ document, onDocumentChange: handleDocumentChange, onCommandError: handleCommandError });
  const { setViewport, setSelection, setEditingTextElement, setInteraction, cancelInteraction, execute, undo, redo, canUndo, canRedo } = store;
  useEditorPerformanceObserver(baseMetric, metricSink);
  const { viewModel } = store;
  const { direction: uiDirection, t } = useI18n();
  const slide = viewModel.document.slides.find(({ id }) => id === viewModel.activeSlideId)!;
  const slideHeight = CANONICAL_SLIDE_WIDTH * viewModel.document.aspectRatio.height / viewModel.document.aspectRatio.width;
  const elementIndex = useMemo(() => indexDocumentElements(viewModel.document), [viewModel.document]);
  const selectedElements = viewModel.selectedElementIds.flatMap((id) => {
    const element = elementIndex.get(id)?.element;
    return element ? [element] : [];
  });
  const interaction = useCanonicalInteractionAdapter({
    document: viewModel.document,
    slide,
    slideWidth: CANONICAL_SLIDE_WIDTH,
    slideHeight,
    zoom: viewModel.viewport.zoom,
    selectedIds: viewModel.selectedElementIds,
    onCommand: execute,
    onInteraction: setInteraction,
  });
  useEffect(() => {
    const element = surfaceRef.current;
    if (!element) return;
    const update = () => {
      const containerWidth = Math.max(1, element.clientWidth);
      const containerHeight = Math.max(1, element.clientHeight);
      if (containerWidth !== viewModel.viewport.containerWidth || containerHeight !== viewModel.viewport.containerHeight) {
        setViewport({ ...viewModel.viewport, containerWidth, containerHeight });
      }
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [setViewport, viewModel.viewport]);
  const setSelectedIds = useCallback((ids: string[]) => setSelection({ selectedIds: ids, anchorId: ids.at(-1) ?? null }), [setSelection]);
  const zoom = useCallback((action: "in" | "out" | "fit" | "width" | "reset") => {
    const current = viewModel.viewport;
    setViewport(action === "fit"
      ? fitSlideViewport(current, CANONICAL_SLIDE_WIDTH, slideHeight)
      : action === "width"
        ? fitWidthViewport(current, CANONICAL_SLIDE_WIDTH)
        : action === "reset"
          ? resetViewport(current)
          : zoomViewport(current, current.zoom + (action === "in" ? EDITOR_ZOOM_STEP : -EDITOR_ZOOM_STEP)));
  }, [setViewport, slideHeight, viewModel.viewport]);
  useCanonicalKeyboardAdapter({
    document: viewModel.document,
    slide,
    selectedIds: viewModel.selectedElementIds,
    onCommand: execute,
    onSelection: setSelectedIds,
    onEscape: () => { cancelInteraction(); setSelectedIds([]); setEditingTextElement(null); },
    onUndo: undo,
    onRedo: redo,
    onZoom: (action) => zoom(action),
  });
  const editingText = viewModel.editingTextElementId ? elementIndex.get(viewModel.editingTextElementId)?.element : undefined;
  return <section className={`flex h-full min-h-0 flex-col ${className}`} data-editor="canonical" dir={uiDirection}>
    <EditorToolbar slide={slide} selectedElements={selectedElements} canUndo={canUndo} canRedo={canRedo} onCommand={execute} onUndo={undo} onRedo={redo} onZoom={zoom} onEditText={setEditingTextElement} />
    <div className="flex min-h-0 flex-1">
      <LayerPanel
        slide={slide}
        selectedIds={viewModel.selectedElementIds}
        onSelect={(id, additive) => setSelection(additive
          ? toggleSelection(viewModel.document, { selectedIds: viewModel.selectedElementIds, anchorId: viewModel.selectedElementIds.at(-1) ?? null }, id)
          : { selectedIds: [id], anchorId: id })}
        onCommand={execute}
      />
      <div ref={surfaceRef} className="relative min-h-0 min-w-0 flex-1 overflow-hidden bg-neutral-200" dir="ltr" tabIndex={0} aria-label={t("editor.canonicalCanvas")} onWheel={(event) => {
        if (!event.ctrlKey && !event.metaKey) return;
        event.preventDefault();
        const bounds = event.currentTarget.getBoundingClientRect();
        setViewport(zoomViewport(viewModel.viewport, viewModel.viewport.zoom + (event.deltaY < 0 ? EDITOR_ZOOM_STEP : -EDITOR_ZOOM_STEP), { x: event.clientX - bounds.left, y: event.clientY - bounds.top }));
      }}>
        <CanonicalKonvaStage
          document={viewModel.document}
          slideId={slide.id}
          viewport={viewModel.viewport}
          selectedElementIds={viewModel.selectedElementIds}
          guides={viewModel.guides}
          temporaryTransforms={viewModel.temporaryTransforms}
          assetUrls={assetUrls}
          interactive
          onSelect={(id, additive) => setSelection(additive
            ? toggleSelection(viewModel.document, { selectedIds: viewModel.selectedElementIds, anchorId: viewModel.selectedElementIds.at(-1) ?? null }, id)
            : { selectedIds: [id], anchorId: id })}
          onClearSelection={() => setSelectedIds([])}
          onDragStart={interaction.onDragStart}
          onDragPreview={interaction.onDragPreview}
          onDragCommit={interaction.onDragCommit}
          onTransformCommit={interaction.onTransformCommit}
          onMarqueeSelection={(box) => setSelection(marqueeSelection(slide, box))}
        />
      </div>
      {editingText?.type === "text" && <aside className="w-80 border-s bg-background">
        <CanonicalTextEditor element={editingText as TextElement} slideId={slide.id} defaultDirection={slide.direction ?? viewModel.document.baseDirection} onCommand={execute} onClose={() => setEditingTextElement(null)} />
      </aside>}
    </div>
  </section>;
}
