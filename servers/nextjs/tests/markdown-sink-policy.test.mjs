import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const rendererPaths = [
  "../components/MarkDownRender.tsx",
  "../app/(presentation-generator)/documents-preview/components/MarkdownRenderer.tsx",
  "../app/(presentation-generator)/components/MarkdownInlineText.tsx",
  "../app/(presentation-generator)/outline/components/OutlineItem.tsx",
];

test("every Markdown HTML sink imports the centralized safe policy", async () => {
  for (const relativePath of rendererPaths) {
    const source = await readFile(new URL(relativePath, import.meta.url), "utf8");
    assert.match(source, /@\/lib\/safe-markdown/, relativePath);
    assert.doesNotMatch(source, /from ["']marked["']/, relativePath);
  }
});

test("non-Markdown chart styles no longer use an HTML insertion sink", async () => {
  const source = await readFile(
    new URL("../components/ui/chart.tsx", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(source, /dangerouslySetInnerHTML/);
  assert.match(source, /safeCssIdentifier/);
  assert.match(source, /safeCssColor/);
});

test("the generated slide HTML sink documents and tests its trust boundary", async () => {
  const [component, renderer, tests] = await Promise.all([
    readFile(
      new URL(
        "../app/(presentation-generator)/components/TemplateV2HtmlSlidePreview.tsx",
        import.meta.url,
      ),
      "utf8",
    ),
    readFile(
      new URL("../lib/template-v2-json-to-html.ts", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("./template-v2-json-to-html.test.mjs", import.meta.url),
      "utf8",
    ),
  ]);
  assert.match(component, /Security boundary/);
  assert.match(component, /templateV2UiToHtmlFragment/);
  assert.match(renderer, /parseEmbeddedFontFaces/);
  assert.match(renderer, /normalizeFontResource/);
  assert.match(renderer, /encodeURIComponent\(svg\)/);
  assert.match(renderer, /normalizeTemplateFontResource/);
  assert.match(tests, /escapes hostile presentation fields/);
});
