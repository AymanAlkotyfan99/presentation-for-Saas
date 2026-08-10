import type { EditorCommand } from "@/components/editor/commands";
import { RevisionClientError, type RevisionEnvelope } from "./types";

type FetchLike = typeof fetch;

export class RevisionClient {
  constructor(
    private readonly request: FetchLike = fetch,
    private readonly prefix = "/api/v1/ppt/presentations",
  ) {}

  async save(presentationId: string, baseRevision: number, commands: EditorCommand[], idempotencyKey: string) {
    return this.json<RevisionEnvelope>(`${this.prefix}/${encodeURIComponent(presentationId)}/revisions`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "If-Match": `"${baseRevision}"`,
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify({ baseRevision, commands }),
    });
  }

  async current(presentationId: string) {
    return this.json<RevisionEnvelope>(`${this.prefix}/${encodeURIComponent(presentationId)}/revisions/current`, { method: "GET" });
  }

  async history(presentationId: string, before?: number) {
    const query = before ? `?before=${before}` : "";
    return this.json<Array<Omit<RevisionEnvelope, "document">>>(`${this.prefix}/${encodeURIComponent(presentationId)}/revisions${query}`, { method: "GET" });
  }

  async restore(presentationId: string, targetRevision: number, baseRevision: number, idempotencyKey: string) {
    return this.json<RevisionEnvelope>(`${this.prefix}/${encodeURIComponent(presentationId)}/revisions/${targetRevision}/restore`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "If-Match": `"${baseRevision}"`,
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify({ baseRevision }),
    });
  }

  private async json<T>(url: string, init: RequestInit): Promise<T> {
    let response: Response;
    try {
      response = await this.request(url, { ...init, credentials: "same-origin" });
    } catch {
      throw new RevisionClientError("REVISION_NETWORK_UNAVAILABLE", 0);
    }
    const body = await response.json().catch(() => ({})) as Record<string, unknown>;
    if (!response.ok) {
      throw new RevisionClientError(
        typeof body.code === "string" ? body.code : "REVISION_REQUEST_FAILED",
        response.status,
        body.params && typeof body.params === "object" ? body.params as Record<string, unknown> : {},
      );
    }
    return body as T;
  }
}
