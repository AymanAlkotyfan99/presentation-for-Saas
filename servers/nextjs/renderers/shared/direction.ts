import type { Direction, Locale, LogicalAlignment, Paragraph } from "@/generated/presentation-document";

export type ResolvedDirection = "ltr" | "rtl";

export function directionFromLocale(locale: Locale): ResolvedDirection {
  return locale === "ar" ? "rtl" : "ltr";
}

export function resolveDirection(
  direction: Direction | undefined,
  locale: Locale,
  inherited?: ResolvedDirection,
): ResolvedDirection {
  if (direction === "rtl" || direction === "ltr") return direction;
  return inherited ?? directionFromLocale(locale);
}

export function resolveParagraphDirection(
  paragraph: Paragraph,
  locale: Locale,
  inherited?: ResolvedDirection,
): ResolvedDirection {
  return resolveDirection(paragraph.direction, locale, inherited);
}

export function logicalAlignmentToPhysical(
  alignment: LogicalAlignment,
  direction: ResolvedDirection,
): "left" | "center" | "right" | "justify" {
  if (alignment === "center" || alignment === "justify") return alignment;
  if (alignment === "start") return direction === "rtl" ? "right" : "left";
  return direction === "rtl" ? "left" : "right";
}

export function textFromParagraph(paragraph: Paragraph): string {
  return paragraph.runs.map((run) => run.text).join("");
}

export function textFromParagraphs(paragraphs: Paragraph[]): string {
  return paragraphs.map(textFromParagraph).join("\n");
}

export function browserBidiProperties(
  direction: ResolvedDirection,
  alignment: LogicalAlignment,
) {
  return {
    direction,
    textAlign: logicalAlignmentToPhysical(alignment, direction),
    unicodeBidi: "plaintext" as const,
  };
}
