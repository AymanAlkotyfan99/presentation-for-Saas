import type { IpcMainInvokeEvent } from "electron";

export class UntrustedIpcSenderError extends Error {
  constructor() {
    super("IPC request denied: untrusted renderer");
    this.name = "UntrustedIpcSenderError";
  }
}

export function isTrustedSenderUrl(
  senderUrl: string,
  expectedOrigin: string,
): boolean {
  try {
    const sender = new URL(senderUrl);
    const expected = new URL(expectedOrigin);
    return (
      (sender.protocol === "http:" || sender.protocol === "https:") &&
      sender.origin === expected.origin
    );
  } catch {
    return false;
  }
}

/** Require IPC to originate in the top-level Presenton renderer. */
export function assertTrustedIpcSender(
  event: IpcMainInvokeEvent,
  expectedOrigin: string,
): void {
  const frame = event.senderFrame;
  if (!frame || frame.top !== frame) {
    throw new UntrustedIpcSenderError();
  }
  if (!isTrustedSenderUrl(frame.url, expectedOrigin)) {
    throw new UntrustedIpcSenderError();
  }
}
