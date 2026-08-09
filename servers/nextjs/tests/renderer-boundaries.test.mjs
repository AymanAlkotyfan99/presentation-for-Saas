import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const nextRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(nextRoot, "../..");
const temporary = await mkdtemp(path.join(os.tmpdir(), "bayanly-renderers-"));
await build({
  absWorkingDir: nextRoot,
  bundle: true,
  entryPoints: [path.join(nextRoot, "renderers/shared/index.ts")],
  format: "esm",
  outfile: path.join(temporary, "shared.mjs"),
  platform: "node",
  tsconfig: path.join(nextRoot, "tsconfig.json"),
});
await build({
  absWorkingDir: nextRoot,
  bundle: true,
  entryPoints: [path.join(nextRoot, "tests/browser-render-harness.tsx")],
  format: "cjs",
  outfile: path.join(temporary, "browser-render-harness.cjs"),
  platform: "node",
  tsconfig: path.join(nextRoot, "tsconfig.json"),
});
const shared = await import(pathToFileURL(path.join(temporary, "shared.mjs")).href);
const browser = await import(pathToFileURL(path.join(temporary, "browser-render-harness.cjs")).href);

async function fixture(folder, name) {
  return JSON.parse(await readFile(path.join(repositoryRoot, "schemas/presentation-document/fixtures", folder, name), "utf8"));
}

test("renderer registries and capability manifests are exhaustive", () => {
  const expected = [...shared.CANONICAL_ELEMENT_TYPES].sort();
  assert.deepEqual(browser.browserRendererTypes.sort(), expected);
  for (const manifest of Object.values(shared.RENDERER_CAPABILITIES)) {
    for (const type of expected) assert.ok(manifest.features[type], `${manifest.renderer}:${type}`);
  }
  assert.equal(shared.KONVA_CAPABILITIES.features.gradients, "UNSUPPORTED");
  assert.equal(shared.EXPORT_COMPATIBILITY_CAPABILITIES.features.chart, "RASTERIZED");
  const platform = shared.assetFontCapabilities([{ id: "verified-arabic", scripts: ["arabic", "latin"] }], shared.CANONICAL_ELEMENT_TYPES);
  assert.deepEqual(platform.fontScriptCoverage["verified-arabic"], ["arabic", "latin"]);
});

test("canonical browser renderer emits safe Arabic/mixed-bidi markup without arbitrary HTML", async () => {
  const document = await fixture("valid", "mixed-direction.json");
  const markup = browser.renderCanonicalBrowser(document, document.slides[0].id);
  assert.match(markup, /data-renderer="browser"/);
  assert.match(markup, /dir="rtl"/);
  assert.doesNotMatch(markup, /dangerouslySetInnerHTML|<script|javascript:/i);
  assert.match(markup, /ARR \+24%/);
});

test("deterministic visual parity fixture covers the complete canonical element registry", () => {
  const document = browser.createCanonicalVisualFixture();
  const markup = browser.renderCanonicalBrowser(document, document.slides[0].id);
  assert.doesNotMatch(markup, /Invalid canonical document/);
  for (const type of shared.CANONICAL_ELEMENT_TYPES) {
    if (type === "shape") continue;
    assert.match(markup, new RegExp(`data-canonical-element-type="${type}"`), type);
  }
  assert.equal((markup.match(/data-canonical-element-type="shape"/g) ?? []).length, 2, "hidden shape is retained but not rendered");
});

test("invalid canonical inputs fail visibly at the browser renderer boundary", async () => {
  const malicious = await fixture("invalid", "executable-content.json");
  const markup = browser.renderCanonicalBrowser(malicious, malicious.slides[0]?.id ?? "missing");
  assert.match(markup, /Invalid canonical document/);
  assert.doesNotMatch(markup, /<script|onerror=|javascript:/i);
});

test("asset resolver requires document scope and rejects unsafe, expired, and local URLs", async () => {
  const document = await fixture("valid", "image-slide.json");
  const assetId = document.assets[0].assetId;
  const context = { presentationId: document.presentationId, sessionScope: "test-session" };
  const ready = new shared.CanonicalAssetResolver(async () => ({ url: `/api/assets/${assetId}`, expiresAt: Date.now() + 10_000 }));
  assert.equal((await ready.resolve(document, assetId, context)).status, "ready");
  assert.equal((await ready.resolve(document, assetId, { presentationId: "wrong" })).reason, "unauthorized");
  const collidingDocument = structuredClone(document);
  collidingDocument.presentationId = "10000000-0000-4000-8000-000000000099";
  let scopedCalls = 0;
  const scoped = new shared.CanonicalAssetResolver(async (_asset, authorization) => ({
    url: `/api/assets/${authorization.presentationId}/${++scopedCalls}`,
  }));
  const firstScope = await scoped.resolve(document, assetId, context);
  const secondScope = await scoped.resolve(collidingDocument, assetId, {
    presentationId: collidingDocument.presentationId,
    sessionScope: "other-session",
  });
  assert.equal(scopedCalls, 2, "asset URLs must not be reused across presentation/session scopes");
  assert.notEqual(firstScope.status === "ready" && firstScope.url, secondScope.status === "ready" && secondScope.url);
  for (const url of ["file:///private/image.png", "javascript:alert(1)", "data:image/svg+xml,x", "http://localhost/private"]) {
    const resolver = new shared.CanonicalAssetResolver(async () => ({ url }));
    assert.equal((await resolver.resolve(document, assetId, context)).reason, "unsafe-url", url);
  }
  assert.equal(shared.isSafeScopedAssetUrl("blob:https://app.bayanly.test/00000000-0000-4000-8000-000000000001"), true);
  const expired = new shared.CanonicalAssetResolver(async () => ({ url: "/api/assets/scoped", expiresAt: 1 }), () => 2);
  assert.equal((await expired.resolve(document, assetId, context)).reason, "expired");
});

test("browser images reject a direct unsafe URL even if a caller bypasses the resolver", async () => {
  const document = await fixture("valid", "image-slide.json");
  const assetId = document.assets[0].assetId;
  const markup = browser.renderCanonicalBrowser(document, document.slides[0].id, { [assetId]: "file:///private/secret.png" });
  assert.doesNotMatch(markup, /file:\/\/|<img/i);
  assert.match(markup, /Unavailable image/);
});

test("canonical renderer and editor source contains no executable document path", async () => {
  const roots = [path.join(nextRoot, "renderers"), path.join(nextRoot, "components/editor")];
  const files = [];
  for (const root of roots) await walk(root, files);
  const source = (await Promise.all(files.map((file) => readFile(file, "utf8")))).join("\n");
  assert.doesNotMatch(source, /\b(?:eval|Function)\s*\(/);
  assert.doesNotMatch(source, /dangerouslySetInnerHTML/);
  assert.doesNotMatch(source, /file:\/\//i);
});

async function walk(directory, output) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) await walk(full, output);
    else if (/\.[cm]?[jt]sx?$/.test(entry.name)) output.push(full);
  }
}
