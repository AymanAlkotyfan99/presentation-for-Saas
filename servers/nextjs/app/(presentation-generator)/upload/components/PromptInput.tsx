import { Textarea } from "@/components/ui/textarea";
import { PencilIcon } from "lucide-react";
import { useTranslations } from "@/i18n/catalog";

interface PromptInputProps {
  value: string;
  onChange: (value: string) => void;
}

export function PromptInput({ value, onChange }: PromptInputProps) {
  const t = useTranslations();

  const handleChange = (val: string) => {

    onChange(val);
  };

  return (

    <div className="relative rounded-2xl border border-[#DEDFE5] bg-[#FCFCFE] px-3 py-3 font-syne transition focus-within:border-[#A99AF8] focus-within:bg-white focus-within:ring-4 focus-within:ring-[#6F4EF6]/[0.07] sm:px-4 sm:py-4">
      <div className="mb-1 flex items-center gap-2 min-[1800px]:mb-2">
        <PencilIcon className="h-3.5 w-3.5 min-[1800px]:h-4 min-[1800px]:w-4 min-[2200px]:h-5 min-[2200px]:w-5" />
        <p className="font-syne text-sm font-semibold text-[#333333]">{t("generation.writePrompt")}</p>
      </div>
      <Textarea
        value={value}
        autoFocus={true}
        rows={4}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={t("generation.promptCreativePlaceholder")}
        dir="auto"
        data-testid="prompt-input"
        className="min-h-[156px] max-h-[320px] resize-y overflow-y-auto border-none bg-transparent px-1 py-2 font-syne text-base font-medium leading-7 shadow-none focus-visible:ring-0 focus-visible:ring-transparent focus-visible:ring-offset-0 sm:text-lg custom_scrollbar"
      />
    </div>

  );
}
