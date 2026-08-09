"use client";

import type { PresentationDocument } from "@/generated/presentation-document";
import { CanonicalBrowserSlide } from "@/renderers/browser";
import { CanonicalKonvaStage } from "@/renderers/konva";

export function CanonicalRendererFixtureClient({ document }: { document: PresentationDocument }) {
  const slide = document.slides[0];
  const viewport = { zoom: 0.5, offsetX: 0, offsetY: 0, containerWidth: 640, containerHeight: 360 };
  return <main className="min-h-screen space-y-8 bg-neutral-100 p-8" dir="ltr">
    <h1 className="text-xl font-semibold">Canonical renderer parity fixture</h1>
    <section aria-label="Browser renderer fixture">
      <h2 className="mb-2 font-medium">Browser</h2>
      <div className="h-[360px] w-[640px] overflow-hidden border bg-white"><div style={{ transform: "scale(.5)", transformOrigin: "top left" }}><CanonicalBrowserSlide document={document} slideId={slide.id} /></div></div>
    </section>
    <section aria-label="Konva renderer fixture">
      <h2 className="mb-2 font-medium">Konva</h2>
      <div className="h-[360px] w-[640px] overflow-hidden border bg-white"><CanonicalKonvaStage document={document} slideId={slide.id} viewport={viewport} /></div>
    </section>
  </main>;
}
