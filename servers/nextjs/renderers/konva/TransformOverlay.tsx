"use client";

import { useEffect, useRef } from "react";
import type Konva from "konva";
import { Transformer } from "react-konva";
import type { Geometry } from "@/generated/presentation-document";

export function TransformOverlay({
  stage,
  selectedElementId,
  locked,
  zoom,
  onCommit,
}: {
  stage: Konva.Stage | null;
  selectedElementId: string | null;
  locked: boolean;
  zoom: number;
  onCommit?: (elementId: string, geometry: Geometry, rotation: number) => void;
}) {
  const transformerRef = useRef<Konva.Transformer>(null);
  useEffect(() => {
    const transformer = transformerRef.current;
    if (!transformer || !stage || !selectedElementId || locked) {
      transformer?.nodes([]);
      return;
    }
    const node = stage.findOne(`#canonical-${selectedElementId}`);
    transformer.nodes(node ? [node] : []);
    transformer.getLayer()?.batchDraw();
  }, [locked, selectedElementId, stage]);
  if (!selectedElementId || locked) return null;
  return <Transformer
    ref={transformerRef}
    rotateEnabled
    flipEnabled={false}
    borderStroke="#2563EB"
    borderStrokeWidth={1 / Math.max(zoom, 0.01)}
    anchorSize={8 / Math.max(zoom, 0.01)}
    boundBoxFunc={(oldBox, nextBox) => nextBox.width >= 4 && nextBox.height >= 4 ? nextBox : oldBox}
    onTransformEnd={() => {
      const node = transformerRef.current?.nodes()[0];
      if (!node || !selectedElementId) return;
      const scaleX = Math.abs(node.scaleX());
      const scaleY = Math.abs(node.scaleY());
      const width = Math.max(1, node.width() * scaleX);
      const height = Math.max(1, node.height() * scaleY);
      const geometry = {
        x: node.x() - width / 2,
        y: node.y() - height / 2,
        width,
        height,
      };
      onCommit?.(selectedElementId, geometry, node.rotation());
      node.scale({ x: 1, y: 1 });
    }}
  />;
}
