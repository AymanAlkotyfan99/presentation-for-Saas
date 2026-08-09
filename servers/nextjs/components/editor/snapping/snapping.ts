import type { Element as CanonicalElement, Slide } from "@/generated/presentation-document";
import { elementChildren, rotatedBoundingBox, type BoundingBox } from "@/components/editor/commands/document-index";
import type { EditorGuide } from "@/components/editor/types";

export type SnapAxisCandidate = {
  position: number;
  start: number;
  end: number;
  sourceId: string;
  kind: EditorGuide["kind"];
};

export type SnapIndex = {
  x: SnapAxisCandidate[];
  y: SnapAxisCandidate[];
};

export type SnapResult = {
  deltaX: number;
  deltaY: number;
  guides: EditorGuide[];
};

export function buildSnapIndex(
  slide: Slide,
  slideWidth: number,
  slideHeight: number,
  excludedIds: ReadonlySet<string> = new Set(),
): SnapIndex {
  const x: SnapAxisCandidate[] = [
    candidate(0, 0, slideHeight, "slide:start", "slide-edge"),
    candidate(slideWidth / 2, 0, slideHeight, "slide:center-x", "slide-center"),
    candidate(slideWidth, 0, slideHeight, "slide:end", "slide-edge"),
  ];
  const y: SnapAxisCandidate[] = [
    candidate(0, 0, slideWidth, "slide:top", "slide-edge"),
    candidate(slideHeight / 2, 0, slideWidth, "slide:center-y", "slide-center"),
    candidate(slideHeight, 0, slideWidth, "slide:bottom", "slide-edge"),
  ];
  const stack = [...slide.elements];
  while (stack.length) {
    const element = stack.pop();
    if (!element) continue;
    if (!element.hidden && !excludedIds.has(element.id)) addElementCandidates(element, x, y);
    stack.push(...elementChildren(element));
  }
  x.sort((a, b) => a.position - b.position);
  y.sort((a, b) => a.position - b.position);
  return { x, y };
}

export function snapBoundingBox(
  box: BoundingBox,
  index: SnapIndex,
  options: { zoom: number; screenThreshold?: number; disabled?: boolean },
): SnapResult {
  if (options.disabled) return { deltaX: 0, deltaY: 0, guides: [] };
  const threshold = Math.max(0.5, (options.screenThreshold ?? 6) / Math.max(options.zoom, 0.01));
  const xAnchors = [box.left, (box.left + box.right) / 2, box.right];
  const yAnchors = [box.top, (box.top + box.bottom) / 2, box.bottom];
  const xMatch = closestMatch(xAnchors, index.x, threshold);
  const yMatch = closestMatch(yAnchors, index.y, threshold);
  const guides: EditorGuide[] = [];
  if (xMatch) guides.push({
    id: `guide:x:${xMatch.candidate.sourceId}`,
    axis: "x",
    position: xMatch.candidate.position,
    start: Math.min(box.top, xMatch.candidate.start),
    end: Math.max(box.bottom, xMatch.candidate.end),
    kind: xMatch.candidate.kind,
  });
  if (yMatch) guides.push({
    id: `guide:y:${yMatch.candidate.sourceId}`,
    axis: "y",
    position: yMatch.candidate.position,
    start: Math.min(box.left, yMatch.candidate.start),
    end: Math.max(box.right, yMatch.candidate.end),
    kind: yMatch.candidate.kind,
  });
  return { deltaX: xMatch?.delta ?? 0, deltaY: yMatch?.delta ?? 0, guides };
}

function addElementCandidates(
  element: CanonicalElement,
  x: SnapAxisCandidate[],
  y: SnapAxisCandidate[],
) {
  const box = rotatedBoundingBox(element.geometry, element.transform?.rotation);
  x.push(
    candidate(box.left, box.top, box.bottom, `${element.id}:left`, "element-edge"),
    candidate((box.left + box.right) / 2, box.top, box.bottom, `${element.id}:center-x`, "element-center"),
    candidate(box.right, box.top, box.bottom, `${element.id}:right`, "element-edge"),
  );
  y.push(
    candidate(box.top, box.left, box.right, `${element.id}:top`, "element-edge"),
    candidate((box.top + box.bottom) / 2, box.left, box.right, `${element.id}:center-y`, "element-center"),
    candidate(box.bottom, box.left, box.right, `${element.id}:bottom`, "element-edge"),
  );
}

function candidate(
  position: number,
  start: number,
  end: number,
  sourceId: string,
  kind: EditorGuide["kind"],
): SnapAxisCandidate {
  return { position, start, end, sourceId, kind };
}

function closestMatch(
  anchors: number[],
  candidates: SnapAxisCandidate[],
  threshold: number,
): { delta: number; candidate: SnapAxisCandidate } | null {
  let best: { delta: number; candidate: SnapAxisCandidate } | null = null;
  for (const anchor of anchors) {
    const insertion = lowerBound(candidates, anchor);
    for (const index of [insertion - 1, insertion]) {
      const candidate = candidates[index];
      if (!candidate) continue;
      const delta = candidate.position - anchor;
      if (Math.abs(delta) <= threshold && (!best || Math.abs(delta) < Math.abs(best.delta))) {
        best = { delta, candidate };
      }
    }
  }
  return best;
}

function lowerBound(candidates: SnapAxisCandidate[], value: number) {
  let low = 0;
  let high = candidates.length;
  while (low < high) {
    const middle = (low + high) >>> 1;
    if (candidates[middle].position < value) low = middle + 1;
    else high = middle;
  }
  return low;
}
