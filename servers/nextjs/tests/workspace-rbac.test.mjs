import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { mkdtemp } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const nextRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(nextRoot, "../..");
const temporary = await mkdtemp(path.join(repositoryRoot, ".cache/workspace-rbac-"));
const outfile = path.join(temporary, "capabilities.mjs");
await build({
  bundle: true,
  stdin: { contents: 'export * from "./features/workspaces/capabilities.ts";', resolveDir: nextRoot, loader: "ts" },
  format: "esm", outfile, platform: "node", tsconfig: path.join(nextRoot, "tsconfig.json"),
});
const capabilities = await import(pathToFileURL(outfile).href);

test("client capabilities accept known server grants and deny unknown values", () => {
  const grants = capabilities.normalizeCapabilities(["presentations:read", "members:manage", "made-up:grant"]);
  assert.equal(capabilities.can(grants, "presentations:read"), true);
  assert.equal(capabilities.can(grants, "members:manage"), true);
  assert.equal(capabilities.can(grants, "workspace:delete"), false);
  assert.equal(grants.has("made-up:grant"), false);
});

test("role controls never offer OWNER as an ordinary role transition", () => {
  assert.deepEqual(capabilities.editableRolesFor("OWNER"), ["ADMIN", "EDITOR", "VIEWER"]);
  assert.deepEqual(capabilities.editableRolesFor("ADMIN"), ["ADMIN", "EDITOR", "VIEWER"]);
  assert.deepEqual(capabilities.editableRolesFor("EDITOR"), []);
  assert.deepEqual(capabilities.editableRolesFor(null), []);
});

test("workspace UI is localized in English and Arabic and uses logical layout", async () => {
  const [english, arabic, switcher, members] = await Promise.all([
    readFile(path.join(nextRoot, "messages/en.json"), "utf8").then(JSON.parse),
    readFile(path.join(nextRoot, "messages/ar.json"), "utf8").then(JSON.parse),
    readFile(path.join(nextRoot, "features/workspaces/WorkspaceSwitcher.tsx"), "utf8"),
    readFile(path.join(nextRoot, "features/workspaces/MembersPanel.tsx"), "utf8"),
  ]);
  assert.deepEqual(Object.keys(english.workspace).sort(), Object.keys(arabic.workspace).sort());
  assert.match(arabic.workspace.members, /[\u0600-\u06ff]/);
  assert.doesNotMatch(`${switcher}\n${members}`, /\b(?:ml|mr|pl|pr)-/);
  assert.match(members, /can\("members:manage"\)/);
  assert.match(members, /can\("invitations:manage"\)/);
});
