import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const nextRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(nextRoot, "../..");
const temporary = await mkdtemp(path.join(os.tmpdir(), "bayanly-editor-state-"));
await build({
  absWorkingDir: nextRoot,
  bundle: true,
  entryPoints: ["components/editor/history/history.ts", "components/editor/selection/selection.ts", "components/editor/snapping/snapping.ts", "components/editor/viewport/viewport.ts"].map((entry) => path.join(nextRoot, entry)),
  format: "esm",
  outdir: temporary,
  entryNames: "[name]",
  outExtension: { ".js": ".mjs" },
  platform: "node",
  tsconfig: path.join(nextRoot, "tsconfig.json"),
});
const history = await import(pathToFileURL(path.join(temporary, "history.mjs")).href);
const selection = await import(pathToFileURL(path.join(temporary, "selection.mjs")).href);
const snapping = await import(pathToFileURL(path.join(temporary, "snapping.mjs")).href);
const viewport = await import(pathToFileURL(path.join(temporary, "viewport.mjs")).href);
const document = JSON.parse(await readFile(path.join(repositoryRoot, "schemas/presentation-document/fixtures/valid/minimal-en.json"), "utf8"));
const slideId = document.slides[0].id;
const shape = (id, x, y, zOrder, extra = {}) => ({ id, type: "shape", geometry: { x, y, width: 100, height: 60 }, zOrder, shapeKind: "rectangle", ...extra });
const ids = ["20000000-0000-4000-8000-000000000001", "20000000-0000-4000-8000-000000000002", "20000000-0000-4000-8000-000000000003"];
document.slides[0].elements = [shape(ids[0], 20, 20, 0), shape(ids[1], 300, 20, 1), shape(ids[2], 600, 20, 2, { hidden: true })];

function move(id, value) {
  return { commandId: `move:${id}:${value}`, type: "MOVE_ELEMENTS", targetIds: [id], payload: { slideId, deltaX: value, deltaY: 0 } };
}

test("one bounded command history supports undo, redo, and redo invalidation", () => {
  let state = history.createEditorHistory(document, 2);
  state = history.executeEditorCommand(state, move(ids[0], 1));
  state = history.executeEditorCommand(state, move(ids[0], 2));
  state = history.executeEditorCommand(state, move(ids[0], 3));
  assert.equal(state.past.length, 2);
  const after = state.present;
  state = history.undoEditorCommand(state);
  assert.equal(state.future.length, 1);
  state = history.redoEditorCommand(state);
  assert.deepEqual(state.present, after);
  state = history.undoEditorCommand(state);
  state = history.executeEditorCommand(state, move(ids[0], 4));
  assert.equal(state.future.length, 0);
});

test("selection uses stable IDs, filters missing IDs, and excludes hidden canvas elements", () => {
  assert.deepEqual(selection.selectOnly(document, ids[0]).selectedIds, [ids[0]]);
  const toggled = selection.toggleSelection(document, { selectedIds: [ids[0]], anchorId: ids[0] }, ids[1]);
  assert.deepEqual(new Set(toggled.selectedIds), new Set([ids[0], ids[1]]));
  assert.deepEqual(selection.selectAllVisible(document.slides[0]).selectedIds, [ids[0], ids[1]]);
  assert.deepEqual(selection.sanitizeSelection(document, { selectedIds: [ids[0], "missing"], anchorId: "missing" }).selectedIds, [ids[0]]);
  assert.deepEqual(selection.marqueeSelection(document.slides[0], { left: 0, top: 0, right: 500, bottom: 200 }).selectedIds, [ids[0], ids[1]]);
});

test("snapping uses zoom-aware thresholds and sorted candidate lookup", () => {
  const index = snapping.buildSnapIndex(document.slides[0], 1280, 720, new Set([ids[0]]));
  const result = snapping.snapBoundingBox({ left: 638, top: 100, right: 738, bottom: 160 }, index, { zoom: 1, screenThreshold: 6 });
  assert.equal(result.deltaX, 2);
  assert.equal(result.guides[0].kind, "slide-center");
  const precise = snapping.snapBoundingBox({ left: 638, top: 100, right: 738, bottom: 160 }, index, { zoom: 4, screenThreshold: 6 });
  assert.equal(precise.deltaX, 0);
});

test("viewport zoom is bounded, cursor-centered, and never mutates geometry", () => {
  const base = { zoom: 1, offsetX: 0, offsetY: 0, containerWidth: 800, containerHeight: 600 };
  assert.equal(viewport.zoomViewport(base, 99).zoom, 4);
  assert.equal(viewport.zoomViewport(base, 0).zoom, 0.25);
  const centered = viewport.zoomViewport(base, 2, { x: 100, y: 100 });
  assert.deepEqual(centered, { ...base, zoom: 2, offsetX: -100, offsetY: -100 });
  assert.equal(viewport.fitSlideViewport(base, 1280, 720).zoom > 0, true);
});
