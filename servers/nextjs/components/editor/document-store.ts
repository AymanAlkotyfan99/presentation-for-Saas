"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";
import type { PresentationDocument } from "@/generated/presentation-document";
import { assertPresentationDocument } from "@/lib/presentation-document/validate";
import type { EditorCommand } from "@/components/editor/commands";
import {
  createEditorHistory,
  executeEditorCommand,
  redoEditorCommand,
  replaceHistoryDocument,
  undoEditorCommand,
  type EditorHistoryState,
} from "@/components/editor/history/history";
import { sanitizeSelection, type SelectionState } from "@/components/editor/selection/selection";
import { DEFAULT_EDITOR_VIEWPORT, type EditorGuide, type EditorInteractionMode, type EditorViewModel, type EditorViewport, type TemporaryElementTransform } from "./types";

type StoreState = {
  history: EditorHistoryState;
  activeSlideId: string;
  selection: SelectionState;
  hoveredElementId: string | null;
  editingTextElementId: string | null;
  viewport: EditorViewport;
  guides: EditorGuide[];
  temporaryTransforms: Record<string, TemporaryElementTransform>;
  interactionMode: EditorInteractionMode;
};

type StoreAction =
  | { type: "EXECUTE"; command: EditorCommand; history?: EditorHistoryState }
  | { type: "UNDO" }
  | { type: "REDO" }
  | { type: "RESET_DOCUMENT"; document: PresentationDocument }
  | { type: "ACTIVE_SLIDE"; slideId: string }
  | { type: "SELECTION"; selection: SelectionState }
  | { type: "HOVER"; elementId: string | null }
  | { type: "TEXT_EDIT"; elementId: string | null }
  | { type: "VIEWPORT"; viewport: EditorViewport }
  | { type: "INTERACTION"; mode: EditorInteractionMode; guides?: EditorGuide[]; transforms?: Record<string, TemporaryElementTransform> }
  | { type: "CANCEL_INTERACTION" };

function initialState(document: PresentationDocument, historyLimit: number): StoreState {
  const valid = assertPresentationDocument(document);
  return {
    history: createEditorHistory(valid, historyLimit),
    activeSlideId: [...valid.slides].sort((a, b) => a.order - b.order)[0]!.id,
    selection: { selectedIds: [], anchorId: null },
    hoveredElementId: null,
    editingTextElementId: null,
    viewport: { ...DEFAULT_EDITOR_VIEWPORT },
    guides: [],
    temporaryTransforms: {},
    interactionMode: "select",
  };
}

function reducer(state: StoreState, action: StoreAction): StoreState {
  switch (action.type) {
    case "EXECUTE": {
      const history = action.history ?? executeEditorCommand(state.history, action.command);
      return {
        ...state,
        history,
        selection: sanitizeSelection(history.present, state.selection),
        guides: [],
        temporaryTransforms: {},
        interactionMode: "select",
      };
    }
    case "UNDO": {
      const history = undoEditorCommand(state.history);
      return { ...state, history, selection: sanitizeSelection(history.present, state.selection) };
    }
    case "REDO": {
      const history = redoEditorCommand(state.history);
      return { ...state, history, selection: sanitizeSelection(history.present, state.selection) };
    }
    case "RESET_DOCUMENT": {
      const document = assertPresentationDocument(action.document);
      return {
        ...state,
        history: replaceHistoryDocument(state.history, document),
        activeSlideId: document.slides.some((slide) => slide.id === state.activeSlideId)
          ? state.activeSlideId
          : document.slides[0]!.id,
        selection: sanitizeSelection(document, state.selection),
      };
    }
    case "ACTIVE_SLIDE":
      return state.history.present.slides.some((slide) => slide.id === action.slideId)
        ? { ...state, activeSlideId: action.slideId, selection: { selectedIds: [], anchorId: null }, editingTextElementId: null }
        : state;
    case "SELECTION":
      return { ...state, selection: sanitizeSelection(state.history.present, action.selection) };
    case "HOVER":
      return { ...state, hoveredElementId: action.elementId };
    case "TEXT_EDIT":
      return { ...state, editingTextElementId: action.elementId, interactionMode: action.elementId ? "text-edit" : "select" };
    case "VIEWPORT":
      return { ...state, viewport: action.viewport };
    case "INTERACTION":
      return { ...state, interactionMode: action.mode, guides: action.guides ?? state.guides, temporaryTransforms: action.transforms ?? state.temporaryTransforms };
    case "CANCEL_INTERACTION":
      return { ...state, interactionMode: "select", guides: [], temporaryTransforms: {} };
  }
}

