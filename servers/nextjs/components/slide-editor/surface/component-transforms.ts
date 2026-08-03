import type Konva from "konva";
import { TRANSFORM_ANCHOR_ATTR } from "@/components/slide-editor/selection/transformSession";
import {
  componentSideResizeBox,
  resizeComponentFromSideTransform,
  type ComponentSideResizeAnchor,
} from "@/components/slide-editor/model/component-resize";
import {
  clamp,
  componentBox,
  positionFromNodeInParent,
  readString,
  resizeComponent,
  resizeComponentElementBounds,
  resizeComponentFrame,
  STAGE_BOX,
  type Box,
  type Point,
  type RawComponent,
} from "@/components/slide-editor/model/model";

export type ComponentTransformAnchor =
  | "top-left" | "top-center" | "top-right"
  | "middle-left" | "middle-right"
  | "bottom-left" | "bottom-center" | "bottom-right"
  | "rotater";

type ComponentResizeMode = "scale-content" | "resize-element-bounds" | "resize-frame";
type ComponentTransformBox = Box & { scaleX: number; scaleY: number; rawWidth: number; rawHeight: number };
type ComponentSideTransformTarget = { anchor: ComponentSideResizeAnchor; box: Box; rotation: number };
export type ComponentSideTransformPreview = { source: RawComponent; sourceBox: Box; target: ComponentSideTransformTarget };

const HORIZONTAL_ANCHORS = new Set<ComponentTransformAnchor>(["middle-left", "middle-right"]);
const VERTICAL_ANCHORS = new Set<ComponentTransformAnchor>(["top-center", "bottom-center"]);

export function isComponentSideResizeAnchor(anchor: ComponentTransformAnchor | null): anchor is ComponentSideResizeAnchor {
  return Boolean(anchor && (HORIZONTAL_ANCHORS.has(anchor) || VERTICAL_ANCHORS.has(anchor)));
}

export function isTopOrLeftSideResizeAnchor(anchor: ComponentSideResizeAnchor) {
  return anchor === "top-center" || anchor === "middle-left";
}

export function hasTransformScale(node: Konva.Node) {
  return Math.abs(node.scaleX() - 1) >= 0.001 || Math.abs(node.scaleY() - 1) >= 0.001;
}

function transformerForNode(node: Konva.Node) {
  const stage = node.getStage();
  return stage?.find<Konva.Transformer>("Transformer").find((candidate) => candidate.getNodes().includes(node)) ?? null;
}

function isTransformAnchor(value: string | null | undefined): value is ComponentTransformAnchor {
  return ["top-left", "top-center", "top-right", "middle-left", "middle-right", "bottom-left", "bottom-center", "bottom-right", "rotater"].includes(value ?? "");
}

export function componentTransformAnchorForNode(node: Konva.Node): ComponentTransformAnchor | null {
  const active = transformerForNode(node)?.getActiveAnchor() ?? readString(node.getAttr(TRANSFORM_ANCHOR_ATTR));
  return isTransformAnchor(active) ? active : null;
}

function resizeMode(anchor: ComponentTransformAnchor | null, scaleX: number, scaleY: number): ComponentResizeMode {
  if (anchor === "rotater") return "resize-frame";
  if (anchor && (HORIZONTAL_ANCHORS.has(anchor) || VERTICAL_ANCHORS.has(anchor))) return "resize-element-bounds";
  if (anchor) return "scale-content";
  const changedX = Math.abs(scaleX - 1) > 0.001;
  const changedY = Math.abs(scaleY - 1) > 0.001;
  if (changedX && changedY) return "scale-content";
  if (changedX || changedY) return "resize-element-bounds";
  return "resize-frame";
}

function transformedBox(box: Box, scaleX: number, scaleY: number, anchor: ComponentTransformAnchor | null): ComponentTransformBox {
  const nextScaleX = (anchor && VERTICAL_ANCHORS.has(anchor)) || anchor === "rotater" ? 1 : scaleX;
  const nextScaleY = (anchor && HORIZONTAL_ANCHORS.has(anchor)) || anchor === "rotater" ? 1 : scaleY;
  const rawWidth = Math.max(1, box.width * nextScaleX);
  const rawHeight = Math.max(1, box.height * nextScaleY);
  return { ...box, width: rawWidth, height: rawHeight, scaleX: box.width > 0 ? rawWidth / box.width : 1, scaleY: box.height > 0 ? rawHeight / box.height : 1, rawWidth, rawHeight };
}

function positionFromTransform(box: Box, node: Konva.Node, next: ComponentTransformBox, anchor: ComponentTransformAnchor | null): Point {
  if (isComponentSideResizeAnchor(anchor)) {
    return { x: clamp(box.x, 0, Math.max(0, STAGE_BOX.width - next.width)), y: clamp(box.y, 0, Math.max(0, STAGE_BOX.height - next.height)) };
  }
  const raw = positionFromNodeInParent(node, STAGE_BOX, { ...next, width: next.rawWidth, height: next.rawHeight });
  return { x: clamp(raw.x, 0, Math.max(0, STAGE_BOX.width - next.width)), y: clamp(raw.y, 0, Math.max(0, STAGE_BOX.height - next.height)) };
}

export function componentFromNodeTransform(component: RawComponent, node: Konva.Group, anchor: ComponentTransformAnchor | null) {
  const box = componentBox(component);
  const next = transformedBox(box, node.scaleX(), node.scaleY(), anchor);
  const mode = resizeMode(anchor, node.scaleX(), node.scaleY());
  node.scaleX(1); node.scaleY(1);
  const nextBox = { ...positionFromTransform(box, node, next, anchor), width: next.width, height: next.height, rotation: node.rotation() };
  if (mode === "resize-frame") return resizeComponentFrame(component, nextBox);
  if (mode === "resize-element-bounds") return resizeComponentElementBounds(component, { ...nextBox, scaleX: next.scaleX, scaleY: next.scaleY });
  return resizeComponent(component, { ...nextBox, scaleX: next.scaleX, scaleY: next.scaleY });
}

function syncNodeBox(node: Konva.Group, box: Box) {
  node.setAttrs({ x: box.x + box.width / 2, y: box.y + box.height / 2, width: box.width, height: box.height, offsetX: box.width / 2, offsetY: box.height / 2, scaleX: 1, scaleY: 1 });
  transformerForNode(node)?.forceUpdate();
  node.getLayer()?.batchDraw();
}

export function componentSideTransformTargetFromNode(node: Konva.Group, anchor: ComponentSideResizeAnchor, sourceBox: Box) {
  const box = componentSideResizeBox(sourceBox, { width: Math.max(1, node.width() * node.scaleX()), height: Math.max(1, node.height() * node.scaleY()) }, anchor, STAGE_BOX);
  syncNodeBox(node, box);
  return { anchor, box, rotation: node.rotation() };
}

export function componentFromSideTransformPreview({ source, sourceBox, target }: ComponentSideTransformPreview) {
  return resizeComponentFromSideTransform(source, sourceBox, { width: target.box.width, height: target.box.height }, target.anchor, STAGE_BOX, target.rotation).component;
}
