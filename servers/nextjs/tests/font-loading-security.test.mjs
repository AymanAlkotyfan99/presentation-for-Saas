import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  buildFontFaceCss,
  escapeCssString,
  injectFontResources,
  normalizeFontResource,
  normalizeFontResources,
} from "../lib/font-loading-security.mjs";

const hookSource = await readFile(
  new URL("../app/(presentation-generator)/hooks/useFontLoad.tsx", import.meta.url),
  "utf8",
);
const googleFontsSource = await readFile(
  new URL("../components/slide-editor/text/google-fonts.ts", import.meta.url),
  "utf8",
);

const policy = {
  documentOrigin: "https://app.presenton.test",
  trustedAssetOrigins: ["https://api.presenton.test"],
};

test("only exact HTTPS Google Fonts stylesheet endpoints are external", () => {
  for (const url of [
    "https://fonts.googleapis.com/css2?family=Inter&display=swap",
    "https://fonts.googleapis.com/css?family=Roboto",
  ]) {
    assert.deepEqual(normalizeFontResource("Inter", url, policy), {
      family: "Inter",
      kind: "stylesheet",
      url,
    });
  }

  for (const url of [
    "http://fonts.googleapis.com/css2?family=Inter",
    "https://fonts.googleapis.com.evil.test/css2?family=Inter",
    "https://evil-fonts.googleapis.com/css2?family=Inter",
    "https://fonts.googleapis.com:444/css2?family=Inter",
    "https://user@fonts.googleapis.com/css2?family=Inter",
    "https://fonts.googleapis.com/not-css?family=Inter",
    "//fonts.googleapis.com/css2?family=Inter",
    "https:fonts.googleapis.com/css2?family=Inter",
  ]) {
    assert.equal(normalizeFontResource("Inter", url, policy), null, url);
  }
});

test("local and narrowly trusted backend font assets remain supported", () => {
  assert.deepEqual(normalizeFontResource("Local", "/fonts/local.woff2", policy), {
    family: "Local",
    kind: "font",
    url: "https://app.presenton.test/fonts/local.woff2",
  });
  assert.equal(normalizeFontResource("Theme", "/themes/font.css?v=2", policy), null);
  assert.deepEqual(
    normalizeFontResource(
      "Uploaded",
      "https://api.presenton.test/app_data/fonts/uploaded.otf",
      policy,
    ),
    {
      family: "Uploaded",
      kind: "font",
      url: "https://api.presenton.test/app_data/fonts/uploaded.otf",
    },
  );

  for (const url of [
    "https://untrusted.test/font.woff2",
    "https://api.presenton.test/private/font.woff2",
    "https://api.presenton.test/app_data/font.css",
    "/fonts/not-a-font.html",
  ]) {
    assert.equal(normalizeFontResource("Blocked", url, policy), null, url);
  }

  assert.deepEqual(
    normalizeFontResource("Local", "fonts/../fonts/local.woff2?v=1", {
      ...policy,
      preserveRelativeUrls: true,
    }),
    {
      family: "Local",
      kind: "font",
      url: "/fonts/local.woff2?v=1",
    },
  );
  assert.equal(
    normalizeFontResource(
      "Blocked",
      "/static/fonts%2fprivate.woff2",
      policy,
    ),
    null,
  );
});

test("unsafe protocols, malformed URLs, and controls are rejected", () => {
  for (const url of [
    "javascript:alert(1)",
    "data:font/woff2;base64,AAAA",
    "blob:https://app.presenton.test/id",
    "file:///tmp/font.ttf",
    "ftp://app.presenton.test/font.ttf",
    "/fonts/font.woff2#fragment",
    "/fonts/bad\\name.woff2",
    "/fonts/bad\nname.woff2",
  ]) {
    assert.equal(normalizeFontResource("Blocked", url, policy), null, url);
  }
  assert.equal(normalizeFontResource("Bad\nFamily", "/fonts/font.woff2", policy), null);
  assert.equal(normalizeFontResource("\u202eSpoofed", "/fonts/font.woff2", policy), null);
});

