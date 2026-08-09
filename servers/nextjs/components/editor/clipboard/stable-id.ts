export function createCanonicalStableId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  throw new Error("EDITOR_SECURE_ID_SOURCE_UNAVAILABLE");
}
