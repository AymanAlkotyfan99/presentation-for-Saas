import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const nextRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(nextRoot, "../..");
const temporary = await mkdtemp(path.join(os.tmpdir(), "bayanly-editor-commands-"));
const outfile = path.join(temporary, "commands.mjs");
await build({
  absWorkingDir: nextRoot,
  bundle: true,
  entryPoints: [path.join(nextRoot, "components/editor/commands/index.ts")],
  format: "esm",
  outfile,
  platform: "node",
  tsconfig: path.join(nextRoot, "tsconfig.json"),
});
const commands = await import(pathToFileURL(outfile).href);
const minimal = JSON.parse(await readFile(path.join(repositoryRoot, "schemas/presentation-document/fixtures/valid/minimal-en.json"), "utf8"));

const ids = {
  shape1: "10000000-0000-4000-8000-000000000001",
  shape2: "10000000-0000-4000-8000-000000000002",
  shape3: "10000000-0000-4000-8000-000000000003",
  shape4: "10000000-0000-4000-8000-000000000004",
  text: "10000000-0000-4000-8000-000000000005",
  paragraph: "10000000-0000-4000-8000-000000000006",
  run: "10000000-0000-4000-8000-000000000007",
  image: "10000000-0000-4000-8000-000000000008",
  asset1: "10000000-0000-4000-8000-000000000009",
  asset2: "10000000-0000-4000-8000-00000000000a",
  group: "10000000-0000-4000-8000-00000000000b",
  slide2: "10000000-0000-4000-8000-00000000000c",
  slide3: "10000000-0000-4000-8000-00000000000d",
};

function shape(id, x, zOrder) {
  return { id, type: "shape", geometry: { x, y: 30 + x, width: 80, height: 60 }, zOrder, shapeKind: "rectangle", style: { fill: "#2563EB" } };
}

function editorDocument() {
  const document = structuredClone(minimal);
  document.assets = [
    { assetId: ids.asset1, kind: "image", mimeType: "image/png", sourceType: "uploaded", role: "content" },
    { assetId: ids.asset2, kind: "image", mimeType: "image/webp", sourceType: "uploaded", role: "content" },
  ];
  return document;
}

function command(type, targetIds, payload) {
  return { commandId: `test:${type.toLowerCase()}`, type, targetIds, payload };
}

function applyRoundTrip(document, operation) {
  const snapshot = structuredClone(document);
  const result = commands.applyCommand(document, operation);
  assert.deepEqual(document, snapshot, `${operation.type} mutated its input`);
  const inverse = commands.invertCommand(document, operation);
  assert.deepEqual(commands.applyCommand(result, inverse), snapshot, `${operation.type} inverse did not restore input`);
  assert.deepEqual(commands.applyCommand(document, operation), result, `${operation.type} was not deterministic`);
  return result;
}

