import {
  PRESENTATION_DOCUMENT_SCHEMA,
  type PresentationDocument,
  type TextRun,
} from "@/generated/presentation-document";

export const CANONICAL_LIMITS = Object.freeze({
  maxDocumentBytes: 5 * 1024 * 1024,
  maxTotalElements: 5_000,
  maxGroupDepth: 8,
  maxTotalTextCharacters: 2_000_000,
  maxNotesCharacters: 50_000,
  maxChartPoints: 5_000,
});

export type CanonicalValidationIssue = {
  code: string;
  path: string;
};

export type CanonicalValidationResult =
  | { ok: true; document: PresentationDocument }
  | { ok: false; issues: CanonicalValidationIssue[] };

type JsonObject = { [key: string]: JsonValue };
type JsonValue = null | boolean | number | string | JsonValue[] | JsonObject;
type SchemaNode = { [key: string]: unknown };

const UNSAFE_TEXT = /<\s*\/?[a-z][^>]*>|javascript\s*:|data\s*:[^\s]+|on[a-z]+\s*=/i;
const ABSOLUTE_LOCAL_PATH = /(?:^|[\s"'])(?:[a-z]:[\\/]|file:\/\/|\/(?:home|users|tmp|var|etc|opt)\/)/i;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const PROTOTYPE_KEYS = new Set(["__proto__", "constructor", "prototype"]);

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function schemaObject(value: unknown): SchemaNode | null {
  return isObject(value) ? value : null;
}

function numberKeyword(schema: SchemaNode, key: string): number | undefined {
  const value = schema[key];
  return typeof value === "number" ? value : undefined;
}

function resolveRef(reference: string): SchemaNode | null {
  const name = reference.startsWith("#/$defs/") ? reference.slice(8) : "";
  const definitions = schemaObject(PRESENTATION_DOCUMENT_SCHEMA.$defs);
  return definitions ? schemaObject(definitions[name]) : null;
}

function validateSchema(
  value: unknown,
  schema: SchemaNode,
  path: string,
  issues: CanonicalValidationIssue[],
): void {
  if (typeof schema.$ref === "string") {
    const target = resolveRef(schema.$ref);
    if (!target) issues.push({ code: "CANONICAL_SCHEMA_REFERENCE_INVALID", path });
    else validateSchema(value, target, path, issues);
    return;
  }
  if (Object.hasOwn(schema, "const") && value !== schema.const) {
    issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
    return;
  }
  if (Array.isArray(schema.enum) && !schema.enum.includes(value)) {
    issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
    return;
  }
  for (const keyword of ["oneOf", "anyOf"] as const) {
    const alternatives = schema[keyword];
    if (Array.isArray(alternatives)) {
      const matches = alternatives.filter((candidate) => {
        const candidateIssues: CanonicalValidationIssue[] = [];
        const node = schemaObject(candidate);
        if (node) validateSchema(value, node, path, candidateIssues);
        else candidateIssues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
        return candidateIssues.length === 0;
      }).length;
      if ((keyword === "oneOf" && matches !== 1) || (keyword === "anyOf" && matches === 0)) {
        issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      }
      return;
    }
  }

  if (schema.type === "null") {
    if (value !== null) issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
    return;
  }
  if (schema.type === "boolean") {
    if (typeof value !== "boolean") issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
    return;
  }
  if (schema.type === "number" || schema.type === "integer") {
    if (typeof value !== "number" || !Number.isFinite(value) || (schema.type === "integer" && !Number.isInteger(value))) {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      return;
    }
    const minimum = numberKeyword(schema, "minimum");
    const maximum = numberKeyword(schema, "maximum");
    const exclusiveMinimum = numberKeyword(schema, "exclusiveMinimum");
    const multipleOf = numberKeyword(schema, "multipleOf");
    if ((minimum !== undefined && value < minimum) ||
        (maximum !== undefined && value > maximum) ||
        (exclusiveMinimum !== undefined && value <= exclusiveMinimum) ||
        (multipleOf !== undefined && Math.abs(value / multipleOf - Math.round(value / multipleOf)) > 1e-9)) {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
    }
    return;
  }
  if (schema.type === "string") {
    if (typeof value !== "string") {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      return;
    }
    const minLength = numberKeyword(schema, "minLength");
    const maxLength = numberKeyword(schema, "maxLength");
    if ((minLength !== undefined && value.length < minLength) ||
        (maxLength !== undefined && value.length > maxLength) ||
        (typeof schema.pattern === "string" && !new RegExp(schema.pattern, "u").test(value)) ||
        (schema.format === "uuid" && !UUID.test(value))) {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      return;
    }
    if (schema.format === "uri") {
      try { new URL(value); } catch { issues.push({ code: "CANONICAL_SCHEMA_INVALID", path }); }
    }
    return;
  }
  if (schema.type === "array") {
    if (!Array.isArray(value)) {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      return;
    }
    const minItems = numberKeyword(schema, "minItems");
    const maxItems = numberKeyword(schema, "maxItems");
    if ((minItems !== undefined && value.length < minItems) || (maxItems !== undefined && value.length > maxItems)) {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      return;
    }
    const itemSchema = schemaObject(schema.items);
    if (itemSchema) value.forEach((item, index) => validateSchema(item, itemSchema, `${path}[${index}]`, issues));
    return;
  }
  if (schema.type === "object") {
    if (!isObject(value)) {
      issues.push({ code: "CANONICAL_SCHEMA_INVALID", path });
      return;
    }
    const properties = schemaObject(schema.properties) ?? {};
    const required = Array.isArray(schema.required) ? new Set(schema.required.filter((name): name is string => typeof name === "string")) : new Set<string>();
    for (const name of required) {
      if (!Object.hasOwn(value, name)) issues.push({ code: "CANONICAL_SCHEMA_INVALID", path: `${path}.${name}` });
    }
    for (const [name, child] of Object.entries(value)) {
      const childSchema = schemaObject(properties[name]);
      if (!childSchema) {
        if (schema.additionalProperties === false) issues.push({ code: "CANONICAL_UNKNOWN_FIELD", path: `${path}.${name}` });
      } else {
        validateSchema(child, childSchema, `${path}.${name}`, issues);
      }
    }
  }
}

function rawSafetyScan(value: unknown): CanonicalValidationIssue | null {
  let serialized: string;
  try {
    serialized = JSON.stringify(value);
  } catch {
    return { code: "CANONICAL_JSON_INVALID", path: "$" };
  }
  if (serialized === undefined || new TextEncoder().encode(serialized).byteLength > CANONICAL_LIMITS.maxDocumentBytes) {
    return { code: "CANONICAL_DOCUMENT_TOO_LARGE", path: "$" };
  }
  const stack: Array<{ value: unknown; depth: number; path: string }> = [{ value, depth: 0, path: "$" }];
  while (stack.length) {
    const current = stack.pop();
    if (!current) break;
    if (current.depth > 32) return { code: "CANONICAL_NESTING_EXCESSIVE", path: current.path };
    if (typeof current.value === "string" && UNSAFE_TEXT.test(current.value)) {
      return { code: "CANONICAL_EXECUTABLE_CONTENT", path: current.path };
    }
    if (typeof current.value === "string" && ABSOLUTE_LOCAL_PATH.test(current.value)) {
      return { code: "CANONICAL_LOCAL_PATH_FORBIDDEN", path: current.path };
    }
    if (typeof current.value === "number" && !Number.isFinite(current.value)) {
      return { code: "CANONICAL_NONFINITE_NUMBER", path: current.path };
    }
    if (Array.isArray(current.value)) {
      current.value.forEach((child, index) => stack.push({ value: child, depth: current.depth + 1, path: `${current.path}[${index}]` }));
    } else if (isObject(current.value)) {
      for (const [key, child] of Object.entries(current.value)) {
        if (PROTOTYPE_KEYS.has(key)) return { code: "CANONICAL_PROTOTYPE_KEY", path: `${current.path}.${key}` };
        stack.push({ value: child, depth: current.depth + 1, path: `${current.path}.${key}` });
      }
    }
  }
  return null;
}

function isSafeExternalUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    const host = parsed.hostname.replace(/\.$/, "").replace(/^\[|\]$/g, "").toLowerCase();
    if (parsed.protocol !== "https:" || parsed.username || parsed.password || host === "localhost" || host.endsWith(".local")) return false;
    const ipv4 = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/)?.slice(1).map(Number);
    if (ipv4 && ipv4.every((part) => part <= 255)) {
      const [first, second] = ipv4;
      if (
        first === 0 || first === 10 || first === 127 || first >= 224 ||
        (first === 100 && second >= 64 && second <= 127) ||
        (first === 169 && second === 254) ||
        (first === 172 && second >= 16 && second <= 31) ||
        (first === 192 && (second === 0 || second === 168)) ||
        (first === 198 && (second === 18 || second === 19 || second === 51)) ||
        (first === 203 && second === 0)
      ) return false;
    }
    if (
      host === "::" || host === "::1" || host.startsWith("fc") ||
      host.startsWith("fd") || host.startsWith("::ffff:") ||
      /^fe[89ab]/.test(host) || host.startsWith("ff")
    ) return false;
    return true;
  } catch {
    return false;
  }
}

