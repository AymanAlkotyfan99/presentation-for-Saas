import type { TextElement } from "@/generated/presentation-document";
import { browserBidiProperties, resolveParagraphDirection } from "@/renderers/shared/direction";
import { safeColor } from "@/renderers/shared/style";
import type { BrowserElementRendererProps } from "./types";

export function BrowserTextRenderer({ element, context }: BrowserElementRendererProps<TextElement>) {
  return <div
    style={{
      width: "100%",
      height: "100%",
      display: "flex",
      flexDirection: "column",
      justifyContent: element.verticalAlignment === "middle" ? "center" : element.verticalAlignment === "bottom" ? "flex-end" : "flex-start",
      overflow: "hidden",
    }}
  >
    {element.paragraphs.map((paragraph) => {
      const direction = resolveParagraphDirection(paragraph, context.locale, context.direction);
      return <p key={paragraph.id} dir={direction} style={{ ...browserBidiProperties(direction, paragraph.logicalAlignment), margin: 0, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
        {paragraph.runs.map((run) => <span
          key={run.id}
          lang={run.language}
          style={{
            color: safeColor(run.color, "#111827"),
            fontFamily: resolveFont(context, run.fontFamilyRef),
            fontSize: run.fontSize,
            fontWeight: run.fontWeight,
            fontStyle: run.fontStyle,
            lineHeight: run.lineHeight,
            letterSpacing: run.letterSpacing,
            textDecoration: run.decorations?.map((value) => value === "line-through" ? "line-through" : "underline").join(" "),
          }}
        >{run.text}</span>)}
      </p>;
    })}
  </div>;
}

function resolveFont(context: BrowserElementRendererProps<TextElement>["context"], reference?: string) {
  const family = context.document.fontPolicy.families.find(({ id }) => id === reference)
    ?? context.document.fontPolicy.families.find(({ id }) => id === context.document.fontPolicy.defaultBodyRef);
  return family ? [family.family, ...family.fallbacks].join(", ") : "Arial, sans-serif";
}
