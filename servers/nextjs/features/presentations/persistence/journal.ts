import type { PendingRevision } from "./types";

const DATABASE = "bayanly-revision-recovery-v1";
const STORE = "pending-command-batches";
export const MAX_JOURNAL_ENTRIES = 250;
export const MAX_JOURNAL_BYTES = 1024 * 1024;

export interface RevisionJournal {
  put(entry: PendingRevision): Promise<void>;
  remove(presentationId: string, idempotencyKey: string): Promise<void>;
  list(presentationId: string, actorScope: string): Promise<PendingRevision[]>;
  clearPresentation(presentationId: string, actorScope: string): Promise<void>;
}

function key(entry: Pick<PendingRevision, "presentationId" | "actorScope" | "idempotencyKey">) {
  return `${entry.actorScope}:${entry.presentationId}:${entry.idempotencyKey}`;
}

export class MemoryRevisionJournal implements RevisionJournal {
  private entries = new Map<string, PendingRevision>();
  async put(entry: PendingRevision) { this.entries.set(key(entry), structuredClone(entry)); this.prune(); }
  async remove(presentationId: string, idempotencyKey: string) {
    for (const [entryKey, value] of this.entries) if (value.presentationId === presentationId && value.idempotencyKey === idempotencyKey) this.entries.delete(entryKey);
  }
  async list(presentationId: string, actorScope: string) {
    return [...this.entries.values()].filter((entry) => entry.presentationId === presentationId && entry.actorScope === actorScope).sort((a, b) => a.createdAt - b.createdAt).map((entry) => structuredClone(entry));
  }
  async clearPresentation(presentationId: string, actorScope: string) {
    for (const [entryKey, value] of this.entries) if (value.presentationId === presentationId && value.actorScope === actorScope) this.entries.delete(entryKey);
  }
  private prune() {
    const entries = [...this.entries.entries()].sort((a, b) => a[1].createdAt - b[1].createdAt);
    let bytes = entries.reduce((sum, [, entry]) => sum + JSON.stringify(entry).length, 0);
    while (entries.length > MAX_JOURNAL_ENTRIES || bytes > MAX_JOURNAL_BYTES) {
      const oldest = entries.shift();
      if (!oldest) break;
      bytes -= JSON.stringify(oldest[1]).length;
      this.entries.delete(oldest[0]);
    }
  }
}

export class IndexedDbRevisionJournal implements RevisionJournal {
  constructor(private readonly indexedDBFactory: IDBFactory = indexedDB) {}

  async put(entry: PendingRevision) {
    if (JSON.stringify(entry).length > MAX_JOURNAL_BYTES) throw new Error("REVISION_JOURNAL_ENTRY_TOO_LARGE");
    const database = await this.open();
    await transaction(database, "readwrite", (store) => store.put({ ...entry, key: key(entry) }));
    await this.prune(database);
  }
  async remove(presentationId: string, idempotencyKey: string) {
    const database = await this.open();
    const values = await all(database);
    await transaction(database, "readwrite", (store) => {
      values.filter((entry) => entry.presentationId === presentationId && entry.idempotencyKey === idempotencyKey).forEach((entry) => store.delete(entry.key));
    });
  }
  async list(presentationId: string, actorScope: string) {
    return (await all(await this.open()))
      .filter((entry) => entry.presentationId === presentationId && entry.actorScope === actorScope)
      .sort((a, b) => a.createdAt - b.createdAt)
      .map((stored) => {
        const entry = structuredClone(stored);
        Reflect.deleteProperty(entry, "key");
        return entry;
      });
  }
  async clearPresentation(presentationId: string, actorScope: string) {
    const database = await this.open();
    const values = await all(database);
    await transaction(database, "readwrite", (store) => values.filter((entry) => entry.presentationId === presentationId && entry.actorScope === actorScope).forEach((entry) => store.delete(entry.key)));
  }
  private open(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      const request = this.indexedDBFactory.open(DATABASE, 1);
      request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "key" });
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }
  private async prune(database: IDBDatabase) {
    const values = (await all(database)).sort((a, b) => a.createdAt - b.createdAt);
    let bytes = values.reduce((sum, entry) => sum + JSON.stringify(entry).length, 0);
    const remove: string[] = [];
    while (values.length > MAX_JOURNAL_ENTRIES || bytes > MAX_JOURNAL_BYTES) {
      const oldest = values.shift(); if (!oldest) break;
      bytes -= JSON.stringify(oldest).length; remove.push(oldest.key);
    }
    await transaction(database, "readwrite", (store) => remove.forEach((entryKey) => store.delete(entryKey)));
  }
}

type StoredEntry = PendingRevision & { key: string };
function all(database: IDBDatabase): Promise<StoredEntry[]> {
  return new Promise((resolve, reject) => {
    const request = database.transaction(STORE, "readonly").objectStore(STORE).getAll();
    request.onsuccess = () => resolve(request.result as StoredEntry[]);
    request.onerror = () => reject(request.error);
  });
}
function transaction(database: IDBDatabase, mode: IDBTransactionMode, mutate: (store: IDBObjectStore) => void) {
  return new Promise<void>((resolve, reject) => {
    const tx = database.transaction(STORE, mode); mutate(tx.objectStore(STORE));
    tx.oncomplete = () => resolve(); tx.onerror = () => reject(tx.error); tx.onabort = () => reject(tx.error);
  });
}
