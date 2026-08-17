import { normalizeOutlineContent } from "@/lib/outline-content";
import { limitOutlines } from "@/utils/presentationLimits";

export type PresentationPrepareRequest = {
  presentation_id: string | null;
  outlines: { content: string }[];
  layout: string | null;
  title?: string | null;
};

export function buildPresentationPrepareBody(
  input: PresentationPrepareRequest
): PresentationPrepareRequest {
  return {
    ...input,
    outlines: limitOutlines(input.outlines).map((outline) => ({
      ...outline,
      content: normalizeOutlineContent(outline.content),
    })),
  };
}

export function serializePresentationPrepareBody(
  input: PresentationPrepareRequest
): string {
  return JSON.stringify(buildPresentationPrepareBody(input));
}
