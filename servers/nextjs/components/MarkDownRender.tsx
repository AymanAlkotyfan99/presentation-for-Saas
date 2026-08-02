"use client";

import React, { useMemo } from "react";

import { cn } from "@/lib/utils";
import { renderSafeMarkdown } from "@/lib/safe-markdown";

interface MarkdownRendererProps {
    content: string;
    className?: string;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className }) => {
    const markdownContent = useMemo(
        () => renderSafeMarkdown(content),
        [content]
    );

    return (
        <div
            className={cn("prose prose-slate max-w-none mb-10", className)}
            dangerouslySetInnerHTML={{ __html: markdownContent }}
        />
    );
};

export default MarkdownRenderer;
