"use client";

import { useEffect } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import type { Direction, Paragraph, TextElement } from "@/generated/presentation-document";
import { createEditorCommandId, type EditorCommand } from "@/components/editor/commands";
import { createCanonicalStableId } from "@/components/editor/clipboard/stable-id";
import { textFromParagraphs } from "@/renderers/shared/direction";
import { useTranslations } from "@/i18n/catalog";

export function CanonicalTextEditor({
  element,
  slideId,
  defaultDirection,
  onCommand,
  onClose,
}: {
  element: TextElement;
  slideId: string;
  defaultDirection: Direction;
  onCommand: (command: EditorCommand) => void;
  onClose: () => void;
}) {
  const t = useTranslations();
  const editor = useEditor({
    extensions: [StarterKit.configure({ heading: false, codeBlock: false, blockquote: false, horizontalRule: false })],
    content: textFromParagraphs(element.paragraphs),
    immediatelyRender: false,
    editorProps: { attributes: { role: "textbox", "aria-multiline": "true", class: "min-h-24 rounded border p-2 outline-none" } },
  });
  useEffect(() => {
    if (!editor || editor.isFocused) return;
    const next = textFromParagraphs(element.paragraphs);
    if (editor.getText({ blockSeparator: "\n" }) !== next) editor.commands.setContent(next);
  }, [editor, element.paragraphs]);
  if (!editor) return null;
  const commit = () => {
    const text = editor.getText({ blockSeparator: "\n" });
    if (text !== textFromParagraphs(element.paragraphs)) {
      onCommand({
        commandId: createEditorCommandId("text"),
        type: "UPDATE_TEXT",
        targetIds: [element.id],
        payload: { slideId, paragraphs: paragraphsFromText(text, element.paragraphs, defaultDirection) },
      });
    }
    onClose();
  };
  return <div className="space-y-2 p-2" dir={defaultDirection === "rtl" ? "rtl" : "ltr"}>
    <EditorContent editor={editor} onBlur={commit} />
    <button type="button" className="rounded border px-2 py-1 text-xs" onClick={commit}>{t("editor.doneEditing")}</button>
  </div>;
}

function paragraphsFromText(text: string, previous: Paragraph[], direction: Direction): Paragraph[] {
  return text.split("\n").map((line, index) => {
    const prior = previous[index];
    const firstRun = prior?.runs[0];
    return {
      id: prior?.id ?? createCanonicalStableId(),
      direction: prior?.direction ?? direction,
      logicalAlignment: prior?.logicalAlignment ?? "start",
      runs: [{
        ...(firstRun ?? {}),
        id: firstRun?.id ?? createCanonicalStableId(),
        text: line,
      }],
    };
  });
}
