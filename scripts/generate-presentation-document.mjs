import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const schemaPath = path.join(root, "schemas/presentation-document/v1.schema.json");
const typesPath = path.join(root, "servers/nextjs/generated/presentation-document.ts");
const check = process.argv.includes("--check");

const UUID = { type: "string", format: "uuid" };
const safeText = (maxLength, minLength = 0) => ({
  type: "string",
  minLength,
  maxLength,
  pattern: "^(?![\\s\\S]*(?:<\\s*/?[A-Za-z][^>]*>|javascript:|on[a-zA-Z]+\\s*=))[\\s\\S]*$",
});
const nullable = (value) => ({ anyOf: [value, { type: "null" }] });
const arrayOf = (items, maxItems, minItems = 0) => ({
  type: "array",
  items,
  minItems,
  maxItems,
});
const object = (properties, required = Object.keys(properties)) => ({
  type: "object",
  additionalProperties: false,
  properties,
  required,
});
const ref = (name) => ({ $ref: `#/$defs/${name}` });

const elementBase = (type) => ({
  id: UUID,
  type: { const: type },
  geometry: ref("geometry"),
  transform: ref("transform"),
  style: ref("style"),
  accessibility: ref("accessibility"),
  zOrder: { type: "integer", minimum: 0, maximum: 100000 },
  locked: { type: "boolean" },
  hidden: { type: "boolean" },
  compatibility: ref("elementCompatibility"),
});

const element = (type, extra, required = []) => object(
  { ...elementBase(type), ...extra },
  ["id", "type", "geometry", "zOrder", ...required],
);

