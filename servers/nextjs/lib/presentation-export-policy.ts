export const UNVERIFIED_PRESENTATION_EXPORT_ERROR_CODE =
  "UNVERIFIED_PRESENTATION_EXPORT_DISABLED";

export function isUnverifiedPresentationExportEnabled(): boolean {
  return process.env.ENABLE_UNVERIFIED_PRESENTATION_EXPORT === "true";
}
