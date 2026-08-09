import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const fixtureRoot = path.join(root, "schemas/presentation-document/fixtures");
const validRoot = path.join(fixtureRoot, "valid");
const invalidRoot = path.join(fixtureRoot, "invalid");

const id = (number) => `00000000-0000-4000-8000-${number.toString(16).padStart(12, "0")}`;
const clone = (value) => structuredClone(value);
let nextId = 100;
const freshId = () => id(nextId++);
const normalized = (value) => {
  if (Array.isArray(value)) return value.map(normalized);
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map((key) => [key, normalized(value[key])]));
  return value;
};
const checksum = (value) => createHash("sha256").update(JSON.stringify(normalized(value)), "utf8").digest("hex");
const run = (text, language = "en") => ({ id: freshId(), text, language, fontFamilyRef: language === "ar" ? "arabic-ui" : "body", fontSize: 32, color: "#111827" });
const paragraph = (text, direction = "ltr", language = "en") => ({ id: freshId(), direction, logicalAlignment: "start", runs: [run(text, language)] });
const geometry = (x = 80, y = 80, width = 1120, height = 560) => ({ x, y, width, height, anchor: "top-start" });
const textElement = (text, direction = "ltr", language = "en") => ({
  id: freshId(), type: "text", geometry: geometry(), zOrder: 0,
  paragraphs: [paragraph(text, direction, language)], verticalAlignment: "top", overflow: "shrink",
});
const baseDocument = (documentId = freshId(), presentationId = freshId()) => ({
  schemaVersion: "1.0.0",
  documentId,
  presentationId,
  title: "Quarterly review",
  locale: "en",
  baseDirection: "ltr",
  aspectRatio: { width: 16, height: 9 },
  theme: { themeRef: "bayanly-default", colorTokens: [{ name: "primary", value: "#2563EB" }], defaultBackground: "#FFFFFF" },
  fontPolicy: {
    families: [
      { id: "body", family: "Inter", fallbacks: ["Arial", "sans-serif"] },
      { id: "arabic-ui", family: "Noto Sans Arabic", fallbacks: ["Tahoma", "Arial"] },
    ],
    defaultBodyRef: "body", defaultHeadingRef: "body", allowSystemFallback: true,
  },
  metadata: { authoringIntent: "generated", sourceApplicationVersion: "0.9.3-beta" },
  slides: [{ id: freshId(), order: 0, semanticRole: "title", layoutIntent: "free", elements: [] }],
  assets: [],
  exportHints: { preferredAspect: "16:9", editablePreference: "preferred", includeNotes: false, rendererFallback: "legacy" },
  compatibility: { sourceVersion: "canonical-v1", requiresLegacyRenderer: false, warnings: [], unsupportedFeatures: [] },
});

const valid = {};
valid["minimal-en.json"] = baseDocument();

const arabic = baseDocument();
arabic.title = "مراجعة الأداء الربعي";
arabic.locale = "ar";
arabic.baseDirection = "rtl";
arabic.slides[0].elements = [textElement("ملخص النتائج الرئيسية", "rtl", "ar")];
valid["minimal-ar.json"] = arabic;

const mixed = baseDocument();
mixed.title = "Bayanly — ملخص 2026";
mixed.locale = "ar";
mixed.baseDirection = "auto";
mixed.slides[0].elements = [{
  id: freshId(), type: "text", geometry: geometry(), zOrder: 0,
  paragraphs: [{ id: freshId(), direction: "auto", logicalAlignment: "start", runs: [run("الإيرادات ", "ar"), run("ARR +24%", "en")] }],
}];
valid["mixed-direction.json"] = mixed;

const textHeavy = baseDocument();
textHeavy.slides[0].elements = [{
  id: freshId(), type: "text", geometry: geometry(), zOrder: 0,
  paragraphs: Array.from({ length: 40 }, (_, index) => paragraph(`Evidence-backed paragraph ${index + 1}: deterministic canonical text.`, "ltr", "en")),
}];
valid["text-heavy.json"] = textHeavy;

const image = baseDocument();
const imageAssetId = freshId();
image.assets = [{ assetId: imageAssetId, kind: "image", mimeType: "image/png", sourceType: "uploaded", role: "content", metadata: { width: 1600, height: 900 } }];
image.slides[0].elements = [{ id: freshId(), type: "image", geometry: geometry(), zOrder: 0, assetId: imageAssetId, fit: "cover", crop: { x: 0, y: 0, width: 1, height: 1, focalX: 0.5, focalY: 0.5 }, altText: "Illustrative market chart" }];
valid["image-slide.json"] = image;

const table = baseDocument();
const cell = (text) => ({ paragraphs: [paragraph(text)] });
table.slides[0].elements = [{ id: freshId(), type: "table", geometry: geometry(), zOrder: 0, headerRows: 1, rows: [{ cells: [cell("Metric"), cell("Value")] }, { cells: [cell("ARR"), cell("24%")] }] }];
valid["table-slide.json"] = table;

