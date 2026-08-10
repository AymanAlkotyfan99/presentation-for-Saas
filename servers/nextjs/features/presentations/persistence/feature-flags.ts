function enabled(value: string | undefined, fallback: boolean) {
  if (value === undefined || value === "") return fallback;
  return value === "1" || value.toLowerCase() === "true";
}

export function persistenceFeatureFlags(env: Record<string, string | undefined> = process.env) {
  return Object.freeze({
    revisionWrites: enabled(env.NEXT_PUBLIC_REVISION_WRITES_ENABLED ?? env.REVISION_WRITES_ENABLED, false),
    indexedDbRecovery: enabled(env.NEXT_PUBLIC_INDEXEDDB_RECOVERY_ENABLED ?? env.INDEXEDDB_RECOVERY_ENABLED, false),
    versionHistory: enabled(env.NEXT_PUBLIC_VERSION_HISTORY_ENABLED ?? env.VERSION_HISTORY_ENABLED, false),
  });
}
