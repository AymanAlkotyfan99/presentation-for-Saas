import { Group, Rect, Text } from "react-konva";
import type { Element as CanonicalElement } from "@/generated/presentation-document";

export function BasicPlaceholder({ element }: { element: CanonicalElement }) {
  return <Group listening={false}>
    <Rect width={element.geometry.width} height={element.geometry.height} fill="#FEF2F2" stroke="#DC2626" dash={[8, 4]} />
    <Text width={element.geometry.width} height={element.geometry.height} text={`Unsupported: ${String(element.type)}`} align="center" verticalAlign="middle" fill="#991B1B" fontSize={14} />
  </Group>;
}
