import { Group, Rect } from "react-konva";
import type { ContainerElement, GroupElement } from "@/generated/presentation-document";
import type { KonvaElementRendererProps } from "./types";
import { rendererStyle } from "@/renderers/shared/style";

export function GroupRenderer({ element, context }: KonvaElementRendererProps<GroupElement>) {
  const style = rendererStyle(element);
  return <Group clipX={0} clipY={0} clipWidth={element.geometry.width} clipHeight={element.geometry.height}>
    {(element.style?.fill || element.style?.stroke) && <Rect width={element.geometry.width} height={element.geometry.height} {...style} listening={false} />}
    {[...element.children].sort((a, b) => a.zOrder - b.zOrder).map((child) => context.renderElement(child))}
  </Group>;
}

export function ContainerRenderer({ element, context }: KonvaElementRendererProps<ContainerElement>) {
  const style = rendererStyle(element);
  return <Group clipX={0} clipY={0} clipWidth={element.geometry.width} clipHeight={element.geometry.height}>
    <Rect width={element.geometry.width} height={element.geometry.height} {...style} listening={false} />
    {[...element.children].sort((a, b) => a.zOrder - b.zOrder).map((child) => context.renderElement(child))}
  </Group>;
}
