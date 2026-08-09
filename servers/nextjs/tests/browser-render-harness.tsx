import { renderToStaticMarkup } from "react-dom/server";
import type { PresentationDocument } from "@/generated/presentation-document";
import { CanonicalBrowserSlide, browserRendererRegistry } from "@/renderers/browser";
import { createCanonicalVisualFixture } from "@/components/editor/fixtures/visual";

export const browserRendererTypes = Object.keys(browserRendererRegistry);

export function renderCanonicalBrowser(document: PresentationDocument, slideId: string, assetUrls?: Readonly<Record<string, string | undefined>>) {
  return renderToStaticMarkup(<CanonicalBrowserSlide document={document} slideId={slideId} assetUrls={assetUrls} />);
}

export { createCanonicalVisualFixture };