const defs = {
  locale: { type: "string", enum: ["en", "ar"] },
  direction: { type: "string", enum: ["ltr", "rtl", "auto"] },
  logicalAlignment: { type: "string", enum: ["start", "center", "end", "justify"] },
  color: { type: "string", pattern: "^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$" },
  stableReference: { type: "string", minLength: 1, maxLength: 128, pattern: "^[A-Za-z0-9][A-Za-z0-9._:-]*$" },
  geometry: object({
    x: { type: "number", minimum: -5120, maximum: 5120 },
    y: { type: "number", minimum: -2880, maximum: 2880 },
    width: { type: "number", exclusiveMinimum: 0, maximum: 5120 },
    height: { type: "number", exclusiveMinimum: 0, maximum: 2880 },
    anchor: { type: "string", enum: ["top-start", "top-center", "top-end", "center", "bottom-start", "bottom-center", "bottom-end"] },
  }, ["x", "y", "width", "height"]),
  transform: object({
    rotation: { type: "number", minimum: -360, maximum: 360 },
    flipHorizontal: { type: "boolean" },
    flipVertical: { type: "boolean" },
  }, []),
  stroke: object({
    color: ref("color"),
    width: { type: "number", minimum: 0, maximum: 100 },
    opacity: { type: "number", minimum: 0, maximum: 1 },
    dash: arrayOf({ type: "number", minimum: 0, maximum: 1000 }, 32),
  }, ["color", "width"]),
  shadow: object({
    color: ref("color"),
    blur: { type: "number", minimum: 0, maximum: 500 },
    offsetX: { type: "number", minimum: -1000, maximum: 1000 },
    offsetY: { type: "number", minimum: -1000, maximum: 1000 },
    opacity: { type: "number", minimum: 0, maximum: 1 },
  }, ["color"]),
  style: object({
    opacity: { type: "number", minimum: 0, maximum: 1 },
    fill: ref("color"),
    stroke: ref("stroke"),
    shadow: ref("shadow"),
    cornerRadius: { type: "number", minimum: 0, maximum: 2000 },
  }, []),
  accessibility: object({
    label: safeText(512, 1),
    description: safeText(2048),
    decorative: { type: "boolean" },
  }, []),
  elementCompatibility: object({
    source: { type: "string", enum: ["v1", "v2", "template", "canonical"] },
    legacyId: safeText(128),
    sourceLayoutRef: ref("stableReference"),
    warnings: arrayOf(ref("stableReference"), 64),
  }, []),
  hyperlink: object({
    kind: { type: "string", enum: ["external", "asset"] },
    href: {
      type: "string",
      minLength: 9,
      maxLength: 2048,
      format: "uri",
      pattern: "^https://(?!localhost(?:[:/]|$)|127\\.|10\\.|192\\.168\\.|169\\.254\\.|172\\.(?:1[6-9]|2[0-9]|3[01])\\.)",
    },
    assetId: UUID,
  }, ["kind"]),
  textRun: object({
    id: UUID,
    text: safeText(100000),
    language: safeText(35, 2),
    fontFamilyRef: ref("stableReference"),
    fontWeight: { type: "integer", minimum: 100, maximum: 900, multipleOf: 100 },
    fontStyle: { type: "string", enum: ["normal", "italic"] },
    decorations: arrayOf({ type: "string", enum: ["underline", "line-through"] }, 2),
    fontSize: { type: "number", exclusiveMinimum: 0, maximum: 512 },
    color: ref("color"),
    lineHeight: { type: "number", minimum: 0.5, maximum: 10 },
    letterSpacing: { type: "number", minimum: -100, maximum: 100 },
    hyperlink: ref("hyperlink"),
  }, ["id", "text"]),
  listIntent: object({
    kind: { type: "string", enum: ["bullet", "number"] },
    level: { type: "integer", minimum: 0, maximum: 8 },
    start: { type: "integer", minimum: 1, maximum: 100000 },
  }, ["kind", "level"]),
  paragraph: object({
    id: UUID,
    direction: ref("direction"),
    logicalAlignment: ref("logicalAlignment"),
    list: ref("listIntent"),
    runs: arrayOf(ref("textRun"), 10000, 1),
  }, ["id", "direction", "logicalAlignment", "runs"]),
  crop: object({
    x: { type: "number", minimum: 0, maximum: 1 },
    y: { type: "number", minimum: 0, maximum: 1 },
    width: { type: "number", exclusiveMinimum: 0, maximum: 1 },
    height: { type: "number", exclusiveMinimum: 0, maximum: 1 },
    focalX: { type: "number", minimum: 0, maximum: 1 },
    focalY: { type: "number", minimum: 0, maximum: 1 },
  }, ["x", "y", "width", "height"]),
  point: object({
    x: { type: "number", minimum: -5120, maximum: 5120 },
    y: { type: "number", minimum: -2880, maximum: 2880 },
  }),
  tableCell: object({
    paragraphs: arrayOf(ref("paragraph"), 100, 1),
    columnSpan: { type: "integer", minimum: 1, maximum: 50 },
    rowSpan: { type: "integer", minimum: 1, maximum: 100 },
    background: ref("color"),
  }, ["paragraphs"]),
  tableRow: object({ cells: arrayOf(ref("tableCell"), 50, 1) }),
  chartSeries: object({
    id: UUID,
    name: safeText(512, 1),
    values: arrayOf({ type: "number", minimum: -1000000000000, maximum: 1000000000000 }, 5000, 1),
    color: ref("color"),
  }, ["id", "name", "values"]),
  textElement: element("text", {
    paragraphs: arrayOf(ref("paragraph"), 1000, 1),
    verticalAlignment: { type: "string", enum: ["top", "middle", "bottom"] },
    overflow: { type: "string", enum: ["clip", "ellipsis", "shrink"] },
  }, ["paragraphs"]),
  imageElement: element("image", {
    assetId: UUID,
    fit: { type: "string", enum: ["contain", "cover", "fill"] },
    crop: ref("crop"),
    altText: safeText(2048),
  }, ["assetId", "fit"]),
  shapeElement: element("shape", {
    shapeKind: { type: "string", enum: ["rectangle", "rounded-rectangle", "ellipse", "triangle", "diamond"] },
  }, ["shapeKind"]),
  lineElement: element("line", { points: arrayOf(ref("point"), 1000, 2) }, ["points"]),
  arrowElement: element("arrow", {
    points: arrayOf(ref("point"), 1000, 2),
    head: { type: "string", enum: ["start", "end", "both"] },
  }, ["points", "head"]),
  vectorElement: element("vector", {
    points: arrayOf(ref("point"), 10000, 2),
    closed: { type: "boolean" },
  }, ["points", "closed"]),
  iconElement: element("icon", {
    assetId: UUID,
    iconName: ref("stableReference"),
  }),
  tableElement: element("table", {
    rows: arrayOf(ref("tableRow"), 100, 1),
    headerRows: { type: "integer", minimum: 0, maximum: 100 },
  }, ["rows"]),
  chartElement: element("chart", {
    chartId: UUID,
    chartType: { type: "string", enum: ["area", "bar", "bubble", "donut", "horizontal-bar", "line", "pie", "polar-area", "radar", "scatter", "stacked-bar"] },
    categoryLabels: arrayOf(safeText(512), 5000),
    series: arrayOf(ref("chartSeries"), 100, 1),
    title: safeText(1024),
  }, ["chartId", "chartType", "series"]),
  containerElement: element("container", {
    layoutIntent: { type: "string", enum: ["free", "row", "column", "grid", "stack"] },
    children: arrayOf(ref("element"), 500),
  }, ["layoutIntent", "children"]),
  groupElement: element("group", { children: arrayOf(ref("element"), 500, 1) }, ["children"]),
};

