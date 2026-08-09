import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const nextRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(nextRoot, "../..");
const temporary = await mkdtemp(path.join(os.tmpdir(), "bayanly-rtl-editor-"));
await build({
  absWorkingDir: nextRoot,
  bundle: true,
  entryPoints: ["renderers/shared/direction.ts", "renderers/shared/feature-flags.ts", "components/editor/clipboard/clipboard.ts", "components/editor/shortcuts/shortcuts.ts"].map((entry) => path.join(nextRoot, entry)),
  format: "esm",
  outdir: temporary,
  entryNames: "[name]",
  outExtension: { ".js": ".mjs" },
  platform: "node",
  tsconfig: path.join(nextRoot, "tsconfig.json"),
});
const direction = await import(pathToFileURL(path.join(temporary, "direction.mjs")).href);
const flags = await import(pathToFileURL(path.join(temporary, "feature-flags.mjs")).href);
const clipboard = await import(pathToFileURL(path.join(temporary, "clipboard.mjs")).href);
const shortcuts = await import(pathToFileURL(path.join(temporary, "shortcuts.mjs")).href);

test("direction utilities preserve logical text order and map only logical alignment", () => {
  const paragraph = { id: "p", direction: "auto", logicalAlignment: "start", runs: [{ id: "r1", text: "الإيرادات " }, { id: "r2", text: "ARR +24% (Q1) user@example.com https://example.com" }] };
  assert.equal(direction.resolveParagraphDirection(paragraph, "ar"), "rtl");
  assert.equal(direction.textFromParagraph(paragraph), "الإيرادات ARR +24% (Q1) user@example.com https://example.com");
  assert.equal(direction.logicalAlignmentToPhysical("start", "rtl"), "right");
  assert.equal(direction.logicalAlignmentToPhysical("end", "rtl"), "left");
  assert.equal(direction.logicalAlignmentToPhysical("start", "ltr"), "left");
});

test("canonical clipboard is versioned, regenerates nested stable IDs, and rejects unauthorized assets", async () => {
  const document = JSON.parse(await readFile(path.join(repositoryRoot, "schemas/presentation-document/fixtures/valid/group-container-slide.json"), "utf8"));
  const selected = [document.slides[0].elements[0].id];
  const raw = clipboard.serializeCanonicalClipboard(clipboard.canonicalClipboardFragment(document, selected));
  let value = 900;
  const idFactory = () => `30000000-0000-4000-8000-${String(value++).padStart(12, "0")}`;
  const result = clipboard.pasteCanonicalClipboard(raw, document, document.slides[0].id, idFactory, () => `paste:${value++}`);
  assert.equal(result.ok, true);
  assert.notEqual(result.targetIds[0], selected[0]);
  assert.doesNotThrow(() => JSON.stringify(result.commands));

  const image = JSON.parse(await readFile(path.join(repositoryRoot, "schemas/presentation-document/fixtures/valid/image-slide.json"), "utf8"));
  const imageRaw = clipboard.serializeCanonicalClipboard(clipboard.canonicalClipboardFragment(image, [image.slides[0].elements[0].id]));
  image.assets = [];
  assert.equal(clipboard.pasteCanonicalClipboard(imageRaw, image, image.slides[0].id, idFactory, () => "paste:asset").reason, "unauthorized-asset");
});

test("safe rollout defaults canonical renderers off and legacy fallback on", () => {
  assert.deepEqual(flags.rendererFeatureFlags({}), {
    canonicalKonvaRenderer: false,
    canonicalBrowserRenderer: false,
    unifiedEditorCommands: false,
    legacyRendererFallback: true,
  });
  assert.equal(flags.rendererFeatureFlags({ CANONICAL_KONVA_RENDERER_ENABLED: "true" }).canonicalKonvaRenderer, true);
});

test("central shortcuts cover platform redo, editing guards, selection, deletion, and zoom", () => {
  const key = (key, extra = {}) => shortcuts.editorShortcut({ key, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, target: null, ...extra });
  assert.equal(key("z", { metaKey: true }), "undo");
  assert.equal(key("Z", { metaKey: true, shiftKey: true }), "redo");
  assert.equal(key("y", { ctrlKey: true }), "redo");
  assert.equal(key("a", { ctrlKey: true }), "select-all");
  assert.equal(key("Backspace"), "delete");
  assert.equal(key("0", { ctrlKey: true }), "zoom-reset");
  assert.equal(shortcuts.nudgeDistance(true), 10);
});
