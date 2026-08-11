"use client";

import { useCallback, useEffect, useState } from "react";
import { useI18n } from "@/i18n/catalog";
import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { jobsApi } from "./api";
import type { DurableJob, JobStatus } from "./types";

const terminal = new Set<JobStatus>(["SUCCEEDED", "FAILED", "CANCELLED", "DEAD_LETTER"]);
const catalogSegment = (value: string) => value.toLowerCase().replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());

export function JobCenter() {
  const { t } = useI18n();
  const workspace = useWorkspace();
  const [jobs, setJobs] = useState<DurableJob[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      setJobs(await jobsApi.list());
      setNotice(null);
    } catch {
      setNotice(t("jobs.loadError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void reload();
    const timer = window.setInterval(() => {
      if (jobs.some((job) => !terminal.has(job.status))) void reload();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [jobs, reload]);

  const statusKey = (job: DurableJob) => {
    if (job.status === "QUEUED" && job.attemptCount > 0) return "retrying";
    if (job.status === "SUCCEEDED" && job.result?.partial === true) return "partial";
    return catalogSegment(job.status);
  };

  return (
    <main className="mx-auto w-full max-w-5xl p-6" aria-labelledby="jobs-title">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 id="jobs-title" className="text-2xl font-semibold text-slate-950">{t("jobs.title")}</h1>
          <p className="mt-1 text-sm text-slate-600">{t("jobs.description")}</p>
        </div>
        <button type="button" className="rounded-md border px-3 py-2 text-sm" onClick={() => void reload()}>{t("jobs.refresh")}</button>
      </div>
      {notice && <p role="alert" className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-800">{notice}</p>}
      {loading ? <p className="text-slate-600">{t("jobs.loading")}</p> : (
        <ul className="space-y-3">
          {jobs.map((job) => (
            <li key={job.id} className="rounded-lg border bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium text-slate-950">{t(`jobs.operations.${job.operation.split(".").map(catalogSegment).join(".")}`, { fallback: job.operation })}</p>
                  <p className="mt-1 text-xs text-slate-500">{new Date(job.createdAt).toLocaleString()}</p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-800" role="status">
                  {t(`jobs.status.${statusKey(job)}`)}
                </span>
              </div>
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100" aria-label={t("jobs.progress", { progress: job.progress })}>
                <div className="h-full bg-violet-600 transition-[width]" style={{ width: `${job.progress}%` }} />
              </div>
              <div className="mt-2 flex flex-wrap justify-between gap-2 text-sm text-slate-600">
                <span>{job.progressMessage ?? t("jobs.waiting")}</span>
                <span>{t("jobs.attempts", { current: job.attemptCount, maximum: job.maxAttempts })}</span>
              </div>
              {job.safeErrorMessage && <p className="mt-3 text-sm text-red-700">{job.safeErrorMessage}</p>}
              <div className="mt-4 flex gap-3">
                {workspace.can("jobs:write") && ["PENDING", "QUEUED", "RUNNING"].includes(job.status) && (
                  <button className="rounded-md border border-red-200 px-3 py-1.5 text-sm text-red-700" onClick={async () => { await jobsApi.cancel(job.id); await reload(); }}>{t("jobs.cancel")}</button>
                )}
                {workspace.can("jobs:write") && job.status === "FAILED" && (
                  <button className="rounded-md bg-violet-700 px-3 py-1.5 text-sm text-white" onClick={async () => { await jobsApi.retry(job.id); await reload(); }}>{t("jobs.retry")}</button>
                )}
              </div>
            </li>
          ))}
          {jobs.length === 0 && <li className="rounded-lg border border-dashed p-8 text-center text-slate-600">{t("jobs.empty")}</li>}
        </ul>
      )}
    </main>
  );
}
