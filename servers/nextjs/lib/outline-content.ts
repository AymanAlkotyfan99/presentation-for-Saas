const OUTLINE_BREAK_TAG_PATTERN = /<\s*br\s*\/?\s*>/gi;
const MARKDOWN_HEADING_PATTERN = /^#{1,6}\s+/;
const WRAPPING_EMPHASIS_PATTERN = /^(?:\*\*|__)(.*)(?:\*\*|__)$/;

export type OutlineContentParts = {
  normalized: string;
  title: string;
  body: string;
};

/** Convert only known line-break markup into inert text newlines. */
export function normalizeOutlineContent(value: string): string {
  return (typeof value === "string" ? value : "")
    .replace(OUTLINE_BREAK_TAG_PATTERN, "\n")
    .replace(/\r\n?/g, "\n");
}

/** Split an outline into a plain-text title and Markdown supporting content. */
export function splitOutlineContent(value: string): OutlineContentParts {
  const normalized = normalizeOutlineContent(value);
  const lines = normalized.split("\n");
  const titleIndex = lines.findIndex((line) => line.trim().length > 0);

  if (titleIndex === -1) {
    return { normalized, title: "", body: "" };
  }

  const rawTitle = lines[titleIndex].trim().replace(MARKDOWN_HEADING_PATTERN, "");
  const emphasisMatch = rawTitle.match(WRAPPING_EMPHASIS_PATTERN);
  const title = (emphasisMatch?.[1] ?? rawTitle).trim();
  const body = lines.slice(titleIndex + 1).join("\n").trim();

  return { normalized, title, body };
}
