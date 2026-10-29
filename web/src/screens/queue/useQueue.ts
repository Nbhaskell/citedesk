import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "../../api/context";
import type { InquirySummary } from "../../api/types";
import { useAnnounce } from "../../components/LiveRegion";
import { queue as words } from "../../copy";
import { useResource } from "../../hooks/useResource";
import { toQuery, type QueueView } from "./params";

export const QUEUE_POLL_MS = 5000;

interface MorePages {
  key: string;
  items: InquirySummary[];
  cursor: string | null;
  failed: boolean;
  busy: boolean;
}

/**
 * The queue's rows for a view. The first page is refreshed every few seconds; "show more" pages
 * are fetched once when asked for and kept until the view changes, so a refresh never throws away
 * what the person has scrolled to. New arrivals are announced, politely, without moving focus.
 */
export function useQueue(view: QueueView) {
  const api = useApi();
  const announce = useAnnounce();
  const query = toQuery(view);
  const key = JSON.stringify(query);
  const queryRef = useRef(query);
  useEffect(() => {
    queryRef.current = query;
  });

  const first = useResource((signal) => api.listInquiries(query, signal), {
    intervalMs: QUEUE_POLL_MS,
    key,
  });
  const [more, setMore] = useState<MorePages | null>(null);
  const extra = more?.key === key ? more : null;

  const seen = useRef<{ key: string; ids: Set<number> } | null>(null);
  const page = first.data;
  useEffect(() => {
    if (!page) return;
    const ids = page.items.map((item) => item.id);
    if (seen.current?.key !== key) {
      seen.current = { key, ids: new Set(ids) };
      return;
    }
    const known = seen.current.ids;
    const arrived = ids.filter((id) => !known.has(id));
    ids.forEach((id) => known.add(id));
    if (arrived.length > 0) announce(words.newInquiries(arrived.length));
  }, [page, key, announce]);

  const cursor = extra ? extra.cursor : (page?.next_cursor ?? null);
  const loadMore = useCallback(async () => {
    if (!cursor) return;
    const kept = (previous: MorePages | null) => (previous?.key === key ? previous.items : []);
    setMore((previous) => ({ key, items: kept(previous), cursor, failed: false, busy: true }));
    try {
      const next = await api.listInquiries({ ...queryRef.current, cursor });
      setMore((previous) => ({
        key,
        items: [...kept(previous), ...next.items],
        cursor: next.next_cursor,
        failed: false,
        busy: false,
      }));
    } catch {
      setMore((previous) => ({ key, items: kept(previous), cursor, failed: true, busy: false }));
    }
  }, [api, cursor, key]);

  const firstIds = new Set(page?.items.map((item) => item.id));
  const items = page
    ? [...page.items, ...(extra?.items ?? []).filter((item) => !firstIds.has(item.id))]
    : [];

  return {
    items,
    loading: first.loading,
    error: first.error,
    hasData: page !== null,
    hasMore: cursor !== null,
    loadingMore: extra?.busy ?? false,
    moreFailed: extra?.failed ?? false,
    loadMore,
    reload: first.reload,
  };
}
