import { useMemo } from "react";
import type { Element as CanonicalElement, PresentationDocument } from "@/generated/presentation-document";
import { validatePresentationDocument } from "@/lib/presentation-document/validate";
import { resolveDirection } from "@/renderers/shared/direction";
import { safeColor } from "@/renderers/shared/style";
import { CANONICAL_SLIDE_WIDTH } from "@/renderers/shared/geometry";
import { CanonicalBrowserElement } from "./registry";
import type { CanonicalBrowserContext } from "./types";

export function CanonicalBrowserSlide({
  document,
  slideId,
  assetUrls = {},
  className,
}: {
  document: PresentationDocument;
  slideId: string;
  assetUrls?: Readonly<Record<string, string | undefined>>;
  className?: string;
}) {
  const validation = useMemo(() => validatePresentationDocument(document), [document]);
  if (!validation.ok) return <div role="alert" data-renderer="browser">Invalid canonical document</div>;
  const validDocument = validation.document;
  const slide = validDocument.slides.find(({ id }) => id === slideId);
  if (!slide) return <div role="alert">Slide unavailable</div>;
  const height = CANONICAL_SLIDE_WIDTH * validDocument.aspectRatio.height / validDocument.aspectRatio.width;
  return <CanonicalBrowserScene document={validDocument} slideId={slideId} assetUrls={assetUrls} width={CANONICAL_SLIDE_WIDTH} height={height} className={className} />;
}

function CanonicalBrowserScene({ document, slideId, assetUrls, width, height, className }: { document: PresentationDocument; slideId: string; assetUrls: Readonly<Record<string, string | undefined>>; width: number; height: number; className?: string }) {
  const slide = document.slides.find(({ id }) => id === slideId)!;
  const context = useMemo<Omit<CanonicalBrowserContext, "renderElement">>(() => ({
    document,
    locale: slide.locale ?? document.locale,
    direction: resolveDirection(slide.direction, slide.locale ?? document.locale, resolveDirection(document.baseDirection, document.locale)),
    assetUrls,
  }), [assetUrls, document, slide.direction, slide.locale]);
  return <div
    className={className}
    dir={context.direction}
    data-canonical-slide-id={slide.id}
    data-renderer="browser"
    style={{ position: "relative", width, height, overflow: "hidden", isolation: "isolate", background: safeColor(slide.background?.color ?? document.theme.defaultBackground, "#FFFFFF") }}
  >{[...slide.elements].sort((a, b) => a.zOrder - b.zOrder || a.id.localeCompare(b.id)).map((element) => renderBrowserElement(element, context))}</div>;
}

function renderBrowserElement(element: CanonicalElement, base: Omit<CanonicalBrowserContext, "renderElement">): React.ReactNode {
  const context: CanonicalBrowserContext = { ...base, renderElement: (child) => renderBrowserElement(child, base) };
  return <CanonicalBrowserElement key={element.id} element={element} context={context} />;
}
