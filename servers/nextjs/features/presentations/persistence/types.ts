import type { PresentationDocument } from "@/generated/presentation-document";
import type { EditorCommand } from "@/components/editor/commands";

export type RevisionSaveStatus =
  | "idle"
  | "unsaved"
  | "saving"
  | "saved"
  | "offline"
  | "conflict"
  | "error"
  | "read-only";

export type RevisionEnvelope = {
  revision: number;
  parentRevision: number | null;
  checksum: string;
  source: string;
  restoredFromRevision?: number;
  replayed: boolean;
  document: PresentationDocument;
  createdAt: string;
};

export type PendingRevision = {
  presentationId: string;
  actorScope: string;
  baseRevision: number;
  idempotencyKey: string;
  commands: EditorCommand[];
  createdAt: number;
  attempts: number;
};

export type RevisionConflict = {
  currentRevision: number;
  currentChecksum?: string;
};

export class RevisionClientError extends Error {
  constructor(
    readonly code: string,
    readonly status: number,
    readonly params: Record<string, unknown> = {},
  ) {
    super(code);
    this.name = "RevisionClientError";
  }
}
