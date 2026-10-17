import { useEffect, useState } from "react";
import { get } from "./api/client";

interface FetchState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

export function useFetch<T>(path: string): FetchState<T> & { reload: () => void } {
  const [state, setState] = useState<FetchState<T>>({
    data: null,
    error: null,
    loading: true,
  });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true }));
    get<T>(path)
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch(
        (e) => alive && setState({ data: null, error: String(e), loading: false }),
      );
    return () => {
      alive = false;
    };
  }, [path, tick]);

  return { ...state, reload: () => setTick((t) => t + 1) };
}
