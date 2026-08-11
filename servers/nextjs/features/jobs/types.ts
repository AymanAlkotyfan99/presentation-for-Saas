export type JobStatus =
  | "PENDING"
  | "QUEUED"
  | "RUNNING"
  | "CANCELLATION_REQUESTED"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELLED"
  | "DEAD_LETTER";

export interface DurableJob {
  id: string;
  workspaceId: string;
  operation: string;
  queueClass: string;
  status: JobStatus;
  progress: number;
  progressMessage: string | null;
  attemptCount: number;
  maxAttempts: number;
  resourceType: string | null;
  resourceId: string | null;
  sourceRevision: number | null;
  safeErrorCode: string | null;
  safeErrorMessage: string | null;
  result?: Record<string, unknown> | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  updatedAt: string;
}

export interface JobEvent {
  type: string;
  data: Record<string, unknown>;
  createdAt: string;
}
