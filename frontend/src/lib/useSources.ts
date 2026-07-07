import { useEffect, useState } from "react";

export interface Source {
  doc: string;
  jurisdiction: string;
  chunks: number;
  sections: number;
}

/** Fetches the corpus document list from GET /api/sources. */
export function useSources() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/sources")
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled) setSources(d.sources ?? []);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { sources, loading, error };
}