function semanticValidation(document: PresentationDocument): CanonicalValidationIssue | null {
  const seen = new Set<string>();
  const addId = (id: string, path: string): CanonicalValidationIssue | null => {
    if (seen.has(id)) return { code: "CANONICAL_DUPLICATE_ID", path };
    seen.add(id);
    return null;
  };
  let issue = addId(document.documentId, "$.documentId");
  if (issue) return issue;
  const assets = new Set<string>();
  for (let index = 0; index < document.assets.length; index += 1) {
    const id = document.assets[index].assetId;
    issue = addId(id, `$.assets[${index}].assetId`);
    if (issue) return issue;
    assets.add(id);
  }
  const fontIds = new Set(document.fontPolicy.families.map((family) => family.id));
  if (fontIds.size !== document.fontPolicy.families.length) return { code: "CANONICAL_DUPLICATE_FONT_REFERENCE", path: "$.fontPolicy.families" };
  if (document.fontPolicy.defaultBodyRef && !fontIds.has(document.fontPolicy.defaultBodyRef)) return { code: "CANONICAL_FONT_REFERENCE_INVALID", path: "$.fontPolicy.defaultBodyRef" };
  if (document.fontPolicy.defaultHeadingRef && !fontIds.has(document.fontPolicy.defaultHeadingRef)) return { code: "CANONICAL_FONT_REFERENCE_INVALID", path: "$.fontPolicy.defaultHeadingRef" };
  if (document.fontPolicy.families.some((family) => family.assetId && !assets.has(family.assetId))) return { code: "CANONICAL_ASSET_REFERENCE_INVALID", path: "$.fontPolicy.families.assetId" };
  const validateTextRun = (run: TextRun, path: string): CanonicalValidationIssue | null => {
    if (run.fontFamilyRef && !fontIds.has(run.fontFamilyRef)) return { code: "CANONICAL_FONT_REFERENCE_INVALID", path: `${path}.fontFamilyRef` };
    if (run.hyperlink?.kind === "external" && (!run.hyperlink.href || run.hyperlink.assetId || !isSafeExternalUrl(run.hyperlink.href))) return { code: "CANONICAL_URL_UNSAFE", path: `${path}.hyperlink` };
    if (run.hyperlink?.kind === "asset" && (!run.hyperlink.assetId || run.hyperlink.href || !assets.has(run.hyperlink.assetId))) return { code: "CANONICAL_ASSET_REFERENCE_INVALID", path: `${path}.hyperlink` };
    return null;
  };
  const orders = new Set<number>();
  let totalElements = 0;
  let totalText = document.title.length;
  for (let slideIndex = 0; slideIndex < document.slides.length; slideIndex += 1) {
    const slide = document.slides[slideIndex];
    issue = addId(slide.id, `$.slides[${slideIndex}].id`);
    if (issue) return issue;
    if (orders.has(slide.order)) return { code: "CANONICAL_DUPLICATE_SLIDE_ORDER", path: `$.slides[${slideIndex}].order` };
    orders.add(slide.order);
    if (slide.background?.assetId && !assets.has(slide.background.assetId)) return { code: "CANONICAL_ASSET_REFERENCE_INVALID", path: `$.slides[${slideIndex}].background.assetId` };
    if (slide.speakerNotes) {
      issue = addId(slide.speakerNotes.id, `$.slides[${slideIndex}].speakerNotes.id`);
      if (issue) return issue;
      let noteCharacters = 0;
      for (const paragraph of slide.speakerNotes.paragraphs) {
        issue = addId(paragraph.id, `$.slides[${slideIndex}].speakerNotes.paragraphs`);
        if (issue) return issue;
        for (const run of paragraph.runs) {
          issue = addId(run.id, `$.slides[${slideIndex}].speakerNotes.paragraphs.runs`);
          if (issue) return issue;
          noteCharacters += run.text.length;
          issue = validateTextRun(run, `$.slides[${slideIndex}].speakerNotes.paragraphs.runs`);
          if (issue) return issue;
        }
      }
      if (noteCharacters > CANONICAL_LIMITS.maxNotesCharacters) return { code: "CANONICAL_NOTES_TOO_LARGE", path: `$.slides[${slideIndex}].speakerNotes` };
    }
    const stack = slide.elements.map((element) => ({ element, depth: 1 }));
    while (stack.length) {
      const current = stack.pop();
      if (!current) break;
      totalElements += 1;
      if (current.depth > CANONICAL_LIMITS.maxGroupDepth) return { code: "CANONICAL_GROUP_DEPTH_EXCEEDED", path: `$.slides[${slideIndex}].elements` };
      issue = addId(current.element.id, `$.slides[${slideIndex}].elements`);
      if (issue) return issue;
      if (current.element.type === "image" && !assets.has(current.element.assetId)) return { code: "CANONICAL_ASSET_REFERENCE_INVALID", path: `$.slides[${slideIndex}].elements` };
      if (current.element.type === "icon" && !current.element.assetId && !current.element.iconName) return { code: "CANONICAL_ICON_REFERENCE_REQUIRED", path: `$.slides[${slideIndex}].elements` };
      if (current.element.type === "icon" && current.element.assetId && !assets.has(current.element.assetId)) return { code: "CANONICAL_ASSET_REFERENCE_INVALID", path: `$.slides[${slideIndex}].elements` };
      if (current.element.type === "text") {
        for (const paragraph of current.element.paragraphs) {
          issue = addId(paragraph.id, `$.slides[${slideIndex}].elements.paragraphs`);
          if (issue) return issue;
          for (const run of paragraph.runs) {
            issue = addId(run.id, `$.slides[${slideIndex}].elements.paragraphs.runs`);
            if (issue) return issue;
            totalText += run.text.length;
            issue = validateTextRun(run, `$.slides[${slideIndex}].elements.paragraphs.runs`);
            if (issue) return issue;
          }
        }
      }
      if (current.element.type === "table") {
        const width = current.element.rows[0]?.cells.length ?? 0;
        if (current.element.rows.some((row) => row.cells.length !== width)) return { code: "CANONICAL_TABLE_SHAPE_INVALID", path: `$.slides[${slideIndex}].elements.rows` };
        for (const row of current.element.rows) for (const cell of row.cells) for (const paragraph of cell.paragraphs) {
          issue = addId(paragraph.id, `$.slides[${slideIndex}].elements.rows.cells.paragraphs`);
          if (issue) return issue;
          for (const run of paragraph.runs) {
            issue = addId(run.id, `$.slides[${slideIndex}].elements.rows.cells.paragraphs.runs`);
            if (issue) return issue;
            totalText += run.text.length;
            issue = validateTextRun(run, `$.slides[${slideIndex}].elements.rows.cells.paragraphs.runs`);
            if (issue) return issue;
          }
        }
      }
      if (current.element.type === "chart") {
        issue = addId(current.element.chartId, `$.slides[${slideIndex}].elements.chartId`);
        if (issue) return issue;
        let points = 0;
        for (const series of current.element.series) {
          issue = addId(series.id, `$.slides[${slideIndex}].elements.series.id`);
          if (issue) return issue;
          points += series.values.length;
        }
        if (points > CANONICAL_LIMITS.maxChartPoints) return { code: "CANONICAL_CHART_TOO_LARGE", path: `$.slides[${slideIndex}].elements.series` };
      }
      if (current.element.type === "container" || current.element.type === "group") {
        current.element.children.forEach((element) => stack.push({ element, depth: current.depth + 1 }));
      }
    }
  }
  if (totalElements > CANONICAL_LIMITS.maxTotalElements) return { code: "CANONICAL_ELEMENTS_EXCESSIVE", path: "$.slides" };
  if (totalText > CANONICAL_LIMITS.maxTotalTextCharacters) return { code: "CANONICAL_TEXT_EXCESSIVE", path: "$.slides" };
  if (orders.size !== document.slides.length || [...orders].some((order) => order < 0 || order >= document.slides.length)) return { code: "CANONICAL_SLIDE_ORDER_INVALID", path: "$.slides" };
  return null;
}