defs.element = {
  oneOf: ["text", "image", "shape", "line", "arrow", "vector", "icon", "table", "chart", "container", "group"]
    .map((name) => ref(`${name}Element`)),
};
defs.speakerNotes = object({
  id: UUID,
  locale: ref("locale"),
  direction: ref("direction"),
  paragraphs: arrayOf(ref("paragraph"), 1000),
}, ["id", "locale", "direction", "paragraphs"]);
defs.slideBackground = object({ color: ref("color"), assetId: UUID }, []);
defs.slideCompatibility = object({
  legacySlideId: safeText(128),
  legacyLayoutGroup: safeText(128),
  legacyLayout: safeText(128),
  requiresLegacyRenderer: { type: "boolean" },
  warnings: arrayOf(ref("stableReference"), 128),
}, []);
defs.slide = object({
  id: UUID,
  order: { type: "integer", minimum: 0, maximum: 199 },
  title: safeText(512),
  semanticRole: { type: "string", enum: ["title", "content", "section", "table-of-contents", "closing", "other"] },
  background: ref("slideBackground"),
  layoutIntent: { type: "string", enum: ["free", "row", "column", "grid", "stack", "template"] },
  elements: arrayOf(ref("element"), 500),
  speakerNotes: ref("speakerNotes"),
  locale: ref("locale"),
  direction: ref("direction"),
  transitionHint: { type: "string", enum: ["none", "fade", "push"] },
  exportCapabilities: arrayOf({ type: "string", enum: ["raster", "pdf", "editable-text", "notes", "requires-fallback"] }, 5, 0),
  compatibility: ref("slideCompatibility"),
}, ["id", "order", "layoutIntent", "elements"]);
defs.assetMetadata = object({
  width: { type: "integer", minimum: 1, maximum: 100000 },
  height: { type: "integer", minimum: 1, maximum: 100000 },
  byteSize: { type: "integer", minimum: 0, maximum: 2000000000 },
  sha256: { type: "string", pattern: "^[a-f0-9]{64}$" },
  originalName: safeText(255),
}, []);
defs.asset = object({
  assetId: UUID,
  kind: { type: "string", enum: ["image", "icon", "font"] },
  mimeType: { type: "string", enum: ["image/png", "image/jpeg", "image/webp", "image/gif", "font/ttf", "font/otf", "font/woff", "font/woff2"] },
  sourceType: { type: "string", enum: ["uploaded", "generated", "stock", "template", "legacy"] },
  role: { type: "string", enum: ["content", "background", "logo", "decoration", "icon", "font"] },
  metadata: ref("assetMetadata"),
}, ["assetId", "kind", "mimeType", "sourceType", "role"]);
defs.themeToken = object({ name: ref("stableReference"), value: ref("color") });
defs.theme = object({
  themeRef: ref("stableReference"),
  revisionRef: ref("stableReference"),
  colorTokens: arrayOf(ref("themeToken"), 128),
  spacingScale: arrayOf({ type: "number", minimum: 0, maximum: 1000 }, 64),
  defaultBackground: ref("color"),
}, ["themeRef", "colorTokens"]);
defs.fontFamily = object({
  id: ref("stableReference"),
  family: safeText(128, 1),
  fallbacks: arrayOf(safeText(128, 1), 16),
  assetId: UUID,
}, ["id", "family", "fallbacks"]);
defs.fontPolicy = object({
  families: arrayOf(ref("fontFamily"), 128),
  defaultBodyRef: ref("stableReference"),
  defaultHeadingRef: ref("stableReference"),
  allowSystemFallback: { type: "boolean" },
}, ["families", "allowSystemFallback"]);
defs.documentMetadata = object({
  description: safeText(4096),
  tags: arrayOf(safeText(128, 1), 100),
  authoringIntent: { type: "string", enum: ["generated", "edited", "imported", "template-derived"] },
  sourceApplicationVersion: safeText(64),
}, []);
defs.exportHints = object({
  preferredAspect: { type: "string", enum: ["16:9", "4:3", "custom"] },
  editablePreference: { type: "string", enum: ["preferred", "not-required", "raster-ok"] },
  accessibilityTitle: safeText(512),
  includeNotes: { type: "boolean" },
  capabilityRequirements: arrayOf({ type: "string", enum: ["mixed-direction", "custom-fonts", "charts", "tables", "transparency", "speaker-notes"] }, 16),
  rendererFallback: { type: "string", enum: ["legacy", "raster", "fail"] },
}, ["preferredAspect", "includeNotes", "rendererFallback"]);
defs.documentCompatibility = object({
  sourceVersion: { type: "string", enum: ["canonical-v1", "v1-standard", "v2-standard", "template-v2"] },
  legacyPresentationVersion: safeText(64),
  legacyLayoutRef: safeText(128),
  requiresLegacyRenderer: { type: "boolean" },
  warnings: arrayOf(ref("stableReference"), 256),
  unsupportedFeatures: arrayOf(ref("stableReference"), 256),
}, ["sourceVersion", "requiresLegacyRenderer", "warnings", "unsupportedFeatures"]);
defs.extension = object({
  namespace: { type: "string", pattern: "^[a-z][a-z0-9.-]{2,127}$" },
  version: { type: "string", pattern: "^[0-9]+\\.[0-9]+$" },
  value: { oneOf: [safeText(2048), { type: "number", minimum: -1000000000000, maximum: 1000000000000 }, { type: "boolean" }] },
});

