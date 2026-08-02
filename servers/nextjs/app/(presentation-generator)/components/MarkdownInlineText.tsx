"use client";

import React, { useMemo } from "react";
import { renderSafeInlineMarkdown } from "@/lib/safe-markdown";

interface MarkdownInlineTextProps {
  content: string;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Renders inline markdown (e.g. **bold**) without block wrappers like <p>.
 * Used for export/preview where Tiptap edit mode is off.
 */
const MarkdownInlineText: React.FC<MarkdownInlineTextProps> = ({
  content,
  className = "",
  style,
}) => {
  const html = useMemo(
    () => renderSafeInlineMarkdown(content || ""),
    [content]
  );

  if (!html) {
    return (
      <span className={className} style={style}>
        {content}
      </span>
    );
  }

  return (
    <span
      className={className}
      style={style}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
};

export default MarkdownInlineText;