export function validatePresentationDocument(input: unknown): CanonicalValidationResult {
  const safetyIssue = rawSafetyScan(input);
  if (safetyIssue) return { ok: false, issues: [safetyIssue] };
  // Match Pydantic's `exclude_none=True` boundary before schema validation so
  // explicit nulls on optional object fields normalize to omission in both
  // runtimes. Required nullable values still fail as missing after this step.
  const normalizedInput = normalizedValue(input as JsonValue);
  const issues: CanonicalValidationIssue[] = [];
  validateSchema(normalizedInput, PRESENTATION_DOCUMENT_SCHEMA as unknown as SchemaNode, "$", issues);
  if (issues.length) return { ok: false, issues: issues.slice(0, 50) };
  const document = normalizedInput as PresentationDocument;
  const semanticIssue = semanticValidation(document);
  return semanticIssue ? { ok: false, issues: [semanticIssue] } : { ok: true, document };
}

export function assertPresentationDocument(input: unknown): PresentationDocument {
  const result = validatePresentationDocument(input);
  if (!result.ok) throw new Error(`${result.issues[0]?.code ?? "CANONICAL_SCHEMA_INVALID"}:${result.issues[0]?.path ?? "$"}`);
  return result.document;
}

function normalizedValue(value: JsonValue): JsonValue {
  if (Array.isArray(value)) return value.map(normalizedValue);
  if (isObject(value)) {
    const sorted: JsonObject = {};
    for (const key of Object.keys(value).sort()) {
      if (value[key] !== null) sorted[key] = normalizedValue(value[key]);
    }
    return sorted;
  }
  return value;
}

export function canonicalJson(document: PresentationDocument): string {
  return JSON.stringify(normalizedValue(document as unknown as JsonValue));
}

export async function canonicalChecksum(document: PresentationDocument): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonicalJson(document)));
  return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
}
