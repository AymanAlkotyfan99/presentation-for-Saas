import { Line } from "react-konva";
import type { EditorGuide } from "@/components/editor/types";

export function GuideOverlay({ guides, zoom }: { guides: EditorGuide[]; zoom: number }) {
  return <>
    {guides.map((guide) => <Line
      key={guide.id}
      points={guide.axis === "x"
        ? [guide.position, guide.start, guide.position, guide.end]
        : [guide.start, guide.position, guide.end, guide.position]}
      stroke="#E11D48"
      strokeWidth={1 / Math.max(zoom, 0.01)}
      dash={[4 / Math.max(zoom, 0.01), 3 / Math.max(zoom, 0.01)]}
      listening={false}
      perfectDrawEnabled={false}
    />)}
  </>;
}
