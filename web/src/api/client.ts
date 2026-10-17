// Typed fetch + TanStack Query. Results are cached per path, so switching
// back to a period or tab you've already opened is instant; data only
// changes when an ingest runs, so it's treated as fresh for 5 minutes.
import { QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5 * 60_000, refetchOnWindowFocus: false, placeholderData: (prev: unknown) => prev },
  },
});

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().then((j) => j.detail, () => null);
    throw new Error(detail ? `${detail}` : `${method} ${path} failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

/** GET with caching. Keeps showing the previous result while a new period loads. */
export function useApi<T>(path: string) {
  return useQuery<T>({ queryKey: [path], queryFn: () => request<T>("GET", path) });
}

/** PUT, then refetch every cached query whose path starts with one of `invalidates`. */
export function useSave<B>(invalidates: string[]) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ path, body }: { path: string; body: B }) => request("PUT", path, body),
    onSuccess: () =>
      client.invalidateQueries({
        predicate: (q) => invalidates.some((p) => String(q.queryKey[0]).startsWith(p)),
      }),
  });
}
