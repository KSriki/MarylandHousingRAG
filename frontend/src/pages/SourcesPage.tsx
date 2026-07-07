import { FileText, Loader2 } from "lucide-react";
import { useSources } from "@/lib/useSources";

export function SourcesPage() {
  const { sources, loading, error } = useSources();

  return (
    <div>
      <div className="mb-3.5 font-sans text-xs uppercase tracking-[0.14em] text-accent">
        The corpus
      </div>
      <h1 className="mb-3 text-[28px] font-semibold leading-[1.2] tracking-[-0.02em]">
        What this tool knows
      </h1>
      <p className="mb-8 max-w-[60ch] text-lg text-text-dim">
        Answers are drawn only from these documents. If a question isn't covered
        here, the tool will say so rather than guess.
      </p>

      {loading && (
        <div className="flex items-center gap-2 font-sans text-sm text-text-faint">
          <Loader2 size={16} className="animate-spin" /> Loading sources…
        </div>
      )}

      {!loading && error && (
        <p className="font-sans text-sm text-danger">
          Couldn't load the source list. The service may be starting up.
        </p>
      )}

      {!loading && !error && sources.length === 0 && (
        <div className="rounded-lg border border-border bg-surface px-5 py-8 text-center">
          <p className="font-sans text-text-dim">No documents ingested yet.</p>
          <p className="mt-1 font-sans text-[13px] text-text-faint">
            Run <span className="font-mono text-accent">mdhpp ingest</span> to
            build the index.
          </p>
        </div>
      )}

      <div className="grid gap-2.5">
        {sources.map((s) => (
          <div
            key={s.doc}
            className="flex items-center gap-4 rounded-[10px] border border-border bg-surface px-[18px] py-4"
          >
            <FileText size={18} className="shrink-0 text-accent-dim" />
            <div>
              <div className="text-[17px] capitalize">{s.doc}</div>
              <div className="mt-0.5 font-sans text-[12.5px] text-text-faint">
                {s.jurisdiction} · {s.sections} sections
              </div>
            </div>
            <span className="ml-auto whitespace-nowrap font-mono text-xs text-accent">
              {s.chunks} passages
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