test("font family and URL values are CSS-string escaped", () => {
  const family = 'Bad";}body{background:red}/*</style>';
  const resource = normalizeFontResource(
    family,
    "/fonts/safe.woff2?label=%22%29%3B%7D",
    policy,
  );
  assert.ok(resource);
  const css = buildFontFaceCss(resource);
  assert.ok(css);
  assert.doesNotMatch(css, /font-family: "Bad";/);
  assert.doesNotMatch(css, /<\/style>/i);
  assert.match(css, /Bad\\22 /);
  assert.match(css, /\\3C \/style/);
  assert.equal(escapeCssString('a"b\\c'), "a\\22 b\\5C c");
});

test("malformed maps and throwing values fail closed", () => {
  assert.deepEqual(normalizeFontResources(null, policy), []);
  assert.deepEqual(normalizeFontResources([], policy), []);

  const hostile = { Safe: "/fonts/safe.ttf" };
  Object.defineProperty(hostile, "Throwing", {
    enumerable: true,
    get() {
      throw new Error("getter must not escape");
    },
  });
  assert.deepEqual(normalizeFontResources(hostile, policy), [
    {
      family: "Safe",
      kind: "font",
      url: "https://app.presenton.test/fonts/safe.ttf",
    },
  ]);
});

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName;
    this.attributes = new Map();
    this.href = "";
    this.rel = "";
    this.textContent = "";
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
}

test("the hook delegates policy and DOM construction to the centralized helper", () => {
  assert.match(hookSource, /injectFontResources/);
  assert.match(hookSource, /getFastAPIUrl\(\)/);
  assert.doesNotMatch(hookSource, /querySelector/);
  assert.doesNotMatch(hookSource, /@font-face|textContent\s*=/);
});

test("the slide editor loader delegates both catalog and template fonts", () => {
  assert.match(googleFontsSource, /normalizeFontResource/);
  assert.match(googleFontsSource, /buildFontFaceCss/);
  assert.match(googleFontsSource, /normalizeGoogleFontResource/);
  assert.doesNotMatch(
    googleFontsSource,
    /function\s+isFontStylesheetUrl|\/fonts\\\.googleapis\\\.com\//,
  );
  assert.doesNotMatch(googleFontsSource, /style\.textContent\s*=\s*`@font-face/);
});

test("the DOM loader never interpolates hostile values into selectors", () => {
  const children = [];
  const fakeDocument = {
    head: {
      appendChild(element) {
        children.push(element);
      },
    },
    createElement(tagName) {
      return new FakeElement(tagName);
    },
    querySelectorAll(selector) {
      if (selector === 'link[rel="stylesheet"]') {
        return children.filter(
          (element) => element.tagName === "link" && element.rel === "stylesheet",
        );
      }
      if (selector === "style[data-presenton-font-face]") {
        return children.filter(
          (element) =>
            element.tagName === "style" &&
            element.getAttribute("data-presenton-font-face") === "true",
        );
      }
      throw new Error(`unexpected or interpolated selector: ${selector}`);
    },
  };
  const hostileFamily = 'Bad"] style, link { color: red } /*</style>';
  const fonts = {
    Inter: "https://fonts.googleapis.com/css2?family=Inter&display=swap",
    Local: "/fonts/local.woff2",
    Uploaded: "https://api.presenton.test/app_data/fonts/uploaded.ttf",
    [hostileFamily]: "/fonts/hostile.otf",
    External: "https://evil.test/attack.css",
    Lookalike: "https://fonts.googleapis.com.evil.test/css2?family=Inter",
    Script: "javascript:alert(1)",
  };
  assert.doesNotThrow(() => injectFontResources(fonts, policy, fakeDocument));
  assert.equal(children.length, 4);
  assert.equal(children.filter((element) => element.tagName === "link").length, 1);
  assert.equal(children.filter((element) => element.tagName === "style").length, 3);

  const hostileStyle = children.find(
    (element) => element.getAttribute("data-font-family") === hostileFamily,
  );
  assert.ok(hostileStyle);
  assert.doesNotMatch(hostileStyle.textContent, /<\/style>/i);
  assert.match(hostileStyle.textContent, /\\22 /);

  assert.doesNotThrow(() => injectFontResources(fonts, policy, fakeDocument));
  assert.equal(children.length, 4, "safe resources are deduplicated");
});
