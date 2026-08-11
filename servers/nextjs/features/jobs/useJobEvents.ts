"use client";

import { useEffect, useRef } from "react";
import { jobsApi } from "./api";
import type { JobEvent } from "./types";

export function useJobEvents(jobId: string | null, onEvent: (event: JobEvent) => void) {
  const callback = useRef(onEvent);
  const lastEventId = useRef(0);

  useEffect(() => {
    callback.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!jobId) return;
    const source = new EventSource(jobsApi.eventsUrl(jobId, lastEventId.current), { withCredentials: true });
    source.onmessage = (message) => {
      const id = Number(message.lastEventId);
      if (Number.isFinite(id)) lastEventId.current = Math.max(lastEventId.current, id);
      callback.current(JSON.parse(message.data) as JobEvent);
    };
    const namedEvents = ["submitted", "queued", "started", "retry_started", "progress", "retry_scheduled", "cancellation_requested", "cancelled", "failed", "dead_letter", "succeeded"];
    for (const name of namedEvents) {
      source.addEventListener(name, (message) => {
        const event = message as MessageEvent<string>;
        const id = Number(event.lastEventId);
        if (Number.isFinite(id)) lastEventId.current = Math.max(lastEventId.current, id);
        callback.current(JSON.parse(event.data) as JobEvent);
      });
    }
    return () => source.close();
  }, [jobId]);
}
