import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { performance } from "node:perf_hooks";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const nextRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const temporary = await mkdtemp(path.join(os.tmpdir(), "bayanly-editor-performance-"));
await build({
  absWorkingDir: nextRoot,
  bundle: true,
  entryPoints: ["components/editor/fixtures/performance.ts", "components/editor/history/history.ts", "components/editor/snapping/snapping.ts", "lib/presentation-document/validate.ts"].map((entry) => path.join(nextRoot, entry)),
  format: "esm",
  outdir: temporary,
  entryNames: "[name]",
  outExtension: { ".js": ".mjs" },
  platform: "node",
  tsconfig: path.join(nextRoot, "tsconfig.json"),
});
const fixtures = await import(pathToFileURL(path.join(temporary, "performance.mjs")).href);
const history = await import(pathToFileURL(path.join(temporary, "history.mjs")).href);
const snapping = await import(pathToFileURL(path.join(temporary, "snapping.mjs")).href);
const validator = await import(pathToFileURL(path.join(temporary, "validate.mjs")).href);

const budgets = {
  "10x100": { validate: 200, command: 300, undo: 25, snap: 100 },
  "30x1000": { validate: 600, command: 900, undo: 25, snap: 150 },
  "50x3000": { validate: 1500, command: 2200, undo: 25, snap: 200 },
};

for (const size of Object.keys(budgets)) {
  test(`measured editor core budget ${size}`, () => {
    const memoryBefore = process.memoryUsage().heapUsed;
    const document = fixtures.createEditorPerformanceFixture(size);
    const validation = measure(() => validator.validatePresentationDocument(document));
    assert.equal(validation.value.ok, true);
    const slide = document.slides[0];
    const snap = measure(() => snapping.buildSnapIndex(slide, 1280, 720));
    const target = slide.elements[0];
    let state = history.createEditorHistory(document, 100);
    const operation = { commandId: `performance:${size}`, type: "MOVE_ELEMENTS", targetIds: [target.id], payload: { slideId: slide.id, deltaX: 1, deltaY: 1 } };
    const command = measure(() => history.executeEditorCommand(state, operation));
    state = command.value;
    const undo = measure(() => history.undoEditorCommand(state));
    const memoryMiB = Math.max(0, process.memoryUsage().heapUsed - memoryBefore) / 1024 / 1024;
    const result = { fixture: size, validateMs: round(validation.ms), commandMs: round(command.ms), undoMs: round(undo.ms), snapIndexMs: round(snap.ms), heapGrowthMiB: round(memoryMiB) };
    console.info(`EDITOR_PERF ${JSON.stringify(result)}`);
    assert.ok(validation.ms < budgets[size].validate, `validation ${validation.ms}ms`);
    assert.ok(command.ms < budgets[size].command, `command ${command.ms}ms`);
    assert.ok(undo.ms < budgets[size].undo, `undo ${undo.ms}ms`);
    assert.ok(snap.ms < budgets[size].snap, `snap ${snap.ms}ms`);
    assert.ok(memoryMiB < 200, `heap growth ${memoryMiB} MiB`);
  });
}

function measure(operation) {
  const start = performance.now();
  const value = operation();
  return { value, ms: performance.now() - start };
}

function round(value) {
  return Math.round(value * 100) / 100;
}
