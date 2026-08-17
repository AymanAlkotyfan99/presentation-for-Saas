import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { build } from "esbuild";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const tempDirectory = await mkdtemp(path.join(os.tmpdir(), "outline-content-"));
await build({
  absWorkingDir: projectRoot,
  bundle: true,
  entryPoints: {
    outline: "./lib/outline-content.ts",
    markdown: "./lib/safe-markdown.ts",
  },
  format: "esm",
  outdir: tempDirectory,
  platform: "node",
  tsconfig: path.join(projectRoot, "tsconfig.json"),
});

const { normalizeOutlineContent, splitOutlineContent } = await import(
  pathToFileURL(path.join(tempDirectory, "outline.js")).href
);
const { renderSafeMarkdown } = await import(
  pathToFileURL(path.join(tempDirectory, "markdown.js")).href
);

for (const [label, input] of [
  ["br", "Title<br>Body"],
  ["self-closing br", "Title<br/>Body"],
  ["spaced self-closing br", "Title<br />Body"],
]) {
  test(`normalizes ${label} without interpreting HTML`, () => {
    const parts = splitOutlineContent(input);
    assert.equal(parts.normalized, "Title\nBody");
    assert.equal(parts.title, "Title");
    assert.equal(parts.body, "Body");
    assert.doesNotMatch(renderSafeMarkdown(parts.body), /&lt;br|<br/i);
  });
}

test("preserves normal newlines and separates a Markdown heading", () => {
  assert.deepEqual(splitOutlineContent("## Personalized Learning\nAdaptive systems respond."), {
    normalized: "## Personalized Learning\nAdaptive systems respond.",
    title: "Personalized Learning",
    body: "Adaptive systems respond.",
  });
});

test("preserves Arabic and mixed Arabic/English text", () => {
  const arabic = splitOutlineContent("## مستقبل التعليم<br>تعلم مخصص لكل طالب");
  const mixed = splitOutlineContent("## الذكاء الاصطناعي وAI<br />تعليم أكثر مرونة");

  assert.equal(arabic.title, "مستقبل التعليم");
  assert.equal(arabic.body, "تعلم مخصص لكل طالب");
  assert.equal(mixed.title, "الذكاء الاصطناعي وAI");
  assert.equal(mixed.body, "تعليم أكثر مرونة");
});

test("normalization does not turn arbitrary HTML into executable markup", () => {
  const normalized = normalizeOutlineContent(
    "## Safe title<br><img src=x onerror=alert(1)><script>alert(2)</script>"
  );
  const parts = splitOutlineContent(normalized);
  const html = renderSafeMarkdown(parts.body);

  assert.doesNotMatch(html, /<img\b|<script\b/i);
  assert.match(html, /&lt;img/);
  assert.match(html, /&lt;script&gt;/);
});
