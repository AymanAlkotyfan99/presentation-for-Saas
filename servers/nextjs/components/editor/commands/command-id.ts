let sequence = 0;

export function createEditorCommandId(prefix: string) {
  sequence = (sequence + 1) % Number.MAX_SAFE_INTEGER;
  const random = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${sequence.toString(36)}`;
  return `${prefix}:${random}`.slice(0, 128);
}
