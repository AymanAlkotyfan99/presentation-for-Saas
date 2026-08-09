import type { ComponentType } from "react";
import type {
  Element as CanonicalElement,
  Locale,
  PresentationDocument,
} from "@/generated/presentation-document";
import type { TemporaryElementTransform } from "@/components/editor/types";
import type { CanonicalElementType, ElementOfType } from "@/renderers/shared/registry";
import type { ResolvedDirection } from "@/renderers/shared/direction";

export type CanonicalKonvaContext = {
  document: PresentationDocument;
  locale: Locale;
  direction: ResolvedDirection;
  assetUrls: Readonly<Record<string, string | undefined>>;
  selectedIds: ReadonlySet<string>;
  temporaryTransforms: Readonly<Record<string, TemporaryElementTransform>>;
  interactive: boolean;
  onSelect?: (elementId: string, additive: boolean) => void;
  onDragStart?: (element: CanonicalElement) => void;
  onDragPreview?: (element: CanonicalElement, x: number, y: number, snappingDisabled?: boolean) => { x: number; y: number };
  onDragCommit?: (element: CanonicalElement, x: number, y: number) => void;
  renderElement: (element: CanonicalElement) => React.ReactNode;
};

export type KonvaElementRendererProps<T extends CanonicalElement = CanonicalElement> = {
  element: T;
  context: CanonicalKonvaContext;
};

export type KonvaRendererRegistry = {
  [K in CanonicalElementType]: ComponentType<KonvaElementRendererProps<ElementOfType<K>>>;
};
