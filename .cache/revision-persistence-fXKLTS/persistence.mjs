// features/presentations/persistence/types.ts
var RevisionClientError = class extends Error {
  constructor(code, status, params = {}) {
    super(code);
    this.code = code;
    this.status = status;
    this.params = params;
    this.name = "RevisionClientError";
  }
};

// features/presentations/persistence/feature-flags.ts
function enabled(value, fallback) {
  if (value === void 0 || value === "") return fallback;
  return value === "1" || value.toLowerCase() === "true";
}
function persistenceFeatureFlags(env = process.env) {
  return Object.freeze({
    revisionWrites: enabled(env.NEXT_PUBLIC_REVISION_WRITES_ENABLED ?? env.REVISION_WRITES_ENABLED, false),
    indexedDbRecovery: enabled(env.NEXT_PUBLIC_INDEXEDDB_RECOVERY_ENABLED ?? env.INDEXEDDB_RECOVERY_ENABLED, false),
    versionHistory: enabled(env.NEXT_PUBLIC_VERSION_HISTORY_ENABLED ?? env.VERSION_HISTORY_ENABLED, false)
  });
}

// features/presentations/persistence/revision-client.ts
var RevisionClient = class {
  constructor(request = fetch, prefix = "/api/v1/ppt/presentations") {
    this.request = request;
    this.prefix = prefix;
  }
  async save(presentationId, baseRevision, commands, idempotencyKey) {
    return this.json(`${this.prefix}/${encodeURIComponent(presentationId)}/revisions`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "If-Match": `"${baseRevision}"`,
        "Idempotency-Key": idempotencyKey
      },
      body: JSON.stringify({ baseRevision, commands })
    });
  }
  async current(presentationId) {
    return this.json(`${this.prefix}/${encodeURIComponent(presentationId)}/revisions/current`, { method: "GET" });
  }
  async history(presentationId, before) {
    const query = before ? `?before=${before}` : "";
    return this.json(`${this.prefix}/${encodeURIComponent(presentationId)}/revisions${query}`, { method: "GET" });
  }
  async restore(presentationId, targetRevision, baseRevision, idempotencyKey) {
    return this.json(`${this.prefix}/${encodeURIComponent(presentationId)}/revisions/${targetRevision}/restore`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "If-Match": `"${baseRevision}"`,
        "Idempotency-Key": idempotencyKey
      },
      body: JSON.stringify({ baseRevision })
    });
  }
  async json(url, init) {
    let response;
    try {
      response = await this.request(url, { ...init, credentials: "same-origin" });
    } catch {
      throw new RevisionClientError("REVISION_NETWORK_UNAVAILABLE", 0);
    }
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new RevisionClientError(
        typeof body.code === "string" ? body.code : "REVISION_REQUEST_FAILED",
        response.status,
        body.params && typeof body.params === "object" ? body.params : {}
      );
    }
    return body;
  }
};

