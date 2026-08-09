import { useState, useCallback } from "react";
import { notify } from "@/components/ui/sonner";
import { useTranslations } from "@/i18n/catalog";

export const useFileUpload = () => {
  const t = useTranslations();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleRawFileSelect = useCallback((file: File) => {
    const lowerName = file.name.toLowerCase();
    const isPptx = lowerName.endsWith(".pptx");
    if (!isPptx) {
      notify.error(t("customTemplates.invalidFile"), t("customTemplates.invalidFileDescription"));
      return;
    }

    const maxSize = 100 * 1024 * 1024;
    if (file.size > maxSize) {
      notify.error(t("customTemplates.fileTooLarge"), t("customTemplates.fileTooLargeDescription"));
      return;
    }

    setSelectedFile(file);
  }, [t]);

  const handleFileSelect = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      handleRawFileSelect(file);
    },
    [handleRawFileSelect]
  );

  const removeFile = useCallback(() => {
    setSelectedFile(null);
  }, []);

  return {
    selectedFile,
    handleFileSelect,
    handleRawFileSelect,
    removeFile,
  };
};
