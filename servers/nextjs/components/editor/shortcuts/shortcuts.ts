export type EditorShortcutAction =
  | "undo"
  | "redo"
  | "copy"
  | "paste"
  | "duplicate"
  | "delete"
  | "nudge-left"
  | "nudge-right"
  | "nudge-up"
  | "nudge-down"
  | "select-all"
  | "escape"
  | "zoom-in"
  | "zoom-out"
  | "zoom-reset";

export function editorShortcut(event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey" | "target">): EditorShortcutAction | null {
  if (isTypingTarget(event.target) && event.key !== "Escape") return null;
  const command = event.ctrlKey || event.metaKey;
  const key = event.key.toLowerCase();
  if (command && key === "z") return event.shiftKey ? "redo" : "undo";
  if (command && key === "y") return "redo";
  if (command && key === "c") return "copy";
  if (command && key === "v") return "paste";
  if (command && key === "d") return "duplicate";
  if (command && key === "a") return "select-all";
  if (command && (key === "+" || key === "=")) return "zoom-in";
  if (command && key === "-") return "zoom-out";
  if (command && key === "0") return "zoom-reset";
  if (event.key === "Delete" || event.key === "Backspace") return "delete";
  if (event.key === "Escape") return "escape";
  if (event.key === "ArrowLeft") return "nudge-left";
  if (event.key === "ArrowRight") return "nudge-right";
  if (event.key === "ArrowUp") return "nudge-up";
  if (event.key === "ArrowDown") return "nudge-down";
  return null;
}

export function nudgeDistance(shiftKey: boolean) {
  return shiftKey ? 10 : 1;
}

function isTypingTarget(target: EventTarget | null) {
  if (typeof HTMLElement === "undefined") return false;
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}
