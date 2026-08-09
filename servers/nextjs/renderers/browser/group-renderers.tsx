import type { ContainerElement, GroupElement } from "@/generated/presentation-document";
import type { BrowserElementRendererProps } from "./types";

export function BrowserGroupRenderer({ element, context }: BrowserElementRendererProps<GroupElement>) {
  return <div style={{ position: "relative", width: "100%", height: "100%", overflow: "hidden" }}>
    {[...element.children].sort((a, b) => a.zOrder - b.zOrder).map(context.renderElement)}
  </div>;
}

export function BrowserContainerRenderer({ element, context }: BrowserElementRendererProps<ContainerElement>) {
  return <div style={{ position: "relative", width: "100%", height: "100%", overflow: "hidden" }} data-layout-intent={element.layoutIntent}>
    {[...element.children].sort((a, b) => a.zOrder - b.zOrder).map(context.renderElement)}
  </div>;
}
