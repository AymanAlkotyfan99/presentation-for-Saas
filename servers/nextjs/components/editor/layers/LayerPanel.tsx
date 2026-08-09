"use client";

import { useMemo } from "react";
import { Eye, EyeOff, Lock, Unlock } from "lucide-react";
import type { Slide } from "@/generated/presentation-document";
import type { EditorCommand } from "@/components/editor/commands";
import { createEditorCommandId } from "@/components/editor/commands";
import { useTranslations } from "@/i18n/catalog";
import { buildLayerTree, layerOrderCommand, type LayerNode, type LayerOrderAction } from "./layers";

export function LayerPanel({
  slide,
  selectedIds,
  onSelect,
  onCommand,
}: {
  slide: Slide;
  selectedIds: string[];
  onSelect: (id: string, additive: boolean) => void;
  onCommand: (command: EditorCommand) => void;
}) {
  const t = useTranslations();
  const tree = useMemo(() => buildLayerTree(slide), [slide]);
  const reorder = (node: LayerNode, action: LayerOrderAction) => {
    const command = layerOrderCommand(slide, node.id, action, createEditorCommandId("layer"), node.parentId ?? undefined);
    if (command) onCommand(command);
  };
  return (
    <aside aria-label={t("editor.layers.title")} className="flex min-w-64 flex-col gap-1 overflow-auto p-2">
      <h2 className="px-2 text-sm font-semibold">{t("editor.layers.title")}</h2>
      <div role="tree" aria-multiselectable="true">
        {tree.map((node) => <LayerRow key={node.id} slideId={slide.id} node={node} selectedIds={selectedIds} onSelect={onSelect} onCommand={onCommand} onReorder={reorder} />)}
      </div>
    </aside>
  );
}

function LayerRow({
  node,
  slideId,
  selectedIds,
  onSelect,
  onCommand,
  onReorder,
}: {
  node: LayerNode;
  slideId: string;
  selectedIds: string[];
  onSelect: (id: string, additive: boolean) => void;
  onCommand: (command: EditorCommand) => void;
  onReorder: (node: LayerNode, action: LayerOrderAction) => void;
}) {
  const t = useTranslations();
  const selected = selectedIds.includes(node.id);
  const toggle = (type: "LOCK_ELEMENTS" | "UNLOCK_ELEMENTS" | "HIDE_ELEMENTS" | "SHOW_ELEMENTS") => onCommand({
    commandId: createEditorCommandId("layer-toggle"),
    type,
    targetIds: [node.id],
    payload: { slideId },
  } as EditorCommand);
  return (
    <div role="treeitem" aria-selected={selected} aria-expanded={node.children.length ? true : undefined}>
      <div className={`group flex items-center gap-1 rounded px-1 py-1 ${selected ? "bg-accent" : ""}`} style={{ paddingInlineStart: `${node.depth * 12 + 4}px` }}>
        <button className="min-w-0 flex-1 truncate text-start text-xs" onClick={(event) => onSelect(node.id, event.shiftKey)} aria-label={t("editor.layers.select", { type: node.type })}>
          <span aria-hidden="true">{node.type}</span> <bdi>{node.id.slice(0, 8)}</bdi>
        </button>
        <button onClick={() => toggle(node.hidden ? "SHOW_ELEMENTS" : "HIDE_ELEMENTS")} aria-label={t(node.hidden ? "editor.layers.show" : "editor.layers.hide")}>
          {node.hidden ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
        <button onClick={() => toggle(node.locked ? "UNLOCK_ELEMENTS" : "LOCK_ELEMENTS")} aria-label={t(node.locked ? "editor.layers.unlock" : "editor.layers.lock")}>
          {node.locked ? <Lock size={14} /> : <Unlock size={14} />}
        </button>
        <button onClick={() => onReorder(node, "forward")} aria-label={t("editor.layers.forward")}>↑</button>
        <button onClick={() => onReorder(node, "backward")} aria-label={t("editor.layers.backward")}>↓</button>
      </div>
      {node.children.map((child) => <LayerRow key={child.id} slideId={slideId} node={child} selectedIds={selectedIds} onSelect={onSelect} onCommand={onCommand} onReorder={onReorder} />)}
    </div>
  );
}
