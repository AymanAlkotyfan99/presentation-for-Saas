import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { mkdtemp, readFile } from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const nextRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(nextRoot, "../..");
const temporary = await mkdtemp(path.join(repositoryRoot, ".cache/revision-parity-"));
const outfile = path.join(temporary, "commands.mjs");
await build({
  bundle: true,
  stdin: {
    contents: 'export { applyCommandBatch } from "./components/editor/commands/index.ts"; export { canonicalChecksum, canonicalJson } from "./lib/presentation-document/validate.ts";',
    resolveDir: nextRoot,
    loader: "ts",
  },
  format: "esm",
  outfile,
  platform: "node",
  tsconfig: path.join(nextRoot, "tsconfig.json"),
});
const frontend = await import(pathToFileURL(outfile).href);
const minimal = JSON.parse(await readFile(path.join(repositoryRoot, "schemas/presentation-document/fixtures/valid/minimal-en.json"), "utf8"));

function uuid(index) { return `20000000-0000-4000-8000-${index.toString(16).padStart(12, "0")}`; }
function pseudoRandom(seed) { return () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32); }

test("property-style command replay and canonical checksums agree across TypeScript and Python", async () => {
  const random = pseudoRandom(0xBADA55);
  const slideId = minimal.slides[0].id;
  const commands = [];
  for (let index = 1; index <= 12; index += 1) {
    const id = uuid(index);
    commands.push({
      commandId: `parity:add:${index}`, type: "ADD_ELEMENT", targetIds: [id],
      payload: { slideId, element: { id, type: "shape", geometry: { x: 50 + index * 40, y: 50 + index * 20, width: 80, height: 60 }, zOrder: index - 1, shapeKind: "rectangle", style: { fill: "#2563EB" } } },
    });
  }
  for (let index = 0; index < 120; index += 1) {
    const target = uuid(1 + Math.floor(random() * 12));
    const choice = index % 6;
    const base = { commandId: `parity:random:${index}`, targetIds: [target] };
    if (choice === 0) commands.push({ ...base, type: "MOVE_ELEMENTS", payload: { slideId, deltaX: Math.round((random() - 0.5) * 8 * 1e6) / 1e6, deltaY: Math.round((random() - 0.5) * 8 * 1e6) / 1e6 } });
    if (choice === 1) commands.push({ ...base, type: "ROTATE_ELEMENTS", payload: { slideId, rotationById: { [target]: Math.round((random() * 60 - 30) * 1e6) / 1e6 } } });
    if (choice === 2) commands.push({ ...base, type: "UPDATE_STYLE", payload: { slideId, style: { opacity: Math.round((0.25 + random() * 0.75) * 1e6) / 1e6 } } });
    if (choice === 3) commands.push({ ...base, type: "HIDE_ELEMENTS", payload: { slideId } });
    if (choice === 4) commands.push({ ...base, type: "SHOW_ELEMENTS", payload: { slideId } });
    if (choice === 5) commands.push({ ...base, type: "RESIZE_ELEMENTS", payload: { slideId, geometryById: { [target]: { x: 50 + Number.parseInt(target.slice(-2), 16), y: 80 + Number.parseInt(target.slice(-2), 16), width: 40 + Math.round(random() * 100), height: 40 + Math.round(random() * 80) } } } });
  }
  const typescriptDocument = frontend.applyCommandBatch(minimal, commands);
  const candidates = [
    process.env.PYTHON,
    path.join(repositoryRoot, "servers/fastapi/.venv/Scripts/python.exe"),
    path.join(repositoryRoot, "servers/fastapi/.venv/bin/python"),
    "python",
  ].filter(Boolean);
  const python = candidates.find((candidate) => candidate === "python" || existsSync(candidate));
  const run = spawnSync(python, ["scripts/apply_revision_commands.py"], {
    cwd: path.join(repositoryRoot, "servers/fastapi"),
    input: JSON.stringify({ document: minimal, commands }), encoding: "utf8",
    maxBuffer: 10 * 1024 * 1024,
  });
  assert.equal(run.status, 0, run.stderr);
  const backend = JSON.parse(run.stdout);
  assert.equal(backend.canonicalJson, frontend.canonicalJson(typescriptDocument));
  assert.equal(backend.checksum, await frontend.canonicalChecksum(typescriptDocument));
  assert.deepEqual(backend.document, typescriptDocument);
});
