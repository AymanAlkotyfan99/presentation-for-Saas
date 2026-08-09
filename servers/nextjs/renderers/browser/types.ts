import type { ComponentType } from "react";
import type { Element as CanonicalElement, Locale, PresentationDocument } from "@/generated/presentation-document";
import type { CanonicalElementType, ElementOfType } from "@/renderers/shared/registry";
import type { ResolvedDirection } from "@/renderers/shared/direction";

export type CanonicalBrowserContext = {
  document: PresentationDocument;
  locale: Locale;
  direction: ResolvedDirection;
  assetUrls: Readonly<Record<string, string | undefined>>;
  renderElement: (element: CanonicalElement) => React.ReactNode;
};

export type BrowserElementRendererProps<T extends CanonicalElement = CanonicalElement> = {
  element: T;
  context: CanonicalBrowserContext;
};

export type BrowserRendererRegistry = {
  [K in CanonicalElementType]: ComponentType<BrowserElementRendererProps<ElementOfType<K>>>;
};
