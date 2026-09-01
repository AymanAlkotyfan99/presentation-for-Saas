import assert from "node:assert/strict";
import { mkdir, mkdtemp } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const nextRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(nextRoot, "../..");
const cacheRoot = path.join(repositoryRoot, ".cache");
await mkdir(cacheRoot, { recursive: true });
const temporary = await mkdtemp(path.join(cacheRoot, "revision-persistence-"));
const outfile = path.join(temporary, "persistence.mjs");
await build({
  bundle: true,
  stdin: {
    contents: 'export * from "./features/presentations/persistence/core.ts";',
    resolveDir: nextRoot,
    loader: "ts",
  },
  format: "esm",
  outfile,
  platform: "node",
  tsconfig: path.join(nextRoot, "tsconfig.json"),
});
const persistence = await import(pathToFileURL(outfile).href);

const command = {
  commandId: "save:test-1",
  type: "UPDATE_SLIDE",
  targetIds: ["10000000-0000-4000-8000-000000000001"],
  payload: { changes: { title: "Recovered" } },
};
const document = { presentationId: "p", slides: [] };

function response(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

test("autosave reports saved only after durable server acknowledgement and removes its journal entry", async () => {
  const journal = new persistence.MemoryRevisionJournal();
  let resolveRequest;
  let idempotencyKey;
  const client = new persistence.RevisionClient(async (_url, init) => {
    idempotencyKey = init.headers["Idempotency-Key"];
    return new Promise((resolve) => { resolveRequest = resolve; });
  });
  const controller = new persistence.RevisionAutosaveController("p", "user:u", 1, journal, client, () => true, undefined, 60_000);
  await controller.enqueue(command);
  assert.equal(controller.getSnapshot().status, "unsaved");
  assert.equal((await journal.list("p", "user:u")).length, 1);
  const saving = controller.flush();
  await Promise.resolve();
  assert.equal(controller.getSnapshot().status, "saving");
  assert.equal(controller.getSnapshot().acknowledgedRevision, 1);
  resolveRequest(response({ revision: 2, parentRevision: 1, checksum: "a".repeat(64), source: "command", replayed: false, document, createdAt: new Date().toISOString() }));
  await saving;
  assert.equal(controller.getSnapshot().status, "saved");
  assert.equal(controller.getSnapshot().acknowledgedRevision, 2);
  assert.equal((await journal.list("p", "user:u")).length, 0);
  assert.ok(idempotencyKey);
  controller.dispose();
});

test("ambiguous network failure retains the same idempotency key for safe retry", async () => {
  const journal = new persistence.MemoryRevisionJournal();
  const keys = [];
  let attempts = 0;
  const client = new persistence.RevisionClient(async (_url, init) => {
    keys.push(init.headers["Idempotency-Key"]); attempts += 1;
    if (attempts === 1) throw new TypeError("offline after send");
    return response({ revision: 2, parentRevision: 1, checksum: "b".repeat(64), source: "command", replayed: true, document, createdAt: new Date().toISOString() });
  });
  const controller = new persistence.RevisionAutosaveController("p", "user:u", 1, journal, client, () => true, undefined, 60_000);
  await controller.enqueue(command); await controller.flush();
  assert.equal(controller.getSnapshot().status, "offline");
  controller.setOnline(true); await controller.flush();
  assert.deepEqual(keys, [keys[0], keys[0]]);
  assert.equal(controller.getSnapshot().status, "saved");
  controller.dispose();
});

test("reload recovery preserves command-only journal and surfaces stale-base conflict", async () => {
  const journal = new persistence.MemoryRevisionJournal();
  await journal.put({ presentationId: "p", actorScope: "user:u", baseRevision: 1, idempotencyKey: "persisted", commands: [command], createdAt: 1, attempts: 0 });
  const client = new persistence.RevisionClient(async () => response({ revision: 3, parentRevision: 2, checksum: "c".repeat(64), source: "command", replayed: false, document, createdAt: new Date().toISOString() }));
  const reloaded = new persistence.RevisionAutosaveController("p", "user:u", 1, journal, client, () => true, undefined, 60_000);
  await reloaded.recover();
  assert.equal(reloaded.getSnapshot().status, "conflict");
  assert.equal(reloaded.getSnapshot().conflict.currentRevision, 3);
  assert.match(reloaded.recoveryPayload(), /UPDATE_SLIDE/);
  reloaded.dispose();
});

test("multi-tab lease is single-writer until expiry and journal storage is bounded", async () => {
  const active = { tabId: "tab-a", expiresAt: 100 };
  assert.equal(persistence.resolveLease(active, "tab-b", 50).ownership, "read-only");
  assert.equal(persistence.resolveLease(active, "tab-b", 101).ownership, "writer");
  const journal = new persistence.MemoryRevisionJournal();
  for (let index = 0; index < persistence.MAX_JOURNAL_ENTRIES + 10; index += 1) {
    await journal.put({ presentationId: "p", actorScope: "user:u", baseRevision: 1, idempotencyKey: `key-${index}`, commands: [command], createdAt: index, attempts: 0 });
  }
  assert.equal((await journal.list("p", "user:u")).length, persistence.MAX_JOURNAL_ENTRIES);
});
