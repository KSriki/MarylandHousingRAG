import { Clock, Trash2 } from "lucide-react";
import type { HistoryItem } from "@/lib/useHistory";

interface Props {
  items: HistoryItem[];
  onPick: (question: string) => void;
  onClear: () => void;
}

export function HistoryPage({ items, onPick, onClear }: Props) {
  return (
    <div>
      <div className="mb-3.5 flex items-baseline gap-3">
        <div className="font-sans text-xs uppercase tracking-[0.14em] text-accent">
          On this device
        </div>
        {items.length > 0 && (
          <button
            onClick={onClear}
            className="ml-auto flex items-center gap-1.5 font-sans text-[13px] text-text-faint hover:text-danger"
          >
            <Trash2 size={13} /> Clear history
          </button>
        )}
      </div>
      <h1 className="mb-3 text-[28px] font-semibold leading-[1.2] tracking-[-0.02em]">
        Your past questions
      </h1>
      <p className="mb-8 max-w-[60ch] text-lg text-text-dim">
        Kept only in this browser — nothing is sent anywhere or tied to you.
      </p>

      {items.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface px-5 py-8 text-center">
          <p className="font-sans text-text-dim">No questions yet.</p>
          <p className="mt-1 font-sans text-[13px] text-text-faint">
            Ask something and it'll show up here.
          </p>
        </div>
      ) : (
        <div className="grid gap-2.5">
          {items.map((item) => (
            <button
              key={item.id}
              onClick={() => onPick(item.question)}
              className="flex items-center gap-4 rounded-[10px] border border-border bg-surface px-[18px] py-4 text-left hover:border-accent-dim"
            >
              <Clock size={16} className="shrink-0 text-text-faint" />
              <div>
                <div className="text-[16px]">{item.question}</div>
                <div className="mt-0.5 font-sans text-[12px] text-text-faint">
                  {new Date(item.at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
