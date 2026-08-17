import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { build } from "esbuild";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const tempDirectory = await mkdtemp(path.join(os.tmpdir(), "presentation-prepare-"));
const outfile = path.join(tempDirectory, "presentation-prepare.mjs");
await build({
  absWorkingDir: projectRoot,
  bundle: true,
  entryPoints: ["./lib/presentation-prepare.ts"],
  format: "esm",
  outfile,
  platform: "node",
  tsconfig: path.join(projectRoot, "tsconfig.json"),
});

const { buildPresentationPrepareBody, serializePresentationPrepareBody } =
  await import(pathToFileURL(outfile).href);

test("presentationPrepare serializes the complete ten-slide request contract", () => {
  const input = {
    presentation_id: "2a58af5c-5c39-48d9-ab72-630895e44640",
    layout: "executive",
    title: "How Artificial Intelligence Is Transforming the Future of Education",
    outlines: Array.from({ length: 10 }, (_, index) => ({
      content: `## Slide ${index + 1}<br>Supporting point ${index + 1}`,
    })),
  };

  const serialized = serializePresentationPrepareBody(input);
  const parsed = JSON.parse(serialized);

  assert.equal(parsed.presentation_id, input.presentation_id);
  assert.equal(parsed.layout, "executive");
  assert.equal(parsed.title, input.title);
  assert.equal(parsed.outlines.length, 10);
  assert.equal(parsed.outlines[0].content, "## Slide 1\nSupporting point 1");
  assert.equal(parsed.outlines[9].content, "## Slide 10\nSupporting point 10");
});

test("presentationPrepare does not mutate the editor outlines", () => {
  const input = {
    presentation_id: "presentation-id",
    layout: "dynamic",
    outlines: [{ content: "Title<br/>Body" }],
  };

  const body = buildPresentationPrepareBody(input);

  assert.equal(input.outlines[0].content, "Title<br/>Body");
  assert.equal(body.outlines[0].content, "Title\nBody");
});
