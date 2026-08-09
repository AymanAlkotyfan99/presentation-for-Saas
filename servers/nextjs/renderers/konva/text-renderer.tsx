import { Fragment } from "react";
import { Text } from "react-konva";
import type { TextElement } from "@/generated/presentation-document";
import type { KonvaElementRendererProps } from "./types";
import { logicalAlignmentToPhysical, resolveParagraphDirection, textFromParagraph } from "@/renderers/shared/direction";
import { safeColor } from "@/renderers/shared/style";

export function TextRenderer({ element, context }: KonvaElementRendererProps<TextElement>) {
  const paragraphHeight = element.geometry.height / Math.max(1, element.paragraphs.length);
  return <>
    {element.paragraphs.map((paragraph, index) => {
      const run = paragraph.runs[0];
      const direction = resolveParagraphDirection(paragraph, context.locale, context.direction);
      return <Fragment key={paragraph.id}>
        <Text
          x={0}
          y={index * paragraphHeight}
          width={element.geometry.width}
          height={paragraphHeight}
          text={textFromParagraph(paragraph)}
          direction={direction}
          align={logicalAlignmentToPhysical(paragraph.logicalAlignment, direction)}
          verticalAlign={element.verticalAlignment === "middle" ? "middle" : element.verticalAlignment === "bottom" ? "bottom" : "top"}
          fontFamily={fontFamily(context, run?.fontFamilyRef)}
          fontSize={run?.fontSize ?? 24}
          fontStyle={`${run?.fontStyle === "italic" ? "italic" : "normal"} ${run?.fontWeight && run.fontWeight >= 600 ? "bold" : "normal"}`}
          fill={safeColor(run?.color, "#111827")}
          lineHeight={run?.lineHeight ?? 1.2}
          letterSpacing={run?.letterSpacing ?? 0}
          wrap="word"
          ellipsis={element.overflow === "ellipsis"}
          perfectDrawEnabled={false}
        />
      </Fragment>;
    })}
  </>;
}

function fontFamily(context: KonvaElementRendererProps<TextElement>["context"], reference?: string) {
  const family = context.document.fontPolicy.families.find(({ id }) => id === reference)
    ?? context.document.fontPolicy.families.find(({ id }) => id === context.document.fontPolicy.defaultBodyRef);
  return family ? [family.family, ...family.fallbacks].join(", ") : "Arial, sans-serif";
}