export function canonicalToEditorViewModel(
  document: PresentationDocument,
  options: { activeSlideId?: string; historyLimit?: number } = {},
): EditorViewModel {
  const state = initialState(document, options.historyLimit ?? 100);
  if (options.activeSlideId && document.slides.some((slide) => slide.id === options.activeSlideId)) {
    state.activeSlideId = options.activeSlideId;
  }
  return stateToViewModel(state);
}

export function editorViewModelToCanonicalOperation(
  viewModel: EditorViewModel,
  command: EditorCommand,
) {
  return { document: viewModel.document, command };
}

export function useCanonicalEditorStore({
  document,
  historyLimit = 100,
  onDocumentChange,
  onCommandError,
}: {
  document: PresentationDocument;
  historyLimit?: number;
  onDocumentChange?: (document: PresentationDocument, command?: EditorCommand) => void;
  onCommandError?: (command: EditorCommand, error: unknown) => void;
}) {
  const [state, dispatch] = useReducer(reducer, undefined, () => initialState(document, historyLimit));
  const externalDocumentRef = useRef(document);
  const lastEmittedDocumentRef = useRef<PresentationDocument | null>(null);
  const pendingCommandRef = useRef<EditorCommand | undefined>(undefined);

  useEffect(() => {
    if (document === externalDocumentRef.current) return;
    externalDocumentRef.current = document;
    if (document === lastEmittedDocumentRef.current) return;
    dispatch({ type: "RESET_DOCUMENT", document });
  }, [document]);

  const execute = useCallback((command: EditorCommand) => {
    try {
      const history = executeEditorCommand(state.history, command);
      pendingCommandRef.current = command;
      dispatch({ type: "EXECUTE", command, history });
    } catch (error) {
      onCommandError?.(command, error);
      throw error;
    }
  }, [onCommandError, state.history]);
  const viewModel = useMemo(() => stateToViewModel(state), [state]);

  useEffect(() => {
    if (state.history.present === externalDocumentRef.current) return;
    if (state.history.present === lastEmittedDocumentRef.current) return;
    lastEmittedDocumentRef.current = state.history.present;
    const command = pendingCommandRef.current;
    pendingCommandRef.current = undefined;
    onDocumentChange?.(state.history.present, command);
  }, [onDocumentChange, state.history.present]);
  const undo = useCallback(() => dispatch({ type: "UNDO" }), []);
  const redo = useCallback(() => dispatch({ type: "REDO" }), []);
  const setActiveSlide = useCallback((slideId: string) => dispatch({ type: "ACTIVE_SLIDE", slideId }), []);
  const setSelection = useCallback((selection: SelectionState) => dispatch({ type: "SELECTION", selection }), []);
  const setHoveredElement = useCallback((elementId: string | null) => dispatch({ type: "HOVER", elementId }), []);
  const setEditingTextElement = useCallback((elementId: string | null) => dispatch({ type: "TEXT_EDIT", elementId }), []);
  const setViewport = useCallback((viewport: EditorViewport) => dispatch({ type: "VIEWPORT", viewport }), []);
  const setInteraction = useCallback((mode: EditorInteractionMode, guides?: EditorGuide[], transforms?: Record<string, TemporaryElementTransform>) => dispatch({ type: "INTERACTION", mode, guides, transforms }), []);
  const cancelInteraction = useCallback(() => dispatch({ type: "CANCEL_INTERACTION" }), []);
  return {
    viewModel,
    canUndo: state.history.past.length > 0,
    canRedo: state.history.future.length > 0,
    historyDepth: state.history.past.length,
    execute,
    undo,
    redo,
    setActiveSlide,
    setSelection,
    setHoveredElement,
    setEditingTextElement,
    setViewport,
    setInteraction,
    cancelInteraction,
  };
}

function stateToViewModel(state: StoreState): EditorViewModel {
  return {
    document: state.history.present,
    activeSlideId: state.activeSlideId,
    selectedElementIds: state.selection.selectedIds,
    hoveredElementId: state.hoveredElementId,
    editingTextElementId: state.editingTextElementId,
    viewport: state.viewport,
    guides: state.guides,
    temporaryTransforms: state.temporaryTransforms,
    interactionMode: state.interactionMode,
  };
}