test("every Sprint 5 editor command is immutable, deterministic, serializable, and reversible", () => {
  let document = editorDocument();
  const slideId = document.slides[0].id;
  const additions = [
    shape(ids.shape1, 10, 0),
    shape(ids.shape2, 140, 1),
    shape(ids.shape3, 300, 2),
    { id: ids.text, type: "text", geometry: { x: 30, y: 300, width: 400, height: 100 }, zOrder: 3, paragraphs: [{ id: ids.paragraph, direction: "ltr", logicalAlignment: "start", runs: [{ id: ids.run, text: "Before", fontFamilyRef: "body" }] }] },
    { id: ids.image, type: "image", geometry: { x: 500, y: 300, width: 180, height: 100 }, zOrder: 4, assetId: ids.asset1, fit: "cover" },
  ];
  for (const element of additions) document = applyRoundTrip(document, command("ADD_ELEMENT", [element.id], { slideId, element }));

  document = applyRoundTrip(document, command("DUPLICATE_ELEMENTS", [ids.shape1], { slideId, copies: [{ sourceId: ids.shape1, element: shape(ids.shape4, 500, 5) }] }));
  document = applyRoundTrip(document, command("UPDATE_ELEMENT", [ids.shape1], { slideId, changes: { geometry: { x: 20, y: 40, width: 80, height: 60 } } }));
  document = applyRoundTrip(document, command("MOVE_ELEMENTS", [ids.shape1, ids.shape2], { slideId, deltaX: 4.25, deltaY: -3.5 }));
  document = applyRoundTrip(document, command("RESIZE_ELEMENTS", [ids.shape1], { slideId, geometryById: { [ids.shape1]: { x: 24.25, y: 36.5, width: 120, height: 90 } } }));
  document = applyRoundTrip(document, command("ROTATE_ELEMENTS", [ids.shape1], { slideId, rotationById: { [ids.shape1]: 17.5 } }));
  document = applyRoundTrip(document, command("UPDATE_STYLE", [ids.shape1], { slideId, style: { opacity: 0.8, fill: "#7C3AED" } }));
  document = applyRoundTrip(document, command("ALIGN_ELEMENTS", [ids.shape1, ids.shape2], { slideId, alignment: "start" }));
  document = applyRoundTrip(document, command("DISTRIBUTE_ELEMENTS", [ids.shape1, ids.shape2, ids.shape3], { slideId, axis: "horizontal" }));
  document = applyRoundTrip(document, command("REORDER_ELEMENTS", [ids.image], { slideId, orderedIds: [ids.image, ids.text, ids.shape4, ids.shape3, ids.shape2, ids.shape1] }));
  const indexed = commands.indexDocumentElements(document);
  const selected = [ids.shape1, ids.shape2].map((id) => indexed.get(id).element);
  const boxes = selected.map((element) => commands.rotatedBoundingBox(element.geometry, element.transform?.rotation));
  const box = commands.unionBoundingBoxes(boxes);
  document = applyRoundTrip(document, command("GROUP_ELEMENTS", [ids.shape1, ids.shape2], { slideId, group: { id: ids.group, type: "group", geometry: { x: box.left, y: box.top, width: box.right - box.left, height: box.bottom - box.top }, zOrder: 0, children: [] } }));
  document = applyRoundTrip(document, command("UNGROUP_ELEMENTS", [ids.group], { slideId }));
  document = applyRoundTrip(document, command("LOCK_ELEMENTS", [ids.shape1], { slideId }));
  document = applyRoundTrip(document, command("UNLOCK_ELEMENTS", [ids.shape1], { slideId }));
  document = applyRoundTrip(document, command("HIDE_ELEMENTS", [ids.shape1], { slideId }));
  document = applyRoundTrip(document, command("SHOW_ELEMENTS", [ids.shape1], { slideId }));
  document = applyRoundTrip(document, command("UPDATE_TEXT", [ids.text], { slideId, paragraphs: [{ id: ids.paragraph, direction: "rtl", logicalAlignment: "start", runs: [{ id: ids.run, text: "العربية ARR 24%", fontFamilyRef: "arabic-ui" }] }] }));
  document = applyRoundTrip(document, command("REPLACE_ASSET", [ids.image], { slideId, assetId: ids.asset2 }));
  document = applyRoundTrip(document, command("DELETE_ELEMENTS", [ids.shape4], { slideId }));

  const slide2 = { id: ids.slide2, order: 1, title: "Second", layoutIntent: "free", elements: [] };
  document = applyRoundTrip(document, command("ADD_SLIDE", [ids.slide2], { slide: slide2 }));
  document = applyRoundTrip(document, command("UPDATE_SLIDE", [ids.slide2], { changes: { direction: "rtl", locale: "ar" } }));
  document = applyRoundTrip(document, command("DUPLICATE_SLIDE", [ids.slide2], { copies: [{ sourceId: ids.slide2, slide: { ...slide2, id: ids.slide3, order: 2, title: "Third" } }] }));
  document = applyRoundTrip(document, command("REORDER_SLIDES", [ids.slide3, ids.slide2, slideId], { orderedSlideIds: [ids.slide3, ids.slide2, slideId] }));
  document = applyRoundTrip(document, command("DELETE_SLIDE", [ids.slide3], {}));
  document = applyRoundTrip(document, command("BATCH", [ids.shape1], { commands: [
    { ...command("MOVE_ELEMENTS", [ids.shape1], { slideId, deltaX: 1, deltaY: 0 }), commandId: "test:batch:move-x" },
    { ...command("MOVE_ELEMENTS", [ids.shape1], { slideId, deltaX: 0, deltaY: 1 }), commandId: "test:batch:move-y" },
  ] }));

  assert.doesNotThrow(() => JSON.stringify(document));
});

test("unknown, locked, duplicate, non-finite, and executable commands fail closed", () => {
  let document = editorDocument();
  const slideId = document.slides[0].id;
  document = commands.applyCommand(document, command("ADD_ELEMENT", [ids.shape1], { slideId, element: shape(ids.shape1, 10, 0) }));
  assert.throws(() => commands.applyCommand(document, command("MOVE_ELEMENTS", [ids.shape2], { slideId, deltaX: 1, deltaY: 1 })), /EDITOR_ELEMENT_NOT_FOUND/);
  const locked = commands.applyCommand(document, command("LOCK_ELEMENTS", [ids.shape1], { slideId }));
  assert.throws(() => commands.applyCommand(locked, command("DELETE_ELEMENTS", [ids.shape1], { slideId })), /EDITOR_ELEMENT_LOCKED/);
  assert.throws(() => commands.applyCommand(document, command("ADD_ELEMENT", [ids.shape1], { slideId, element: shape(ids.shape1, 20, 1) })), /EDITOR_DUPLICATE_ID/);
  assert.throws(() => commands.applyCommand(document, command("MOVE_ELEMENTS", [ids.shape1], { slideId, deltaX: Number.NaN, deltaY: 0 })), /EDITOR_(COMMAND_NOT_SERIALIZABLE|NONFINITE_NUMBER)/);
  const executable = command("UPDATE_ELEMENT", [ids.shape1], { slideId, changes: { style: { fill: "javascript:alert(1)" } } });
  assert.throws(() => commands.applyCommand(document, executable), /EDITOR_COMMAND_RESULT_INVALID/);
  assert.throws(() => commands.applyCommand(document, command("BATCH", [], { commands: [] })), /EDITOR_COMMAND_BATCH_EMPTY/);
  const duplicateId = command("MOVE_ELEMENTS", [ids.shape1], { slideId, deltaX: 1, deltaY: 0 });
  assert.throws(
    () => commands.applyCommand(document, command("BATCH", [ids.shape1], { commands: [duplicateId, duplicateId] })),
    /EDITOR_COMMAND_ID_DUPLICATE/,
  );
});
