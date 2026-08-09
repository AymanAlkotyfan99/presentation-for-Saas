import type { EditorGuide } from "@/components/editor/types";

export function deduplicateGuides(guides: EditorGuide[]): EditorGuide[] {
  const byKey = new Map<string, EditorGuide>();
  for (const guide of guides) {
    const key = `${guide.axis}:${Math.round(guide.position * 1000)}`;
    const existing = byKey.get(key);
    byKey.set(key, existing
      ? { ...existing, start: Math.min(existing.start, guide.start), end: Math.max(existing.end, guide.end) }
      : guide);
  }
  return [...byKey.values()];
}

export function clearTransientGuides(): EditorGuide[] {
  return [];
}
