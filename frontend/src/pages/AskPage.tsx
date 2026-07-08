import { useEffect, useState } from "react";
import { AlertCircle, ArrowRight, Plus } from "lucide-react";
import { useAsk } from "@/lib/useAsk";
import { CitationCard } from "@/components/CitationCard";

const EXAMPLES = [
  "Can my HOA stop me from installing solar panels?",
  "What notice is required before an HOA meeting?",
  "Can the association put a lien on my home for unpaid assessments?",
];

interface Props {
  onAsked: (q: string) => void;
  initialQuestion?: string | null;
}

export function AskPage({ onAsked, initialQuestion }: Props) {
  const [input, setInput] = useState("");
  const { status, answer, citations, disclaimer, error, stage, ask, reset } = useAsk();

  const submit = (q: string) => {
    const question = q.trim();
    if (!question || status === "streaming") return;
    onAsked(question);
    void ask(question);
  };

  // Auto-run a question replayed from history.
  useEffect(() => {
    if (initialQuestion) {
      setInput(initialQuestion);
      submit(initialQuestion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const hasResult = status !== "idle";

  return (
    <div>
      {!hasResult && (
        <>
          <div className="mb-3.5 font-sans text-xs uppercase tracking-[0.14em] text-accent">
            Informational · not legal advice
          </div>
          <h1 className="mb-3 text-[34px] font-semibold leading-[1.2] tracking-[-0.02em]">
            What does Maryland law say about your home?
          </h1>
          <p className="mb-8 max-w-[60ch] text-lg text-text-dim">
            Ask about HOA rules, condominium governance, or county housing code.
            You'll get the governing policy and the exact citation — not a verdict.
          </p>
        </>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
        className="mb-2 flex gap-2.5 rounded-xl border border-border bg-surface py-2 pl-[18px] pr-2 focus-within:border-accent-dim"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about Maryland housing or HOA law…"
          className="flex-1 bg-transparent font-serif text-[17px] text-text outline-none"
          aria-label="Your question"
        />
        <button
          type="submit"
          disabled={status === "streaming" || !input.trim()}
          className="flex items-center gap-1.5 rounded-lg bg-accent px-5 py-2.5 font-sans text-sm font-medium text-[#17140c] hover:bg-[#d8b26a] disabled:cursor-not-allowed disabled:opacity-50"
        >
          Ask <ArrowRight size={16} />
        </button>
      </form>

      {!hasResult && (
        <div className="flex flex-wrap items-center gap-2 pl-1 pt-1">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => {
                setInput(ex);
                submit(ex);
              }}
              className="flex items-center gap-1 rounded-full border border-border px-3 py-1.5 font-sans text-[12.5px] text-text-faint hover:border-accent-dim hover:text-text-dim"
            >
              <Plus size={12} /> {ex}
            </button>
          ))}
        </div>
      )}

      {hasResult && (
        <section className="mt-11">
          <div className="mb-3.5 flex items-center gap-2 font-sans text-xs uppercase tracking-[0.12em] text-text-faint">
            Guidance
            {status === "streaming" && <span className="text-accent">· streaming</span>}
          </div>

          {error ? (
            <div className="flex items-start gap-2.5 rounded-lg border border-danger/25 bg-danger/[0.08] px-4 py-3.5 font-sans text-sm text-danger">
              <AlertCircle size={15} className="mt-0.5 shrink-0" />
              <span>
                Something went wrong reaching the service. Try again in a moment.
                <span className="mt-1 block text-text-faint">{error}</span>
              </span>
            </div>
          ) : (
            <div
              className={`text-lg leading-[1.7] ${
                status === "streaming" ? "stream-caret" : ""
              }`}
            >
              {answer ? (
                answer
                  .split("\n")
                  .filter(Boolean)
                  .map((p, i) => (
                    <p key={i} className="mb-4">
                      {p}
                    </p>
                  ))
              ) : stage === "generating" ? (
                <span className="inline-flex items-center gap-2 text-text-faint">
                  <span className="stream-caret">Reading the statute and drafting guidance…</span>
                </span>
              ) : null}
            </div>
          )}

          {citations.length > 0 && (
            <div className="mt-8 grid gap-3">
              {citations.map((c, i) => (
                <CitationCard key={i} citation={c} />
              ))}
            </div>
          )}

          {disclaimer && (
            <div className="mt-9 flex items-start gap-2.5 rounded-lg border border-danger/25 bg-danger/[0.08] px-4 py-3.5 font-sans text-[13px] text-danger">
              <AlertCircle size={15} className="mt-0.5 shrink-0" />
              {disclaimer}
            </div>
          )}

          <button
            onClick={() => {
              reset();
              setInput("");
            }}
            className="mt-8 font-sans text-sm text-text-faint underline hover:text-accent"
          >
            Ask another question
          </button>
        </section>
      )}
    </div>
  );
}
