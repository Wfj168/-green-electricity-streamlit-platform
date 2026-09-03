import { useEffect, useState } from "react";

interface ResourceState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useV2Resource<T>(loader: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<ResourceState<T>>({ data: null, loading: true, error: null });

  useEffect(() => {
    const controller = new AbortController();
    setState({ data: null, loading: true, error: null });
    loader(controller.signal)
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          data: null,
          loading: false,
          error: error instanceof Error ? error.message : "未知接口错误",
        });
      });
    return () => controller.abort();
  }, [loader]);

  return state;
}
