"use client";

import { useEffect, useState } from "react";
import { Group, Image as KonvaImage, Rect, Text } from "react-konva";
import type { IconElement, ImageElement } from "@/generated/presentation-document";
import type { KonvaElementRendererProps } from "./types";
import { rendererStyle } from "@/renderers/shared/style";
import { isSafeScopedAssetUrl } from "@/renderers/shared/asset-resolver";

export function ImageRenderer({ element, context }: KonvaElementRendererProps<ImageElement>) {
  const candidateUrl = context.assetUrls[element.assetId];
  const url = candidateUrl && isSafeScopedAssetUrl(candidateUrl) ? candidateUrl : undefined;
  const image = useScopedImage(url);
  const style = rendererStyle(element);
  if (!image) return <AssetPlaceholder width={element.geometry.width} height={element.geometry.height} label={url ? "Loading image" : "Unavailable image"} />;
  return <KonvaImage image={image} width={element.geometry.width} height={element.geometry.height} opacity={style.opacity} cornerRadius={style.cornerRadius} imageSmoothingEnabled listening={context.interactive} />;
}

export function IconRenderer({ element, context }: KonvaElementRendererProps<IconElement>) {
  if (element.assetId) {
    const imageElement: ImageElement = { ...element, type: "image", assetId: element.assetId, fit: "contain" };
    return <ImageRenderer element={imageElement} context={context} />;
  }
  return <AssetPlaceholder width={element.geometry.width} height={element.geometry.height} label={element.iconName ?? "Icon"} />;
}

function useScopedImage(url: string | undefined) {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  useEffect(() => {
    if (!url || typeof window === "undefined") {
      setImage(null);
      return;
    }
    const candidate = new window.Image();
    candidate.decoding = "async";
    candidate.onload = () => setImage(candidate);
    candidate.onerror = () => setImage(null);
    candidate.src = url;
    return () => {
      candidate.onload = null;
      candidate.onerror = null;
    };
  }, [url]);
  return image;
}

export function AssetPlaceholder({ width, height, label }: { width: number; height: number; label: string }) {
  return <Group listening={false}>
    <Rect width={width} height={height} fill="#F3F4F6" stroke="#9CA3AF" dash={[6, 4]} />
    <Text width={width} height={height} text={label} align="center" verticalAlign="middle" fill="#4B5563" fontSize={Math.min(16, Math.max(10, height / 5))} />
  </Group>;
}
