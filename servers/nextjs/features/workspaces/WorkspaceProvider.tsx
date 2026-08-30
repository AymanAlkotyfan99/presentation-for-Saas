"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { normalizeCapabilities, can as hasCapability } from "./capabilities";
import { getRuntimeCapabilities, workspaceApi } from "./api";
import type { WorkspacePermission, WorkspaceSummary } from "./types";

interface WorkspaceContextValue {
  available: boolean;
  loading: boolean;
  current: WorkspaceSummary | null;
  workspaces: WorkspaceSummary[];
  error: string | null;
  can: (permission: WorkspacePermission) => boolean;
  switchWorkspace: (workspaceId: string) => Promise<void>;
  refresh: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [available, setAvailable] = useState(false);
  const [current, setCurrent] = useState<WorkspaceSummary | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [workspaceEpoch, setWorkspaceEpoch] = useState(0);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const runtimeCapabilities = await getRuntimeCapabilities();
      if (!runtimeCapabilities.workspaces) {
        setAvailable(false);
        setCurrent(null);
        setWorkspaces([]);
        setError(null);
        return;
      }
      const [nextCurrent, nextWorkspaces] = await Promise.all([workspaceApi.current(), workspaceApi.list()]);
      setCurrent(nextCurrent);
      setWorkspaces(nextWorkspaces);
      setAvailable(true);
      setError(null);
    } catch (cause) {
      const status = (cause as { status?: number }).status;
      setAvailable(false);
      if (status === 404) setError(null);
      else setError(cause instanceof Error ? cause.message : "Workspace request failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const switchWorkspace = useCallback(async (workspaceId: string) => {
    if (workspaceId === current?.id) return;
    const selected = await workspaceApi.select(workspaceId);
    setCurrent(selected);
    setWorkspaces((items) => items.map((item) => item.id === selected.id ? selected : item));
    setWorkspaceEpoch((value) => value + 1);
    window.dispatchEvent(new CustomEvent("bayanly:workspace-changed", { detail: { workspaceId } }));
  }, [current?.id]);

  const capabilities = useMemo(() => normalizeCapabilities(current?.permissions ?? []), [current?.permissions]);
  const value = useMemo<WorkspaceContextValue>(() => ({
    available, loading, current, workspaces, error,
    can: (permission) => hasCapability(capabilities, permission),
    switchWorkspace, refresh,
  }), [available, loading, current, workspaces, error, capabilities, switchWorkspace, refresh]);

  return <WorkspaceContext.Provider value={value}><React.Fragment key={workspaceEpoch}>{children}</React.Fragment></WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return context;
}