const chart = baseDocument();
chart.slides[0].elements = [{ id: freshId(), type: "chart", geometry: geometry(), zOrder: 0, chartId: freshId(), chartType: "bar", categoryLabels: ["Q1", "Q2", "Q3"], series: [{ id: freshId(), name: "Revenue", values: [12, 18, 24], color: "#2563EB" }] }];
valid["chart-slide.json"] = chart;

const group = baseDocument();
group.slides[0].elements = [{ id: freshId(), type: "group", geometry: geometry(), zOrder: 0, children: [{ id: freshId(), type: "container", geometry: geometry(0, 0, 600, 300), zOrder: 0, layoutIntent: "row", children: [textElement("Grouped content")] }] }];
valid["group-container-slide.json"] = group;

const notes = baseDocument();
notes.exportHints.includeNotes = true;
notes.slides[0].speakerNotes = { id: freshId(), locale: "en", direction: "ltr", paragraphs: [paragraph("Explain the assumptions without exposing private source material.")] };
valid["speaker-notes.json"] = notes;

const legacyV1 = baseDocument();
legacyV1.compatibility = { sourceVersion: "v1-standard", legacyPresentationVersion: "v1-standard", legacyLayoutRef: "legacy-basic", requiresLegacyRenderer: false, warnings: ["legacy-content-converted"], unsupportedFeatures: [] };
legacyV1.slides[0].compatibility = { legacySlideId: "legacy-slide-1", legacyLayoutGroup: "basic", legacyLayout: "title", requiresLegacyRenderer: false, warnings: [] };
legacyV1.slides[0].elements = [textElement("Converted V1 content")];
valid["legacy-v1-converted.json"] = legacyV1;

const legacyV2 = baseDocument();
legacyV2.compatibility = { sourceVersion: "v2-standard", legacyPresentationVersion: "v2-standard", legacyLayoutRef: "template-v2", requiresLegacyRenderer: false, warnings: [], unsupportedFeatures: [] };
legacyV2.slides[0].layoutIntent = "template";
legacyV2.slides[0].elements = [textElement("Converted V2 UI tree")];
valid["legacy-v2-converted.json"] = legacyV2;

const maximum = baseDocument();
maximum.slides = Array.from({ length: 200 }, (_, order) => ({ id: freshId(), order, layoutIntent: "free", elements: [] }));
maximum.assets = Array.from({ length: 128 }, (_, index) => ({ assetId: freshId(), kind: "image", mimeType: "image/webp", sourceType: "template", role: index === 0 ? "background" : "decoration" }));
valid["maximum-bounded.json"] = maximum;

const invalid = {};
const script = clone(valid["minimal-en.json"]);
script.title = "<script>alert(1)</script>";
invalid["executable-content.json"] = { document: script, expectedCode: "CANONICAL_EXECUTABLE_CONTENT" };

const badUrl = clone(mixed);
badUrl.slides[0].elements[0].paragraphs[0].runs[0].hyperlink = { kind: "external", href: "http://example.com/report" };
invalid["unsafe-url.json"] = { document: badUrl, expectedCode: "CANONICAL_SCHEMA_INVALID" };

const badAsset = clone(image);
badAsset.slides[0].elements[0].assetId = id(999999);
invalid["invalid-asset-reference.json"] = { document: badAsset, expectedCode: "CANONICAL_ASSET_REFERENCE_INVALID" };

const deep = baseDocument();
let children = [textElement("Too deep")];
for (let depth = 0; depth < 9; depth += 1) children = [{ id: freshId(), type: "group", geometry: geometry(), zOrder: 0, children }];
deep.slides[0].elements = children;
invalid["excessive-depth.json"] = { document: deep, expectedCode: "CANONICAL_GROUP_DEPTH_EXCEEDED" };

const manifest = { schemaVersion: "1.0.0", valid: {}, invalid: {} };
await mkdir(validRoot, { recursive: true });
await mkdir(invalidRoot, { recursive: true });
for (const [name, document] of Object.entries(valid)) {
  await writeFile(path.join(validRoot, name), `${JSON.stringify(document, null, 2)}\n`, "utf8");
  manifest.valid[name] = { checksum: checksum(document) };
}
for (const [name, fixture] of Object.entries(invalid)) {
  await writeFile(path.join(invalidRoot, name), `${JSON.stringify(fixture.document, null, 2)}\n`, "utf8");
  manifest.invalid[name] = { expectedCode: fixture.expectedCode };
}
await writeFile(path.join(fixtureRoot, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log(`Generated ${Object.keys(valid).length} valid and ${Object.keys(invalid).length} invalid canonical fixtures.`);
