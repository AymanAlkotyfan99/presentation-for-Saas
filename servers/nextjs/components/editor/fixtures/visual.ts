import type { Element as CanonicalElement, PresentationDocument } from "@/generated/presentation-document";
import { createEditorPerformanceFixture } from "./performance";

export function createCanonicalVisualFixture(): PresentationDocument {
  const document = createEditorPerformanceFixture("10x100");
  const id = (value: number) => `50000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
  const paragraph = (value: number, text: string, direction: "ltr" | "rtl" | "auto" = "ltr") => ({
    id: id(value),
    direction,
    logicalAlignment: "start" as const,
    runs: [{ id: id(value + 1), text, language: direction === "rtl" ? "ar" : "en", fontFamilyRef: "body", fontSize: 20, color: "#111827" }],
  });
  const elements: CanonicalElement[] = [
    { id: id(1), type: "text", geometry: { x: 40, y: 30, width: 500, height: 80 }, zOrder: 0, paragraphs: [paragraph(2, "الإيرادات ARR +24% (Q1)", "auto")] },
    { id: id(4), type: "image", geometry: { x: 880, y: 30, width: 320, height: 160 }, zOrder: 1, assetId: id(90), fit: "cover", crop: { x: 0, y: 0, width: 1, height: 1, focalX: 0.5, focalY: 0.5 }, altText: "Deterministic local fixture" },
    { id: id(5), type: "shape", geometry: { x: 40, y: 140, width: 180, height: 100 }, transform: { rotation: 8 }, style: { fill: "#DBEAFE", stroke: { color: "#2563EB", width: 2 }, shadow: { color: "#111827", blur: 8, offsetX: 2, offsetY: 3, opacity: 0.2 }, cornerRadius: 14 }, zOrder: 2, locked: true, shapeKind: "rounded-rectangle" },
    { id: id(6), type: "line", geometry: { x: 250, y: 150, width: 180, height: 80 }, style: { stroke: { color: "#7C3AED", width: 4, dash: [8, 4] } }, zOrder: 3, points: [{ x: 0, y: 70 }, { x: 180, y: 10 }] },
    { id: id(7), type: "arrow", geometry: { x: 460, y: 150, width: 180, height: 80 }, style: { stroke: { color: "#059669", width: 4 } }, zOrder: 4, points: [{ x: 0, y: 40 }, { x: 180, y: 40 }], head: "end" },
    { id: id(8), type: "vector", geometry: { x: 670, y: 140, width: 140, height: 100 }, style: { fill: "#FDE68A", stroke: { color: "#D97706", width: 2 } }, zOrder: 5, points: [{ x: 10, y: 90 }, { x: 70, y: 10 }, { x: 130, y: 90 }], closed: true },
    { id: id(9), type: "icon", geometry: { x: 830, y: 140, width: 100, height: 100 }, zOrder: 6, iconName: "fixture-star", accessibility: { label: "Fixture icon" } },
    { id: id(10), type: "table", geometry: { x: 40, y: 280, width: 520, height: 180 }, zOrder: 7, headerRows: 1, rows: [
      { cells: [{ background: "#E5E7EB", paragraphs: [paragraph(11, "Metric")] }, { background: "#E5E7EB", paragraphs: [paragraph(13, "القيمة", "rtl")] }] },
      { cells: [{ paragraphs: [paragraph(15, "ARR")] }, { paragraphs: [paragraph(17, "+24%")] }] },
    ] },
    { id: id(19), type: "chart", geometry: { x: 600, y: 280, width: 580, height: 180 }, zOrder: 8, chartId: id(20), chartType: "bar", categoryLabels: ["Q1", "Q2", "Q3"], series: [{ id: id(21), name: "Revenue", values: [12, 18, 24], color: "#2563EB" }], title: "Quarterly revenue" },
    { id: id(22), type: "group", geometry: { x: 40, y: 500, width: 320, height: 140 }, transform: { rotation: -4 }, zOrder: 9, children: [
      { id: id(23), type: "shape", geometry: { x: 10, y: 10, width: 300, height: 120 }, style: { fill: "#ECFDF5", stroke: { color: "#059669", width: 2 } }, zOrder: 0, shapeKind: "rectangle" },
      { id: id(24), type: "text", geometry: { x: 30, y: 40, width: 260, height: 60 }, zOrder: 1, paragraphs: [paragraph(25, "Stable nested group")] },
    ] },
    { id: id(27), type: "container", geometry: { x: 410, y: 500, width: 380, height: 140 }, style: { fill: "#F5F3FF", stroke: { color: "#7C3AED", width: 2 } }, zOrder: 10, layoutIntent: "row", children: [
      { id: id(28), type: "text", geometry: { x: 20, y: 30, width: 340, height: 80 }, zOrder: 0, paragraphs: [paragraph(29, "حاوية عربية + English", "rtl")] },
    ] },
    { id: id(31), type: "shape", geometry: { x: 850, y: 520, width: 260, height: 100 }, zOrder: 11, hidden: true, shapeKind: "ellipse", style: { fill: "#FCA5A5" } },
  ];
  document.slides[0] = { ...document.slides[0], title: "Canonical renderer parity", locale: "ar", direction: "rtl", elements };
  document.assets = [{ assetId: id(90), kind: "image", mimeType: "image/png", sourceType: "template", role: "content", metadata: { width: 640, height: 360, originalName: "fixture.png" } }];
  return document;
}
