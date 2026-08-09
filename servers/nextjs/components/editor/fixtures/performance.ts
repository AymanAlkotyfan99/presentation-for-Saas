import type { PresentationDocument, ShapeElement } from "@/generated/presentation-document";

export type EditorPerformanceFixtureSize = "10x100" | "30x1000" | "50x3000";

export const EDITOR_PERFORMANCE_FIXTURES = Object.freeze({
  "10x100": { slides: 10, elements: 100 },
  "30x1000": { slides: 30, elements: 1_000 },
  "50x3000": { slides: 50, elements: 3_000 },
} satisfies Record<EditorPerformanceFixtureSize, { slides: number; elements: number }>);

export function createEditorPerformanceFixture(size: EditorPerformanceFixtureSize): PresentationDocument {
  const specification = EDITOR_PERFORMANCE_FIXTURES[size];
  let nextId = 1_000;
  let remaining = specification.elements;
  const slides = Array.from({ length: specification.slides }, (_, slideIndex) => {
    const count = Math.ceil(remaining / (specification.slides - slideIndex));
    remaining -= count;
    const elements: ShapeElement[] = Array.from({ length: count }, (_, elementIndex) => ({
      id: uuid(nextId++),
      type: "shape",
      geometry: {
        x: 16 + (elementIndex % 12) * 102,
        y: 16 + (Math.floor(elementIndex / 12) % 8) * 82,
        width: 88,
        height: 64,
      },
      zOrder: elementIndex,
      shapeKind: elementIndex % 5 === 0 ? "rounded-rectangle" : "rectangle",
      style: { fill: elementIndex % 2 ? "#E5E7EB" : "#DBEAFE", cornerRadius: 6 },
    }));
    return {
      id: uuid(100 + slideIndex),
      order: slideIndex,
      title: `Reference slide ${slideIndex + 1}`,
      layoutIntent: "free" as const,
      elements,
    };
  });
  return {
    schemaVersion: "1.0.0",
    documentId: uuid(1),
    presentationId: uuid(2),
    title: `Editor performance fixture ${size}`,
    locale: "en",
    baseDirection: "ltr",
    aspectRatio: { width: 16, height: 9 },
    theme: { themeRef: "bayanly-performance", colorTokens: [{ name: "primary", value: "#2563EB" }], defaultBackground: "#FFFFFF" },
    fontPolicy: { families: [{ id: "body", family: "Arial", fallbacks: ["sans-serif"] }], defaultBodyRef: "body", defaultHeadingRef: "body", allowSystemFallback: true },
    metadata: { authoringIntent: "edited", sourceApplicationVersion: "sprint-5-fixture" },
    slides,
    assets: [],
    exportHints: { preferredAspect: "16:9", editablePreference: "preferred", includeNotes: false, rendererFallback: "legacy" },
    compatibility: { sourceVersion: "canonical-v1", requiresLegacyRenderer: false, warnings: [], unsupportedFeatures: [] },
  };
}

function uuid(value: number) {
  return `40000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
}
