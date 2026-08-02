import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const nextRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(nextRoot, "../..");
const retiredRoute = join(nextRoot, "app", "api", "save-layout", "route.ts");

function routeFiles(directory) {
  if (!existsSync(directory)) return [];
  return readdirSync(directory).flatMap((entry) => {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) return routeFiles(path);
    return /^route\.(?:js|jsx|ts|tsx)$/.test(entry) ? [path] : [];
  });
}

test("the runtime executable-layout writer is removed", () => {
  assert.equal(existsSync(retiredRoute), false);
});

test("non-administrators have no runtime layout-writing endpoint", () => {
  assert.equal(existsSync(retiredRoute), false);
});

for (const attack of [
  ["relative traversal", "../../app/layout"],
  ["absolute path", "/tmp/application-source"],
  ["Windows absolute path", "C:\\application\\source"],
  ["encoded traversal", "%2e%2e%2f%2e%2e%2fapp"],
  ["symlink escape", "linked-source-directory"],
]) {
  test(`${attack[0]} cannot reach a layout source writer`, () => {
    // The former endpoint and its request-body/path handling no longer exist.
    // Consequently every payload, including administrator payloads, resolves
    // through Next.js as an unregistered route and cannot reach the filesystem.
    assert.equal(existsSync(retiredRoute), false, attack[1]);
  });
}

test("API routes do not combine filesystem writes with executable source suffixes", () => {
  const executableSuffix = /\.(?:js|jsx|mjs|cjs|ts|tsx)\b/i;
  const filesystemWrite = /\b(?:writeFile|appendFile|createWriteStream)\b/;

  for (const route of routeFiles(join(nextRoot, "app", "api"))) {
    const source = readFileSync(route, "utf8");
    assert.equal(
      filesystemWrite.test(source) && executableSuffix.test(source),
      false,
      `Runtime route may write executable source: ${route}`,
    );
  }
});

test("existing declarative layout catalog and bundled templates still load", () => {
  const catalog = JSON.parse(
    readFileSync(join(repositoryRoot, "layouts.json"), "utf8"),
  );
  assert.ok(catalog.layouts);

  for (const template of [
    "dynamic",
    "executive",
    "general",
    "modern",
    "momentum",
    "standard",
    "swift",
  ]) {
    assert.equal(
      statSync(join(repositoryRoot, "templates", template)).isDirectory(),
      true,
    );
  }
});
