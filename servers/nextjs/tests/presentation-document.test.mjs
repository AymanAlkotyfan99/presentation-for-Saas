import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { build } from "esbuild";

const nextRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(nextRoot, "../..");
const fixtureRoot = path.join(repositoryRoot, "schemas/presentation-document/fixtures");
const manifest = JSON.parse(await readFile(path.join(fixtureRoot, "manifest.json"), "utf8"));
const temporary = await mkdtemp(path.join(os.tmpdir(), "bayanly-canonical-"));
const outfile = path.join(temporary, "presentation-document.mjs");
await build({
  absWorkingDir: nextRoot,
  bundle: true,
  entryPoints: ["./lib/presentation-document/validate.ts"],
  format: "esm",
  outfile,
  platform: "node",
  tsconfig: path.join(nextRoot, "tsconfig.json"),
});
const validator = await import(pathToFileURL(outfile).href);

async function fixture(folder, name) {
  return JSON.parse(await readFile(path.join(fixtureRoot, folder, name), "utf8"));
}

test("TypeScript accepts every shared golden fixture and matches Python SHA-256", async () => {
  for (const [name, expected] of Object.entries(manifest.valid)) {
    const source = await fixture("valid", name);
    const result = validator.validatePresentationDocument(source);
    assert.equal(result.ok, true, name);
    assert.equal(await validator.canonicalChecksum(result.document), expected.checksum, name);
    assert.equal(validator.canonicalJson(result.document), validator.canonicalJson(JSON.parse(validator.canonicalJson(result.document))), name);
  }
});

test("TypeScript rejects shared hostile fixtures with the same stable codes", async () => {
  for (const [name, expected] of Object.entries(manifest.invalid)) {
    const result = validator.validatePresentationDocument(await fixture("invalid", name));
    assert.equal(result.ok, false, name);
    assert.equal(result.issues[0].code, expected.expectedCode, name);
  }
});

test("schema/runtime reject unknown fields, invalid geometry, direction and duplicate IDs", async () => {
  const minimal = await fixture("valid", "minimal-en.json");
  const cases = [
    { ...structuredClone(minimal), executableJavascript: "alert(1)" },
    Object.assign(structuredClone(minimal), { baseDirection: "left" }),
    (() => { const value = structuredClone(minimal); value.slides[0].elements = [{ id: value.slides[0].id, type: "shape", geometry: { x: 0, y: 0, width: -1, height: 20 }, zOrder: 0, shapeKind: "rectangle" }]; return value; })(),
    (() => { const value = structuredClone(minimal); value.assets = [{ assetId: value.slides[0].id, kind: "image", mimeType: "image/png", sourceType: "uploaded", role: "content" }]; return value; })(),
  ];
  for (const value of cases) assert.equal(validator.validatePresentationDocument(value).ok, false);
});

test("bounded parser rejects excessive bytes and arbitrary authoring HTML", async () => {
  const minimal = await fixture("valid", "minimal-en.json");
  const excessive = structuredClone(minimal);
  excessive.metadata.description = "x".repeat(5 * 1024 * 1024);
  assert.equal(validator.validatePresentationDocument(excessive).issues[0].code, "CANONICAL_DOCUMENT_TOO_LARGE");
  const html = structuredClone(minimal);
  html.title = "<b>authoring HTML</b>";
  assert.equal(validator.validatePresentationDocument(html).issues[0].code, "CANONICAL_EXECUTABLE_CONTENT");
  const localPath = structuredClone(minimal);
  localPath.metadata.description = "file at C:\\private\\deck.json";
  assert.equal(validator.validatePresentationDocument(localPath).issues[0].code, "CANONICAL_LOCAL_PATH_FORBIDDEN");
  const dataUrl = structuredClone(minimal);
  dataUrl.metadata.description = "data:image/svg+xml;base64,PHN2Zz4=";
  assert.equal(validator.validatePresentationDocument(dataUrl).issues[0].code, "CANONICAL_EXECUTABLE_CONTENT");
});

test("normalization drops optional nulls to match Python exclude-none checksums", async () => {
  const minimal = await fixture("valid", "minimal-en.json");
  const explicitNull = structuredClone(minimal);
  explicitNull.metadata.description = null;
  assert.equal(validator.validatePresentationDocument(explicitNull).ok, true);
  assert.equal(validator.canonicalJson(explicitNull), validator.canonicalJson(minimal));
});
