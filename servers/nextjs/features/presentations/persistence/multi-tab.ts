export type TabOwnership = "writer" | "read-only";

type Lease = { tabId: string; expiresAt: number };
const LEASE_MS = 8_000;

export class PresentationTabCoordinator {
  readonly tabId: string;
  private ownership: TabOwnership = "read-only";
  private timer: ReturnType<typeof setInterval> | null = null;
  private listeners = new Set<(ownership: TabOwnership) => void>();
  private channel: BroadcastChannel | null = null;

  constructor(
    readonly presentationId: string,
    private readonly clock: () => number = Date.now,
    tabId?: string,
  ) {
    this.tabId = tabId ?? globalThis.crypto?.randomUUID?.() ?? `tab-${Math.random().toString(36).slice(2)}`;
  }

  start() {
    if (typeof window === "undefined") return;
    if ("BroadcastChannel" in globalThis) {
      this.channel = new BroadcastChannel(`bayanly:presentation:${this.presentationId}`);
      this.channel.onmessage = (event) => {
        if (event.data?.type === "lease" && event.data.tabId !== this.tabId) this.refresh();
      };
    }
    window.addEventListener("storage", this.onStorage);
    this.refresh();
    this.timer = setInterval(() => this.refresh(), LEASE_MS / 2);
  }

  canWrite() { return this.ownership === "writer"; }
  getOwnership() { return this.ownership; }
  subscribe(listener: (ownership: TabOwnership) => void) {
    this.listeners.add(listener); listener(this.ownership);
    return () => this.listeners.delete(listener);
  }
  takeOverIfExpired() { this.refresh(true); return this.canWrite(); }

  close() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    if (typeof window !== "undefined") window.removeEventListener("storage", this.onStorage);
    if (this.canWrite()) localStorage.removeItem(this.key);
    this.channel?.close(); this.channel = null;
  }

  private get key() { return `bayanly:revision-lease:${this.presentationId}`; }
  private onStorage = (event: StorageEvent) => { if (event.key === this.key) this.refresh(); };
  private refresh(force = false) {
    if (typeof localStorage === "undefined") return;
    const now = this.clock();
    const lease = readLease(localStorage.getItem(this.key));
    const decision = resolveLease(lease, this.tabId, now, force);
    if (decision.ownership === "writer") {
      const next = decision.lease!;
      localStorage.setItem(this.key, JSON.stringify(next));
      const confirmed = readLease(localStorage.getItem(this.key));
      this.setOwnership(confirmed?.tabId === this.tabId ? "writer" : "read-only");
      this.channel?.postMessage({ type: "lease", tabId: this.tabId, expiresAt: next.expiresAt });
    } else {
      this.setOwnership("read-only");
    }
  }
  private setOwnership(value: TabOwnership) {
    if (value === this.ownership) return;
    this.ownership = value; this.listeners.forEach((listener) => listener(value));
  }
}

export function resolveLease(existing: Lease | null, tabId: string, now: number, force = false): { ownership: TabOwnership; lease: Lease | null } {
  if (force || !existing || existing.expiresAt <= now || existing.tabId === tabId) {
    return { ownership: "writer", lease: { tabId, expiresAt: now + LEASE_MS } };
  }
  return { ownership: "read-only", lease: existing };
}

function readLease(value: string | null): Lease | null {
  try {
    const parsed = JSON.parse(value ?? "null");
    return parsed && typeof parsed.tabId === "string" && Number.isFinite(parsed.expiresAt) ? parsed : null;
  } catch { return null; }
}