const schema = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  $id: "https://schemas.bayanly.com/presentation-document/v1.schema.json",
  title: "Bayanly Presentation Document v1",
  description: "Renderer-independent canonical presentation authoring document.",
  type: "object",
  additionalProperties: false,
  properties: {
    schemaVersion: { const: "1.0.0" },
    documentId: UUID,
    presentationId: UUID,
    title: safeText(512, 1),
    locale: ref("locale"),
    baseDirection: ref("direction"),
    aspectRatio: object({
      width: { type: "number", exclusiveMinimum: 0, maximum: 100 },
      height: { type: "number", exclusiveMinimum: 0, maximum: 100 },
    }),
    theme: ref("theme"),
    fontPolicy: ref("fontPolicy"),
    metadata: ref("documentMetadata"),
    slides: arrayOf(ref("slide"), 200, 1),
    assets: arrayOf(ref("asset"), 2000),
    exportHints: ref("exportHints"),
    compatibility: ref("documentCompatibility"),
    extensions: arrayOf(ref("extension"), 64),
  },
  required: ["schemaVersion", "documentId", "presentationId", "title", "locale", "baseDirection", "aspectRatio", "theme", "fontPolicy", "metadata", "slides", "assets", "exportHints", "compatibility"],
  $defs: defs,
};

function pascal(value) {
  return value.replace(/(^|[-_ ])([a-z])/g, (_match, _sep, letter) => letter.toUpperCase());
}

function tsType(node) {
  if (node.$ref) return pascal(node.$ref.split("/").at(-1));
  if (Object.hasOwn(node, "const")) return JSON.stringify(node.const);
  if (node.enum) return node.enum.map((value) => JSON.stringify(value)).join(" | ");
  if (node.oneOf) return node.oneOf.map(tsType).join(" | ");
  if (node.anyOf) return node.anyOf.map(tsType).join(" | ");
  if (node.allOf) return node.allOf.map(tsType).join(" & ");
  if (node.type === "string") return "string";
  if (node.type === "number" || node.type === "integer") return "number";
  if (node.type === "boolean") return "boolean";
  if (node.type === "null") return "null";
  if (node.type === "array") return `Array<${tsType(node.items)}>`;
  if (node.type === "object") {
    const required = new Set(node.required || []);
    const fields = Object.entries(node.properties || {}).map(([name, child]) =>
      `  ${JSON.stringify(name)}${required.has(name) ? "" : "?"}: ${tsType(child)};`,
    );
    return `{\n${fields.join("\n")}\n}`;
  }
  throw new Error(`Unsupported schema node in TypeScript generator: ${JSON.stringify(node)}`);
}

function generateTypes() {
  const lines = [
    "/* This file is generated by scripts/generate-presentation-document.mjs. Do not edit. */",
    "/* Source: schemas/presentation-document/v1.schema.json */",
    "",
  ];
  for (const [name, definition] of Object.entries(defs)) {
    lines.push(`export type ${pascal(name)} = ${tsType(definition)};`, "");
  }
  lines.push(`export type PresentationDocument = ${tsType(schema)};`, "");
  lines.push(
    "export const PRESENTATION_DOCUMENT_SCHEMA = ",
    `${JSON.stringify(schema, null, 2)} as const;`,
    "",
  );
  return `${lines.join("\n")}\n`;
}

const schemaOutput = `${JSON.stringify(schema, null, 2)}\n`;
const typesOutput = generateTypes();

async function emit(target, content) {
  if (check) {
    const current = await readFile(target, "utf8").catch(() => "");
    if (current !== content) throw new Error(`${path.relative(root, target)} is stale; run npm run canonical:generate`);
    return;
  }
  await writeFile(target, content, "utf8");
}

await emit(schemaPath, schemaOutput);
await emit(typesPath, typesOutput);
console.log(check ? "Canonical schema and bindings are current." : "Generated canonical schema and TypeScript bindings.");
