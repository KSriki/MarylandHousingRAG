import type { Citation } from "@/lib/useAsk";

/** The signature element: a citation rendered like a statute stamp. */
export function CitationCard({ citation }: { citation: Citation }) {
  return (
    <div className="rounded-r-[10px] border border-l-[3px] border-l-accent border-border bg-surface px-[18px] py-4">
      <div className="mb-2 flex items-baseline gap-3">
        <span className="font-mono text-sm font-semibold tracking-tight text-accent">
          {citation.section}
        </span>
        <span className="font-sans text-[12.5px] uppercase tracking-[0.06em] text-text-dim">
          {citation.doc}
        </span>
        {citation.url && (
          <a
            href={citation.url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto font-sans text-xs text-text-faint underline hover:text-accent"
          >
            Read source
          </a>
        )}
      </div>
      <p className="text-[15.5px] leading-[1.55] text-text-dim">{citation.snippet}</p>
    </div>
  );
}
