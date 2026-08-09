import type {
  Element as CanonicalElement,
  Geometry,
  Paragraph,
  PresentationDocument,
  Slide,
  Style,
  Transform,
} from "@/generated/presentation-document";

export type EditorCommandType =
  | "ADD_ELEMENT"
  | "DELETE_ELEMENTS"
  | "DUPLICATE_ELEMENTS"
  | "UPDATE_ELEMENT"
  | "MOVE_ELEMENTS"
  | "RESIZE_ELEMENTS"
  | "ROTATE_ELEMENTS"
  | "REORDER_ELEMENTS"
  | "GROUP_ELEMENTS"
  | "UNGROUP_ELEMENTS"
  | "LOCK_ELEMENTS"
  | "UNLOCK_ELEMENTS"
  | "HIDE_ELEMENTS"
  | "SHOW_ELEMENTS"
  | "ALIGN_ELEMENTS"
  | "DISTRIBUTE_ELEMENTS"
  | "UPDATE_TEXT"
  | "UPDATE_STYLE"
  | "REPLACE_ASSET"
  | "ADD_SLIDE"
  | "DELETE_SLIDE"
  | "DUPLICATE_SLIDE"
  | "REORDER_SLIDES"
  | "UPDATE_SLIDE"
  | "BATCH";

type BaseCommand<T extends EditorCommandType> = {
  commandId: string;
  type: T;
  targetIds: string[];
};

export type MutableElementChanges = {
  geometry?: Geometry;
  transform?: Transform;
  style?: Style;
  locked?: boolean;
  hidden?: boolean;
  zOrder?: number;
};

export type MutableSlideChanges = Partial<
  Pick<
    Slide,
    | "title"
    | "semanticRole"
    | "background"
    | "layoutIntent"
    | "speakerNotes"
    | "locale"
    | "direction"
    | "transitionHint"
    | "exportCapabilities"
    | "compatibility"
  >
>;

export type AddElementCommand = BaseCommand<"ADD_ELEMENT"> & {
  payload: { slideId: string; element: CanonicalElement; parentId?: string };
};

export type DeleteElementsCommand = BaseCommand<"DELETE_ELEMENTS"> & {
  payload: { slideId: string };
};

export type DuplicateElementsCommand = BaseCommand<"DUPLICATE_ELEMENTS"> & {
  payload: {
    slideId: string;
    copies: Array<{ sourceId: string; element: CanonicalElement; parentId?: string }>;
  };
};

export type UpdateElementCommand = BaseCommand<"UPDATE_ELEMENT"> & {
  payload: { slideId: string; changes: MutableElementChanges };
};

export type MoveElementsCommand = BaseCommand<"MOVE_ELEMENTS"> & {
  payload: { slideId: string; deltaX: number; deltaY: number };
};

export type ResizeElementsCommand = BaseCommand<"RESIZE_ELEMENTS"> & {
  payload: { slideId: string; geometryById: Record<string, Geometry> };
};

export type RotateElementsCommand = BaseCommand<"ROTATE_ELEMENTS"> & {
  payload: { slideId: string; rotationById: Record<string, number> };
};

export type ReorderElementsCommand = BaseCommand<"REORDER_ELEMENTS"> & {
  payload: { slideId: string; orderedIds: string[]; parentId?: string };
};

export type GroupElementsCommand = BaseCommand<"GROUP_ELEMENTS"> & {
  payload: {
    slideId: string;
    group: Extract<CanonicalElement, { type: "group" }>;
    parentId?: string;
  };
};

export type UngroupElementsCommand = BaseCommand<"UNGROUP_ELEMENTS"> & {
  payload: { slideId: string };
};

export type ToggleElementsCommand<T extends "LOCK_ELEMENTS" | "UNLOCK_ELEMENTS" | "HIDE_ELEMENTS" | "SHOW_ELEMENTS"> =
  BaseCommand<T> & { payload: { slideId: string } };

export type AlignElementsCommand = BaseCommand<"ALIGN_ELEMENTS"> & {
  payload: {
    slideId: string;
    alignment: "start" | "center-horizontal" | "end" | "top" | "center-vertical" | "bottom";
  };
};

export type DistributeElementsCommand = BaseCommand<"DISTRIBUTE_ELEMENTS"> & {
  payload: { slideId: string; axis: "horizontal" | "vertical" };
};

export type UpdateTextCommand = BaseCommand<"UPDATE_TEXT"> & {
  payload: { slideId: string; paragraphs: Paragraph[] };
};

export type UpdateStyleCommand = BaseCommand<"UPDATE_STYLE"> & {
  payload: { slideId: string; style: Style };
};

export type ReplaceAssetCommand = BaseCommand<"REPLACE_ASSET"> & {
  payload: { slideId: string; assetId: string };
};

export type AddSlideCommand = BaseCommand<"ADD_SLIDE"> & {
  payload: { slide: Slide };
};

export type DeleteSlideCommand = BaseCommand<"DELETE_SLIDE"> & {
  payload: Record<string, never>;
};

export type DuplicateSlideCommand = BaseCommand<"DUPLICATE_SLIDE"> & {
  payload: { copies: Array<{ sourceId: string; slide: Slide }> };
};

export type ReorderSlidesCommand = BaseCommand<"REORDER_SLIDES"> & {
  payload: { orderedSlideIds: string[] };
};

export type UpdateSlideCommand = BaseCommand<"UPDATE_SLIDE"> & {
  payload: { changes: MutableSlideChanges };
};

export type BatchCommand = BaseCommand<"BATCH"> & {
  payload: { commands: EditorCommand[] };
};

export type EditorCommand =
  | AddElementCommand
  | DeleteElementsCommand
  | DuplicateElementsCommand
  | UpdateElementCommand
  | MoveElementsCommand
  | ResizeElementsCommand
  | RotateElementsCommand
  | ReorderElementsCommand
  | GroupElementsCommand
  | UngroupElementsCommand
  | ToggleElementsCommand<"LOCK_ELEMENTS">
  | ToggleElementsCommand<"UNLOCK_ELEMENTS">
  | ToggleElementsCommand<"HIDE_ELEMENTS">
  | ToggleElementsCommand<"SHOW_ELEMENTS">
  | AlignElementsCommand
  | DistributeElementsCommand
  | UpdateTextCommand
  | UpdateStyleCommand
  | ReplaceAssetCommand
  | AddSlideCommand
  | DeleteSlideCommand
  | DuplicateSlideCommand
  | ReorderSlidesCommand
  | UpdateSlideCommand
  | BatchCommand;

export type EditorInverseCommand = {
  commandId: string;
  type: "RESTORE_DOCUMENT";
  targetIds: string[];
  payload: { document: PresentationDocument };
};

export type EditorCommandValidationIssue = {
  code: string;
  targetId?: string;
  detail?: string;
};

export type EditorCommandValidationResult =
  | { ok: true }
  | { ok: false; issues: EditorCommandValidationIssue[] };
