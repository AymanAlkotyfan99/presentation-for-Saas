import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const catalogs = await Promise.all(["en", "ar"].map(async (locale) => JSON.parse(await readFile(path.join(projectRoot, "messages", `${locale}.json`), "utf8"))));

function interpolate(message, values) {
  return message.replace(/\{([A-Za-z][A-Za-z0-9]*)\}/g, (placeholder, key) => values[key] === undefined ? placeholder : String(values[key]));
}

test("interpolation treats values as text and never evaluates markup", () => {
  for (const catalog of catalogs) {
    const result = interpolate(catalog.common.welcome, { productName: '<img src=x onerror="alert(1)">' });
    assert.match(result, /<img/);
    assert.doesNotMatch(result, /\[object Object\]/);
    // React renders this returned string as a text node; catalogs never opt in to dangerouslySetInnerHTML.
    assert.equal(typeof result, "string");
  }
});

