import type { EditorCommand } from "@/components/editor/commands";
import type { RendererCapabilityStatus } from "@/renderers/shared/capability";
import { useEffect, useRef } from "react";

export type EditorMetric = Readonly<{
  renderer: "konva" | "browser" | "legacy";
  schemaVersion: "1.0.0";
  slideCountBucket: "1-10" | "11-30" | "31-50" | "50+";
  elementCountBucket: "0-100" | "101-1000" | "1001-3000" | "3000+";
  commandType?: EditorCommand["type"];
  commandStatus?: "success" | "failure";
  undoDepthBucket?: "0" | "1-10" | "11-50" | "51-100" | "100+";
  frameTimeBucket?: "0-16" | "17-33" | "34-100" | "100+";
  assetLoadStatus?: "ready" | "fallback" | "failed";
  parityStatus?: RendererCapabilityStatus;
  longTaskCount?: number;
}>;

export type EditorMetricSink = (metric: EditorMetric) => void;

export function countBucket(count: number, boundaries: [number, number, number], labels: [string, string, string, string]) {
  if (count <= boundaries[0]) return labels[0];
  if (count <= boundaries[1]) return labels[1];
  if (count <= boundaries[2]) return labels[2];
  return labels[3];
}

export function frameTimeBucket(milliseconds: number): EditorMetric["frameTimeBucket"] {
  if (milliseconds <= 16) return "0-16";
  if (milliseconds <= 33) return "17-33";
  if (milliseconds <= 100) return "34-100";
  return "100+";
}

export function useEditorPerformanceObserver(
  base: EditorMetric,
  sink?: EditorMetricSink,
) {
  const baseRef = useRef(base);
  useEffect(() => { baseRef.current = base; }, [base]);
  useEffect(() => {
    if (!sink || typeof window === "undefined") return;
    let frame = 0;
    let previous = performance.now();
    let accumulated = 0;
    let samples = 0;
    const tick = (now: number) => {
      if (samples > 0) accumulated += now - previous;
      previous = now;
      samples += 1;
      if (samples >= 60) {
        sink({ ...baseRef.current, frameTimeBucket: frameTimeBucket(accumulated / 59) });
        accumulated = 0;
        samples = 0;
      }
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    let longTasks = 0;
    const observer = typeof PerformanceObserver !== "undefined"
      ? new PerformanceObserver((list) => {
        longTasks += list.getEntries().length;
        sink({ ...baseRef.current, longTaskCount: Math.min(longTasks, 10_000) });
      })
      : null;
    try { observer?.observe({ entryTypes: ["longtask"] }); } catch { observer?.disconnect(); }
    return () => {
      window.cancelAnimationFrame(frame);
      observer?.disconnect();
    };
  }, [sink]);
}

export function editorDeckMetric(
  renderer: EditorMetric["renderer"],
  slideCount: number,
  elementCount: number,
): EditorMetric {
  return {
    renderer,
    schemaVersion: "1.0.0",
    slideCountBucket: countBucket(slideCount, [10, 30, 50], ["1-10", "11-30", "31-50", "50+"]) as EditorMetric["slideCountBucket"],
    elementCountBucket: countBucket(elementCount, [100, 1000, 3000], ["0-100", "101-1000", "1001-3000", "3000+"]) as EditorMetric["elementCountBucket"],
  };
}
