"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";
import type { PresentationDocument } from "@/generated/presentation-document";
import type { EditorCommand } from "@/components/editor/commands";
import { RevisionAutosaveController } from "./autosave-controller";
import { persistenceFeatureFlags } from "./feature-flags";
import { IndexedDbRevisionJournal, MemoryRevisionJournal } from "./journal";
import { PresentationTabCoordinator } from "./multi-tab";
import { RevisionClient } from "./revision-client";

export type RevisionPersistenceOptions = {
  presentationId: string;
  actorScope: string;
  initialRevision: number;
  onServerDocument?: (document: PresentationDocument) => void;
  enabled?: boolean;
};

const DISABLED_SNAPSHOT = { status: "idle" as const, acknowledgedRevision: 0, pendingCommands: 0, conflict: null, errorCode: null };

export function useRevisionPersistence(options: RevisionPersistenceOptions | null) {
  const flags = persistenceFeatureFlags();
  const enabled = Boolean(options?.enabled ?? flags.revisionWrites) && Boolean(options);
  const presentationId = options?.presentationId;
  const actorScope = options?.actorScope;
  const initialRevision = options?.initialRevision;
  const onServerDocument = options?.onServerDocument;
  const coordinator = useMemo(() => enabled && presentationId ? new PresentationTabCoordinator(presentationId) : null, [enabled, presentationId]);
  const controller = useMemo(() => {
    if (!enabled || !presentationId || !actorScope || initialRevision === undefined || !coordinator) return null;
    const journal = flags.indexedDbRecovery && typeof indexedDB !== "undefined"
      ? new IndexedDbRevisionJournal()
      : new MemoryRevisionJournal();
    return new RevisionAutosaveController(
      presentationId, actorScope, initialRevision,
      journal, new RevisionClient(), () => coordinator.canWrite(),
      onServerDocument,
    );
  }, [actorScope, coordinator, enabled, flags.indexedDbRecovery, initialRevision, onServerDocument, presentationId]);

  useEffect(() => {
    if (!controller || !coordinator) return;
    coordinator.start();
    const unsubscribe = coordinator.subscribe((ownership) => controller.setWritable(ownership === "writer"));
    const online = () => controller.setOnline(true);
    const offline = () => controller.setOnline(false);
    window.addEventListener("online", online); window.addEventListener("offline", offline);
    controller.setOnline(navigator.onLine);
    void controller.recover().catch(() => controller.setOnline(false));
    return () => {
      unsubscribe(); controller.dispose(); coordinator.close();
      window.removeEventListener("online", online); window.removeEventListener("offline", offline);
    };
  }, [controller, coordinator]);

  const snapshot = useSyncExternalStore(
    controller?.subscribe ?? (() => () => undefined),
    controller?.getSnapshot ?? (() => DISABLED_SNAPSHOT),
    () => DISABLED_SNAPSHOT,
  );
  return {
    ...snapshot,
    enabled,
    enqueue: (command: EditorCommand) => controller?.enqueue(command) ?? Promise.resolve(),
    flush: () => controller?.flush() ?? Promise.resolve(),
    retry: () => controller?.retry(),
    reloadServerVersion: () => controller?.reloadServerVersion() ?? Promise.resolve(),
    recoveryPayload: () => controller?.recoveryPayload() ?? "",
    takeOverIfExpired: () => coordinator?.takeOverIfExpired() ?? false,
  };
}
