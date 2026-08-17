import React from "react";
import { PresentationCard } from "./PresentationCard";
import { PresentationResponse } from "@/app/(presentation-generator)/services/api/dashboard";
import {
  PresentationLibraryEmpty,
  PresentationLibraryError,
  PresentationLibrarySkeleton,
} from "./PresentationLibraryState";

interface PresentationGridProps {
  presentations: PresentationResponse[];
  viewMode?: "grid" | "list";
  isLoading?: boolean;
  error?: string | null;
  searchActive?: boolean;
  onRetry?: () => void;
  onClearSearch?: () => void;
  onPresentationDeleted?: (presentationId: string) => void;
  onPresentationDuplicated?: (presentation: PresentationResponse) => void;
}

export const PresentationGrid = ({
  presentations,
  viewMode = "grid",
  isLoading = false,
  error = null,
  searchActive = false,
  onRetry,
  onClearSearch,
  onPresentationDeleted,
  onPresentationDuplicated,
}: PresentationGridProps) => {
  if (isLoading) {
    return <PresentationLibrarySkeleton />;
  }

  if (error) {
    return <PresentationLibraryError error={error} onRetry={onRetry} />;
  }

  if (!presentations || presentations.length === 0) {
    return <PresentationLibraryEmpty searchActive={searchActive} onClearSearch={onClearSearch} />;
  }

  return (
    <div
      className={
        viewMode === "grid"
          ? "grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
          : "grid grid-cols-1 gap-4"
      }
    >
      {presentations.map((presentation) => (

        <PresentationCard
          key={presentation.id}
          id={presentation.id}
          title={presentation.title}
          presentation={presentation}
          viewMode={viewMode}
          onDeleted={onPresentationDeleted}
          onDuplicated={onPresentationDuplicated}
        />
      ))}
    </div>
  );
};
