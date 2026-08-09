import type {
  Element as CanonicalElement,
  Geometry,
  PresentationDocument,
} from "@/generated/presentation-document";

export type EditorInteractionMode =
  | "select"
  | "marquee"
  | "drag"
  | "resize"
  | "rotate"
  | "text-edit";

export type EditorGuide = {
  id: string;
  axis: "x" | "y";
  position: number;
  start: number;
  end: number;
  kind: "slide-edge" | "slide-center" | "element-edge" | "element-center" | "equal-spacing";
};

export type TemporaryElementTransform = {
  geometry?: Geometry;
  rotation?: number;
};

export type EditorViewport = {
  zoom: number;
  offsetX: number;
  offsetY: number;
  containerWidth: number;
  containerHeight: number;
};

export type EditorViewModel = {
  document: PresentationDocument;
  activeSlideId: string;
  selectedElementIds: string[];
  hoveredElementId: string | null;
  editingTextElementId: string | null;
  viewport: EditorViewport;
  guides: EditorGuide[];
  temporaryTransforms: Record<string, TemporaryElementTransform>;
  interactionMode: EditorInteractionMode;
};

export type ElementPath = {
  slideId: string;
  element: CanonicalElement;
  parentId: string | null;
  depth: number;
  index: number;
};

export const DEFAULT_EDITOR_VIEWPORT: EditorViewport = Object.freeze({
  zoom: 1,
  offsetX: 0,
  offsetY: 0,
  containerWidth: 1280,
  containerHeight: 720,
});
