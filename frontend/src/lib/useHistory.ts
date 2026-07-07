import { useCallback, useEffect, useState } from "react";

export interface HistoryItem {
  id: string;
  question: string;
  at: number;
}

const KEY = "mdhpp.history.v1";

/** Local-only question history (no accounts, no server). */
export function useHistory() {
  const [items, setItems] = useState<HistoryItem[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setItems(JSON.parse(raw));
    } catch {
      /* ignore corrupt storage */
    }
  }, []);

  const persist = useCallback((next: HistoryItem[]) => {
    setItems(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* storage full or blocked — history is best-effort */
    }
  }, []);

  const add = useCallback(
    (question: string) => {
      const item: HistoryItem = {
        id: crypto.randomUUID(),
        question,
        at: Date.now(),
      };
      // De-dupe consecutive identical questions; cap at 50.
      persist(
        [item, ...items.filter((i) => i.question !== question)].slice(0, 50),
      );
    },
    [items, persist],
  );

  const clear = useCallback(() => persist([]), [persist]);

  return { items, add, clear };
}