// features/presentations/persistence/journal.ts
var DATABASE = "bayanly-revision-recovery-v1";
var STORE = "pending-command-batches";
var MAX_JOURNAL_ENTRIES = 250;
var MAX_JOURNAL_BYTES = 1024 * 1024;
function key(entry) {
  return `${entry.actorScope}:${entry.presentationId}:${entry.idempotencyKey}`;
}
var MemoryRevisionJournal = class {
  entries = /* @__PURE__ */ new Map();
  async put(entry) {
    this.entries.set(key(entry), structuredClone(entry));
    this.prune();
  }
  async remove(presentationId, idempotencyKey) {
    for (const [entryKey, value] of this.entries) if (value.presentationId === presentationId && value.idempotencyKey === idempotencyKey) this.entries.delete(entryKey);
  }
  async list(presentationId, actorScope) {
    return [...this.entries.values()].filter((entry) => entry.presentationId === presentationId && entry.actorScope === actorScope).sort((a, b) => a.createdAt - b.createdAt).map((entry) => structuredClone(entry));
  }
  async clearPresentation(presentationId, actorScope) {
    for (const [entryKey, value] of this.entries) if (value.presentationId === presentationId && value.actorScope === actorScope) this.entries.delete(entryKey);
  }
  prune() {
    const entries = [...this.entries.entries()].sort((a, b) => a[1].createdAt - b[1].createdAt);
    let bytes = entries.reduce((sum, [, entry]) => sum + JSON.stringify(entry).length, 0);
    while (entries.length > MAX_JOURNAL_ENTRIES || bytes > MAX_JOURNAL_BYTES) {
      const oldest = entries.shift();
      if (!oldest) break;
      bytes -= JSON.stringify(oldest[1]).length;
      this.entries.delete(oldest[0]);
    }
  }
};
var IndexedDbRevisionJournal = class {
  constructor(indexedDBFactory = indexedDB) {
    this.indexedDBFactory = indexedDBFactory;
  }
  async put(entry) {
    if (JSON.stringify(entry).length > MAX_JOURNAL_BYTES) throw new Error("REVISION_JOURNAL_ENTRY_TOO_LARGE");
    const database = await this.open();
    await transaction(database, "readwrite", (store) => store.put({ ...entry, key: key(entry) }));
    await this.prune(database);
  }
  async remove(presentationId, idempotencyKey) {
    const database = await this.open();
    const values = await all(database);
    await transaction(database, "readwrite", (store) => {
      values.filter((entry) => entry.presentationId === presentationId && entry.idempotencyKey === idempotencyKey).forEach((entry) => store.delete(entry.key));
    });
  }
  async list(presentationId, actorScope) {
    return (await all(await this.open())).filter((entry) => entry.presentationId === presentationId && entry.actorScope === actorScope).sort((a, b) => a.createdAt - b.createdAt).map((stored) => {
      const entry = structuredClone(stored);
      Reflect.deleteProperty(entry, "key");
      return entry;
    });
  }
  async clearPresentation(presentationId, actorScope) {
    const database = await this.open();
    const values = await all(database);
    await transaction(database, "readwrite", (store) => values.filter((entry) => entry.presentationId === presentationId && entry.actorScope === actorScope).forEach((entry) => store.delete(entry.key)));
  }
  open() {
    return new Promise((resolve, reject) => {
      const request = this.indexedDBFactory.open(DATABASE, 1);
      request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "key" });
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }
  async prune(database) {
    const values = (await all(database)).sort((a, b) => a.createdAt - b.createdAt);
    let bytes = values.reduce((sum, entry) => sum + JSON.stringify(entry).length, 0);
    const remove = [];
    while (values.length > MAX_JOURNAL_ENTRIES || bytes > MAX_JOURNAL_BYTES) {
      const oldest = values.shift();
      if (!oldest) break;
      bytes -= JSON.stringify(oldest).length;
      remove.push(oldest.key);
    }
    await transaction(database, "readwrite", (store) => remove.forEach((entryKey) => store.delete(entryKey)));
  }
};
function all(database) {
  return new Promise((resolve, reject) => {
    const request = database.transaction(STORE, "readonly").objectStore(STORE).getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
function transaction(database, mode, mutate) {
  return new Promise((resolve, reject) => {
    const tx = database.transaction(STORE, mode);
    mutate(tx.objectStore(STORE));
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

// features/presentations/persistence/multi-tab.ts
var LEASE_MS = 8e3;
var PresentationTabCoordinator = class {
  constructor(presentationId, clock = Date.now, tabId) {
    this.presentationId = presentationId;
    this.clock = clock;
    this.tabId = tabId ?? globalThis.crypto?.randomUUID?.() ?? `tab-${Math.random().toString(36).slice(2)}`;
  }
  tabId;
  ownership = "read-only";
  timer = null;
  listeners = /* @__PURE__ */ new Set();
  channel = null;
  start() {
    if (typeof window === "undefined") return;
    if ("BroadcastChannel" in globalThis) {
      this.channel = new BroadcastChannel(`bayanly:presentation:${this.presentationId}`);
      this.channel.onmessage = (event) => {
        if (event.data?.type === "lease" && event.data.tabId !== this.tabId) this.refresh();
      };
    }
    window.addEventListener("storage", this.onStorage);
    this.refresh();
    this.timer = setInterval(() => this.refresh(), LEASE_MS / 2);
  }
  canWrite() {
    return this.ownership === "writer";
  }
  getOwnership() {
    return this.ownership;
  }
  subscribe(listener) {
    this.listeners.add(listener);
    listener(this.ownership);
    return () => this.listeners.delete(listener);
  }
  takeOverIfExpired() {
    this.refresh(true);
    return this.canWrite();
  }
  close() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    if (typeof window !== "undefined") window.removeEventListener("storage", this.onStorage);
    if (this.canWrite()) localStorage.removeItem(this.key);
    this.channel?.close();
    this.channel = null;
  }
  get key() {
    return `bayanly:revision-lease:${this.presentationId}`;
  }
  onStorage = (event) => {
    if (event.key === this.key) this.refresh();
  };
  refresh(force = false) {
    if (typeof localStorage === "undefined") return;
    const now = this.clock();
    const lease = readLease(localStorage.getItem(this.key));
    const decision = resolveLease(lease, this.tabId, now, force);
    if (decision.ownership === "writer") {
      const next = decision.lease;
      localStorage.setItem(this.key, JSON.stringify(next));
      const confirmed = readLease(localStorage.getItem(this.key));
      this.setOwnership(confirmed?.tabId === this.tabId ? "writer" : "read-only");
      this.channel?.postMessage({ type: "lease", tabId: this.tabId, expiresAt: next.expiresAt });
    } else {
      this.setOwnership("read-only");
    }
  }
  setOwnership(value) {
    if (value === this.ownership) return;
    this.ownership = value;
    this.listeners.forEach((listener) => listener(value));
  }
};
function resolveLease(existing, tabId, now, force = false) {
  if (force || !existing || existing.expiresAt <= now || existing.tabId === tabId) {
    return { ownership: "writer", lease: { tabId, expiresAt: now + LEASE_MS } };
  }
  return { ownership: "read-only", lease: existing };
}
function readLease(value) {
  try {
    const parsed = JSON.parse(value ?? "null");
    return parsed && typeof parsed.tabId === "string" && Number.isFinite(parsed.expiresAt) ? parsed : null;
  } catch {
    return null;
  }
}

// features/presentations/persistence/autosave-controller.ts
var RevisionAutosaveController = class {
  constructor(presentationId, actorScope, initialRevision, journal, client, canWrite, onServerDocument, debounceMs = 750) {
    this.presentationId = presentationId;
    this.actorScope = actorScope;
    this.journal = journal;
    this.client = client;
    this.canWrite = canWrite;
    this.onServerDocument = onServerDocument;
    this.debounceMs = debounceMs;
    this.snapshot = { status: "idle", acknowledgedRevision: initialRevision, pendingCommands: 0, conflict: null, errorCode: null };
  }
  commands = [];
  pendingKey = null;
  timer = null;
  saving = false;
  online = true;
  disposed = false;
  recoveryBaseRevision = null;
  snapshot;
  listeners = /* @__PURE__ */ new Set();
  getSnapshot = () => this.snapshot;
  subscribe = (listener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };
  async recover() {
    const entries = await this.journal.list(this.presentationId, this.actorScope);
    if (!entries.length) return;
    const current = await this.client.current(this.presentationId);
    this.snapshot.acknowledgedRevision = current.revision;
    const first = entries[0];
    this.commands = entries.flatMap((entry) => entry.commands);
    this.pendingKey = first.idempotencyKey;
    if (first.baseRevision !== current.revision || entries.some((entry, index) => index > 0 && entry.baseRevision < first.baseRevision)) {
      this.recoveryBaseRevision = first.baseRevision;
      this.update({ status: "conflict", pendingCommands: this.commands.length, conflict: { currentRevision: current.revision, currentChecksum: current.checksum } });
      return;
    }
    for (const entry of entries.slice(1)) await this.journal.remove(this.presentationId, entry.idempotencyKey);
    await this.persistPending();
    this.update({ status: "unsaved", pendingCommands: this.commands.length });
    this.schedule();
  }
  async enqueue(command) {
    if (this.disposed) return;
    if (!this.canWrite()) {
      this.update({ status: "read-only" });
      return;
    }
    this.commands.push(structuredClone(command));
    this.pendingKey ??= makeIdempotencyKey();
    await this.persistPending();
    this.update({ status: this.online ? "unsaved" : "offline", pendingCommands: this.commands.length, errorCode: null });
    this.schedule();
  }
  setOnline(online) {
    this.online = online;
    if (!online && this.commands.length) this.update({ status: "offline" });
    if (online && this.commands.length && this.snapshot.status !== "conflict") {
      this.update({ status: "unsaved" });
      this.schedule(0);
    }
  }
  setWritable(writable) {
    if (!writable) this.update({ status: "read-only" });
    else if (this.commands.length && this.snapshot.status !== "conflict") {
      this.update({ status: this.online ? "unsaved" : "offline" });
      this.schedule(0);
    }
  }
  async flush() {
    if (this.saving || !this.commands.length || !this.online || !this.canWrite() || this.snapshot.status === "conflict") return;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    const commands = this.commands;
    const key2 = this.pendingKey;
    const baseRevision = this.snapshot.acknowledgedRevision;
    this.commands = [];
    this.pendingKey = null;
    this.saving = true;
    this.update({ status: "saving", pendingCommands: commands.length });
    try {
      const response = await this.client.save(this.presentationId, baseRevision, commands, key2);
      if (response.revision < this.snapshot.acknowledgedRevision || !response.replayed && response.parentRevision !== baseRevision) {
        throw new RevisionClientError("REVISION_ACK_INVALID", 409, { currentRevision: response.revision });
      }
      await this.journal.remove(this.presentationId, key2);
      this.snapshot.acknowledgedRevision = response.revision;
      this.recoveryBaseRevision = null;
      this.onServerDocument?.(response.document);
      if (this.commands.length) {
        await this.persistPending();
        this.update({ status: "unsaved", pendingCommands: this.commands.length, conflict: null, errorCode: null });
        this.schedule(0);
      } else {
        this.update({ status: "saved", pendingCommands: 0, conflict: null, errorCode: null });
      }
    } catch (error) {
      const newerCommands = this.commands;
      const newerKey = this.pendingKey;
      this.commands = [...commands, ...newerCommands];
      this.pendingKey = key2;
      if (newerKey) await this.journal.remove(this.presentationId, newerKey);
      await this.persistPending();
      if (error instanceof RevisionClientError && (error.code === "REVISION_CONFLICT" || error.code === "REVISION_ACK_INVALID")) {
        this.update({
          status: "conflict",
          pendingCommands: this.commands.length,
          conflict: { currentRevision: Number(error.params.currentRevision ?? baseRevision), currentChecksum: typeof error.params.currentChecksum === "string" ? error.params.currentChecksum : void 0 },
          errorCode: error.code
        });
      } else if (error instanceof RevisionClientError && error.status === 0) {
        this.online = false;
        this.update({ status: "offline", pendingCommands: this.commands.length, errorCode: error.code });
      } else {
        this.update({ status: "error", pendingCommands: this.commands.length, errorCode: error instanceof RevisionClientError ? error.code : "REVISION_SAVE_FAILED" });
      }
    } finally {
      this.saving = false;
    }
  }
  async reloadServerVersion() {
    const current = await this.client.current(this.presentationId);
    await this.journal.clearPresentation(this.presentationId, this.actorScope);
    this.commands = [];
    this.pendingKey = null;
    this.recoveryBaseRevision = null;
    this.onServerDocument?.(current.document);
    this.update({ status: "saved", acknowledgedRevision: current.revision, pendingCommands: 0, conflict: null, errorCode: null });
  }
  recoveryPayload() {
    return JSON.stringify({ schemaVersion: 1, presentationId: this.presentationId, baseRevision: this.recoveryBaseRevision ?? this.snapshot.acknowledgedRevision, commands: this.commands }, null, 2);
  }
  retry() {
    this.online = true;
    if (this.snapshot.status !== "conflict") {
      this.update({ status: "unsaved" });
      this.schedule(0);
    }
  }
  dispose() {
    this.disposed = true;
    if (this.timer) clearTimeout(this.timer);
    this.listeners.clear();
  }
  schedule(delay = this.debounceMs) {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.flush(), delay);
  }
  async persistPending() {
    if (!this.pendingKey || !this.commands.length) return;
    const entry = {
      presentationId: this.presentationId,
      actorScope: this.actorScope,
      baseRevision: this.snapshot.acknowledgedRevision,
      idempotencyKey: this.pendingKey,
      commands: this.commands,
      createdAt: Date.now(),
      attempts: 0
    };
    await this.journal.put(entry);
  }
  update(changes) {
    this.snapshot = { ...this.snapshot, ...changes };
    this.listeners.forEach((listener) => listener(this.snapshot));
  }
};
function makeIdempotencyKey() {
  return globalThis.crypto?.randomUUID?.() ?? `save-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
export {
  IndexedDbRevisionJournal,
  MAX_JOURNAL_BYTES,
  MAX_JOURNAL_ENTRIES,
  MemoryRevisionJournal,
  PresentationTabCoordinator,
  RevisionAutosaveController,
  RevisionClient,
  RevisionClientError,
  persistenceFeatureFlags,
  resolveLease
};
