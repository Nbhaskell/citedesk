import { createContext, useContext, useEffect, useRef, type ReactNode } from "react";
import { useApi } from "../api/context";
import type { StatusResponse } from "../api/types";
import { connection } from "../copy";
import { useResource, type Resource } from "../hooks/useResource";
import { useAnnounce } from "./LiveRegion";

export const STATUS_POLL_MS = 5000;

const StatusContext = createContext<Resource<StatusResponse> | null>(null);

/** The API's status, refreshed every few seconds. The header, footer and tab title read it. */
export function StatusProvider({ children }: { children: ReactNode }) {
  const api = useApi();
  const status = useResource((signal) => api.status(signal), { intervalMs: STATUS_POLL_MS });
  const announce = useAnnounce();
  const lost = status.error !== null;
  const wasLost = useRef(false);

  useEffect(() => {
    if (lost && !wasLost.current) announce(connection.lost);
    if (!lost && wasLost.current) announce(connection.restored);
    wasLost.current = lost;
  }, [lost, announce]);

  return <StatusContext.Provider value={status}>{children}</StatusContext.Provider>;
}

export function useStatus(): Resource<StatusResponse> {
  const status = useContext(StatusContext);
  if (!status) throw new Error("useStatus needs a StatusProvider above it");
  return status;
}
