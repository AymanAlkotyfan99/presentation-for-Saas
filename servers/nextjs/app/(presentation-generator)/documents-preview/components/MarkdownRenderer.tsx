"use client";

import React, { useMemo } from "react";

import { renderSafeMarkdown } from "@/lib/safe-markdown";

interface MarkdownRendererProps {
  content: string;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  const markdownContent = useMemo(
    () => renderSafeMarkdown(content),
    [content]
  );

  return (
    <div
      className="prose prose-slate max-w-none mb-10"
      dangerouslySetInnerHTML={{ __html: markdownContent }}
    />
  );
};

export default MarkdownRenderer;
