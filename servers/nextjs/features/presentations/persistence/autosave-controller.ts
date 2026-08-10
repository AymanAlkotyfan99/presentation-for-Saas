import type { EditorCommand } from "@/components/editor/commands";
import type { PresentationDocument } from "@/generated/presentation-document";
import type { RevisionJournal } from "./journal";
import { RevisionClient } from "./revision-client";
import { RevisionClientError, type PendingRevision, type RevisionConflict, type RevisionSaveStatus } from "./types";

export type RevisionAutosaveSnapshot = {
  status: RevisionSaveStatus;
  acknowledgedRevision: number;
  pendingCommands: number;
  conflict: RevisionConflict | null;
  errorCode: string | null;
};

export class RevisionAutosaveController {
  private commands: EditorCommand[] = [];
  private pendingKey: string | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private saving = false;
  private online = true;
  private disposed = false;
  private recoveryBaseRevision: number | null = null;
  private snapshot: RevisionAutosaveSnapshot;
  private listeners = new Set<(snapshot: RevisionAutosaveSnapshot) => void>();

  constructor(
    readonly presentationId: string,
    readonly actorScope: string,
    initialRevision: number,
    private readonly journal: RevisionJournal,
    private readonly client: RevisionClient,
    private readonly canWrite: () => boolean,
    private readonly onServerDocument?: (document: PresentationDocument) => void,
    private readonly debounceMs = 750,
  ) {
    this.snapshot = { status: "idle", acknowledgedRevision: initialRevision, pendingCommands: 0, conflict: null, errorCode: null };
  }

  getSnapshot = () => this.snapshot;
  subscribe = (listener: (snapshot: RevisionAutosaveSnapshot) => void) => {
    this.listeners.add(listener); return () => this.listeners.delete(listener);
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

  async enqueue(command: EditorCommand) {
    if (this.disposed) return;
    if (!this.canWrite()) { this.update({ status: "read-only" }); return; }
    this.commands.push(structuredClone(command));
    this.pendingKey ??= makeIdempotencyKey();
    await this.persistPending();
    this.update({ status: this.online ? "unsaved" : "offline", pendingCommands: this.commands.length, errorCode: null });
    this.schedule();
  }

  setOnline(online: boolean) {
    this.online = online;
    if (!online && this.commands.length) this.update({ status: "offline" });
    if (online && this.commands.length && this.snapshot.status !== "conflict") { this.update({ status: "unsaved" }); this.schedule(0); }
  }

  setWritable(writable: boolean) {
    if (!writable) this.update({ status: "read-only" });
    else if (this.commands.length && this.snapshot.status !== "conflict") { this.update({ status: this.online ? "unsaved" : "offline" }); this.schedule(0); }
  }

  async flush() {
    if (this.saving || !this.commands.length || !this.online || !this.canWrite() || this.snapshot.status === "conflict") return;
    if (this.timer) clearTimeout(this.timer); this.timer = null;
    const commands = this.commands;
    const key = this.pendingKey!;
    const baseRevision = this.snapshot.acknowledgedRevision;
    this.commands = []; this.pendingKey = null; this.saving = true;
    this.update({ status: "saving", pendingCommands: commands.length });
    try {
      const response = await this.client.save(this.presentationId, baseRevision, commands, key);
      if (response.revision < this.snapshot.acknowledgedRevision || (!response.replayed && response.parentRevision !== baseRevision)) {
        throw new RevisionClientError("REVISION_ACK_INVALID", 409, { currentRevision: response.revision });
      }
      await this.journal.remove(this.presentationId, key);
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
      this.commands = [...commands, ...newerCommands]; this.pendingKey = key;
      if (newerKey) await this.journal.remove(this.presentationId, newerKey);
      await this.persistPending();
      if (error instanceof RevisionClientError && (error.code === "REVISION_CONFLICT" || error.code === "REVISION_ACK_INVALID")) {
        this.update({
          status: "conflict", pendingCommands: this.commands.length,
          conflict: { currentRevision: Number(error.params.currentRevision ?? baseRevision), currentChecksum: typeof error.params.currentChecksum === "string" ? error.params.currentChecksum : undefined },
          errorCode: error.code,
        });
      } else if (error instanceof RevisionClientError && error.status === 0) {
        this.online = false; this.update({ status: "offline", pendingCommands: this.commands.length, errorCode: error.code });
      } else {
        this.update({ status: "error", pendingCommands: this.commands.length, errorCode: error instanceof RevisionClientError ? error.code : "REVISION_SAVE_FAILED" });
      }
    } finally { this.saving = false; }
  }

  async reloadServerVersion() {
    const current = await this.client.current(this.presentationId);
    await this.journal.clearPresentation(this.presentationId, this.actorScope);
    this.commands = []; this.pendingKey = null;
    this.recoveryBaseRevision = null;
    this.onServerDocument?.(current.document);
    this.update({ status: "saved", acknowledgedRevision: current.revision, pendingCommands: 0, conflict: null, errorCode: null });
  }

  recoveryPayload() {
    return JSON.stringify({ schemaVersion: 1, presentationId: this.presentationId, baseRevision: this.recoveryBaseRevision ?? this.snapshot.acknowledgedRevision, commands: this.commands }, null, 2);
  }

  retry() { this.online = true; if (this.snapshot.status !== "conflict") { this.update({ status: "unsaved" }); this.schedule(0); } }
  dispose() { this.disposed = true; if (this.timer) clearTimeout(this.timer); this.listeners.clear(); }

  private schedule(delay = this.debounceMs) {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.flush(), delay);
  }
  private async persistPending() {
    if (!this.pendingKey || !this.commands.length) return;
    const entry: PendingRevision = {
      presentationId: this.presentationId, actorScope: this.actorScope,
      baseRevision: this.snapshot.acknowledgedRevision, idempotencyKey: this.pendingKey,
      commands: this.commands, createdAt: Date.now(), attempts: 0,
    };
    await this.journal.put(entry);
  }
  private update(changes: Partial<RevisionAutosaveSnapshot>) {
    this.snapshot = { ...this.snapshot, ...changes };
    this.listeners.forEach((listener) => listener(this.snapshot));
  }
}

function makeIdempotencyKey() {
  return globalThis.crypto?.randomUUID?.() ?? `save-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
