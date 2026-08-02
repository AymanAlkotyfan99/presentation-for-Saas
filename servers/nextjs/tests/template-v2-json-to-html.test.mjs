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

async function importRenderer() {
  const tempDirectory = await mkdtemp(path.join(os.tmpdir(), "template-v2-html-"));
  const outfile = path.join(tempDirectory, "template-v2-json-to-html.mjs");
  await build({
    absWorkingDir: projectRoot,
    bundle: true,
    entryPoints: ["lib/template-v2-json-to-html.ts"],
    format: "esm",
    outfile,
    platform: "node",
    tsconfig: path.join(projectRoot, "tsconfig.json"),
  });
  return import(pathToFileURL(outfile).href);
}

test("renders template v2 text run underlines in generated HTML", async () => {
  const { templateV2UiToHtml } = await importRenderer();

  const html = templateV2UiToHtml({
    elements: [
      {
        type: "text",
        position: { x: 0, y: 0 },
        size: { width: 300, height: 80 },
        font: {
          family: "Arial",
          size: 24,
          color: "#111827",
          underline: true,
        },
        runs: [
          { text: "Under", font: { underline: true } },
          { text: "Plain", font: { underline: false } },
        ],
      },
    ],
  });

  assert.ok(html);
  assert.match(
    html,
    /<span style="[^"]*text-decoration:underline;[^"]*">Under\s*<\/span>/,
  );
  assert.match(
    html,
    /<span style="[^"]*text-decoration:none;[^"]*">Plain<\/span>/,
  );
  assert.doesNotMatch(
    html,
    /display:flex;[^"]*text-decoration:underline;/,
    "text wrappers should not force underline onto child runs",
  );
});

test("renders legacy text-decoration underline fields", async () => {
  const { templateV2UiToHtml } = await importRenderer();

  const html = templateV2UiToHtml({
    elements: [
      {
        type: "text",
        position: { x: 0, y: 0 },
        size: { width: 300, height: 80 },
        font: { family: "Arial", size: 24, color: "#111827" },
        runs: [{ text: "Legacy", font: { text_decoration: "underline" } }],
      },
    ],
  });

  assert.ok(html);
  assert.match(
    html,
    /<span style="[^"]*text-decoration:underline;[^"]*">Legacy<\/span>/,
  );
});

test("generated slide HTML escapes hostile presentation fields", async () => {
  const { templateV2UiToHtml } = await importRenderer();

  const html = templateV2UiToHtml(
    {
      background: "#fff;}body{display:none",
      elements: [
        {
          type: "text",
          position: { x: 0, y: 0 },
          size: { width: 300, height: 80 },
          font: {
            family: 'Arial" onmouseover="alert(1)</style><script>alert(1)</script>',
            size: 24,
            color: "red;}body{display:none",
          },
          text: '</div><script>alert(2)</script><img src=x onerror="alert(3)">',
        },
        {
          type: "svg",
          position: { x: 0, y: 100 },
          size: { width: 100, height: 100 },
          svg: '<svg onload="alert(6)"><script>alert(7)</script></svg>',
        },
      ],
    },
    {
      fonts: {
        css: "body{display:none}@import url(https://evil.example/x.css);@font-face{font-family:Safe;src:url('/static/safe.woff2')}",
        fonts: [
          "https://evil.example/tracking.css",
          {
            family: 'Unsafe" Font</STYLE><img src=x onerror="alert(4)">',
            url: 'https://example.com/font.woff2");}</STYLE><img src=x onerror="alert(5)">',
          },
        ],
      },
    },
  );

  assert.ok(html);
  assert.doesNotMatch(html, /<script>alert\(/i);
  assert.doesNotMatch(html, /<img src=x/i);
  assert.doesNotMatch(html, /<svg\b/i);
  assert.doesNotMatch(html, /<\/style><script/i);
  assert.doesNotMatch(html, /"\s+onmouseover=/i);
  assert.doesNotMatch(html, /@import/i);
  assert.doesNotMatch(html, /evil\.example\/tracking\.css/i);
  assert.doesNotMatch(html, /body\{display:none/i);
  assert.match(html, /&lt;script&gt;alert\(2\)&lt;\/script&gt;/i);
  assert.match(html, /data:image\/svg\+xml;charset=utf-8,%3Csvg/i);
  assert.match(html, /@font-face\{font-family:'Safe'/i);
});

test("template font assets are parsed and rebuilt under the centralized URL policy", async () => {
  const { templateV2UiToHtml } = await importRenderer();

  const html = templateV2UiToHtml(
    {
      elements: [
        {
          type: "text",
          position: { x: 0, y: 0 },
          size: { width: 300, height: 80 },
          font: { family: "Safe Bold", size: 24 },
          text: "Font policy",
        },
      ],
    },
    {
      fonts: {
        css: [
          "body{display:none}",
          "@import url('https://evil.example/import.css')",
          "@font-face{font-family:'Safe Bold';src:url('/static/fonts/safe-bold.woff2') format('woff2');font-weight:700;font-style:normal;font-display:block}",
          "@font-face{font-family:'Remote';src:url('https://evil.example/remote.woff2')}",
          "@font-face{font-family:'Data';src:url('data:font/woff2;base64,AAAA')}",
          "@font-face{font-family:'Blob';src:url('blob:https://presenton.invalid/id')}",
          "@font-face{font-family:'File';src:url('file:///tmp/font.ttf')}",
          "@font-face{font-family:'LocalFallback';src:local('Arial')}",
          "@font-face{font-family:'Unexpected';src:url('/static/fonts/unexpected.woff2');unicode-range:U+0-10FFFF}",
          "@font-face{font-family:'Multi';src:url('/static/fonts/one.woff2'),url('/static/fonts/two.woff2')}",
          "@font-face{font-family:'Hostile</style><script>alert(1)</script>';src:url('/static/fonts/hostile.woff2')}",
        ].join(""),
        fonts: [
          {
            family: "Inter",
            url: "https://fonts.googleapis.com/css2?family=Inter&display=swap",
          },
          {
            family: "Lookalike",
            url: "https://fonts.googleapis.com.evil.example/css2?family=Inter",
          },
          {
            family: "Wrong path",
            url: "https://fonts.googleapis.com/not-css?family=Inter",
          },
          {
            family: "Port",
            url: "https://fonts.googleapis.com:444/css2?family=Inter",
          },
          {
            family: "Credentials",
            url: "https://user@fonts.googleapis.com/css2?family=Inter",
          },
          {
            family: "External binary",
            url: "https://cdn.example/font.woff2",
          },
          {
            family: "Synthetic origin",
            url: "https://presenton.invalid/font.woff2",
          },
        ],
      },
    },
  );

  assert.ok(html);
  assert.match(html, /safe-bold\.woff2/);
  assert.match(html, /font-family:'Safe Bold'/);
  assert.match(html, /font-weight:700/);
  assert.match(
    html,
    /<link rel="stylesheet" href="https:\/\/fonts\.googleapis\.com\/css2\?family=Inter&amp;display=swap">/,
  );
  assert.doesNotMatch(html, /body\{display:none|@import/i);
  assert.doesNotMatch(html, /evil\.example|cdn\.example|presenton\.invalid/i);
  assert.doesNotMatch(html, /data:font|blob:|file:\/\//i);
  assert.doesNotMatch(html, /LocalFallback|Unexpected|Multi/);
  assert.doesNotMatch(html, /unicode-range/i);
  assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/i);
  assert.match(html, /Hostile\\3c \/style\\3e \\3c script\\3e alert/i);
});
