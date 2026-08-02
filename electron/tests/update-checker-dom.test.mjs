import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(
  new URL("../app/utils/update-checker.ts", import.meta.url),
  "utf8",
);

test("update banner never inserts remote release data as HTML", () => {
  assert.doesNotMatch(source, /\.innerHTML\s*=/);
  assert.match(source, /document\.createTextNode\(payload\.latest\)/);
  assert.match(source, /white-space:pre-wrap;', payload\.message/);
});

test("update download remains HTTPS and opens without opener access", () => {
  assert.match(source, /parsedDownload\.protocol === 'https:'/);
  assert.match(source, /download\.rel = 'noopener noreferrer'/);
});
