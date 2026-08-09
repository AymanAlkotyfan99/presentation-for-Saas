import type { PresentationDocument } from "@/generated/presentation-document";
import {
  applyCommandToValidDocument,
  type EditorCommand,
  type EditorInverseCommand,
} from "@/components/editor/commands";
import { assertPresentationDocument } from "@/lib/presentation-document/validate";

export type EditorHistoryEntry = {
  command: EditorCommand;
  inverse: EditorInverseCommand;
  before: PresentationDocument;
  after: PresentationDocument;
};

export type EditorHistoryState = {
  present: PresentationDocument;
  past: EditorHistoryEntry[];
  future: EditorHistoryEntry[];
  limit: number;
};

export function createEditorHistory(
  document: PresentationDocument,
  limit = 100,
): EditorHistoryState {
  if (!Number.isInteger(limit) || limit < 1 || limit > 500) {
    throw new RangeError("EDITOR_HISTORY_LIMIT_INVALID");
  }
  return { present: assertPresentationDocument(document), past: [], future: [], limit };
}

export function executeEditorCommand(
  state: EditorHistoryState,
  command: EditorCommand,
): EditorHistoryState {
  const before = state.present;
  const after = applyCommandToValidDocument(before, command);
  if (after === before) return state;
  const entry: EditorHistoryEntry = {
    command,
    inverse: restoreInverse(before, command),
    before,
    after,
  };
  return {
    ...state,
    present: after,
    past: [...state.past, entry].slice(-state.limit),
    future: [],
  };
}

export function executeEditorCommandBatch(
  state: EditorHistoryState,
  commandId: string,
  commands: EditorCommand[],
): EditorHistoryState {
  const before = state.present;
  const batch: EditorCommand = {
    commandId,
    type: "BATCH",
    targetIds: [...new Set(commands.flatMap((command) => command.targetIds))],
    payload: { commands },
  };
  const after = applyCommandToValidDocument(before, batch);
  if (after === before) return state;
  const entry: EditorHistoryEntry = {
    command: batch,
    inverse: {
      commandId: `${commandId}:inverse`,
      type: "RESTORE_DOCUMENT",
      targetIds: batch.targetIds,
      payload: { document: before },
    },
    before,
    after,
  };
  return {
    ...state,
    present: after,
    past: [...state.past, entry].slice(-state.limit),
    future: [],
  };
}

export function undoEditorCommand(state: EditorHistoryState): EditorHistoryState {
  const entry = state.past.at(-1);
  if (!entry) return state;
  return {
    ...state,
    present: entry.before,
    past: state.past.slice(0, -1),
    future: [entry, ...state.future].slice(0, state.limit),
  };
}

export function redoEditorCommand(state: EditorHistoryState): EditorHistoryState {
  const entry = state.future[0];
  if (!entry) return state;
  return {
    ...state,
    present: entry.after,
    past: [...state.past, entry].slice(-state.limit),
    future: state.future.slice(1),
  };
}

export function replaceHistoryDocument(
  state: EditorHistoryState,
  document: PresentationDocument,
): EditorHistoryState {
  return { ...state, present: document, past: [], future: [] };
}

export function historyDepthBucket(depth: number): "0" | "1-10" | "11-50" | "51-100" | "100+" {
  if (depth <= 0) return "0";
  if (depth <= 10) return "1-10";
  if (depth <= 50) return "11-50";
  if (depth <= 100) return "51-100";
  return "100+";
}

function restoreInverse(before: PresentationDocument, command: EditorCommand): EditorInverseCommand {
  return {
    commandId: `${command.commandId}:inverse`,
    type: "RESTORE_DOCUMENT",
    targetIds: [...command.targetIds],
    payload: { document: before },
  };
}
