import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Grip } from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { Textarea } from "@/components/ui/textarea";
import {
  normalizeOutlineContent,
  splitOutlineContent,
} from "@/lib/outline-content";
import { renderSafeMarkdown } from "@/lib/safe-markdown";
import { useTranslations } from "@/i18n/catalog";

interface OutlineItemProps {
  slideOutline: {
    content: string;
  };
  id: string;
  index: number;
  isStreaming: boolean;
  isActiveStreaming?: boolean;
  isStableStreaming?: boolean;
  onUpdate?: (newContent: string) => void;
}

const outlineMarkdownClassName =
  "prose prose-sm max-w-none font-syne text-[15px] font-normal leading-6 text-[#5E6472] [overflow-wrap:anywhere] [&>*]:!my-0 [&>*+*]:!mt-2 [&_p]:text-[15px] [&_p]:font-normal [&_p]:leading-6 [&_p]:text-[#5E6472] [&_strong]:font-semibold [&_strong]:text-[#303442] [&_ul]:!my-0 [&_ul]:list-none [&_ul]:space-y-1.5 [&_ul]:pl-0 [&_ul_li]:my-0 [&_ul_li]:bg-[url('/figma/outline-check.svg')] [&_ul_li]:bg-[length:18px_18px] [&_ul_li]:bg-[position:left_3px] [&_ul_li]:bg-no-repeat [&_ul_li]:pl-6 [&_ul_li]:text-[15px] [&_ul_li]:font-normal [&_ul_li]:leading-6 [&_ul_li]:text-[#424754]";

