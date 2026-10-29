import { useCallback, useState } from "react";
import { useApi } from "../../api/context";
import type { InquiryDetail } from "../../api/types";
import { useResource } from "../../hooks/useResource";

export const DETAIL_POLL_MS = 3000;

/**
 * One inquiry, refreshed every few seconds so a draft appears when it is ready. A decision answers
 * with the new state of the inquiry; `apply` shows that at once, and the next refresh agrees with
 * it. Whichever is newer (by `updated_at`) is what the screen shows.
 */
export function useDetail(id: number) {
  const api = useApi();
  const resource = useResource((signal) => api.inquiry(id, signal), {
    intervalMs: DETAIL_POLL_MS,
    key: String(id),
  });
  const [applied, setApplied] = useState<InquiryDetail | null>(null);
  const apply = useCallback((next: InquiryDetail) => setApplied(next), []);

  const fetched = resource.data;
  const newer =
    applied !== null &&
    applied.inquiry.id === id &&
    (fetched === null || applied.inquiry.updated_at >= fetched.inquiry.updated_at);

  return {
    detail: newer ? applied : fetched,
    loading: resource.loading && !newer,
    error: resource.error,
    reload: resource.reload,
    apply,
  };
}
