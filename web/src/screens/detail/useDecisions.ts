import { useCallback, useState } from "react";
import { ApiError, type ApproveBody, type RejectBody } from "../../api/client";
import { useApi } from "../../api/context";
import type { InquiryDetail } from "../../api/types";
import { useAnnounce } from "../../components/LiveRegion";
import { actions as words } from "../../copy";
import { stageLabel } from "./stages";

function asApiError(error: unknown): ApiError {
  return error instanceof ApiError
    ? error
    : new ApiError(0, "unexpected", "Something went wrong in the page.", null);
}

/**
 * Every decision a reviewer can make, with one busy flag and one error. Each call answers whether
 * it worked; on success the screen is given the new state of the inquiry and the person hears the
 * confirmation. On failure nothing is lost: the caller keeps what was typed.
 */
export function useDecisions(apply: (detail: InquiryDetail) => void) {
  const api = useApi();
  const announce = useAnnounce();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const run = useCallback(
    async (name: string, call: () => Promise<InquiryDetail>, done: string) => {
      setBusy(name);
      setError(null);
      try {
        apply(await call());
        announce(done);
        return true;
      } catch (caught) {
        const failure = asApiError(caught);
        setError(failure);
        announce(failure.message, { assertive: true });
        return false;
      } finally {
        setBusy(null);
      }
    },
    [apply, announce],
  );

  return {
    busy,
    error,
    clearError: useCallback(() => setError(null), []),
    approve: (draftId: number, body: ApproveBody) =>
      run(
        "approve",
        () => api.approve(draftId, body),
        body.edited_body ? words.approveEdited.done : words.approve.done,
      ),
    reject: (draftId: number, body: RejectBody) =>
      run("reject", () => api.reject(draftId, body), words.reject.done),
    redraft: (draftId: number, guidance: string) =>
      run("redraft", () => api.redraft(draftId, { guidance }), words.redraft.done),
    escalate: (inquiryId: number, note: string) =>
      run("escalate", () => api.escalate(inquiryId, { note }), words.escalate.done),
    resolve: (inquiryId: number, note: string | undefined) =>
      run("resolve", () => api.resolve(inquiryId, note ? { note } : {}), words.resolve.done),
    retry: (inquiryId: number, stage: string) =>
      run("retry", () => api.reprocess(inquiryId), words.retry.done(stageLabel(stage))),
  };
}

export type Decisions = ReturnType<typeof useDecisions>;