export function OutlineItem({
  id,
  index,
  slideOutline,
  isStreaming,
  isActiveStreaming = false,
  isStableStreaming = false,
  onUpdate,
}: OutlineItemProps) {
  const t = useTranslations();
  useEffect(() => {
    if (isStreaming) {
      const outlineItem = document.getElementById(`outline-item-${index}`);
      if (outlineItem) {
        outlineItem.scrollIntoView({
          behavior: "smooth",
          block: "center",
          inline: "nearest",
        });
      }
    }
  }, [index, isStreaming, slideOutline.content]);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id, disabled: isStreaming });

  const style = {
    transform: CSS.Transform.toString(
      transform ? { ...transform, scaleX: 1, scaleY: 1 } : null
    ),
    transition,
  };

  const editorRef = useRef<HTMLTextAreaElement>(null);
  const throttleRef = useRef<number | null>(null);
  const [markdownDraft, setMarkdownDraft] = useState(
    normalizeOutlineContent(slideOutline.content || "")
  );
  const [isEditingMarkdown, setIsEditingMarkdown] = useState(false);
  const [renderedHtml, setRenderedHtml] = useState<string>("");

  useEffect(() => {
    setMarkdownDraft(normalizeOutlineContent(slideOutline.content || ""));
  }, [slideOutline.content]);

  useEffect(() => {
    if (!isEditingMarkdown) return;
    const editor = editorRef.current;
    if (!editor) return;

    editor.focus();
    const end = editor.value.length;
    editor.setSelectionRange(end, end);
  }, [isEditingMarkdown]);

  const handleMarkdownBlur = () => {
    const normalizedDraft = normalizeOutlineContent(markdownDraft);
    if (normalizedDraft !== normalizeOutlineContent(slideOutline.content)) {
      onUpdate?.(normalizedDraft);
    }
    setIsEditingMarkdown(false);
  };

  const handleStartMarkdownEdit = () => {
    setMarkdownDraft(normalizeOutlineContent(slideOutline.content || ""));
    setIsEditingMarkdown(true);
  };

  const handleMarkdownKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Tab") return;

    event.preventDefault();
    const target = event.currentTarget;
    const start = target.selectionStart;
    const end = target.selectionEnd;
    const updatedValue = `${markdownDraft.slice(
      0,
      start
    )}\t${markdownDraft.slice(end)}`;

    setMarkdownDraft(updatedValue);
    requestAnimationFrame(() => {
      target.selectionStart = target.selectionEnd = start + 1;
    });
  };

  useEffect(() => {
    if (!isStreaming || !isActiveStreaming) return;
    const { body } = splitOutlineContent(slideOutline.content || "");

    if (throttleRef.current) {
      window.clearTimeout(throttleRef.current);
    }
    throttleRef.current = window.setTimeout(() => {
      setRenderedHtml(renderSafeMarkdown(body, { breaks: true }));
    }, 60);

    return () => {
      if (throttleRef.current) {
        window.clearTimeout(throttleRef.current);
      }
    };
  }, [isStreaming, isActiveStreaming, slideOutline.content]);

  const stableHtml = useMemo(() => {
    if (!isStreaming || isActiveStreaming) return null;
    if (!isStableStreaming) return null;
    return renderSafeMarkdown(
      splitOutlineContent(slideOutline.content || "").body,
      { breaks: true }
    );
  }, [isStreaming, isActiveStreaming, isStableStreaming, slideOutline.content]);

  const previewHtml = useMemo(() => {
    if (isStreaming) return "";
    return renderSafeMarkdown(
      splitOutlineContent(slideOutline.content || "").body,
      { breaks: true }
    );
  }, [isStreaming, slideOutline.content]);

  const displayContent = useMemo(
    () => splitOutlineContent(slideOutline.content || ""),
    [slideOutline.content]
  );

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`group relative mb-4 rounded-2xl border bg-white p-4 font-syne transition-all duration-300 hover:-translate-y-0.5 hover:border-[#D8D3F7] hover:shadow-[0_12px_30px_rgba(36,31,65,0.10)] sm:p-6 ${
        isEditingMarkdown
          ? "border-[#BDB4FE] shadow-[0_6.6px_13.2px_0_rgba(0,0,0,0.10)]"
          : "border-transparent shadow-[0_6.6px_6.6px_rgba(0,0,0,0.10)]"
      } ${isDragging ? "opacity-50" : ""}`}
    >
      <div className="flex items-start gap-3 sm:gap-4">
        <div
          {...attributes}
          {...listeners}
          aria-label={t("outline.moveSlide", { number: index })}
          className="relative flex h-9 w-9 shrink-0 touch-none select-none items-center justify-center rounded-lg border border-transparent text-[#858B98] transition cursor-grab hover:border-[#E2DDFB] hover:bg-[#F5F2FF] hover:text-[#6344E8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7A5AF8]/30 active:cursor-grabbing"
        >
          <Grip aria-hidden="true" className="h-5 w-5" />
        </div>

        <div
          id={`outline-item-${index}`}
          className="flex min-w-0 basis-full flex-col"
        >
          <p className="flex h-6 w-fit items-center rounded-full bg-[#F0EDFF] px-2.5 font-unbounded text-[10px] font-medium tracking-[0.02em] text-[#6044D8]">
            {t("outline.slideLabel", { number: index })}
          </p>

          {isStreaming ? (
            isActiveStreaming ? (
              <div className="mt-3">
                <h2 className="text-lg font-semibold leading-7 text-[#20232D] sm:text-xl" dir="auto">
                  {displayContent.title}
                </h2>
                {renderedHtml && (
                  <div className={`${outlineMarkdownClassName} mt-2`} dir="auto" dangerouslySetInnerHTML={{ __html: renderedHtml }} />
                )}
              </div>
            ) : stableHtml ? (
              <div className="mt-3">
                <h2 className="text-lg font-semibold leading-7 text-[#20232D] sm:text-xl" dir="auto">
                  {displayContent.title}
                </h2>
                {stableHtml && (
                  <div className={`${outlineMarkdownClassName} mt-2`} dir="auto" dangerouslySetInnerHTML={{ __html: stableHtml }} />
                )}
              </div>
            ) : (
              <div className="mt-3" dir="auto">
                <h2 className="text-lg font-semibold leading-7 text-[#20232D] sm:text-xl">
                  {displayContent.title}
                </h2>
                {displayContent.body && <p className="mt-2 whitespace-pre-line text-[15px] leading-6 text-[#5E6472]">{displayContent.body}</p>}
              </div>
            )
          ) : isEditingMarkdown ? (
            <Textarea
              ref={editorRef}
              value={markdownDraft}
              onChange={(event) => setMarkdownDraft(event.target.value)}
              onBlur={handleMarkdownBlur}
              onKeyDown={handleMarkdownKeyDown}
              spellCheck={false}
              placeholder={t("outline.markdownPlaceholder")}
              dir="auto"
              className="mt-3 min-h-[120px] resize-y rounded-xl border-[#D8D8DF] bg-[#FBFBFC] px-4 py-3 font-mono text-[13px] leading-6 text-[#191919] shadow-none focus-visible:border-[#7A5AF8] focus-visible:ring-2 focus-visible:ring-[#7A5AF8]/20"
            />
          ) : (
            <div
              role="button"
              tabIndex={0}
              aria-label={t("outline.editSlideMarkdown", { number: index })}
              onClick={handleStartMarkdownEdit}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  handleStartMarkdownEdit();
                }
              }}
              className="mt-3 min-h-[54px] w-full cursor-text rounded-lg text-start focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7A5AF8]/25 focus-visible:ring-offset-4"
              dir="auto"
            >
              <h2 className="text-lg font-semibold leading-7 text-[#20232D] sm:text-xl">
                {displayContent.title}
              </h2>
              {previewHtml && (
                <div className={`${outlineMarkdownClassName} mt-2`} dangerouslySetInnerHTML={{ __html: previewHtml }} />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
