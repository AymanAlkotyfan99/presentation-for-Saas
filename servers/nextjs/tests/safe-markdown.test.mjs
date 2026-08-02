import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { build } from "esbuild";

const projectRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const tempDirectory = await mkdtemp(path.join(os.tmpdir(), "safe-markdown-"));
const outfile = path.join(tempDirectory, "safe-markdown.mjs");
await build({
  absWorkingDir: projectRoot,
  bundle: true,
  entryPoints: ["lib/safe-markdown.ts"],
  format: "esm",
  outfile,
  platform: "node",
  tsconfig: path.join(projectRoot, "tsconfig.json"),
});

const {
  renderSafeInlineMarkdown,
  renderSafeMarkdown,
  sanitizeMarkdownUrl,
} = await import(pathToFileURL(outfile).href);

test("safe Markdown preserves supported formatting", () => {
  const html = renderSafeMarkdown(
    "## Heading\n\n- **bold**\n- [docs](https://example.com/path?q=1)"
  );

  assert.match(html, /<h2>Heading<\/h2>/);
  assert.match(html, /<strong>bold<\/strong>/);
  assert.match(html, /href="https:\/\/example\.com\/path\?q=1"/);
  assert.match(html, /rel="nofollow noopener noreferrer"/);
});

test("raw HTML and event handlers are rendered inert", () => {
  const html = renderSafeMarkdown(
    '<script>alert(1)</script><img src=x onerror="alert(2)"><svg onload=alert(3)>'
  );

  assert.doesNotMatch(html, /<script[\s>]/i);
  assert.doesNotMatch(html, /<img[\s>]/i);
  assert.doesNotMatch(html, /<svg[\s>]/i);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /&lt;img/);
});

test("unsafe link schemes and encoded variants lose their navigation", () => {
  for (const url of [
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    "java%73cript:alert(1)",
    "java%0ascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
  ]) {
    const html = renderSafeInlineMarkdown(`[open](${url})`);
    assert.doesNotMatch(html, /<a\b/i, url);
    assert.doesNotMatch(html, /href=/i, url);
    assert.match(html, /open/, url);
  }
});

test("unsafe image schemes cannot create resources", () => {
  for (const url of [
    "javascript:alert(1)",
    "data:image/svg+xml,<svg onload=alert(1)>",
    "file:///secret",
    "//tracking.example/pixel.gif",
  ]) {
    const html = renderSafeInlineMarkdown(`![preview](${url})`);
    assert.doesNotMatch(html, /<img\b/i, url);
    assert.doesNotMatch(html, /src=/i, url);
    assert.match(html, /preview/, url);
  }
});

test("safe URL policy is explicit for links and images", () => {
  assert.equal(sanitizeMarkdownUrl("https://example.com/a", "image"), "https://example.com/a");
  assert.equal(sanitizeMarkdownUrl("/app_data/image.png", "image"), "/app_data/image.png");
  assert.equal(sanitizeMarkdownUrl("mailto:test@example.com", "link"), "mailto:test@example.com");
  assert.equal(sanitizeMarkdownUrl("mailto:test@example.com", "image"), null);
  assert.equal(sanitizeMarkdownUrl("blob:https://example.com/id", "image"), null);
});

test("hostile titles and code-language labels remain attributes or text", () => {
  const link = renderSafeInlineMarkdown(
    '[safe](https://example.com "x&quot; onmouseover=alert(1)")'
  );
  const code = renderSafeMarkdown("```js\" onclick=alert(1)\nconst ok = true;\n```");

  assert.match(link, /<a\b/);
  assert.doesNotMatch(link, /"\s+onmouseover=/i);
  assert.doesNotMatch(code, /onclick=/i);
  assert.match(code, /const ok = true;/);
});

test("mixed Arabic and English Markdown remains readable and formatted", () => {
  const html = renderSafeMarkdown(
    "## تقرير Quarterly\n\n- **النتيجة:** Growth 24%\n- [التفاصيل](https://example.com/report)",
  );

  assert.match(html, /<h2>تقرير Quarterly<\/h2>/);
  assert.match(html, /<strong>النتيجة:<\/strong> Growth 24%/);
  assert.match(html, />التفاصيل<\/a>/);
});

test("persisted outline content cannot restore stored HTML or script links", () => {
  const storedOutline =
    '- مقدمة <img src=x onerror="alert(1)">\n' +
    "  - [Review](javascript:alert(2))";
  const html = renderSafeMarkdown(storedOutline);

  assert.doesNotMatch(html, /<img\b|<a\b|javascript:/i);
  assert.match(html, /&lt;img/);
  assert.match(html, /onerror=&quot;/);
  assert.match(html, /Review/);
});

test("AI-produced nested Markdown and hostile HTML stay inert", () => {
  const html = renderSafeMarkdown(
    "> **AI summary**\n> - <details open ontoggle=alert(1)>\n" +
      ">   <summary>hidden</summary><script>alert(2)</script></details>",
  );

  assert.match(html, /<blockquote>/);
  assert.match(html, /<strong>AI summary<\/strong>/);
  assert.doesNotMatch(html, /<details\b|<summary\b|<script\b/i);
  assert.match(html, /&lt;details/);
  assert.match(html, /ontoggle=alert/);
});
